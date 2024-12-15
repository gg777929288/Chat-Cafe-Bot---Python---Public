"""
Module for managing voice rooms in a Discord bot.
"""

import os
import json
import sqlite3  # 保留用於同步操作
import aiosqlite
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands, tasks
from discord import app_commands
from user_info_cog import UserInfoCog

class VoiceRoomManager:
    def __init__(self, bot):
        self.bot = bot
        self.base_path = 'Userfile'
        self.db_path = os.path.join(self.base_path, 'voice_channels.db')
        self.history_db_path = os.path.join(self.base_path, 'voice_history.db')
        self.executor = ThreadPoolExecutor(max_workers=3)
        
    async def initialize(self):
        """Initialize the database asynchronously."""
        await self._init_db_async()

    def _init_db(self):
        """初始化資料庫"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化主資料庫
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_channels (
                channel_id INTEGER PRIMARY KEY,
                owner_id INTEGER,
                status TEXT DEFAULT 'active',
                admins TEXT DEFAULT '[]',
                settings TEXT DEFAULT '{}',
                last_settings TEXT DEFAULT '{}'
            )
        """)
        conn.commit()
        conn.close()
        
        # 初始化歷史記錄資料庫
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                target_id INTEGER,
                action TEXT,
                details TEXT,
                operator_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS text_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    async def _init_db_async(self):
        """初始化資料庫 asynchronously"""
        # ...existing async init code...

    async def update_channel_settings(self, channel_id, settings):
        """更新頻道設置"""
        try:
            print(f"Updating channel {channel_id} settings: {settings}")
            
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                raise ValueError(f"Channel {channel_id} not found")

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
            print(f"Successfully updated channel {channel_id}")
            return True
            
        except discord.Forbidden as e:
            print(f"Permission error updating channel {channel_id}: {e}")
            raise
        except Exception as e:
            print(f"Error updating channel {channel_id}: {e}")
            raise

    async def delete_channel(self, channel_id):
        """刪除頻道"""
        try:
            # 確保 channel_id 為整數
            channel_id = int(channel_id)
            
            # 取得頻道
            channel = self.bot.get_channel(channel_id)
            if not channel:
                raise ValueError(f"Channel not found: {channel_id}")
                
            # 檢查頻道類型
            if not isinstance(channel, discord.VoiceChannel):
                raise ValueError("Not a voice channel")
                
            # 檢查頻道成員
            if len(channel.members) > 0:
                raise ValueError("Channel has active members")
                
            # 儲存設定
            await self.save_channel_settings_before_delete(channel_id)
            
            # 刪除頻道
            await channel.delete(reason="Admin request")
            
            # 更新資料庫
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE voice_channels SET status = 'deleted' WHERE channel_id = ?",
                    (channel_id,)
                )
                await db.commit()
                
            print(f"Successfully deleted channel {channel_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting channel {channel_id}: {e}")
            raise

    async def update_channel_cache(self, channel):
        """更新頻道成員緩存"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._update_channel_cache_sync,
                channel
            )
        except Exception as e:
            print(f"Error updating channel cache: {e}")

    def _update_channel_cache_sync(self, channel):
        """同步執行緩存更新操作"""
        cache_path = os.path.join(self.base_path, 'channel_cache.json')
        try:
            guild = channel.guild
            members = []
            
            if isinstance(channel, discord.VoiceChannel):
                for member in guild.members:
                    # 從 user_info.db 獲取用戶資訊
                    user_info = UserInfoCog.get_user_info(member.id)
                    if not user_info:
                        continue

                    # 檢查該成員是否在頻道中
                    in_channel = member in channel.members
                    # 檢查成員權限
                    perms = channel.permissions_for(member)
                    
                    members.append({
                        'id': str(member.id),
                        'display_name': user_info['display_name'],
                        'avatar_url': user_info['avatar_url'],
                        'connect': perms.connect,
                        'speak': perms.speak,
                        'is_admin': user_info['is_admin'],
                        'in_channel': in_channel,
                        'roles': user_info['guild_roles']
                    })

            # 創建或更新緩存
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            cache = {}
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        cache = json.load(f)
                except Exception as e:
                    print(f"Error reading cache file: {e}")

            cache[str(channel.id)] = {
                'name': channel.name,
                'updated_at': datetime.now().isoformat()
            }

            # 寫入緩存文件
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

            print(f"Successfully updated cache for channel {channel.name} ({channel.id}) with {len(members)} members")
        except Exception as e:
            print(f"Error in _update_channel_cache_sync for channel {channel.id}: {str(e)}")
            raise  # 重新拋出異常以便上層處理

    async def save_channel_settings_before_delete(self, channel_id):
        """異步保存設置並刪除頻道"""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return

            # 獲取頻道擁有者
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT owner_id FROM voice_channels WHERE channel_id = ?", 
                                      (channel_id,)) as cursor:
                    result = await cursor.fetchone()
                    owner_id = result[0] if result else None

            if not owner_id:
                print(f"No owner found for channel {channel_id}")
                return

            # 記錄頻道的基本設置
            settings = {
                'name': channel.name,
                'user_limit': channel.user_limit,
                'bitrate': channel.bitrate,
                'rtc_region': channel.rtc_region,
                'permissions': {
                    str(target.id): {
                        'type': 'role' if isinstance(target, discord.Role) else 'member',
                        'allow': overwrite.pair()[0].value,
                        'deny': overwrite.pair()[1].value
                    }
                    for target, overwrite in channel.overwrites.items()
                }
            }

            async with aiosqlite.connect(self.db_path) as db:
                # 插入一個新的記錄，標記為已刪除
                await db.execute(
                    "INSERT INTO voice_channels (channel_id, owner_id, status, last_settings) VALUES (?, ?, 'deleted', ?)",
                    (channel_id, owner_id, json.dumps(settings))
                )
                await db.commit()

            print(f"Successfully saved settings for channel {channel.name} before deletion")

        except Exception as e:
            print(f"Error saving channel settings before delete: {e}")
            raise

    async def log_permission_change(self, channel_id, user_id, action, details, operator_id):
        """記錄權限變更到歷史資料庫"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO permission_logs 
               (channel_id, user_id, target_id, action, details, operator_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (channel_id, user_id, details.get('target_id'), action, 
             json.dumps(details), operator_id)
        )
        conn.commit()
        conn.close()

    async def apply_saved_settings(self, channel, owner_id):
        """套用使用者上次的頻道設定，包括禁言/解除禁言、黑名單、語音伺服器位置等"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT last_settings FROM voice_channels WHERE owner_id = ? AND status = 'deleted' ORDER BY rowid DESC LIMIT 1",
                    (owner_id,)
                ) as cursor:
                    result = await cursor.fetchone()
                    
                    if result and result[0]:
                        settings = json.loads(result[0])
                        
                        # 套用基本設定
                        await channel.edit(
                            name=settings.get('name', channel.name),
                            user_limit=settings.get('user_limit', 0),
                            bitrate=settings.get('bitrate', 96000),
                            rtc_region=settings.get('rtc_region')
                        )
                        
                        # 套用權限設定
                        for target_id, perms in settings.get('permissions', {}).items():
                            target = None
                            if perms['type'] == 'role':
                                target = channel.guild.get_role(int(target_id))
                            else:
                                target = channel.guild.get_member(int(target_id))
                                
                            if target:
                                allow = discord.Permissions(perms['allow'])
                                deny = discord.Permissions(perms['deny'])
                                await channel.set_permissions(
                                    target,
                                    overwrite=discord.PermissionOverwrite.from_pair(allow, deny)
                                )
                        
                        # 套用黑名單
                        blacklist = settings.get('blacklist', [])
                        for user_id in blacklist:
                            user = channel.guild.get_member(int(user_id))
                            if user:
                                await channel.set_permissions(user, connect=False)
                        
                        # 套用伺服器端拒聽設置
                        server_reject = settings.get('server_reject', False)
                        if server_reject:
                            # 假設有一個方法來設置伺服器端拒聽
                            await self.enable_server_reject(channel)
                        else:
                            await self.disable_server_reject(channel)
                        
                        print(f"Successfully applied saved settings for user {owner_id}")
        
        except Exception as e:
            print(f"Error applying saved settings: {e}")

    async def enable_server_reject(self, channel):
        """啟用伺服器端拒聽設定"""
        # 實作伺服器端拒聽的具體邏輯
        pass

    async def disable_server_reject(self, channel):
        """禁用伺服器端拒聽設定"""
        # 實作禁用伺服器端拒聽的具體邏輯
        pass

    async def track_member_activity(self, member, channel, action_type):
        """記錄成員活動"""
        try:
            async with aiosqlite.connect(self.history_db_path) as db:
                await db.execute("""
                    INSERT INTO member_activity (
                        channel_id, member_id, action_type, timestamp
                    ) VALUES (?, ?, ?, datetime('now'))
                """, (channel.id, member.id, action_type))
                await db.commit()
                
        except Exception as e:
            print(f"Error tracking member activity: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """處理語音狀態變更"""
        try:
            # 成員加入頻道
            if after.channel and not before.channel:
                await self.track_member_activity(member, after.channel, 'join')
                
            # 成員離開頻道
            elif before.channel and not after.channel:
                await self.track_member_activity(member, before.channel, 'leave')
                
            # 成員在頻道間移動
            elif before.channel and after.channel and before.channel != after.channel:
                await self.track_member_activity(member, before.channel, 'leave')
                await self.track_member_activity(member, after.channel, 'join')
                
            # 成員狀態變更（靜音、拒聽等）
            if before.self_mute != after.self_mute or before.self_deaf != after.self_deaf:
                channel = after.channel or before.channel
                if channel:
                    action = 'status_change'
                    await self.track_member_activity(member, channel, action)
                    
        except Exception as e:
            print(f"Error handling voice state update: {e}")

    async def _init_db(self):
        """初始化資料庫"""
        # ...existing code...
        
        # 添加成員活動記錄表
        async with aiosqlite.connect(self.history_db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS member_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    member_id INTEGER,
                    action_type TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

class VoiceRoomManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manager = VoiceRoomManager(bot)
        self.base_path = 'Userfile'
        self.db_path = os.path.join(self.base_path, 'voice_channels.db')
        self.history_db_path = os.path.join(self.base_path, 'voice_history.db')
        self.logs_path = os.path.join(self.base_path, 'voice_logs')
        os.makedirs(self.logs_path, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.cache_lock = asyncio.Lock()
        self.create_channel_id = 1317132559305543751 # 創建頻道的ID
        self.default_category_id = 1037247176671240212  # 預設創建到的分類ID
        print(f"VoiceRoomManagement initialized with create_channel_id: {self.create_channel_id}")
        print(f"Category ID: {self.default_category_id}")

    async def cog_load(self):
        await self.manager._init_db_async()  # Await the asynchronous init
        self.check_channels.start()
        self.empty_channel_check.start()
        self.delete_empty_voice_channels.start()  # Start the task

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_channels (
                channel_id INTEGER PRIMARY KEY,
                owner_id INTEGER,
                status TEXT DEFAULT 'active',
                admins TEXT DEFAULT '[]',
                settings TEXT DEFAULT '{}',
                last_settings TEXT DEFAULT '{}'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                target_id INTEGER,
                details TEXT,
                operator_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS text_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    async def log_permission_change(self, channel_id, user_id, action, details, operator_id):
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO permission_logs 
               (channel_id, user_id, target_id, action, details, operator_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (channel_id, user_id, details.get('target_id'), action, json.dumps(details), operator_id)
        )
        conn.commit()
        conn.close()

    async def save_channel_settings(self, channel_id):
        """異步保存頻道設置"""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return

            settings = {
                'name': channel.name,
                'user_limit': channel.user_limit,
                'bitrate': channel.bitrate,
                'rtc_region': channel.rtc_region,
                'permissions': {
                    str(target.id): {
                        'type': 'role' if isinstance(target, discord.Role) else 'member',
                        'allow': overwrite.allow.value,
                        'deny': overwrite.deny.value
                    }
                    for target, overwrite in channel.overwrites.items()
                }
            }

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE voice_channels SET last_settings = ? WHERE channel_id = ?",
                    (json.dumps(settings), channel_id)
                )
                await db.commit()

            print(f"Successfully saved settings for channel {channel.name}")
            
        except Exception as e:
            print(f"Error saving channel settings: {e}")
            raise

    async def is_channel_owner(self, ctx, channel_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT owner_id FROM voice_channels WHERE channel_id = ?", (channel_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] == ctx.user.id

    async def update_channel_permissions(self, channel_id, settings):
        """更新頻道權限設定"""
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return False
            
        try:
            # 更新頻道基本設定
            await channel.edit(
                name=settings.get('name', channel.name),
                user_limit=int(settings.get('user_limit', channel.user_limit))
            )
            
            # 更新成員權限
            for member_data in settings.get('members', []):
                member = channel.guild.get_member(int(member_data['id']))
                if member:
                    overwrite = channel.overwrites_for(member)
                    overwrite.connect = member_data.get('connect', None)
                    overwrite.speak = member_data.get('speak', None)
                    await channel.set_permissions(member, overwrite=overwrite)
            
            # 保存最新設定
            await self.save_channel_settings(channel_id)
            return True
            
        except Exception as e:
            print(f"Error updating permissions: {e}")
            return False

    @tasks.loop(seconds=15)  # 更頻繁地更新
    async def check_channels(self):
        """定期更新所有語音頻道的緩存"""
        try:
            async with self.cache_lock:
                for guild in self.bot.guilds:
                    for channel in guild.voice_channels:
                        try:
                            # Fixed: Use self.manager instead of self
                            await self.manager.update_channel_cache(channel)
                            await asyncio.sleep(1)  # 短暫延遲
                        except Exception as e:
                            print(f"Error updating cache for channel {channel.id}: {str(e)}")
        except Exception as e:
            print(f"Error in check_channels: {str(e)}")

    async def save_channel_settings_before_delete(self, channel_id):
        """異步保存設置並刪除頻道"""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return

            # 記錄頻道的基本設置
            settings = {
                'name': channel.name,
                'user_limit': channel.user_limit,
                'bitrate': channel.bitrate,
                'rtc_region': str(channel.rtc_region) if channel.rtc_region else None,
                'permissions': {}
            }

            # 記錄權限設定
            for target, overwrite in channel.overwrites.items():
                # 轉換權限設定為可序列化的格式
                allow, deny = overwrite.pair()
                settings['permissions'][str(target.id)] = {
                    'type': 'role' if isinstance(target, discord.Role) else 'member',
                    'allow': allow.value,
                    'deny': deny.value
                }

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE voice_channels SET last_settings = ? WHERE channel_id = ?",
                    (json.dumps(settings), channel_id)
                )
                await db.commit()

            print(f"Successfully saved settings for channel {channel.name}")

        except Exception as e:
            print(f"Error saving channel settings before delete: {e}")

    async def apply_saved_settings(self, channel, owner_id):
        """套用使用者上次的頻道設置"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT last_settings FROM voice_channels WHERE owner_id = ? AND status = 'deleted' ORDER BY rowid DESC LIMIT 1",
                    (owner_id,)
                ) as cursor:
                    result = await cursor.fetchone()
                    
                    if result and result[0]:
                        settings = json.loads(result[0])
                        
                        # 套用基本設定
                        await channel.edit(
                            name=settings.get('name', channel.name),
                            user_limit=settings.get('user_limit', 0),
                            bitrate=settings.get('bitrate', 96000),
                            rtc_region=settings.get('rtc_region')
                        )
                        
                        # 套用權限設定
                        for target_id, perms in settings.get('permissions', {}).items():
                            target = None
                            if perms['type'] == 'role':
                                target = channel.guild.get_role(int(target_id))
                            else:
                                target = channel.guild.get_member(int(target_id))
                                
                            if target:
                                allow = discord.Permissions(perms['allow'])
                                deny = discord.Permissions(perms['deny'])
                                await channel.set_permissions(
                                    target,
                                    overwrite=discord.PermissionOverwrite.from_pair(allow, deny)
                                )
                                
                        print(f"Successfully applied saved settings for user {owner_id}")

        except Exception as e:
            print(f"Error applying saved settings: {e}")

    async def delete_empty_channel(self, channel_id):
        """刪除空頻道並保存設置"""
        try:
            # 先保存設置
            await self.save_channel_settings_before_delete(channel_id)
            
            # 然後刪除頻道
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.delete()
                
                # 更新數據庫狀態
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE voice_channels SET status = 'deleted' WHERE channel_id = ?",
                    (channel_id,)
                )
                conn.commit()
                conn.close()
                print(f"Successfully deleted empty channel: {channel.name}")
                
        except Exception as e:
            print(f"Error deleting channel {channel_id}: {e}")

    @tasks.loop(seconds=5)  # 每5秒檢查一次
    async def empty_channel_check(self):
        """檢查並刪除空的語音頻道"""
        try:
            # 從數據庫獲取所有活躍的自動創建頻道
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id FROM voice_channels WHERE status = 'active'")
            channels = cursor.fetchall()
            conn.close()

            for (channel_id,) in channels:
                channel = self.bot.get_channel(channel_id)
                if channel and len(channel.members) == 0:
                    await self.delete_empty_channel(channel_id)

        except Exception as e:
            print(f"Error in empty_channel_check: {e}")

    @empty_channel_check.before_loop
    async def before_empty_channel_check(self):
        """等待機器人準備就緒"""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def delete_empty_voice_channels(self):
        """定期檢查並刪除空的語音頻道"""
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if len(channel.members) == 0 and channel.id != self.create_channel_id:
                    try:
                        # Check if the channel was created by voice_room_management.py
                        async with aiosqlite.connect(self.db_path) as db:
                            async with db.execute("SELECT 1 FROM voice_channels WHERE channel_id = ? AND status = 'active'", (channel.id,)) as cursor:
                                if await cursor.fetchone():
                                    await channel.delete(reason="自動刪除空的語音頻道")
                                    logging.info(f"Deleted empty voice channel: {channel.name} ({channel.id})")
                    except Exception as e:
                        logging.error(f"Failed to delete channel {channel.name} ({channel.id}): {e}")

    def cog_unload(self):
        self.check_channels.cancel()
        self.executor.shutdown(wait=True)
        self.empty_channel_check.cancel()
        self.delete_empty_voice_channels.cancel()  # Cancel the task

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """處理使用者加入創建頻道時的邏輯"""
        try:
            # 詳細的偵錯日誌
            print("\n=== Voice State Update Debug Info ===")
            print(f"Member: {member.name} ({member.id})")
            print(f"Before channel: {before.channel.id if before.channel else None}")
            print(f"After channel: {after.channel.id if after.channel else None}")
            print(f"Create channel ID: {self.create_channel_id}")

            # 檢查是否進入創建頻道
            if not after.channel:
                return

            if after.channel.id == self.create_channel_id:
                print(f"User {member.name} entered create channel")
                
                # 獲取目標類別
                target_category = self.bot.get_channel(self.default_category_id)
                if not target_category:
                    print(f"ERROR: Could not find category {self.default_category_id}")
                    return

                try:
                    # 創建新頻道
                    overwrites = {
                        member.guild.default_role: discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                            speak=True
                        ),
                        member: discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                            speak=True,
                            stream=True,
                            manage_channels=True,
                            move_members=True,
                            mute_members=True,
                            deafen_members=True
                        ),
                        member.guild.me: discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                            speak=True,
                            manage_channels=True,
                            move_members=True
                        )
                    }

                    new_channel = await target_category.create_voice_channel(
                        name=f"{member.display_name}的房間",
                        overwrites=overwrites,
                        bitrate=96000,
                        user_limit=99
                    )
                    print(f"Created channel: {new_channel.name} ({new_channel.id})")

                    # 套用上次的設置
                    await self.manager.apply_saved_settings(new_channel, member.id)

                    # 移動用戶
                    await member.move_to(new_channel)
                    print(f"Moved {member.name} to new channel")

                    # 記錄到資料庫
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "INSERT INTO voice_channels (channel_id, owner_id, status) VALUES (?, ?, 'active')",
                            (new_channel.id, member.id)
                        )
                        await db.commit()
                    print("Database updated")

                except Exception as e:
                    print(f"Error creating channel: {str(e)}")
                    traceback.print_exc()

        except Exception as e:
            print(f"Error in voice_state_update: {str(e)}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.TextChannel):
            # 檢查是否為語音頻道的文字頻道
            if message.channel.category and message.channel.name.endswith('-text'):
                conn = sqlite3.connect(self.history_db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO text_logs (channel_id, user_id, message) VALUES (?, ?, ?)",
                    (message.channel.id, message.author.id, message.content)
                )
                conn.commit()
                conn.close()

    @app_commands.command(name="更名", description="重命名你的語音頻道")
    async def rename(self, interaction: discord.Interaction, name: str):
        try:
            if not interaction.user.voice:
                await interaction.response.send_message("你必須在語音頻道中才能使用此指令！", ephemeral=True)
                return
                
            channel_id = interaction.user.voice.channel.id
            await self.manager.update_channel_settings(channel_id, {'name': name})
            await interaction.response.send_message(f"頻道名稱已更改為: {name}", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"更改名稱失敗: {str(e)}", ephemeral=True)

    @app_commands.command(name="人數限制", description="設置頻道人數上限")
    @app_commands.default_permissions(connect=True)  # 添加默認權限
    async def set_limit(self, interaction: discord.Interaction, limit: int):
        if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
            await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
            return
        await interaction.user.voice.channel.edit(user_limit=limit)
        await interaction.response.send_message(f"頻道人數上限已設置為: {limit}", ephemeral=True)

    @app_commands.command(name="禁止進入", description="禁止特定用戶進入頻道")
    async def ban_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
            await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
            return
        await interaction.user.voice.channel.set_permissions(user, connect=False)
        await self.log_permission_change(
            interaction.user.voice.channel.id,
            user.id,
            "禁止進入",
            {"target_id": user.id, "permission": "connect", "value": False},
            interaction.user.id
        )
        await interaction.response.send_message(f"已禁止 {user.mention} 進入頻道", ephemeral=True)

    @app_commands.command(name="解除禁止", description="解除用戶的進入限制")
    async def unban_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
            await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
            return
        await interaction.user.voice.channel.set_permissions(user, connect=None)
        await interaction.response.send_message(f"已解除 {user.mention} 的進入限制", ephemeral=True)

    @app_commands.command(name="禁言", description="禁言特定用戶")
    async def mute_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
            await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
            return
        await interaction.user.voice.channel.set_permissions(user, speak=False)
        await interaction.response.send_message(f"已禁言 {user.mention}", ephemeral=True)

    @app_commands.command(name="解除禁言", description="解除用戶禁言")
    async def unmute_user(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
            await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
            return
        await interaction.user.voice.channel.set_permissions(user, speak=None)
        await interaction.response.send_message(f"已解除 {user.mention} 的禁言", ephemeral=True)

    

    @app_commands.command(name="選擇地區", description="選擇並設置你的語音頻道地區")
    async def set_region(self, interaction: discord.Interaction, region: str):
            """透過指令來設定你的語音頻道地區。"""
            if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
                await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
                return

            regions = {
                "美國西部": "us_west",
                "美國東部": "us_east", 
                "美國中部": "us_central",
                "歐洲西部": "eu_west",
                "歐洲中部": "eu_central",
                "新加坡": "singapore",
                "日本": "japan",
                "巴西": "brazil",
                "香港": "hongkong",
                "雪梨": "sydney",
                "南非": "south_africa",
                "印度": "india",
                "自動": None
            }

            if region not in regions:
                region_list = "\n".join([f"• {name}" for name in regions.keys()])
                await interaction.response.send_message(
                    f"無效的地區！請使用以下其中一個地區名稱：\n{region_list}", 
                    ephemeral=True
                )
                return

            try:
                await interaction.user.voice.channel.edit(rtc_region=regions[region])
                await interaction.response.send_message(
                    f"頻道地區已設置為: {region}", 
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"設置地區時發生錯誤: {str(e)}", 
                    ephemeral=True
                )

    @app_commands.command(name="新增管理員", description="新增頻道管理員")
    async def add_admin(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.voice or not await self.is_channel_owner(interaction, interaction.user.voice.channel.id):
            await interaction.response.send_message("你必須在自己的語音頻道中才能使用此指令！", ephemeral=True)
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT admins FROM voice_channels WHERE channel_id = ?", 
                      (interaction.user.voice.channel.id,))
        result = cursor.fetchone()
        
        admins = json.loads(result[0]) if result and result[0] else []
        if user.id not in admins:
            admins.append(user.id)
            cursor.execute("UPDATE voice_channels SET admins = ? WHERE channel_id = ?",
                         (json.dumps(admins), interaction.user.voice.channel.id))
            conn.commit()
            await interaction.response.send_message(f"已將 {user.mention} 添加為頻道管理員", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.mention} 已經是管理員了", ephemeral=True)
        conn.close()


async def setup(bot):
    await bot.add_cog(VoiceRoomManagement(bot))