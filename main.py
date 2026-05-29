import os
import discord
from discord.ext import commands
from discord.ui import View, Select
from discord import app_commands
import asyncio

# 1. إعداد الـ Intents (ضروري جداً لتجنب الخطأ الذي واجهته)
intents = discord.Intents.default()
intents.message_content = True  # تفعيل قراءة الرسائل
intents.members = True          # تفعيل صلاحية الأعضاء

bot = commands.Bot(command_prefix="!", intents=intents)

# 2. كلاس القائمة المنسدلة (بدون descriptions كما طلبت)
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ]
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=options)

    async def callback(self, interaction: discord.Interaction):
        # إنشاء القناة
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        await interaction.response.send_message(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)
        await channel.send(f"أهلاً {interaction.user.mention}، لقد اخترت: **{self.values[0]}**. فريق الدعم سيصلك قريباً.")

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None) # يمنع توقف القائمة
        self.add_item(TicketSelect())

# 3. أمر فتح رسالة التذاكر
@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="تذكرة...",
        description="للطلب أو الاستفسار أو الدعم الفني نرجو منك فتح تذكرة عبر النظام المخصص.\n\nعند فتح التذكرة، يرجى توضيح جميع التفاصيل.",
        color=0x8B4513
    )
    await interaction.response.send_message(embed=embed, view=TicketView())

# 4. تشغيل البوت
@bot.event
async def on_ready():
    await bot.tree.sync() # مزامنة الأوامر
    print(f'البوت يعمل الآن: {bot.user}')

TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
