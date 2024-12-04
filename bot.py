import sqlite3  # Import the sqlite3 module，用於連接SQLite數據庫，作為Discord機器人的用戶數據庫
import logging  # Import the logging module，用於記錄機器人的活動
import asyncio  # Ensure asyncio is imported
import sys  # Import the sys module，用於系統相關操作
import discord  # Import the discord module，用於創建Discord機器人
import os  # Import the os module，用於訪問環境變量
from discord.ext import commands  # Import the commands module from discord.ext

# Configuration

ANNOUNCEMENT_CHANNEL_ID = 834770383323791420  # Replace with your announcement channel ID
DATABASE = 'Userfile/userdata.db'
LOG_FILE = 'Userfile/bot.log'

# Initialize bot
intents = discord.Intents.default()    # Create a new intents object
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Load the cogs
async def load_cogs():
    await bot.load_extension('announcement_cog')
    await bot.load_extension('account_cog')
    await bot.load_extension('user_info_cog')
    await bot.load_extension('voice_room_management')
    await bot.load_extension('report_cog')
    await bot.load_extension('error_handler_cog')
    await bot.load_extension('help_cog')  # Add this line to load the new help cog

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')
print("機器人啟動中...") #若代碼成功啟動，顯示機器人正在啟動

#載入資料庫
conn = sqlite3.connect(DATABASE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
             id INTEGER PRIMARY KEY AUTOINCREMENT, 
             account TEXT UNIQUE,
             email TEXT UNIQUE,
             password TEXT
             )''') #創建用戶SQL數據庫
conn.commit()

@bot.event
async def on_ready():
    print(f'{bot.user} 已經上線！')
    await load_cogs()
    await bot.change_presence(activity=discord.Game(name="輸入 !指令 可以查詢本機器人的指令喔！"))
    print("機器人已成功加載！") #若機器人成功加載，顯示機器人已成功加載

def auto_restart(func):
    """Decorator to automatically restart a function if it fails.""" 
    max_retries = 3
    retry_count = 0
    async def wrapper(*args, **kwargs):
        """Wrapper function to retry the decorated function.""" 
        nonlocal retry_count
        try:
            return await func(*args, **kwargs)
        except Exception:
            retry_count += 1
            if retry_count >= max_retries:
                logging.critical("Function %s failed after %d retries", func.__name__, max_retries)
                return
            await asyncio.sleep(5)  # Wait before retrying
            return await wrapper(*args, **kwargs)
    return wrapper




bot.run('你的Discord機器人Token')  # 這裡換成你的機器人Token