import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'已啟動 {bot.user} 的聊天服務')

@bot.tree.command(name='聊天', description='發送訊息到指定頻道')
@app_commands.describe(message_content='要發送的訊息內容')
async def chat(interaction: discord.Interaction, message_content: str):
    try:
        announcement_channel_id = 630009594760134676  # 替換為你的訊息頻道 ID
        channel = bot.get_channel(announcement_channel_id)

        if channel is None:
            await interaction.response.send_message('❌ 找不到指定的訊息頻道。')
            return

        # 發送訊息並回覆
        sent_message = await channel.send(message_content)
        await interaction.response.send_message('✅ 訊息已發送到指定頻道。')

    except Exception as e:
        await interaction.response.send_message(f'❌ 發生錯誤：{str(e)}')
async def setup(bot):
    await bot.add_cog(Chat(bot))
bot.run('123456789123456798 ')  # 替換為你的機器人 Token
