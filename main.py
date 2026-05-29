import os
import discord
import asyncio
from discord.ext import commands
from discord.ui import View, Select

# إعداد الصلاحيات (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 1. كلاس زر الإغلاق (يظهر داخل التذكرة)
class CloseButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ضع ID رتبة الإدارة هنا
        admin_role_id = 1508308453615996938
        
        is_admin = any(role.id == admin_role_id for role in interaction.user.roles)
        if is_admin or interaction.user.id == interaction.channel.owner_id:
            await interaction.response.send_message("سيتم إغلاق القناة وحذفها بعد 5 ثوانٍ...")
            await asyncio.sleep(5)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("عذراً، لا تملك صلاحية الإغلاق.", ephemeral=True)

# 2. كلاس القائمة (التي تظهر في رسالة التذاكر)
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ]
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=options)

    async def callback(self, interaction: discord.Interaction):
        # إنشاء قناة التذكرة
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        
        # الرسالة الترحيبية داخل التذكرة
        embed = discord.Embed(
            title="نظام التذاكر",
            description=f"أهلاً {interaction.user.mention}، سيقوم فريق الدعم بمساعدتك بخصوص ({self.values[0]}) قريباً.\n\nللإغلاق اضغط على الزر أدناه.",
            color=discord.Color.green()
        )
        
        await channel.send(embed=embed, view=CloseButton())
        await interaction.response.send_message(f"تم فتح تذكرتك: {channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# 3. أمر فتح رسالة التذاكر (Slash Command)
@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    # اجعلها عامة ليراها الجميع، لكنها رسالة واحدة فقط
    embed = discord.Embed(
        title="تذكرة...",
        description="للطلب أو الاستفسار، نرجو منك فتح تذكرة عبر النظام المخصص حتى يتمكن فريق العمل من خدمتك.",
        color=0x8B4513
    )
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.event
async def on_ready():
    bot.add_view(CloseButton())
    bot.add_view(TicketView())
    await bot.tree.sync()
    print(f'البوت جاهز: {bot.user}')

bot.run(os.environ.get('DISCORD_TOKEN'))
