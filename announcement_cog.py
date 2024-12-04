import discord
from discord.ext import commands

class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='公告')
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message=None):
        if not message:
            await ctx.send('請提供公告內容！使用方式：!公告 <內容>')
            return

        announcement_channel = self.bot.get_channel(1234567890)  #換成你的公告頻道ID
        if not announcement_channel:
            await ctx.send('找不到公告頻道！請確認頻道ID是否正確。')
            return

        embed = discord.Embed(
            title='📢 公告',
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f'由 {ctx.author.name} 發布')

        try:
            await announcement_channel.send(embed=embed)
            await ctx.send('公告已發布！')
        except Exception as e:
            await ctx.send(f'發生錯誤：{str(e)}')

async def setup(bot):
    await bot.add_cog(AnnouncementCog(bot))