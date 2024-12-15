import logging
import sys
import discord
from discord.ext import commands

class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        logging.error(f"Error in {event}: {sys.exc_info()}")
        if event in ['on_message', 'on_voice_state_update']:
            await self.bot.get_channel(834487721619357726).send(
                f"錯誤發生在 {event}！正在嘗試恢復..."
            )

    @commands.Cog.listener()
    async def on_disconnect(self):
        logging.warning("機器人已斷線! Attempting to reconnect...")
        try:
            await self.bot.login(os.getenv('YOUR_BOT_TOKEN')) # DC-TODO: Replace this with your bot token
        except Exception as e:
            logging.error("Failed to reconnect: %s", e)
            os.execv(sys.executable, ['python'] + sys.argv)

async def setup(bot):
    await bot.add_cog(ErrorHandlerCog(bot))