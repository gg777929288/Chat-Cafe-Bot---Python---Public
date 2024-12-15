import discord
from discord.ext import commands, tasks
import json
import os
import asyncio

class UpdateHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_file = 'Userfile/pending_updates.json'
        self.check_updates.start()
    
    def cog_unload(self):
        self.check_updates.cancel()
    
    @tasks.loop(seconds=2.0)
    async def check_updates(self):
        try:
            if not os.path.exists(self.update_file):
                return
                
            with open(self.update_file, 'r') as f:
                updates = json.load(f)
                
            # 清空更新文件
            with open(self.update_file, 'w') as f:
                json.dump({}, f)
            
            if not updates:
                return
                
            await self.process_update(updates)
                
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        except Exception as e:
            print(f"Error processing updates: {e}")
    
    async def process_update(self, update):
        if not self.bot.guilds:
            return
            
        guild = self.bot.guilds[0]
        update_type = update.get('type')
        
        try:
            if update_type == 'create_channel':
                data = update['channel_data']
                if data.get('type') == 'text':
                    await guild.create_text_channel(data['name'])
                elif data.get('type') == 'voice':
                    await guild.create_voice_channel(data['name'])
                    
            elif update_type == 'update_channel':
                channel = guild.get_channel(int(update['channel_id']))
                if channel:
                    await channel.edit(**update['updates'])
                    
            elif update_type == 'delete_channel':
                channel = guild.get_channel(int(update['channel_id']))
                if channel:
                    await channel.delete()
                    
            elif update_type == 'create_category':
                await guild.create_category(update['category_data']['name'])
                
            elif update_type == 'update_permissions':
                channel = guild.get_channel(int(update['channel_id']))
                if channel:
                    overwrite = discord.PermissionOverwrite()
                    for perm, value in update['permissions'].items():
                        setattr(overwrite, perm, value)
                    await channel.edit(overwrites=update['permissions'])
                    
            elif update_type == 'update_member_roles':
                member = guild.get_member(update['member_id'])
                if member:
                    # 獲取新的身分組列表
                    new_roles = [guild.get_role(role_id) for role_id in update['role_ids']]
                    # 過濾掉無效的身分組
                    new_roles = [role for role in new_roles if role is not None]
                    # 保留 @everyone 身分組
                    new_roles.append(guild.default_role)
                    # 更新成員的身分組
                    await member.edit(roles=new_roles)
                    
        except Exception as e:
            print(f"Error executing update {update_type}: {e}")
            # 將失敗的更新寫回文件
            with open(self.update_file, 'w') as f:
                json.dump({
                    'failed_update': update,
                    'error': str(e)
                }, f)

async def setup(bot):
    await bot.add_cog(UpdateHandlerCog(bot))