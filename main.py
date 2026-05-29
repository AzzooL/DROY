import os
import discord
from discord.ext import commands
from discord.ui import View, Select
from discord import app_commands

# إعدادات البوت الأساسية
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- كلاس القائمة المنسدلة ---
class TicketSelect(Select):
    def __init__(self):
        # تم إزالة الـ description كما طلبت
        options = [
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ]
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=options)

    async def callback(self, interaction: discord.Interaction):
        # إنشاء التذكرة
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        await interaction.response.send_message(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)
        await channel.send(f"أهلاً {interaction.user.mention}، اخترت: **{self.values[0]}**. يرجى انتظار رد طاقم العمل.")

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None) # timeout=None يمنع تعطل الأزرار بعد فترة
        self.add_item(TicketSelect())

# --- الأمر ---
@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="نظام التذاكر",
        description="للطلب أو الاستفسار، يرجى فتح تذكرة عبر القائمة أدناه.",
        color=discord.Color.brown()
    )
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'البوت يعمل الآن: {bot.user}')

# تشغيل البوت
TOKEN = os.environ.get('DISCORD_TOKEN')
if TOKEN:
    bot.run(TOKEN)
else:
    print("خطأ: لم يتم العثور على التوكن في متغيرات البيئة!")