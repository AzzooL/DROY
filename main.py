import os
import discord
import asyncio
from discord.ext import commands
from discord.ui import View, Select

# إعدادات البوت الأساسية
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# المتغيرات
LOG_CHANNEL_ID = 1508308536298311750
OPEN_CHANNEL_ID = 1508308491788484648

# دالة الترقيم (تنشئ ملف نصي لحفظ الرقم)
def get_next_number():
    if not os.path.exists("counter.txt"):
        with open("counter.txt", "w") as f: f.write("18")
        return 18
    with open("counter.txt", "r") as f:
        num = int(f.read().strip())
    with open("counter.txt", "w") as f:
        f.write(str(num + 1))
    return num

class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ]
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 1. نرد فوراً بـ defer لتجنب خطأ فشل التفاعل
        await interaction.response.defer(ephemeral=True)
        
        num = get_next_number()
        guild = interaction.guild
        channel_name = f"ticket-{interaction.user.name}-{num}"
        
        # 2. إنشاء القناة
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        
        # 3. إرسال إشعار في قناة الإشعارات
        notify_channel = guild.get_channel(OPEN_CHANNEL_ID)
        if notify_channel:
            await notify_channel.send(f"تم فتح تذكرة جديدة بواسطة {interaction.user.mention}: {channel.mention}")

        await interaction.followup.send(f"تم فتح تذكرتك: {channel.mention}", ephemeral=True)
        await channel.send(f"أهلاً {interaction.user.mention}، سيصلك الدعم قريباً.\nلإغلاق التذكرة اكتب: **!إغلاق**")

@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    view = View(timeout=None)
    view.add_item(TicketSelect())
    # اللون الرصاصي 0x808080
    embed = discord.Embed(title="نظام التذاكر", description="للطلب أو الاستفسار، افتح تذكرة عبر القائمة.", color=0x808080)
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'البوت جاهز: {bot.user}')

bot.run(os.environ.get('DISCORD_TOKEN'))
