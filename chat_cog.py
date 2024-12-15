"""Discord bot cog for chat-related commands and functionalities."""
import discord
from discord.ext import commands

class ChatCog(commands.Cog):
    """A cog for managing chat-related commands and functionalities."""
    
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name='聊天', description='發布內容到指定的文字頻道')
    @commands.has_permissions(administrator=True)
    async def announce(self, interaction: discord.Interaction, message: str, message_id: str = None):
        """Send an announcement to a specified channel, optionally replying to a specific message."""
        if not message:
            await interaction.response.send_message('請提供文字內容！使用方式：/聊天 <內容>', ephemeral=True)
            return

        announcement_channel = self.bot.get_channel(630009594760134676)
        if not announcement_channel:
            await interaction.response.send_message('找不到文字頻道！請確認頻道ID是否正確。', ephemeral=True)
            return

        webhook = await announcement_channel.create_webhook(name=interaction.user.name)
        
        try:
            embed = discord.Embed(
                title='注意看',
                description=message,
                color=discord.Color.blue()
            )
            if message_id:
                target_message = await announcement_channel.fetch_message(int(message_id))
                await webhook.send(
                    embed=embed,
                    username=interaction.user.name,
                    avatar_url=interaction.user.display_avatar.url,
                    reference=target_message
                )
            else:
                await webhook.send(
                    embed=embed,
                    username=interaction.user.name,
                    avatar_url=interaction.user.display_avatar.url
                )
            await webhook.delete()
            await interaction.response.send_message('訊息已發送！', ephemeral=True)
        except (discord.HTTPException, discord.NotFound) as e:
            await interaction.response.send_message(f'發生錯誤：{str(e)}', ephemeral=True)
        finally:
            await interaction.response.send_message('操作完成', ephemeral=True)

    

async def setup(bot):
    cog = ChatCog(bot)
    await bot.add_cog(cog)
