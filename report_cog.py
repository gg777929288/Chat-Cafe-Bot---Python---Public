import discord
import os
import datetime
import asyncio
import hashlib
import sqlite3
from discord.ext import commands

class ReportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'Userfile/reports/reports.db'))
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute('''CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_number TEXT,
                reporter_id TEXT,
                reported_id TEXT,
                violation_type TEXT,
                violation_reason TEXT,
                channel TEXT,
                time TEXT,
                evidence TEXT,
                timestamp TEXT,
                hash TEXT
            )''')

    def generate_case_number(self):
        return f"CASE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    def hash_report(self, report_data):
        report_string = ''.join(report_data)
        return hashlib.sha256(report_string.encode('utf-8')).hexdigest()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        await self.bot.process_commands(message)

        if self.bot.user.mentioned_in(message) and "我要檢舉" in message.content:
            await message.delete()
            report_dir = "Userfile/reports"
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)

            # 檢查是否有提及其他用戶
            reported_user = None
            if message.mentions:
                # 排除機器人自己的mention
                mentions = [user for user in message.mentions if user != self.bot.user]
                if mentions:
                    reported_user = mentions[0]

            try:
                await message.author.send("您正在進行檢舉程序。所有對話內容及相關資訊將被記錄，請如實填寫。")
                violation_embed = discord.Embed(title="請選擇違規類型", description="請點選下方按鈕選擇違規類型")

                class ViolationView(discord.ui.View):
                    def __init__(self):
                        super().__init__()
                        self.value = None

                    @discord.ui.select(
                        placeholder="選擇違規類型",
                        options=[
                            discord.SelectOption(label="騷擾", value="harassment"),
                            discord.SelectOption(label="詐騙", value="scam"),
                            discord.SelectOption(label="謾罵", value="abuse"),
                            discord.SelectOption(label="盜帳號", value="account_theft"),
                            discord.SelectOption(label="色情", value="nsfw"),
                            discord.SelectOption(label="其他", value="other")
                        ]
                    )
                    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
                        """Handle the selection of violation type."""
                        try:
                            self.value = select.values[0]  # 使用 select.values 而不是 interaction.data
                            confirmation_embed = discord.Embed(
                                title="確認選擇",
                                description=(
                                    f"您選擇的違規類型是：{self.value}\n"
                                    "此選項選擇後無法更改，要繼續嗎？"
                                ),
                                color=discord.Color.orange()
                            )
                            confirmation_view = discord.ui.View(timeout=180)  # 添加超時設置

                            async def confirm_button_callback(interaction: discord.Interaction):
                                await interaction.response.edit_message(
                                    content="已確認，請繼續填寫檢舉內容。",
                                    embed=None,
                                    view=None
                                )
                                self.stop()

                            async def cancel_button_callback(interaction: discord.Interaction):
                                await interaction.response.edit_message(
                                    content="請重新選擇違規類型。",
                                    embed=None,
                                    view=None
                                )
                                self.value = None
                                self.stop()

                            confirm_button = discord.ui.Button(label="是", style=discord.ButtonStyle.green)
                            cancel_button = discord.ui.Button(label="否", style=discord.ButtonStyle.red)
                            
                            confirm_button.callback = confirm_button_callback
                            cancel_button.callback = cancel_button_callback
                            
                            confirmation_view.add_item(confirm_button)
                            confirmation_view.add_item(cancel_button)

                            await interaction.response.send_message(
                                embed=confirmation_embed, 
                                view=confirmation_view, 
                                ephemeral=True
                            )
                        except Exception as e:
                            await interaction.response.send_message(
                                content="選擇過程發生錯誤，請重試。", 
                                ephemeral=True
                            )

                view = ViolationView()
                await message.author.send(embed=violation_embed, view=view)
                await view.wait()
                violation_type = view.value

                if violation_type:
                    await message.author.send("請描述違規原因：")
                try:
                    response = await self.bot.wait_for(
                        'message',
                        timeout=300.0,
                        check=lambda m: m.author == message.author and m.channel == message.author.dm_channel
                    )
                    violation_reason = response.content
                except asyncio.TimeoutError:
                    await message.author.send("操作超時，請重新開始檢舉程序。")
                    return
                except Exception as e:
                    await message.author.send(f"發生錯誤：{str(e)}，請重新開始檢舉程序。")
                    return
                questions = [
                    "事發頻道（輸入頻道名稱或ID，若為私訊請輸入DM）：",
                    "事發時間（格式：YYYY/MM/DD HH:MM）：",
                ]

                # 根據是否有預設被檢舉人來決定是否需要詢問
                if reported_user:
                    confirm_msg = (f"被檢舉者：{reported_user.name}#{reported_user.discriminator} "
                                 f"(ID: {reported_user.id})\n是否正確？(是/否)")
                    await message.author.send(confirm_msg)
                    try:
                        response = await self.bot.wait_for(
                            'message',
                            timeout=300.0,
                            check=lambda m: m.author == message.author and m.channel == message.author.dm_channel
                        )
                        if response.content.lower() not in ['是', 'yes', 'y']:
                            # 如果說不是，則詢問正確的被檢舉者資訊
                            questions.extend([
                                "請輸入正確的被檢舉者Discord用戶名稱#Tag：",
                                "請輸入正確的被檢舉者Discord ID："
                            ])
                            reported_user = None
                    except asyncio.TimeoutError:
                        await message.author.send("操作超時，請重新開始檢舉程序。")
                        return
                else:
                    # 如果沒有預設被檢舉人，加入原有的問題
                    questions.extend([
                        "被檢舉者的Discord用戶名稱#Tag：",
                        "被檢舉者的Discord ID："
                    ])

                questions.append("是否有相關截圖證據？（有/無）如有，請直接傳送：")

                answers = [violation_reason]
                for question in questions:
                    await message.author.send(question)
                    if "截圖" in question:
                        try:
                            response = await self.bot.wait_for(
                                'message',
                                timeout=300.0,
                                check=lambda m: m.author == message.author and m.channel == message.author.dm_channel
                            )
                            if response.attachments:
                                answers.append([att.url for att in response.attachments])
                            else:
                                answers.append("無截圖提供")
                        except asyncio.TimeoutError:
                            await message.author.send("操作超時，請重新開始檢舉程序。")
                            return
                    else:
                        try:
                            response = await self.bot.wait_for(
                                'message',
                                timeout=300.0,
                                check=lambda m: m.author == message.author and m.channel == message.author.dm_channel
                            )
                            answers.append(response.content)
                        except asyncio.TimeoutError:
                            await message.author.send("操作超時，請重新開始檢舉程序。")
                            return

                # 如果有預設被檢舉人且確認正確，插入被檢舉人資訊
                if reported_user and len(answers) < 5:
                    answers.insert(2, f"{reported_user.name}#{reported_user.discriminator}")
                    answers.insert(3, str(reported_user.id))

                case_number = self.generate_case_number()
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                report_data = [
                    case_number,
                    str(message.author.id),
                    str(reported_user.id) if reported_user else "N/A",
                    violation_type,
                    answers[0],
                    answers[1],
                    answers[2],
                    ','.join(answers[5]) if answers[5] != "無截圖提供" else "無截圖提供",
                    timestamp
                ]
                report_hash = self.hash_report(report_data)
                report_data.append(report_hash)

                with self.conn:
                    self.conn.execute('''INSERT INTO reports (
                        case_number, reporter_id, reported_id, violation_type, violation_reason, channel, time, evidence, timestamp, hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', report_data)

                report_file = f"Userfile/reports/report_{case_number}.txt"
                with open(report_file, "w", encoding="utf-8") as f:
                    f.write(f"案件編號: {case_number}\n")
                    f.write(f"檢舉者資訊：\n")
                    f.write(f"ID: {message.author.id}\n")
                    f.write(f"名稱: {message.author.name}#{message.author.discriminator}\n")
                    f.write(f"建立時間: {message.author.created_at}\n")
                    f.write(f"\n違規類型: {violation_type}\n")
                    f.write(f"違規原因: {answers[0]}\n")
                    f.write(f"事發頻道: {answers[1]}\n")
                    f.write(f"事發時間: {answers[2]}\n")
                    f.write(f"被檢舉者名稱: {answers[3]}\n")
                    f.write(f"被檢舉者ID: {answers[4]}\n")
                    f.write(f"證據截圖: {answers[5]}\n")
                    f.write(f"報告哈希: {report_hash}\n")

                admin_channel = self.bot.get_channel(00000000000000000) #插入你的管理員頻道ID
                if admin_channel:
                    # Try to fetch the reported user
                    try:
                        reported_user = await self.bot.fetch_user(int(answers[4]))
                        reported_user_avatar = reported_user.avatar.url
                    except:
                        reported_user = None
                        reported_user_avatar = None

                    embed = discord.Embed(
                        title="新檢舉通知",
                        description=f"檢舉者: {message.author.mention}\n"
                                  f"違規類型: {violation_type}\n"
                                  f"被檢舉者: <@{answers[4]}>",
                        color=discord.Color.red()
                    )
                    embed.set_thumbnail(url=message.author.avatar.url)
                    
                    if reported_user_avatar:
                        embed.set_image(url=reported_user_avatar)

                    embed.add_field(name="檢舉者資訊", value=f"ID: {message.author.id}\n"
                                                        f"名稱: {message.author.name}#{message.author.discriminator}\n"
                                                        f"建立時間: {message.author.created_at}\n", inline=False)
                    embed.add_field(name="違規類型", value=violation_type, inline=False)  # 修改這裡
                    embed.add_field(name="違規內容", value=answers[0], inline=False)
                    embed.add_field(name="事發頻道", value=answers[1], inline=False)
                    embed.add_field(name="事發時間", value=answers[2], inline=False)
                    embed.add_field(name="被檢舉者名稱", value=answers[3], inline=False)
                    embed.add_field(name="被檢舉者ID", value=answers[4], inline=False)
                    embed.add_field(name="證據截圖", value="請查看附件", inline=False)

                    confirmation_view = discord.ui.View(timeout=180)

                    async def confirm_button_callback(interaction: discord.Interaction):
                        await interaction.response.send_message(
                            content=f"案件 {case_number} 已確認處理完畢。",
                            ephemeral=True
                        )
                        await admin_channel.send(
                            f"案件 {case_number} 已由 {interaction.user.mention} 確認處理完畢。"
                        )

                    confirm_button = discord.ui.Button(label="確認處理完畢", style=discord.ButtonStyle.green)
                    confirm_button.callback = confirm_button_callback
                    confirmation_view.add_item(confirm_button)

                    await admin_channel.send(embed=embed, view=confirmation_view)

                    if answers[5] != "無截圖提供":
                        for screenshot_url in answers[5]:
                            await admin_channel.send(screenshot_url)

                await message.author.send("感謝您的檢舉，管理員會盡快處理。您的檢舉資料已被保存，以作為未來處理依據。")
                await message.author.send("建議您至客服頻道與我們有更進一步的聯絡。")

            except discord.Forbidden:
                await message.channel.send(f"{message.author.mention} 無法發送私人訊息，請確保您已開啟私訊息權限。", delete_after=10)
                return

        if self.bot.user.mentioned_in(message) and "調閱" in message.content:
            if "檢舉紀錄" in message.content:
                if not message.author.guild_permissions.administrator:
                    await message.channel.send("只有管理員可以使用此功能。")
                    return
                user = message.mentions[1] if len(message.mentions) > 1 else None
                if user:
                    await self.檢舉紀錄(message.channel, user)
                else:
                    await message.channel.send("請提及要調閱檢舉紀錄的使用者。")
            elif "被檢舉紀錄" in message.content:
                if not message.author.guild_permissions.administrator:
                    await message.channel.send("只有管理員可以使用此功能。")
                    return
                user = message.mentions[1] if len(message.mentions) > 1 else None
                if user:
                    await self.被檢舉紀錄(message.channel, user)
                else:
                    await message.channel.send("請提及要調閱被檢舉紀錄的使用者。")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def 檢舉紀錄(self, ctx, user: discord.User):
        cursor = self.conn.execute('SELECT * FROM reports WHERE reporter_id = ?', (str(user.id),))
        records = cursor.fetchall()
        if records:
            for record in records:
                embed = discord.Embed(
                    title="檢舉紀錄",
                    description=f"案件編號: {record[1]}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="案件ID", value=record[0], inline=False)
                embed.add_field(name="檢舉者資訊", value=f"ID: {record[2]}\n名稱: {user.name}#{user.discriminator}\n檢舉建立時間: {record[9]}", inline=False)
                embed.add_field(name="違規類型", value=record[4], inline=False)
                embed.add_field(name="違規原因", value=record[5], inline=False)
                embed.add_field(name="事發頻道", value=record[6], inline=False)
                embed.add_field(name="事發時間", value=record[7], inline=False)
                embed.add_field(name="被檢舉者名稱", value=record[3], inline=False)
                embed.add_field(name="被檢舉者ID", value=record[3], inline=False)

                view = discord.ui.View()

                async def show_evidence_callback(interaction: discord.Interaction):
                    await interaction.response.send_message(f"證據截圖: {record[8]}", ephemeral=True)

                show_evidence_button = discord.ui.Button(label="顯示證據截圖", style=discord.ButtonStyle.primary)
                show_evidence_button.callback = show_evidence_callback
                view.add_item(show_evidence_button)

                await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(f"{user.mention} 沒有檢舉紀錄。")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def 被檢舉紀錄(self, ctx, user: discord.User):
        cursor = self.conn.execute('SELECT * FROM reports WHERE reported_id = ?', (str(user.id),))
        records = cursor.fetchall()
        if records:
            for record in records:
                embed = discord.Embed(
                    title="被檢舉紀錄",
                    description=f"案件編號: {record[1]}",
                    color=discord.Color.red()
                )
                embed.add_field(name="案件ID", value=record[0], inline=False)
                embed.add_field(name="違規類型", value=record[4], inline=False)
                embed.add_field(name="違規原因", value=record[5], inline=False)
                embed.add_field(name="事發頻道", value=record[6], inline=False)
                embed.add_field(name="事發時間", value=record[7], inline=False)
                reporter_user = await self.bot.fetch_user(int(record[2]))
                embed.add_field(name="檢舉者名稱", value=f"{reporter_user.name}#{reporter_user.discriminator}", inline=False)
                embed.add_field(name="被檢舉者ID", value=record[3], inline=False)

                view = discord.ui.View()

                async def show_evidence_callback(interaction: discord.Interaction):
                    await interaction.response.send_message(f"證據截圖: {record[8]}", ephemeral=True)

                show_evidence_button = discord.ui.Button(label="顯示證據截圖", style=discord.ButtonStyle.primary)
                show_evidence_button.callback = show_evidence_callback
                view.add_item(show_evidence_button)

                await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(f"{user.mention} 沒有被檢舉紀錄。")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def 檢舉案件(self, ctx, *, search: str = None):
        query = "SELECT * FROM reports"
        params = []

        if search:
            search_terms = search.split()
            conditions = []
            for term in search_terms:
                if term.startswith("檢舉人:"):
                    conditions.append("reporter_id = ?")
                    params.append(term.split(":", 1)[1])
                elif term.startswith("被檢舉人:"):
                    conditions.append("reported_id = ?")
                    params.append(term.split(":", 1)[1])
                elif term.startswith("管理員:"):
                    conditions.append("admin_id = ?")
                    params.append(term.split(":", 1)[1])
                elif term.startswith("違規類型:"):
                    conditions.append("violation_type = ?")
                    params.append(term.split(":", 1)[1])
                elif term.startswith("事發頻道:"):
                    conditions.append("channel = ?")
                    params.append(term.split(":", 1)[1])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += " LIMIT 50"
        cursor = self.conn.execute(query, params)
        records = cursor.fetchall()

        if records:
            embed = discord.Embed(
                title="檢舉案件列表",
                description="請點擊下方按鈕查看詳細資訊",
                color=discord.Color.green()
            )

            view = discord.ui.View()

            for record in records:
                button = discord.ui.Button(label=f"案件編號: {record[1]}", style=discord.ButtonStyle.primary)

                async def button_callback(interaction: discord.Interaction, record=record):
                    detail_embed = discord.Embed(
                        title="檢舉案件",
                        description=f"案件編號: {record[1]}",
                        color=discord.Color.green()
                    )
                    detail_embed.add_field(name="案件ID", value=record[0], inline=False)
                    detail_embed.add_field(name="檢舉者資訊", value=f"ID: {record[2]}\n名稱: {record[2]}\n檢舉建立時間: {record[9]}", inline=False)
                    detail_embed.add_field(name="違規類型", value=record[4], inline=False)
                    detail_embed.add_field(name="違規原因", value=record[5], inline=False)
                    detail_embed.add_field(name="事發頻道", value=record[6], inline=False)
                    detail_embed.add_field(name="事發時間", value=record[7], inline=False)
                    detail_embed.add_field(name="被檢舉者名稱", value=record[3], inline=False)
                    detail_embed.add_field(name="被檢舉者ID", value=record[3], inline=False)

                    detail_view = discord.ui.View()

                    async def show_evidence_callback(interaction: discord.Interaction):
                        await interaction.response.send_message(f"證據截圖: {record[8]}", ephemeral=True)

                    show_evidence_button = discord.ui.Button(label="顯示證據截圖", style=discord.ButtonStyle.primary)
                    show_evidence_button.callback = show_evidence_callback
                    detail_view.add_item(show_evidence_button)

                    await interaction.response.send_message(embed=detail_embed, view=detail_view, ephemeral=True)

                button.callback = button_callback
                view.add_item(button)

            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("沒有找到符合條件的檢舉案件。")

    @commands.command()
    async def help_report(self, ctx):
        help_text = (
            "**檢舉系統指令說明：**\n"
            "`!檢舉紀錄 @用戶` - 查詢指定用戶的檢舉紀錄。\n"
            "`!被檢舉紀錄 @用戶` - 查詢指定用戶的被檢舉紀錄。\n"
            "`!檢舉案件 [搜尋條件]` - 查詢符合條件的檢���案件。\n"
            "  - 搜尋條件格式：`檢舉人:<ID>` `被檢舉人:<ID>` `管理員:<ID>` `違規類型:<類型>` `事發頻道:<頻道>`\n"
            "  - 例如：`!檢舉案件 檢舉人:123456789 違規類型:騷擾`\n"
        )
        await ctx.send(help_text)

async def setup(bot):
    await bot.add_cog(ReportCog(bot))
