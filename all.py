import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

announcement_channel_id = 123456789123456798  # 替換為你的公告頻道 ID
notification_channel_id = 123456789123456798   # 替換為你的通知頻道 ID

warnings = {}

warnings_file = 'warnings.json'
def save_warnings():
    with open(warnings_file, 'w', encoding='utf-8') as f:
        json.dump(warnings, f, ensure_ascii=False, indent=4)

def load_warnings():
    global warnings
    if os.path.exists(warnings_file):
        with open(warnings_file, 'r', encoding='utf-8') as f:
            warnings = json.load(f)
    else:
        warnings = {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'已啟動 {bot.user} 的服務')

    # 設置機器人的狀態信息
    activity = discord.Game(name="管理伺服器")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # 顯示已加載的功能
    loaded_features = ['警告用號', '清除警告', '封鎖', '解除封鎖', '使用者卡片', '禁言', '解除禁言']
    for feature in loaded_features:
        print(f'已成功加載{feature}功能')

@bot.tree.command(name="警告用戶", description="給違規的使用者發送警告")
@app_commands.describe(member="要警告的用戶", reason="警告原因")
async def issue_warn(interaction: discord.Interaction, member: discord.Member, *, reason: str = '無原因'):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    admin_name = str(interaction.user)  # Fix: Use str(interaction.user) to get the username#discriminator

    if member.id not in warnings:
        warnings[member.id] = []
    warnings[member.id].append({'原因': reason, '時間': timestamp, '管理員姓名': admin_name})

    save_warnings()

    try:
        await member.send(f'⚠️ 你已被警告，原因是：{reason}')
    except Exception as e:
        await interaction.response.send_message(f'⚠️ 無法發送私信給 {member.mention}，但警告已記錄。', ephemeral=True)
        print(e)

    await interaction.response.send_message(f'⚠️ 已成功給 {member.mention} 發出警告。\n原因：{reason}\n時間：{timestamp}')

    notification_channel = bot.get_channel(notification_channel)
    if notification_channel:
        embed = discord.Embed(
            title='⚠️ **警告公告**',
            color=0xFF0000
        )
        embed.add_field(name='🔹 用戶', value=f'{member.name}#{member.discriminator}', inline=True)
        embed.add_field(name='🔹 原因', value=reason, inline=True)
        embed.add_field(name='🔹 發出警告時間', value=timestamp, inline=True)
        embed.add_field(name='🔹 管理員', value=admin_name, inline=True)
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text='此為自動通知，請遵守規則。')

        await notification_channel.send(embed=embed)

@bot.tree.command(name="清除警告", description="若你覺得該人有更正自己行為，可解除警告")
@app_commands.describe(member="要清除警告的用戶", warning_index="警告編號")
async def clear_warning(interaction: discord.Interaction, member: discord.Member, warning_index: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    if member.id not in warnings or len(warnings[member.id]) < warning_index:
        await interaction.response.send_message('❌ 用戶的該警告記錄不存在。', ephemeral=True)
        return

    removed_warning = warnings[member.id].pop(warning_index - 1)
    save_warnings()

    await interaction.response.send_message(f'⚠️ 已成功清除 {member.mention} 的警告記錄：\n原因：{removed_warning["原因"]}\n時間：{removed_warning["時間"]}')

    notification_channel = bot.get_channel(notification_channel_id)
    if notification_channel:
        embed = discord.Embed(
            title='🗑️ **清除警告公告**',
            color=0x00FF00
        )
        embed.add_field(name='🔹 用戶', value=f'{member.name}#{member.discriminator}', inline=True)
        embed.add_field(name='🔹 清除原因', value=removed_warning['原因'], inline=True)
        embed.add_field(name='🔹 清除時間', value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        embed.add_field(name='🔹 管理員', value=str(interaction.user), inline=True)
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text='此為自動通知。')

        await notification_channel.send(embed=embed)

@bot.tree.command(name="封鎖", description="封鎖指定用戶")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "無原因"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    bot_member = interaction.guild.me
    if not bot_member.guild_permissions.ban_members:
        await interaction.response.send_message('❌ 機器人沒有封鎖用戶的權限。', ephemeral=True)
        return

    if bot_member.top_role <= user.top_role:
        await interaction.response.send_message('❌ 機器人的角色層級低於或等於目標用戶，無法封鎖。', ephemeral=True)
        return

    try:
        await user.ban(reason=reason)
        await interaction.response.send_message(f'🔒 已封鎖 {user}。\n原因：{reason}')

        notification_channel = interaction.guild.get_channel(notification_channel_id)
        if notification_channel:
            embed = discord.Embed(title="🚫 **封鎖公告**", color=0xFF0000)
            embed.add_field(name='🔹 用戶', value=f'{user}', inline=True)
            embed.add_field(name='🔹 原因', value=f'{reason}', inline=True)
            embed.add_field(name='🔹 封鎖時間', value=f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', inline=True)
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text='此為自動通知，請遵守規則。')

            await notification_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message('❌ 機器人沒有足夠的權限來封鎖用戶。', ephemeral=True)
    except Exception as e:
        await interaction.response.send_message('❌ 封鎖用戶時發生錯誤。')
        print(e)

@bot.tree.command(name="解除封鎖", description="解除封鎖指定用戶")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    user = await bot.fetch_user(user_id)
    if user is None:
        await interaction.response.send_message('❌ 找不到該用戶。', ephemeral=True)
        return

    try:
        await interaction.guild.unban(user)
        await interaction.response.send_message(f'🔓 已解除封鎖 {user}。')

        notification_channel = interaction.guild.get_channel(notification_channel_id)
        if notification_channel:
            embed = discord.Embed(title="🔓 **解除封鎖公告**", color=0x00FF00)
            embed.add_field(name='🔹 用戶', value=f'{user}', inline=True)
            embed.add_field(name='🔹 解除封鎖時間', value=f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', inline=True)
            embed.set_thumbnail(url=user.avatar.url)
            embed.set_footer(text='此為自動通知，請遵守規則。')

            await notification_channel.send(embed=embed)
    except Exception as e:
        await interaction.response.send_message('❌ 解除封鎖用戶時發生錯誤。')
        print(e)

@bot.tree.command(name="使用者卡片", description="顯示你想查詢的人的資料")
@app_commands.describe(member="要顯示信息的用戶")
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    roles = ', '.join([role.name for role in member.roles if role.name != "@everyone"])
    warningList = warnings.get(member.id, [])

    embed = discord.Embed(
        title=f"📇 身分證 - {member.display_name}",
        color=0x00AE86
    )
    embed.add_field(name='👤 用戶名', value=f"{member.name}#{member.discriminator}", inline=True)
    embed.add_field(name='🆔 用戶ID', value=f"{member.id}", inline=True)
    embed.add_field(name='📅 加入日期', value=member.joined_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    embed.add_field(name='🔖 角色', value=roles, inline=True)
    embed.add_field(name='⚠️ 警告記錄', value=warningList if warningList else "無警告記錄", inline=False)
    embed.set_thumbnail(url=member.avatar.url)

    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        print('❌ 無法私訊用戶，身份證未能傳送。')

    idCardChannel = interaction.guild.get_channel(announcement_channel_id)
    if not idCardChannel:
        await interaction.response.send_message('❌ 找不到身份證顯示頻道。', ephemeral=True)
        return

    await idCardChannel.send(embed=embed)
    await interaction.response.send_message('✅ 身份證已發送到指定頻道。', ephemeral=True)

@bot.tree.command(name="禁言", description="禁言用戶")
@app_commands.describe(member="要禁言的用戶", mute_time="禁言時間（分鐘）", reason="禁言原因")
async def mute(interaction: discord.Interaction, member: discord.Member, mute_time: int = None, reason: str = '無原因'):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    if not member:
        await interaction.response.send_message('❌ 請指定要禁言的用戶。', ephemeral=True)
        return

    mute_duration = mute_time * 60 if mute_time else None
    try:
        await member.timeout(datetime.timedelta(seconds=mute_duration) if mute_duration else None, reason=reason)
        await interaction.response.send_message(f'🔇 已禁言 {member.mention}。\n原因：{reason}')

        notification_channel = bot.get_channel(int(notification_channel_id))
        if notification_channel:
            embed = discord.Embed(
                title='🔇 **禁言公告**',
                color=0xFFA500
            )
            embed.add_field(name='🔹 用戶', value=f'{member.name}#{member.discriminator}', inline=True)
            embed.add_field(name='🔹 原因', value=reason, inline=True)
            embed.add_field(name='🔹 禁言時間', value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            embed.add_field(name='🔹 禁言長度', value=f'{mute_time} 分鐘' if mute_time else '永久', inline=True)
            embed.set_thumbnail(url=member.avatar.url)
            embed.set_footer(text='此為自動通知，請遵守規則。')

            await notification_channel.send(embed=embed)
    except Exception as e:
        print(e)
        await interaction.response.send_message('❌ 禁言用戶時發生錯誤。', ephemeral=True)

@bot.tree.command(name="解除禁言", description="解除禁言")
@app_commands.describe(member="要解除禁言的用戶")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ 你沒有權限使用這個指令。', ephemeral=True)
        return

    if not member:
        await interaction.response.send_message('❌ 請指定要解除禁言的用戶。', ephemeral=True)
        return

    try:
        await member.timeout(None)
        await interaction.response.send_message(f'🔊 已解除 {member.mention} 的禁言。')

        notification_channel = bot.get_channel(int(notification_channel_id))
        if notification_channel:
            embed = discord.Embed(
                title='🔊 **解除禁言公告**',
                color=0x00FF00
            )
            embed.add_field(name='🔹 用戶', value=f'{member.name}#{member.discriminator}', inline=True)
            embed.add_field(name='🔹 解除時間', value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            embed.set_thumbnail(url=member.avatar.url)
            embed.set_footer(text='此為自動通知。')

            await notification_channel.send(embed=embed)
    except Exception as e:
        print(e)
        await interaction.response.send_message('❌ 解除禁言時發生錯誤。', ephemeral=True)

bot.run('123456789123456798 ')  # 替換為你的機器人 Token