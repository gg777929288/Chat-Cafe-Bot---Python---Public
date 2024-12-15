import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name='指令', description='顯示所有可用的機器人指令')
    async def show_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="機器人指令列表", color=discord.Color.blue())
        embed.add_field(name="/公告 <內容>", value="發布公告到指定頻道。", inline=False)
        embed.add_field(name="/創建帳號", value="創建一個新的用戶帳號。", inline=False)
        embed.add_field(name="/登入 <帳號或電子郵件> <密碼>", value="登入到您的帳號。", inline=False)
        embed.add_field(name="/使用者", value="查看您的個人資料。", inline=False)
        embed.add_field(name="/搜尋使用者 <用戶名>", value="搜尋伺服器中的用戶。", inline=False)
        embed.add_field(name="/管理語音頻道", value="管理您當前的語音頻道。", inline=False)
        embed.add_field(name="/檢舉紀錄 @用戶", value="查詢指定用戶的檢舉紀錄。", inline=False)
        embed.add_field(name="/被檢舉紀錄 @用戶", value="查詢指定用戶的被檢舉紀錄。", inline=False)
        embed.add_field(name="/檢舉案件 [搜尋條件]", value="查詢符合條件的檢舉案件。", inline=False)
        embed.add_field(name="/指令", value="查看機器人的指令列表。", inline=False)
        embed.add_field(name="@機器人 我要檢舉 (可@該用戶)", value="檢舉其他人違規的行為。", inline=False)
        embed.add_field(name="/set_channel_name <名稱>", value="設置您當前語音頻道的名稱。", inline=False)
        embed.add_field(name="/set_channel_region <區域>", value="設置您當前語音頻道的區域。", inline=False)
        embed.add_field(name="/mute_user @用戶", value="將指定用戶靜音。", inline=False)
        embed.add_field(name="/deafen_user @用戶", value="將指定用戶禁聲。", inline=False)
        embed.add_field(name="/blacklist_user @用戶", value="將指定用戶列入黑名單。", inline=False)
        embed.add_field(name="/invite_manager @用戶", value="邀請指定用戶為管理員。", inline=False)
        embed.add_field(name="/start_bot", value="啟動機器人。", inline=False)
        embed.add_field(name="/stop_bot", value="停止機器人。", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    cog = HelpCog(bot)
    await bot.add_cog(cog)