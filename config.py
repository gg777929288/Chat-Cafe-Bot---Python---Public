import os
import secrets

class Config:
    # Discord Bot Token
    DISCORD_TOKEN = secrets.token_urlsafe(32)
    
    # 設定資料庫路徑
    DATABASE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Userfile',
        'users.db'
    )
    
    # Discord OAuth2 設定
    DISCORD_CLIENT_ID = secrets.token_hex(16)  # 隨機化 client ID
    DISCORD_CLIENT_SECRET = secrets.token_urlsafe(32)  # 隨機化 client secret
    DISCORD_REDIRECT_URI = 'http://localhost:5000/callback'
    
    # Discord Guild and Admin Role IDs
    GUILD_ID = secrets.token_hex(16)  # 隨機化伺服器 ID
    ADMIN_ROLE_IDS = [secrets.token_hex(16) for _ in range(3)]  # 隨機化管理員身分組 ID 列表
    
    # Flask session 設定
    SECRET_KEY = os.urandom(24)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # ...existing code...