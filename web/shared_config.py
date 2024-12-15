
from flask import Flask
import secrets

# Global variables
bot = None
app = None

def create_flask_app():
    global app
    if not app:
        app = Flask(__name__)
        # 生成一個固定的 secret key
        app.secret_key = secrets.token_hex(16)  # 建議使用更安全的密鑰
        # 或者使用隨機生成的密鑰（但每次重啟服務會導致所有 session 失效）
        # app.secret_key = secrets.token_hex(16)
    return app

def get_bot():
    global bot
    return bot

def init_bot(discord_bot):
    global bot
    bot = discord_bot

# Queue for updates
update_queue = []

def queue_update(update):
    update_queue.append(update)