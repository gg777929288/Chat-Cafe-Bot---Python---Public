# Discord Bot

這是一個使用 `discord.py` 庫製作的 Discord 機器人。該機器人可以加載位於 `./cogs` 目錄中的擴展（Cogs），並且在啟動時同步應用指令樹。

## 主要功能

- 使用 `discord.py` 庫來建立機器人。
- 支援指令前綴 `!`。
- 自動加載 `./cogs` 目錄中的所有擴展。
- 在啟動時同步應用指令樹。
- 每個檔案項目目前皆為獨立運行，main.py為集成Discord斜線指令功能之檔案，其餘為專用功能之檔案

## 代碼詳解

```python
import discord
from discord.ext import commands
import os

# 設置機器人的意圖
intents = discord.Intents.default()
intents.message_content = True

# 創建機器人實例
bot = commands.Bot(command_prefix='!', intents=intents)

# 當機器人準備就緒時執行的事件
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'已啟動 {bot.user} 的聊天服務')

# 加載所有的 Cogs
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')

# 運行機器人
bot.run('YOUR_BOT_TOKEN')
```

1.設置機器人的意圖:
```python
intents = discord.Intents.default()
intents.message_content = True
```
這段代碼設置了機器人的意圖，允許機器人讀取消息內容。

2.創建機器人實例:
```python
bot = commands.Bot(command_prefix='!', intents=intents)
```
這段代碼創建了一個機器人實例，並設置指令前綴為 !。

3.當機器人準備就緒時執行的事件:
```python
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'已啟動 {bot.user} 的聊天服務')
```
當機器人準備就緒時，這段代碼會同步應用指令樹並打印一條消息。

4.加載所有的 Cogs:
```python
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')
```
這段代碼會遍歷 ./cogs 目錄中的所有 .py 文件並加載它們作為擴展。

5.運行機器人:
```python
bot.run('YOUR_BOT_TOKEN')
```
這段代碼會運行機器人，並需要替換 'YOUR_BOT_TOKEN' 為你的實際機器人令牌。

# 如何運行？
1.安裝所需的庫(比如Discord.py，後續需要什麼功能可以自己再下載)：
```python
pip install discord.py
```
2.到Discord Developement Portal這個網站上取得你的機器人Token，b06c.4將你的機器人Token替換到所有檔案中的中的"YOUR_BOT_TOKEN"字樣。
3.確認完所有代碼後運行機器人
```python
python main.py
```
# 目錄結構
.
├── main.py(斜線指令檔案)
└── cogs
    ├── (功能檔案).py
    └── (功能檔案).py
# 授權
此項目有藉助於Copilot AI以及部分Github開源項目，使用 MIT 授權。詳情請參閱 LICENSE 文件。

希望這個 README 能夠幫助你更好地介紹和使用你的 Discord 機器人項目。
