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

    @discord.app_commands.command(name='創建帳號', description='創建一個新的機器人用戶帳號')
    async def create_account(self, interaction: discord.Interaction):
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        await interaction.response.send_message("請輸入帳號:", ephemeral=True)
        try:
            account_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            account = account_msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("超時，請重新開始。", ephemeral=True)
            return

        await interaction.followup.send("請輸入密碼:", ephemeral=True)
        try:
            password_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            password = password_msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("超時，請重新開始。", ephemeral=True)
            return

        await interaction.followup.send("請輸入電子郵件:", ephemeral=True)
        try:
            email_msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            email = email_msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("超時，請重新開始。", ephemeral=True)
            return

        hashed_pw = hash_password(password)
        try:
            c.execute("INSERT INTO users (account, email, password) VALUES (?, ?, ?)",
                      (account, email, hashed_pw))
            conn.commit()
            await interaction.followup.send("帳號創建成功！", ephemeral=True)
            logging.info("一個新帳號已被創建。")
        except sqlite3.IntegrityError:
            class RetryView(discord.ui.View):
                @discord.ui.button(label="重新嘗試", style=discord.ButtonStyle.primary, custom_id="retry_create_account")
                async def retry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.send_message("請重新開始帳號創建流程。", ephemeral=True)
                    await self.create_account(interaction)

            await interaction.followup.send("帳號或Email已存在。", view=RetryView(), ephemeral=True)
            logging.warning("帳號創建失敗：帳號或Email已存在。")

    @discord.app_commands.command(name='登入', description='登入到您的機器人用戶帳號')
    async def login(self, interaction: discord.Interaction, identifier: str, password: str):
        hashed_pw = hash_password(password)
        c.execute("SELECT account FROM users WHERE (account=? OR email=?) AND password=?", (identifier, identifier, hashed_pw))
        result = c.fetchone()
        
        if result:
            await interaction.response.send_message(f"歡迎，{result[0]}！登入成功。", ephemeral=True)
            logging.info(f"User logged in successfully: {result[0]}")
        else:
            await interaction.response.send_message("登入失敗。請檢查帳號和密碼。", ephemeral=True)
            logging.warning(f"Failed login attempt: {identifier}")

async def setup(bot):
    cog = AccountCog(bot)
    await bot.add_cog(cog)