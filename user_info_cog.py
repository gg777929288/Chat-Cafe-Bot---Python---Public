import discord
from discord.ext import commands, tasks
import sqlite3
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from shared_config import bot  # Import the bot instance

class UserInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._init_db()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.update_lock = asyncio.Lock()

    def _init_db(self):
        self.db_path = 'Userfile/user_info.db'
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if 'users' table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                # Check if 'users_backup' already exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users_backup'")
                if cursor.fetchone():
                    cursor.execute("DROP TABLE users_backup")
                
                # Backup existing data
                cursor.execute("ALTER TABLE users RENAME TO users_backup")
                
                # Create new 'users' table with correct schema
                cursor.execute("""
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        display_name TEXT,
                        avatar_url TEXT,
                        guild_roles TEXT DEFAULT '[]',
                        is_admin BOOLEAN DEFAULT FALSE,
                        guild_permissions INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Copy data from backup, handling missing 'id' column
                cursor.execute("PRAGMA table_info(users_backup)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'id' in columns:
                    cursor.execute("""
                        INSERT INTO users (id, name, display_name, avatar_url, last_updated)
                        SELECT id, name, display_name, avatar_url, last_updated FROM users_backup
                    """)
                else:
                    cursor.execute("""
                        INSERT INTO users (name, display_name, avatar_url, last_updated)
                        SELECT name, display_name, avatar_url, last_updated FROM users_backup
                    """)
                
                # Drop the backup table
                cursor.execute("DROP TABLE users_backup")
            
            conn.commit()
        except Exception as e:
            print(f"Error updating user info: {e}")
        finally:
            if conn:
                conn.close()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.update_user_info(member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self.update_user_info(after)

    @tasks.loop(hours=24)
    async def sync_all_users(self):
        """每天同步所有成員資訊"""
        try:
            for guild in self.bot.guilds:
                for member in guild.members:
                    await self.update_user_info(member)
                    await asyncio.sleep(0.1)  # 防止過快更新
        except Exception as e:
            print(f"Error in sync_all_users: {e}")

    def cog_load(self):
        self.sync_all_users.start()

    def cog_unload(self):
        self.sync_all_users.cancel()

    async def update_user_info(self, member):
        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users 
            (id, name, display_name, avatar_url, guild_roles, is_admin, guild_permissions, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            member.id,
            member.name,
            member.display_name,
            str(member.display_avatar.url) if member.display_avatar else None,
            json.dumps([str(role.id) for role in member.roles]),
            member.guild_permissions.administrator,
            member.guild_permissions.value
        ))
        conn.commit()

    @discord.app_commands.command(name="使用者", description="顯示您的個人資料和相關資訊")
    async def user_info(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction)
        if not isinstance(ctx.channel, discord.TextChannel):
            await interaction.response.send_message("此指令只能在文字頻道中使用！", ephemeral=True)
            return

        user = ctx.author
        embed = discord.Embed(title=f"{user.name}的個人資料", color=user.color)

        avatar_url = user.display_avatar.url if user.display_avatar else None
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="用戶ID", value=user.id, inline=True)
        embed.add_field(name="帳號建立時間", value=user.created_at.strftime("%Y/%m/%d"), inline=True)
        embed.add_field(name="伺服器加入時間", value=ctx.author.joined_at.strftime("%Y/%m/%d"), inline=True)

        status = str(getattr(user, 'status', '未知')).title()
        activity = "無動態"
        if hasattr(user, 'activities') and user.activities:
            activity = getattr(user.activities[0], 'name', "無動態")
        embed.add_field(name="目前狀態", value=status, inline=True)
        embed.add_field(name="目前動態", value=activity, inline=True)

        roles = [role.mention for role in user.roles[1:]]
        if roles:
            embed.add_field(name="身分組", value=" ".join(roles), inline=False)

        view = self.UserInfoView(user)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.app_commands.command(name="搜尋使用者", description="在伺服器中搜尋指定用戶名的使用者")
    async def search_user(self, interaction: discord.Interaction, username: str):
        ctx = await self.bot.get_context(interaction)
        if not isinstance(ctx.channel, discord.TextChannel):
            await interaction.response.send_message("此指令只能在文字頻道中使用！", ephemeral=True)
            return

        members = [member for member in ctx.guild.members if username.lower() in member.name.lower()]

        if not members:
            await interaction.response.send_message("找不到符合條件的使用者。", ephemeral=True)
            return

        embed = discord.Embed(title="搜尋結果", color=discord.Color.green())
        for member in members:
            embed.add_field(name=member.name, value=f"ID: {member.id}", inline=False)

        await interaction.response.send_message(embed=embed)
        ctx = await self.bot.get_context(interaction)
        if not isinstance(ctx.channel, discord.TextChannel):
            await interaction.response.send_message("此指令只能在文字頻道中使用！", ephemeral=True)
            return

        user = ctx.author
        embed = discord.Embed(title=f"{user.name}的個人資料", color=user.color)

        avatar_url = user.display_avatar.url if user.display_avatar else None
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="用戶ID", value=user.id, inline=True)
        embed.add_field(name="帳號建立時間", value=user.created_at.strftime("%Y/%m/%d"), inline=True)
        embed.add_field(name="伺服器加入時間", value=ctx.author.joined_at.strftime("%Y/%m/%d"), inline=True)

        status = str(getattr(user, 'status', '未知')).title()
        activity = "無動態"
        if hasattr(user, 'activities') and user.activities:
            activity = getattr(user.activities[0], 'name', "無動態")
        embed.add_field(name="目前狀態", value=status, inline=True)
        embed.add_field(name="目前動態", value=activity, inline=True)

        roles = [role.mention for role in user.roles[1:]]
        if roles:
            embed.add_field(name="身分組", value=" ".join(roles), inline=False)

        view = self.UserInfoView(user)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.app_commands.command(name="搜尋使用者", description="在伺服器中搜尋指定用戶名的使用者")
    async def search_user(self, interaction: discord.Interaction, username: str):
        ctx = await self.bot.get_context(interaction)
        if not isinstance(ctx.channel, discord.TextChannel):
            await interaction.response.send_message("此指令只能在文字頻道中使用！", ephemeral=True)
            return

        members = [member for member in ctx.guild.members if username.lower() in member.name.lower()]

        if not members:
            await interaction.response.send_message("找不到符合條件的使用者。", ephemeral=True)
            return

        embed = discord.Embed(title="搜尋結果", color=discord.Color.green())
        for member in members:
            embed.add_field(name=member.name, value=f"ID: {member.id}", inline=False)

        await interaction.response.send_message(embed=embed)

    @classmethod
    def get_user_info(cls, user_id):
        """獲取用戶資訊的靜態方法"""
        db_path = 'Userfile/user_info.db'
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'name': result[1],
                    'display_name': result[2],
                    'avatar_url': result[3],
                    'guild_roles': json.loads(result[4]),
                    'is_admin': bool(result[5]),
                    'guild_permissions': result[6]
                }
            return None
        finally:
            conn.close()

    @classmethod
    def get_all_users(cls):
        """獲取所有用戶資訊的靜態方法"""
        db_path = 'Userfile/user_info.db'
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
            return [{
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'avatar_url': row[3],
                'guild_roles': json.loads(row[4]),
                'is_admin': bool(row[5]),
                'guild_permissions': row[6]
            } for row in results]
        finally:
            conn.close()

    @classmethod
    def get_member(cls, member_id):
        """Retrieve a Discord member by ID"""
        member = bot.get_user(int(member_id))  # Use the imported bot instance
        return member

    @classmethod
    def block_member(cls, member):
        """Block a member by kicking them from the guild"""
        try:
            asyncio.run_coroutine_threadsafe(member.kick(reason="Blocked by admin"), bot.loop)
        except Exception as e:
            raise e

    @classmethod
    def mute_member(cls, member):
        """Mute a member by assigning a muted role"""
        try:
            muted_role = discord.utils.get(member.guild.roles, name="Muted")
            if not muted_role:
                # Create muted role if it doesn't exist
                muted_role = asyncio.run_coroutine_threadsafe(
                    member.guild.create_role(name="Muted"), bot.loop
                ).result()
                for channel in member.guild.channels:
                    asyncio.run_coroutine_threadsafe(
                        channel.set_permissions(muted_role, speak=False, send_messages=False),
                        bot.loop
                    ).result()
            asyncio.run_coroutine_threadsafe(
                member.add_roles(muted_role, reason="Muted by admin"), bot.loop
            ).result()
        except Exception as e:
            raise e

    @classmethod
    def kick_member(cls, member):
        """Kick a member from the guild"""
        try:
            asyncio.run_coroutine_threadsafe(
                member.kick(reason="Kicked by admin"), bot.loop
            ).result()
        except Exception as e:
            raise e

async def setup(bot):
    cog = UserInfoCog(bot)
    await bot.add_cog(cog)