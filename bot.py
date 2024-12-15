import sqlite3
import logging
import asyncio
import discord
import os
import json
import aiosqlite
from datetime import datetime  # 添加這行
from discord.ext import commands, tasks
from config import Config  # 添加這行
import secrets  # 添加這行

# Configuration
ANNOUNCEMENT_CHANNEL_ID = int(secrets.token_hex(8), 16)
DATABASE = 'Userfile/userdata.db'
LOG_FILE = 'Userfile/bot.log'

# Voice Channel Configuration
VOICE_CREATE_CHANNEL_ID = int(secrets.token_hex(8), 16)
VOICE_CATEGORY_ID = int(secrets.token_hex(8), 16)

# 在文件開頭新增 intents 設置
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True  # 這個很重要！

class CustomBot(commands.Bot):
    async def setup_hook(self):
        # Start background tasks here
        self.loop.create_task(process_updates())
        update_voice_channels.start()

# Replace the existing bot instance with CustomBot
bot = CustomBot(command_prefix='!', intents=intents)

async def load_cogs():
    cog_files = [
        'chat_cog',
        'account_cog',
        'user_info_cog',
        'voice_room_management',  # 確保這個在列表中
        'report_cog',
        'help_cog',
        'update_handler_cog'
    ]
    for cog in cog_files:
        try:
            await bot.load_extension(cog)
        except Exception as e:
            logging.error(f"Failed to load cog {cog}: {e}")

async def update_channel_cache():
    """定期更新頻道資訊快取"""
    while True:
        channels = {}
        for guild in bot.guilds:
            for channel in guild.voice_channels:
                channels[str(channel.id)] = {
                    'name': channel.name,
                    'guild_id': str(channel.guild.id)
                }
        
        cache_path = 'Userfile/channel_cache.json'
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
            
        await asyncio.sleep(60)  # 每60秒更新一次

@bot.event 
async def on_ready():
    print(f'{bot.user} 已經上線！')
    print(f'Voice Create Channel ID: {VOICE_CREATE_CHANNEL_ID}')
    print(f'Voice Category ID: {VOICE_CATEGORY_ID}')
    
    try:
        print("開始同步斜線命令...")
        
        # 先加載所有 cogs
        await load_cogs()
        
        # 全局同步命令
        commands = await bot.tree.sync()
        print(f"已同步 {len(commands)} 個全局斜線命令")
        
        # 針對每個伺服器同步命令
        for guild in bot.guilds:
            try:
                guild_commands = await bot.tree.sync(guild=guild)
                print(f"已同步 {len(guild_commands)} 個命令到 {guild.name}")
            except Exception as e:
                print(f"同步 {guild.name} 的命令時發生錯誤: {e}")
                continue
                
        # 設置機器人狀態
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="輸入 /指令 可以查詢本機器人的指令喔！"
            )
        )
    except Exception as e:
        print(f"同步命令時發生錯誤: {e}")
        return

    print("所有命令同步完成！")
    delete_empty_voice_channels.start()

async def process_updates():
    """處理待處理的更新"""
    update_file = os.path.join('Userfile', 'pending_updates.json')
    
    while True:
        try:
            if os.path.exists(update_file):
                with open(update_file, 'r', encoding='utf-8') as f:
                    updates = json.load(f)
                
                if updates:
                    for update in updates:
                        await handle_update(update)
                    
                    # 清空更新文件
                    with open(update_file, 'w', encoding='utf-8') as f:
                        json.dump([], f)
            
            await asyncio.sleep(10)  # Adding sleep to prevent tight loop
            
        except Exception as e:
            logging.error(f"Error in process_updates: {e}")
            await asyncio.sleep(5)  # 發生錯誤時等待更長時間

async def handle_update(update):
    """處理單個更新請求"""
    try:
        print(f"Processing update: {update}")  # Debug log
        update_type = update.get('type')
        
        if update_type in ['immediate_channel_update', 'update_channel']:
            channel_id = int(update['channel_id'])
            settings = update['settings']
            channel = bot.get_channel(channel_id)
            
            if not channel:
                print(f"Channel {channel_id} not found")
                return False

            try:
                print(f"Directly updating channel {channel_id} settings: {settings}")
                
                # 準備更新參數
                kwargs = {
                    'name': str(settings['name']),
                    'user_limit': int(settings.get('user_limit', 0))
                }
                
                # 設置比特率
                if 'bitrate' in settings:
                    kwargs['bitrate'] = int(settings['bitrate'])
                
                # 設置地區
                if 'rtc_region' in settings:
                    kwargs['rtc_region'] = None if settings['rtc_region'] == 'auto' else settings['rtc_region']
                
                # 直接執行更新
                await channel.edit(**kwargs)
                print(f"Channel {channel_id} updated successfully")
                return True
                
            except discord.Forbidden as e:
                print(f"Permission error: {e}")
                raise
            except Exception as e:
                print(f"Error updating channel: {e}")
                raise

        if update_type == 'delete_channel':
            channel_id = update['channel_id']
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.delete()
                
    except Exception as e:
        print(f"Error in handle_update: {e}")
        return False

async def main():
    try:
        await load_cogs()
        await init_db()
        
        print("正在嘗試連接 Discord...")
        await bot.start(Config.DISCORD_TOKEN)  # Replace with your token securely
    except discord.LoginFailure:
        print("Discord Token 無效")
        logging.error("Invalid Discord token")
    except Exception as e:
        print(f"啟動時發生錯誤: {e}")
        logging.error(f"Bot startup error: {e}")
    finally:
        # 使用 bot 的閉包方法前檢查是否存在
        if hasattr(bot, 'is_closed') and await bot.is_closed():
            try:
                await bot.change_presence(
                    status=discord.Status.offline,
                    activity=discord.Game(name="服務生已下班~~")
                )
            except Exception as e:
                logging.error(f"Error changing presence during shutdown: {e}")

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')
print("機器人啟動中...") #若代碼成功啟動，顯示機器人正在啟動

async def init_db():
    """初始化數據庫"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
                         id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         account TEXT UNIQUE,
                         email TEXT UNIQUE,
                         password TEXT
                         )''')
        await db.commit()

@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("機器人正在關機...")
    await bot.change_presence(
        status=discord.Status.offline,
        activity=discord.Game(name="服務生已下班~~")
    )
    await bot.close()

def auto_restart(func):
    """Decorator to automatically restart a function if it fails.""" 
    max_retries = 3
    retry_count = 0
    async def wrapper(*args, **kwargs):
        """Wrapper function to retry the decorated function.""" 
        nonlocal retry_count
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                logging.error(f"{func.__name__} failed with {e}, retrying ({retry_count}/{max_retries})...")
                await wrapper(*args, **kwargs)
            else:
                logging.error(f"{func.__name__} failed after {max_retries} attempts.")
    return wrapper

async def start_bot():
    """Async function to start the bot"""
    try:
        await main()
    except Exception as e:
        print(f"Bot startup error: {e}")
        logging.error(f"Bot startup error: {e}")

def run_bot():
    """Sync function to run the bot"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutdown via KeyboardInterrupt")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    """監控語音狀態變更"""
    try:
        # 更新頻道快取
        channels_to_update = set()
        if before.channel:
            channels_to_update.add(before.channel)
        if after.channel:
            channels_to_update.add(after.channel)
            
        for channel in channels_to_update:
            await update_channel_members(channel)
            
    except Exception as e:
        print(f"Error in voice state update: {e}")

async def update_channel_members(channel):
    """更新特定頻道的成員資訊"""
    try:
        cache_path = os.path.join('Userfile', 'channel_cache.json')
        cache_data = {}
        
        # 讀取現有快取
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
        
        # 更新頻道資訊
        members_data = []
        for member in channel.members:
            members_data.append({
                'id': str(member.id),
                'name': member.name,
                'display_name': member.display_name,
                'avatar_url': str(member.avatar.url) if member.avatar else None,
                'in_channel': True
            })
        
        cache_data[str(channel.id)] = {
            'name': channel.name,
            'members': members_data,
            'updated_at': datetime.now().isoformat()
        }
        
        # 寫入快取
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"Error updating channel members: {e}")

@tasks.loop(seconds=5)
async def update_voice_channels():
    """定期更新所有語音頻道狀態"""
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            await update_channel_members(channel)

@tasks.loop(seconds=5)
async def delete_empty_voice_channels():
    """定期檢查並刪除空的語音頻道"""
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if len(channel.members) == 0 and channel.id != VOICE_CREATE_CHANNEL_ID:
                try:
                    # Check if the channel was created by voice_room_management.py
                    async with aiosqlite.connect('Userfile/voice_channels.db') as db:
                        async with db.execute("SELECT 1 FROM voice_channels WHERE channel_id = ? AND status = 'active'", (channel.id,)) as cursor:
                            if await cursor.fetchone():
                                await channel.delete(reason="自動刪除空的語音頻道")
                                logging.info(f"Deleted empty voice channel: {channel.name} ({channel.id})")
                except Exception as e:
                    logging.error(f"Failed to delete channel {channel.name} ({channel.id}): {e}")

if __name__ == '__main__':
    run_bot()
