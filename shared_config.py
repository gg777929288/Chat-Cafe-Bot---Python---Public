import discord
from discord.ext import commands
from typing import Optional, Dict, Any
import asyncio
import json
import os
from flask import Flask
from datetime import datetime  # 添加這行
from config import Config

# 初始化共享變量
bot: Optional[commands.Bot] = None
app: Optional[Flask] = None
pending_updates: Dict[str, Any] = {}

# Initialize Flask app
app = Flask(__name__)

# Initialize Discord bot
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def init_bot(token: str) -> commands.Bot:
    global bot
    if bot is None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        
        bot = commands.Bot(command_prefix='!', intents=intents)
    return bot

def get_bot() -> Optional[commands.Bot]:
    return bot

def create_flask_app():
    global app
    if app is None:
        template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'web', 'templates'))
        static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'web', 'static'))
        app = Flask(__name__, 
                    template_folder=template_dir,
                    static_folder=static_dir)
    return app

def queue_update(update_data: Dict[str, Any]) -> None:
    """將更新請求寫入檔案"""
    update_file = os.path.join('Userfile', 'pending_updates.json')
    try:
        # 確保目錄存在
        os.makedirs(os.path.dirname(update_file), exist_ok=True)
        
        # 讀取現有更新
        existing_updates = []
        if os.path.exists(update_file):
            with open(update_file, 'r', encoding='utf-8') as f:
                existing_updates = json.load(f)
        
        # 添加新更新
        existing_updates.append(update_data)
        
        # 寫入更新
        with open(update_file, 'w', encoding='utf-8') as f:
            json.dump(existing_updates, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error queueing update: {e}")

async def broadcast_voice_update(channel_id: int, data: Dict[str, Any]) -> None:
    """廣播語音頻道更新"""
    update_data = {
        'type': 'voice_update',
        'channel_id': channel_id,
        'data': data,
        'timestamp': datetime.now().isoformat()
    }
    
    # 寫入更新檔案
    await queue_update(update_data)

def get_channel_cache(channel_id: str) -> Dict[str, Any]:
    """獲取頻道快取"""
    cache_path = os.path.join('Userfile', 'channel_cache.json')
    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                return cache.get(str(channel_id), {})
    except Exception as e:
        print(f"Error reading channel cache: {e}")
    return {}

# Create instances
bot = init_bot(Config.DISCORD_TOKEN)
app = create_flask_app()