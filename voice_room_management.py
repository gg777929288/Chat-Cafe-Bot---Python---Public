import discord
from discord.ext import commands
import sqlite3
import json
import asyncio
import logging

class VoiceRoomManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_channels = {}  # {channel_id: {'owner': user_id, 'admins': [user_ids], 'banned': [user_ids], 'public': bool}}
        self.INFO_CHANNEL_ID = 921543952631484517
        self.voice_conn = sqlite3.connect('Userfile/Voiceroom.db')
        self.voice_c = self.voice_conn.cursor()
        self.voice_logger = logging.getLogger('voice_room')
        self.voice_logger.setLevel(logging.INFO)
        handler = logging.FileHandler('Userfile/voiceroom.log')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
        self.voice_logger.addHandler(handler)
        self.bot.loop.create_task(self.periodic_check())

    async def periodic_check(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for channel_id in list(self.voice_channels.keys()):
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await self.check_empty_and_transfer(channel)
            await asyncio.sleep(300)  # Check every 5 minutes

    async def create_voice_channel(self, ctx, member, category):
        channel_name = f"{member.name}的小天地"
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(connect=False),
            member: discord.PermissionOverwrite(connect=True, manage_channels=True, manage_permissions=True, mute_members=True)
        }
        
        channel = await category.create_voice_channel(channel_name, overwrites=overwrites)
        self.voice_channels[channel.id] = {
            'owner': member.id,
            'admins': [],
            'banned': [],
            'public': False
        }
        return channel

    async def transfer_ownership(self, channel_id, new_owner_id):
        if channel_id in self.voice_channels:
            old_owner = self.voice_channels[channel_id]['owner']
            self.voice_channels[channel_id]['owner'] = new_owner_id
            if old_owner in self.voice_channels[channel_id]['admins']:
                self.voice_channels[channel_id]['admins'].remove(old_owner)
            return True
        return False

    async def check_empty_and_transfer(self, channel):
        if not channel.members:
            if channel.id in self.voice_channels:
                admins = self.voice_channels[channel.id]['admins']
                
                if admins:
                    new_owner_id = admins[0]
                    await self.transfer_ownership(channel.id, new_owner_id)
                else:
                    await channel.delete()
                    del self.voice_channels[channel.id]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel and before.channel.id in self.voice_channels:
            if member.id == self.voice_channels[before.channel.id]['owner']:
                await self.check_empty_and_transfer(before.channel)

        # Check if the user joined the specific voice channel
        if after.channel and after.channel.id == 1313170094310031520:
            category = discord.utils.get(member.guild.categories, id=1313355301751226428)
            if category:
                new_channel = await self.create_voice_channel(member, category)
                await member.move_to(new_channel)

    @commands.command()
    async def make_admin(self, ctx, member: discord.Member):
        channel = ctx.author.voice.channel
        if channel and channel.id in self.voice_channels:
            if ctx.author.id == self.voice_channels[channel.id]['owner']:
                if member.id not in self.voice_channels[channel.id]['admins']:
                    self.voice_channels[channel.id]['admins'].append(member.id)
                    await channel.set_permissions(member, connect=True, manage_channels=True, mute_members=True)
                    await ctx.send(f"{member.name} 現在是此頻道的管理員。")

    @commands.command()
    async def ban_user(self, ctx, member: discord.Member):
        channel = ctx.author.voice.channel
        if channel and channel.id in self.voice_channels:
            if ctx.author.id == self.voice_channels[channel.id]['owner'] or ctx.author.id in self.voice_channels[channel.id]['admins']:
                if member.id not in self.voice_channels[channel.id]['banned']:
                    self.voice_channels[channel.id]['banned'].append(member.id)
                    await channel.set_permissions(member, connect=False)
                    if member in channel.members:
                        await member.move_to(None)
                    await ctx.send(f"{member.name} 已經被禁止進入此頻道。")

    @commands.command()
    async def set_public(self, ctx, public: bool):
        channel = ctx.author.voice.channel
        if channel and channel.id in self.voice_channels:
            if ctx.author.id == self.voice_channels[channel.id]['owner']:
                self.voice_channels[channel.id]['public'] = public
                await channel.set_permissions(ctx.guild.default_role, connect=public)
                status = "公開" if public else "私密"
                await ctx.send(f"頻道已設為{status}囉！ ✨")

    @commands.command(name='管理語音頻道')
    async def manage_voice_channel(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("你必須先進入語音頻道才能使用此指令！")

        self.voice_c.execute("SELECT owner_id, admin_id FROM voice_rooms WHERE channel_id = ?", (ctx.author.voice.channel.id,))
        result = self.voice_c.fetchone()
        if not result or (ctx.author.id != result[0] and ctx.author.id != result[1]):
            return await ctx.send("只有房主或管理員才能管理語音頻道！")

        embed = discord.Embed(title="語音頻道管理", color=discord.Color.blue())
        embed.description = "請選擇要修改的設定："

        class ManageView(discord.ui.View):
            def __init__(self, bot, timeout=60):
                super().__init__(timeout=timeout)
                self.bot = bot

            @discord.ui.button(label="更改名稱", style=discord.ButtonStyle.primary)
            async def name_button(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("只有指令使用者才能操作此按鈕！", ephemeral=True)
                await interaction.response.send_message("請輸入新的頻道名稱：")
                try:
                    name_msg = await self.bot.wait_for('message', 
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                        timeout=30.0
                    )
                    await ctx.author.voice.channel.edit(name=name_msg.content)
                    await interaction.followup.send("✅ 頻道名稱已更新！")
                except asyncio.TimeoutError:
                    await interaction.followup.send("❌ 操作超時！")

            @discord.ui.button(label="設定人數限制", style=discord.ButtonStyle.primary)
            async def limit_button(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("只有指令使用者才能操作此按鈕！", ephemeral=True)
                await interaction.response.send_message("請輸入人數限制（0為無限制）：")
                try:
                    limit_msg = await self.bot.wait_for('message',
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit(),
                        timeout=30.0
                    )
                    await ctx.author.voice.channel.edit(user_limit=int(limit_msg.content))
                    await interaction.followup.send("✅ 人數限制已更新！")
                except asyncio.TimeoutError:
                    await interaction.followup.send("❌ 操作超時！")

            @discord.ui.button(label="設為公開", style=discord.ButtonStyle.green)
            async def public_button(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("只有指令使用者才能操作此按鈕！", ephemeral=True)
                await ctx.author.voice.channel.set_permissions(ctx.guild.default_role, connect=True)
                await interaction.response.send_message("✅ 頻道已設為公開！")

            @discord.ui.button(label="設為私密", style=discord.ButtonStyle.red)
            async def private_button(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("只有指令使用者才能操作此按鈕！", ephemeral=True)
                await ctx.author.voice.channel.set_permissions(ctx.guild.default_role, connect=False)
                await interaction.response.send_message("✅ 頻道已設為私密！")
        await ctx.send(embed=embed, view=ManageView(self.bot))

    @commands.command()
    async def set_admin(self, ctx, member: discord.Member):
        channel = ctx.author.voice.channel
        if not channel:
            return await ctx.send("哎呀！你必須先進入語音頻道才能使用這個指令喔~ ")
        
        self.voice_c.execute("SELECT owner_id, admin_id FROM voice_rooms WHERE channel_id = ?", (channel.id,))
        result = self.voice_c.fetchone()
        if not result or result[0] != ctx.author.id:
            return await ctx.send("抱歉！這個頻道不是你的小天地呢>_< ")
        if result[1]:
            return await ctx.send("這個頻道已經有管理員囉！")
            
        self.voice_c.execute("UPDATE voice_rooms SET admin_id = ? WHERE channel_id = ?", (member.id, channel.id))
        self.voice_conn.commit()
        await ctx.send(f"太好了！{member.mention} 現在成為這個頻道的管理員啦！✨")

    @commands.command()
    async def remove_admin(self, ctx, member: discord.Member):
        channel = ctx.author.voice.channel
        if channel and channel.id in self.voice_channels:
            if ctx.author.id == self.voice_channels[channel.id]['owner']:
                if member.id in self.voice_channels[channel.id]['admins']:
                    self.voice_channels[channel.id]['admins'].remove(member.id)
                    await channel.set_permissions(member, overwrite=None)
                    await ctx.send(f"{member.name} 已經被移除管理員身份。")
                else:
                    await ctx.send(f"{member.name} 不是此頻道的管理員。")
            else:
                await ctx.send("只有頻道擁有者可以移除管理員。")
        else:
            await ctx.send("你必須在語音頻道中才能使用此指令。")

    @commands.command()
    async def voice_info(self, ctx):
        info_channel = self.bot.get_channel(self.INFO_CHANNEL_ID)
        if ctx.channel.id != self.INFO_CHANNEL_ID:
            return await ctx.send(f"咦？要在 {info_channel.mention} 才能使用這個指令喔！")

        self.voice_c.execute("SELECT * FROM voice_rooms")
        rooms = self.voice_c.fetchall()
        
        embed = discord.Embed(title="✨語音頻道資訊✨", color=discord.Color.blue())
        for room in rooms:
            channel = ctx.guild.get_channel(room[0])
            if channel:
                owner = ctx.guild.get_member(room[1])
                admin = ctx.guild.get_member(room[2]) if room[2] else None
                members = len(channel.members)
                
                field_value = f"Owner: {owner.mention if owner else 'None'}\n"
                field_value += f"Admin: {admin.mention if admin else 'None'}\n"
                field_value += f"Members: {members}\n"
                field_value += f"Status: {room[4]}\n"
                field_value += f"Game: {room[5] or 'None'}"
                
                embed.add_field(name=channel.name, value=field_value, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command()
    async def save_settings(self, ctx):
        channel = ctx.author.voice.channel
        if not channel:
            return await ctx.send("你必須在語音頻道中才能使用此指令！")

        # 檢查是否為房主或副房主
        self.voice_c.execute("SELECT owner_id, admin_id FROM voice_rooms WHERE channel_id = ?", (channel.id,))
        result = self.voice_c.fetchone()
        if not result or (ctx.author.id != result[0] and ctx.author.id != result[1]):
            return await ctx.send("只有房主或副房主才能儲存頻道設定！")

        try:
            # 獲取當前頻道的權限設定
            overwrites = channel.overwrites
            settings = {
                'name': channel.name,
                'user_limit': channel.user_limit,
                'bitrate': channel.bitrate,
                'permissions': {
                    str(role.id): {
                        'allow': overwrite.pair()[0].value,
                        'deny': overwrite.pair()[1].value
                    }
                    for role, overwrite in overwrites.items()
                }
            }

            # 轉換為JSON格式儲存
            settings_json = json.dumps(settings)
            
            # 更新資料庫
            self.voice_c.execute("""
                UPDATE voice_rooms 
                SET settings = ?
                WHERE channel_id = ?
            """, (settings_json, channel.id))
            self.voice_conn.commit()

            await ctx.send("✅ 已成功儲存頻道設定！")
            self.voice_logger.info(f"語音頻道：{channel.id} 的相關設置已經被{ctx.author.id}儲存")

        except Exception as e:
            await ctx.send("❌ 儲存設定時發生錯誤！")
            self.voice_logger.error(f"Error saving channel settings: {e}")

async def setup(bot):
    await bot.add_cog(VoiceRoomManagement(bot))