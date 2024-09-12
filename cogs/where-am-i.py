import discord
from discord.ext import commands
from datetime import datetime

intents = discord.Intents.default()
intents.members = True  # 確保機器人有權限讀取成員信息
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'已啟動 {bot.user} 的群組資訊服務')

@bot.command(name='群組')
async def guild_info(ctx):
    guild = ctx.guild
    roles = guild.roles
    admin_role = None
    for role in roles:
        if role.permissions.administrator:
            admin_role = role
            break

    if admin_role:
        admins = [member for member in guild.members if admin_role in member.roles]
        admin_names = ', '.join([admin.display_name for admin in admins])
    else:
        admin_names = '無'

    embed = discord.Embed(title=f"{guild.name} 的資訊", color=0x00ff00)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="名稱", value=guild.name, inline=True)
    embed.add_field(name="建立日期", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="總人數", value=guild.member_count, inline=True)
    embed.add_field(name="活躍人數", value=len([member for member in guild.members if member.status != discord.Status.offline]), inline=True)
    embed.add_field(name="管理員身份組", value=admin_role.name if admin_role else '無', inline=True)
    embed.add_field(name="擁有管理員身份組的成員", value=admin_names, inline=True)

    await ctx.send(embed=embed)

bot.run('123456789123456798 ')  # TOKEN 在剛剛 Discord Developer 那邊「BOT」頁面裡面

