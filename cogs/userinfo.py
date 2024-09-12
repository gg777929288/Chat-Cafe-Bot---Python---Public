import discord
from discord.ext import commands
from discord import app_commands
import moment

class UserInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='userinfo', description='查詢用戶資訊')
    @app_commands.describe(member='要查詢的成員')
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member):
        roles = ', '.join([role.name for role in member.roles if role.name != "@everyone"])
        warningList = "無警告記錄"  # 這裡可以根據實際情況填寫警告記錄

        embed = discord.Embed(
            title=f"📇 身分證 - {member.display_name}",
            color=0x00AE86
        )
        embed.add_field(name='👤 用戶名', value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name='🆔 用戶ID', value=f"{member.id}", inline=True)
        embed.add_field(name='📅 加入日期', value=moment.date(member.joined_at).format('YYYY-MM-DD HH:mm:ss'), inline=True)
        embed.add_field(name='🔖 角色', value=roles, inline=True)
        embed.add_field(name='⚠️ 警告記錄', value=warningList, inline=False)
        embed.set_thumbnail(url=member.avatar.url)

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message('❌ 無法私訊用戶，身份證未能傳送。')

        idCardChannelId = 921543952631484517 # 替換為你的頻道ID
        idCardChannel = interaction.guild.get_channel(idCardChannelId)

        if not idCardChannel:
            await interaction.response.send_message('❌ 找不到身份證顯示頻道。')
            return

        await idCardChannel.send(embed=embed)
        await interaction.response.send_message('✅ 身份證已發送到指定頻道。')

async def setup(bot):
    await bot.add_cog(UserInfo(bot))
