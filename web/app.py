import os.path
import sys
import secrets  # 添加這行

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import Config


from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import subprocess
import os
import sqlite3
import json
from datetime import datetime, timedelta
import time
from discord.ext import commands
import discord
import traceback
import asyncio
from werkzeug.exceptions import HTTPException
from functools import wraps
import requests
from flask_cors import CORS

# 修改為相對路徑導入
import os.path
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if (parent_dir not in sys.path):
    sys.path.insert(0, parent_dir)
    
# Remove the following line to prevent circular import
from bot import bot  # 直接從 bot.py 導入 bot 實例
from user_info_cog import UserInfoCog
from shared_config import bot, app
from shared_config import queue_update
from voice_room_management import VoiceRoomManager

# 修改初始化部分
from shared_config import get_bot, queue_update
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 創建 ThreadPoolExecutor 用於處理異步操作
executor = ThreadPoolExecutor(max_workers=3)

def run_async(coro):
    """執行異步代碼的輔助函數"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Initialize Flask app
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))
app = Flask(__name__, 
            template_folder=template_dir,
            static_folder=static_dir)

# 添加這些設定
app.config.update(
    SECRET_KEY='your-super-secret-key-here',  # 請更改為一個隨機的長字串
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# 確保設定成功
if not app.secret_key:
    app.secret_key = os.urandom(24)

bot_process = None

# 初始化管理器
voice_manager = None

def init_voice_manager():
    global voice_manager
    if not voice_manager and bot and bot.is_ready():
        voice_manager = VoiceRoomManager(bot)

# 替换 @app.before_first_request 为 before_request
@app.before_request
def before_request():
    init_voice_manager()

# 处理可能的初始化错误
@app.errorhandler(500)
def handle_init_error(e):
    if not bot or not bot.is_ready():
        return jsonify({
            'error': 'Bot is not ready',
            'message': 'Please wait for the bot to initialize',
            'status_code': 503
        }), 503
    return handle_error(e)

# 錯誤處理
@app.errorhandler(Exception)
def handle_error(e):
    # 取得完整的錯誤追蹤
    error_traceback = traceback.format_exc()
    
    # 如果是 HTTP 異常，直接返回
    if isinstance(e, HTTPException):
        response = jsonify({
            'error': str(e),
            'message': e.description,
            'status_code': e.code
        })
        return response, e.code
        
    # 其他異常，返回 500 錯誤
    print(f"Unhandled Error: {error_traceback}")
    response = jsonify({
        'error': str(e),
        'message': 'An unexpected error occurred',
        'status_code': 500
    })
    return response, 500

# 更新現有的 login_required 裝飾器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 保存當前的 URL 以便登入後重定向
            session['next'] = request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def is_admin(user_id):
    return str(user_id) in ADMIN_USER_IDS

@app.route('/login')
def login():
    error = request.args.get('error')
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    # 在 scopes 中增加 guilds.members.read
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={Config.DISCORD_CLIENT_ID}"
        f"&redirect_uri={Config.DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds%20guilds.members.read"
    )
    return render_template('login.html', oauth_url=oauth_url, error=error)

# 更新登入回��處理
# 添加允許的管理員 ID 列表
ADMIN_USER_IDS = [secrets.token_hex(8) for _ in range(3)]  # 隨機化管理員 ID 列表

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('login', error='授權失敗'))
        
    data = {
        'client_id': Config.DISCORD_CLIENT_ID,
        'client_secret': Config.DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.DISCORD_REDIRECT_URI,
        'scope': 'identify guilds guilds.members.read'  # 增加 guilds.members.read 範圍
    }
    
    # 獲取 access token
    r = requests.post('https://discord.com/api/oauth2/token', data=data)
    if r.status_code != 200:
        return redirect(url_for('login', error='授權失敗'))
        
    token = r.json()['access_token']
    
    # 獲取用戶資訊
    headers = {'Authorization': f'Bearer {token}',
               'Content-Type': 'application/json'
               }
    user_info = requests.get('https://discord.com/api/users/@me', headers=headers).json()
    
    # 獲取用戶的伺服器資訊
    guilds = requests.get('https://discord.com/api/users/@me/guilds', headers=headers).json()
    
    # 獲取用戶在特定伺服器中的資訊，包括角色
    guild_member = requests.get(
        f'https://discord.com/api/users/@me/guilds/{Config.GUILD_ID}/member', 
        headers=headers
    ).json()
    
    # 檢查用戶是否為伺服器的管理員
    is_admin = False
    for role_id in guild_member.get('roles', []):
        if role_id in Config.ADMIN_ROLE_IDS:
            is_admin = True
            break

    if not is_admin:
        return redirect(url_for('login', error='您沒有管理員權限'))
    
    # 創建並初始化資料庫
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/dc-dashboard-manager.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 創建表格（如果尚未存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT UNIQUE,
            username TEXT,
            login_time DATETIME
        )
    ''')
    # 插入或更新管理員資料
    cursor.execute('''
        INSERT OR REPLACE INTO admin_users (discord_id, username, login_time)
        VALUES (?, ?, ?)
    ''', (user_info['id'], user_info['username'], datetime.utcnow()))
    conn.commit()
    conn.close()
    
    session['user_id'] = user_info['id']
    session['username'] = user_info['username']
    session['avatar_url'] = f"https://cdn.discordapp.com/avatars/{user_info['id']}/{user_info['avatar']}.png"
    session['is_admin'] = True
    
    next_url = session.pop('next', url_for('home'))
    return redirect(next_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error in home route: {e}")
        return handle_error(e)

@app.route('/bot-status')
def bot_status():
    try:
        global bot_process
        if (bot_process and bot_process.poll() is None):
            return "Bot is running"
        return "Bot is not running"
    except Exception as e:
        return handle_error(e)

@app.route('/log-output')
def log_output():
    log_file_path = os.path.join(os.path.dirname(__file__), '../Userfile/bot.log')
    with open(log_file_path, 'r') as log_file:
        log_content = log_file.read()
    bot_status = "Bot is running" if bot_process and bot_process.poll() is None else "機器人已離線！"
    return f"{bot_status}\n\n{log_content}"

@app.route('/start-bot', methods=['POST'])
def start_bot():
    global bot_process
    if not bot_process or bot_process.poll() is not None:
        try:
            # 使用完整的 Python 路徑
            python_path = sys.executable
            bot_process = subprocess.Popen([python_path, os.path.join(os.path.dirname(__file__), '../bot.py')])
            return jsonify({"status": "success", "message": "Bot started"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "warning", "message": "Bot is already running"})

@app.route('/stop-bot', methods=['POST'])
def stop_bot():
    global bot_process
    if bot_process and bot_process.poll() is None:
        subprocess.run(['python', '-m', 'discord.ext.commands', 'shutdown'])
        bot_process.terminate()
        bot_process.wait()
        return jsonify({"status": "success", "message": "Bot stopped"})
    return jsonify({"status": "warning", "message": "Bot is not running"})

@app.route('/query-reports')
def query_reports():
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/report.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports")
    reports = cursor.fetchall()
    conn.close()
    return jsonify(reports)

@app.route('/bot-status-details')
def bot_status_details():
    global bot_process
    if bot_process and bot_process.poll() is None:
        return jsonify({"status": "running", "pid": bot_process.pid})
    return jsonify({"status": "not running"})

@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin.html')

@app.route('/admin/reports')
@login_required
def admin_reports():
    search_query = request.args.get('search', '')
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/reports/reports.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if search_query:
        cursor.execute("SELECT * FROM reports WHERE report_id LIKE ? OR reporter_id LIKE ? OR reported_id LIKE ?", 
                       (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("SELECT * FROM reports")
    reports = cursor.fetchall()
    conn.close()
    return jsonify(reports)

@app.route('/admin/reports/<int:report_id>')
@login_required
def admin_report_details(report_id):
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/reports/reports.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    conn.close()
    if report:
        return jsonify(report)
    return jsonify({'error': 'Report not found'}), 404

@app.route('/admin/users')
@login_required
def admin_users():
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/userdata.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/admin/voice-rooms')
@login_required
def admin_voice_rooms():
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/Voiceroom.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_rooms")
    voice_rooms = cursor.fetchall()
    conn.close()
    return jsonify(voice_rooms)

@app.route('/voice-rooms')
@login_required
def voice_rooms_page():
    return render_template('voice_rooms.html')

@app.route('/api/voice-rooms')
@login_required
def get_voice_rooms():
    try:
        # Use Discord API directly to get the list of voice channels
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/channels',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get channels')
        
        channels = response.json()
        voice_channels = [ch for ch in channels if ch['type'] == 2]  # Type 2 is for voice channels
        
        active_rooms = []
        for channel in voice_channels:
            room_info = {
                'channel_id': channel['id'],
                'channel_name': channel['name'],
                'owner_id': channel.get('owner_id', 'Unknown'),
                'settings': {
                    'user_limit': channel['user_limit'],
                    'bitrate': channel['bitrate'],
                    'region': channel['rtc_region']
                },
                'members': []  # You can add logic to fetch members if needed
            }
            active_rooms.append(room_info)
        
        return jsonify({
            'active_rooms': active_rooms,
            'inactive_rooms': [],  # You can add logic to fetch inactive rooms if needed
            'deleted_rooms': []  # You can add logic to fetch deleted rooms if needed
        })
        
    except Exception as e:
        print(f"Error in get_voice_rooms: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'active_rooms': [],
            'inactive_rooms': [],
            'deleted_rooms': []
        }), 500

@app.route('/api/voice-rooms/<channel_id>', methods=['PUT'])
@login_required
def update_voice_room(channel_id):
    data = request.json
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_channels.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE voice_channels SET status = ? WHERE channel_id = ?", 
                  (data['status'], channel_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/voice-rooms/<channel_id>', methods=['DELETE'])
@login_required
def delete_voice_room(channel_id):
    try:
        # Use Discord API directly
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.delete(
            f'https://discord.com/api/v9/channels/{channel_id}',
            headers=headers
        )
        
        if response.status_code != 204:
            raise Exception('Failed to delete channel')
        
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "Invalid channel ID"}), 400
    except Exception as e:
        print(f"Error deleting channel: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/voice-rooms/<channel_id>/logs')
@login_required
def get_voice_room_logs(channel_id):
    history_db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_history.db')
    user_db_path = os.path.join(os.path.dirname(__file__), '../Userfile/user_info.db')
    
    # 獲取權限變更紀錄
    voice_conn = sqlite3.connect(history_db_path)
    voice_conn.row_factory = sqlite3.Row
    cursor = voice_conn.cursor()
    
    cursor.execute("""
        SELECT 
            l.*
        FROM permission_logs l
        WHERE l.channel_id = ?
        ORDER BY l.timestamp DESC
    """, (channel_id,))
    
    # ...existing code...

    # 取得文字對話紀錄
    cursor.execute("""
        SELECT * FROM text_logs 
        WHERE channel_id = ? 
        ORDER BY timestamp DESC
    """, (channel_id,))
    text_logs = [dict(row) for row in cursor.fetchall()]
    
    voice_conn.close()
    
    return jsonify({
        'permission_logs': permission_logs,
        'text_logs': text_logs
    })

@app.route('/api/voice-rooms/<channel_id>/permissions', methods=['GET'])
@login_required
def get_voice_room_permissions(channel_id):
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_channels.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 獲取頻道設定
    cursor.execute("SELECT last_settings FROM voice_channels WHERE channel_id = ?", (channel_id,))
    result = cursor.fetchone()
    
    if (result and result[0]):
        settings = json.loads(result[0])
        return jsonify({
            'name': settings.get('name', ''),
            'user_limit': settings.get('user_limit', 0),
            'members': [
                {
                    'id': member_id,
                    'name': f'用戶 {member_id}',  # 這裡可以通過 Discord API 獲取實際用戶名
                    'connect': bool(perms.get('allow', 0) & 0x100000),  # CONNECT permission
                    'speak': bool(perms.get('allow', 0) & 0x200000)     # SPEAK permission
                }
                for member_id, perms in settings.get('permissions', {}).items()
                if (perms.get('type') == 'member')
            ]
        })
    
    return jsonify({'error': 'Channel not found'}), 404
@app.route('/api/voice-channels')
@login_required
def get_voice_channels():
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/Voiceroom.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_channels")
    channels = cursor.fetchall()
    conn.close()
    return jsonify(channels)

@app.route('/api/voice-channels/<channel_id>', methods=['GET'])
@login_required
def get_voice_channel(channel_id):
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/Voiceroom.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_channels WHERE id = ?", (channel_id,))
    channel = cursor.fetchone()
    conn.close()
    if channel:
        return jsonify(channel)
    return jsonify({'error': 'Channel not found'}), 404

@app.route('/api/voice-channels/<channel_id>', methods=['PUT'])
@login_required
def update_voice_channel(channel_id):
    data = request.json
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/Voiceroom.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE voice_channels SET name = ?, user_limit = ?, bitrate = ? WHERE id = ?", 
                   (data['name'], data['user_limit'], data['bitrate'], channel_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/voice-channels/<channel_id>', methods=['DELETE'])
@login_required
def delete_voice_channel(channel_id):
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/Voiceroom.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM voice_channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/voice-history')
@login_required
def get_voice_history():
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_history.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_history")
    history = cursor.fetchall()
    conn.close()
    return jsonify(history)

@app.route('/api/voice-history/<history_id>', methods=['GET'])
@login_required
def get_voice_history_entry(history_id):
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_history.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_history WHERE id = ?", (history_id,))
    entry = cursor.fetchone()
    conn.close()
    if entry:
        return jsonify(entry)
    return jsonify({'error': 'Entry not found'}), 404

@app.route('/api/voice-channels-permissions')
@login_required
def get_voice_channels_permissions():
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_channels.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_channels_permissions")
    permissions = cursor.fetchall()
    conn.close()
    return jsonify(permissions if permissions else [])

# ...existing code...

@app.route('/api/voice-rooms/<channel_id>/permissions', methods=['PUT'])
@login_required
def update_voice_room_permissions(channel_id):
    data = request.json
    db_path = os.path.join(os.path.dirname(__file__), '../Userfile/voice_channels.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 更新設定
    cursor.execute("""
        UPDATE voice_channels 
        SET settings = ? 
        WHERE channel_id = ?
    """, (json.dumps(data), channel_id))
    
    conn.commit()
    conn.close()
    
    # 通知 Discord bot 更新��道設定
    try:
        # 這裡需要實現一個機制來通知 bot 更新設定
        # 可以通過 websocket、共享文件或其他方式
        pass
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    return jsonify({'success': True})

@app.route('/api/voice-rooms/<channel_id>/members')
@login_required
def get_voice_room_members(channel_id):
    cache_path = os.path.join(os.path.dirname(__file__), '../Userfile/channel_cache.json')
    try:
        if not os.path.exists(cache_path):
            print(f"Cache file not found: {cache_path}")
            return jsonify([])
            
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            channel_data = cache.get(str(channel_id), {})
            channel_members = channel_data.get('members', [])
            
            # 獲取所有用戶的最新資訊
            members = []
            for member in channel_members:
                user_info = UserInfoCog.get_user_info(int(member['id']))
                if user_info:
                    members.append({
                        **user_info,
                        'connect': member.get('connect', True),
                        'speak': member.get('speak', True),
                        'in_channel': member.get('in_channel', False)
                    })
            
            return jsonify(members)
            
    except Exception as e:
        print(f"Error getting members for channel {channel_id}: {str(e)}")
        return jsonify([])

@app.route('/api/voice-rooms/<channel_id>/bulk-permissions', methods=['PUT'])
@login_required
def update_bulk_permissions(channel_id):
    data = request.json
    if (data or 'permissions' not in data):
        return jsonify({'error': 'Invalid data'}), 400
        
    # 將更新請求寫入共享文���
    update_file = os.path.join(os.path.dirname(__file__), '../Userfile/pending_updates.json')
    with open(update_file, 'w') as f:
        json.dump({
            'type': 'bulk_permissions',
            'channel_id': channel_id,
            'permissions': data['permissions']
        }, f)
    
    return jsonify({'success': True})

@app.route('/api/voice-rooms/<channel_id>/admins')
@login_required
def get_voice_room_admins(channel_id):
    try:
        # 直接從 user_info.db 獲取管理員列表
        all_users = UserInfoCog.get_all_users()
        admins = [user for user in all_users if (user['is_admin'])]
        return jsonify(admins)
    except Exception as e:
        print(f"Error getting admins: {str(e)}")
        return jsonify([])

@app.route('/admin/members')
@login_required
def admin_members():
    # 將令牌傳遞到模板
    return render_template('admin/members.html', bot_token=Config.DISCORD_TOKEN)

@app.route('/api/voice-rooms/<channel_id>/update', methods=['POST'])
@login_required
def update_voice_room_settings(channel_id):
    try:
        data = request.json
        
       # Use Discord API directly
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.patch(
            f'https://discord.com/api/v9/channels/{channel_id}',
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception('Failed to update channel settings')
        
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "Invalid channel ID"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/members')
@login_required
def api_members():
    try:
        members = UserInfoCog.get_all_users()
        return jsonify(members)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/members/<member_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
async def api_member(member_id):
    if (request.method == 'GET'):
        try:
            # 獲取成員資訊
            guild = bot.guilds[0]
            member = guild.get_member(int(member_id))
            if (member):
                return jsonify({'error': 'Member not found'}), 404

            # 獲取可用的身分組
            roles = [{
                'id': str(role.id),
                'name': role.name,
                'color': str(role.color),
                'position': role.position
            } for role in guild.roles if (role.name != '@everyone')]

            # 獲取成員當前的身分組
            member_roles = [{
                'id': str(role.id),
                'name': role.name
            } for role in member.roles if (role.name != '@everyone')]

            return jsonify({
                'id': str(member.id),
                'name': member.name,
                'display_name': member.display_name,
                'avatar_url': str(member.avatar.url) if (member.avatar) else None,
                'roles': member_roles,
                'available_roles': roles
            })
        except Exception as e:
            print(f"Error getting member info: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    if (request.method == 'PUT'):
        data = request.json
        update_file = os.path.join(os.path.dirname(__file__), '../Userfile/pending_updates.json')
        with open(update_file, 'w') as f:
            json.dump({
                'type': 'update_member',
                'member_id': int(member_id),
                'updates': data
            }, f)
        return jsonify({'success': True})
        
    if (request.method == 'DELETE'):
        try:
            member = bot.get_guild(Config.GUILD_ID).get_member(member_id)
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            await member.kick(reason='Kicked by admin via dashboard')
        except Exception as e:
            print(f"Error kicking member {member_id}: {e}")
            return jsonify({'error': 'Failed to kick member'}), 500
        return jsonify({'success': True})

@app.route('/api/admin/members/<member_id>/roles', methods=['PUT'])
@login_required
def update_member_roles(member_id):
    try:
        data = request.json
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.put(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}/roles',
            headers=headers,
            json={'roles': data['roles']}
        )
        
        if response.status_code != 204:
            raise Exception('Failed to update member roles')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/members/<member_id>/timeout', methods=['POST'])  # Changed from /api/members/ to match the frontend URL
@login_required
def timeout_member_api(member_id):
    try:
        data = request.json
        duration = data.get('duration', 10)  # 預設 10 分鐘
        
        # 計算禁言結束時間
        timeout_end = (datetime.utcnow() + timedelta(minutes=int(duration))).isoformat()
        
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        print(f"Sending timeout request for member {member_id} until {timeout_end}")  # 添加調試日誌
        
        response = requests.patch(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}',
            headers=headers,
            json={
                "communication_disabled_until": timeout_end
            }
        )
        
        if response.status_code not in [200, 204]:
            print(f"Discord API Error: {response.status_code}", response.text)  # 添加調試日誌
            raise Exception('禁言失敗')
        
        return jsonify({'success': True, 'message': '成員已禁言'})
    except Exception as e:
        print(f"Timeout error: {str(e)}")  # 添加調試日誌
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/members/<member_id>/block', methods=['POST'])
@login_required
def block_member_api(member_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.put(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/bans/{member_id}',
            headers=headers,
            json={'reason': 'Blocked by admin via dashboard'}
        )
        if response.status_code != 204:
            raise Exception('Failed to block member')
        return jsonify({'success': True, 'message': 'Member blocked successfully'})
    except Exception as e:
        print(f"Error blocking member {member_id}: {e}")
        return jsonify({'error': 'Failed to block member'}), 500

@app.route('/api/admin/members/<member_id>/kick', methods=['POST'])
@login_required
def kick_member_api(member_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.delete(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}',
            headers=headers,
            json={'reason': 'Kicked by admin via dashboard'}
        )
        if response.status_code != 204:
            raise Exception('Failed to kick member')
        return jsonify({'success': True, 'message': 'Member kicked successfully'})
    except Exception as e:
        print(f"Error kicking member {member_id}: {e}")
        return jsonify({'error': 'Failed to kick member'}), 500

@app.route('/admin/<page>')
@login_required
def admin_page(page):
    if (page in ['members', 'channels', 'roles', 'emojis', 'stickers', 'settings']):
        return render_template(f'admin/{page}.html')
    return render_template('404.html'), 404

@app.route('/api/channels')
@login_required
def get_channels():
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/channels',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get channels')
        
        channels = response.json()
        return jsonify(channels)
    except Exception as e:
        print(f"Error getting channels: {str(e)}")
        return jsonify({'error': f'Failed to get channels: {str(e)}'}), 500

@app.route('/api/channels/<channel_id>', methods=['PUT'])
@login_required
def update_channel(channel_id):
    data = request.json
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.patch(
            f'https://discord.com/api/v9/channels/{channel_id}',
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception('Failed to update channel')
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating channel: {str(e)}")
        return jsonify({'error': f'Failed to update channel: {str(e)}'}), 500

@app.route('/api/channels', methods=['POST'])
@login_required
def create_channel():
    data = request.json
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.post(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/channels',
            headers=headers,
            json=data
        )
        
        if response.status_code != 201:
            raise Exception('Failed to create channel')
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error creating channel: {str(e)}")
        return jsonify({'error': f'Failed to create channel: {str(e)}'}), 500

@app.route('/api/channels/<channel_id>', methods=['DELETE'])
@login_required
def delete_channel(channel_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.delete(
            f'https://discord.com/api/v9/channels/{channel_id}',
            headers=headers
        )
        
        if response.status_code != 204:
            raise Exception('Failed to delete channel')
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting channel: {e}")
        return jsonify({'error': f'Failed to delete channel: {str(e)}'}), 500

@app.route('/api/channels/<channel_id>/permissions', methods=['PUT'])
@login_required
def update_channel_permissions(channel_id):
    data = request.json
    update_file = os.path.join(os.path.dirname(__file__), '../Userfile/pending_updates.json')
    with open(update_file, 'w') as f:
        json.dump({
            'type': 'update_channel_permissions',
            'channel_id': int(channel_id),
            'permissions': data
        }, f)
    return jsonify({'success': True})

@app.route('/api/channels/bulk', methods=['PUT'])
@login_required
def bulk_update_channels():
    data = request.json
    update_file = os.path.join(os.path.dirname(__file__), '../Userfile/pending_updates.json')
    with open(update_file, 'w') as f:
        json.dump({
            'type': 'bulk_channel_update',
            'updates': data
        }, f)
    return jsonify({'success': True})

@app.route('/api/channels/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if (request.method == 'GET'):
        cache_path = os.path.join(os.path.dirname(__file__), '../Userfile/channel_cache.json')
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                channels = json.load(f)
                categories = [ch for ch in channels.values() if (ch.get('type') == 'category')]
                return jsonify(categories)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    elif (request.method == 'POST'):
        data = request.json
        queue_update({
            'type': 'create_category',
            'category_data': data
        })
        return jsonify({'success': True})

@app.route('/api/members/search')
@login_required
def search_members():
    query = request.args.get('query')
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/search?query={query}&limit=50',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception('Failed to search members')
        
        members = response.json()
        return jsonify(members)
    except Exception as e:
        print(f"Error searching members: {str(e)}")
        return jsonify({'error': f'Failed to search members: {str(e)}'}), 500

@app.route('/api/members/<member_id>', methods=['GET', 'PUT'])
@login_required
def manage_member(member_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get member')
        
        member = response.json()
        
        if (request.method == 'GET'):
            return jsonify(member)
            
        response = requests.patch(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}',
            headers=headers,
            json=data
        )
        if response.status_code != 200:
            raise Exception('Failed to update member')
        return jsonify({'success': True})
            
        if response.status_code != 200:
                raise Exception('Failed to update member')
            
        return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/permissions')
@login_required
def get_permissions():
    try:
        guild = bot.guilds[0]
        permissions_data = {
            'roles': {},
            'channels': {}
        }
        # Add permissions data logic here
        return jsonify(permissions_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Enable CORS if necessary
CORS(app)

# ...existing code...

@app.route('/api/members')
@login_required
def get_members():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        # 獲取伺服器成員總數
        guild_response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}?with_counts=true',
            headers=headers
        )
        if guild_response.status_code != 200:
            raise Exception('Failed to get guild info')
            
        guild_data = guild_response.json()
        total_members = guild_data['approximate_member_count']
        total_pages = (total_members + limit - 1) // limit
        
        # 計算 after 參數
        after = "0" if page == 1 else str((page - 1) * limit)
        
        # 獲取成員列表
        members_url = f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members?limit={limit}&after={after}'
        response = requests.get(members_url, headers=headers)
        
        if response.status_code != 200:
            raise Exception('Failed to get members')
            
        members = response.json()
        
        return jsonify({
            'members': members,
            'totalPages': total_pages,
            'currentPage': page,
            'totalMembers': total_members
        })
    except Exception as e:
        print(f"Error getting members: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ...existing code...

#Add endpoint to get all roles
@app.route('/api/roles')
@login_required
def get_roles():
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/roles',
            headers=headers
        )
        if response.status_code != 200:
            return jsonify({'error': '無法獲取身分組'}), 500
        roles = response.json()
       #Exclude @everyone role if desired
        roles = [role for role in roles if role['name'] != '@everyone']
        return jsonify(roles)
    except Exception as e:
        print(f"Error fetching roles: {e}")
        return jsonify({'error': '伺服器錯誤'}), 500
#Add endpoint to get a member's roles
@app.route('/api/members/<member_id>/roles', methods=['GET'])
@login_required
def get_member_roles(member_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}',
            headers=headers
        )
        if response.status_code != 200:
            return jsonify({'error': '無法獲取成員身分組'}), 500
        member = response.json()
        return jsonify(member.get('roles', []))
    except Exception as e:
        print(f"Error fetching member roles: {e}")
        return jsonify({'error': '伺服器錯誤'}), 500



def run_flask():
    try:
        app.run(debug=False, use_reloader=False, port=5000)
    except Exception as e:
        print(f"Error starting Flask: {e}")

if (__name__ == '__main__'):
    run_flask()

# ...existing code...

def start_bot_thread():
    """在新線程中啟動 bot"""
    from bot import run_bot
    run_bot()

def run_app():
    """運行 Flask 應用"""
    app = create_flask_app()

 #在新線程中啟動 bot
    bot_thread = threading.Thread(target=start_bot_thread, daemon=True)
    bot_thread.start()
       

@app.route('/api/members/<member_id>')
@login_required
def get_member_details(member_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        # Get member details from Discord API
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/members/{member_id}',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get member details')
            
        member = response.json()
        
       # Get user presence/status
        presence = {}
        if bot and bot.is_ready():
            guild = bot.get_guild(int(Config.GUILD_ID))
            if guild:
                member_obj = guild.get_member(int(member_id))
                if member_obj:
                    presence = {
                        'status': str(member_obj.status),
                        'activity': str(member_obj.activity) if member_obj.activity else None
                    }
        
        # Combine member data with presence
        member_data = {
            **member,
            'status': presence.get('status', 'offline'),
            'activity': presence.get('activity')
        }
        
        return jsonify(member_data)
        
    except Exception as e:
        print(f"Error getting member details: {str(e)}")
        return jsonify({'error': str(e)}), 500

if (__name__ == '__main__'):
    # Start the Flask app
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host='0.0.0.0', port=port)
# ...existing code...

@app.route('/api/roles/<role_id>', methods=['GET'])
@login_required
def get_role_details(role_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/guilds/{Config.GUILD_ID}/roles/{role_id}',
            headers=headers
        )
        if response.status_code != 200:
            raise Exception('Failed to get role details')
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/<channel_id>', methods=['GET'])
@login_required
def get_channel_details(channel_id):
    try:
        headers = {
            'Authorization': f'Bot {Config.DISCORD_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'https://discord.com/api/v9/channels/{channel_id}',
            headers=headers
        )
        if response.status_code != 200:
            raise Exception('Failed to get channel details')
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ...existing code...

