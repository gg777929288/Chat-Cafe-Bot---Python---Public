import discord
from discord.ext import commands
import sqlite3
import hashlib
import asyncio
import logging

DATABASE = 'Userfile/userdata.db'
conn = sqlite3.connect(DATABASE)
c = conn.cursor()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class AccountCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='創建帳號')
    async def create_account(self, ctx):
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send("請輸入帳號:")
        try:
            account_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            account = account_msg.content
        except asyncio.TimeoutError:
            await ctx.send("超時，請重新開始。")
            return

        await ctx.send("請輸入密碼:")
        try:
            password_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            password = password_msg.content
        except asyncio.TimeoutError:
            await ctx.send("超時，請重新開始。")
            return

        await ctx.send("請輸入電子郵件:")
        try:
            email_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            email = email_msg.content
        except asyncio.TimeoutError:
            await ctx.send("超時，請重新開始。")
            return

        hashed_pw = hash_password(password)
        try:
            c.execute("INSERT INTO users (account, email, password) VALUES (?, ?, ?)",
                      (account, email, hashed_pw))
            conn.commit()
            await ctx.send("帳號創建成功！")
            logging.info("一個新帳號已被創建。")
        except sqlite3.IntegrityError:
            class RetryView(discord.ui.View):
                @discord.ui.button(label="重新嘗試", style=discord.ButtonStyle.primary, custom_id="retry_create_account")
                async def retry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.send_message("請重新開始帳號創建流程。", ephemeral=True)
                    await self.create_account(ctx)

            await ctx.send("帳號或Email已存在。", view=RetryView())
            logging.warning("帳號創建失敗：帳號或Email已存在。")

    @commands.command(name='登入')
    async def login(self, ctx, identifier: str = None, password: str = None):
        try:
            await ctx.message.delete()
        except:
            pass

        if not isinstance(ctx.channel, discord.DMChannel):
            remind_msg = await ctx.send("⚠️ 為了保護您的帳號安全，請使用私訊進行登入！訊息將在5秒後自動刪除...")
            await asyncio.sleep(5)
            await remind_msg.delete()
            return

        if not identifier or not password:
            await ctx.send("請提供帳號和密碼！用法: !登入 <帳號或電子郵件> <密碼>")
            return

        hashed_pw = hash_password(password)
        c.execute("SELECT account FROM users WHERE (account=? OR email=?) AND password=?", (identifier, identifier, hashed_pw))
        result = c.fetchone()
        
        if result:
            await ctx.send(f"歡迎，{result[0]}！登入成功。")
            logging.info(f"User logged in successfully via DM: {result[0]}")
        else:
            await ctx.send("登入失敗。請檢查帳號和密碼。")
            logging.warning(f"Failed login attempt via DM: {identifier}")

async def setup(bot):
    await bot.add_cog(AccountCog(bot))