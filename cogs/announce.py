import discord
from discord.ext import commands
from discord import app_commands
import setproctitle

setproctitle.setproctitle("Discord機器人公告")
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

announcement_channel_id = 123456789123456798   # 替換為你的公告頻道 ID

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'已啟動 {bot.user} 的公告服務')

@bot.tree.command(name="發送公告", description="發送公告到指定頻道")
@app_commands.describe(announcement="公告內容")
async def send_announcement(interaction: discord.Interaction, announcement: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    if not announcement:
        await interaction.response.send_message('❌ 請提供公告內容。', ephemeral=True)
        return

    channel = bot.get_channel(announcement_channel_id)
    if channel is None:
        await interaction.response.send_message('❌ 找不到指定的公告頻道。', ephemeral=True)
        return

    await channel.send(announcement)
    await interaction.response.send_message('✅ 公告已發送到指定頻道。', ephemeral=True)

bot.run('123456789123456798 ')  # 替換為你的機器人 Token
