import discord
from discord.ext import commands, tasks

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'已啟動 {bot.user}的語音房服務')
    check_empty_channels.start()

@bot.event
async def on_voice_state_update(member, before, after):
    # 檢查用戶是否加入了特定語音頻道
    if after.channel and after.channel.id == 1283302523565903872:
        guild = member.guild
        category = discord.utils.get(guild.categories, id=1283302485603123231)
        # 創建新的語音頻道，並添加特定標記
        new_channel = await guild.create_voice_channel(f'{member.name}的語音頻道 [TEMP]', category=category)
        # 設置頻道權限
        await new_channel.set_permissions(member, connect=True, manage_channels=True)
        await new_channel.set_permissions(guild.default_role, connect=False)
        await member.move_to(new_channel)
        await new_channel.send(f'{member.mention}，你的語音頻道已創建！')

@tasks.loop(minutes=0.1)
async def check_empty_channels():
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            # 只刪除帶有特定標記的語音頻道
            if '[TEMP]' in channel.name and len(channel.members) == 0:
                await channel.delete()


bot.run('123456789123456798 ')
