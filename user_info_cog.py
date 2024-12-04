import discord
from discord.ext import commands

class UserInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    class UserInfoView(discord.ui.View):
        def __init__(self, user):
            super().__init__()
            self.user = user

        @discord.ui.button(label="查看共同伺服器", style=discord.ButtonStyle.primary)
        async def show_mutual_guilds(self, interaction: discord.Interaction, button: discord.ui.Button):
            mutual_guilds = [guild.name for guild in interaction.user.mutual_guilds]

            if not mutual_guilds:
                await interaction.response.send_message("沒有共同的伺服器", ephemeral=True)
                return

            embed = discord.Embed(title="共同伺服器", color=discord.Color.blue())
            embed.description = "\n".join(mutual_guilds)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="使用者")
    async def user_info(self, ctx):
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("此指令只能在文字頻道中使用！")
            return

        user = ctx.author
        embed = discord.Embed(title=f"{user.name}的個人資料", color=user.color)

        avatar_url = user.display_avatar.url if user.display_avatar else None
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="用戶ID", value=user.id, inline=True)
        embed.add_field(name="帳號建立時間", value=user.created_at.strftime("%Y/%m/%d"), inline=True)
        embed.add_field(name="伺服器加入時間", value=ctx.author.joined_at.strftime("%Y/%m/%d"), inline=True)

        status = str(getattr(user, 'status', '未知')).title()
        activity = "無動態"
        if hasattr(user, 'activities') and user.activities:
            activity = getattr(user.activities[0], 'name', "無動態")
        embed.add_field(name="目前狀態", value=status, inline=True)
        embed.add_field(name="目前動態", value=activity, inline=True)

        roles = [role.mention for role in user.roles[1:]]
        if roles:
            embed.add_field(name="身分組", value=" ".join(roles), inline=False)

        view = self.UserInfoView(user)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="搜尋使用者")
    async def search_user(self, ctx, *, username: str):
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("此指令只能在文字頻道中使用！")
            return

        members = [member for member in ctx.guild.members if username.lower() in member.name.lower()]

        if not members:
            await ctx.send("找不到符合條件的使用者。")
            return

        embed = discord.Embed(title="搜尋結果", color=discord.Color.green())
        for member in members:
            embed.add_field(name=member.name, value=f"ID: {member.id}", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UserInfoCog(bot))