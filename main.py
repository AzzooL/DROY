import os
import discord
import chat_exporter
from discord.ext import commands
from discord.ui import View, Select

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# القنوات (تأكد من صحة الـ IDs)
LOG_CHANNEL_ID = 1508308536298311750
OPEN_CHANNEL_ID = 1508308491788484648

# دالة الترقيم الدائمة
def get_next_number():
    if not os.path.exists("counter.txt"):
        with open("counter.txt", "w") as f: f.write("18")
    with open("counter.txt", "r") as f:
        num = int(f.read().strip())
    with open("counter.txt", "w") as f:
        f.write(str(num + 1))
    return num

# القائمة (مع تحديد custom_id لضمان العمل)
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ]
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=options, custom_id="ticket_menu")

    async def callback(self, interaction: discord.Interaction):
        # استخدام defer لتجنب خطأ The application did not respond
        await interaction.response.defer(ephemeral=True)
        
        num = get_next_number()
        channel_name = f"ticket-ipn-{num}"
        
        try:
            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
            )
            
            notify_channel = interaction.guild.get_channel(OPEN_CHANNEL_ID)
            if notify_channel:
                await notify_channel.send(f"تم فتح تذكرة جديدة بواسطة {interaction.user.mention}: {channel.mention}")

            await interaction.followup.send(f"تم فتح تذكرتك: {channel.mention}", ephemeral=True)
            await channel.send(f"👋 أهلاً {interaction.user.mention}، سيصلك الدعم قريباً.\nلإغلاق التذكرة اكتب: **!إغلاق**")
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ أثناء إنشاء التذكرة: {e}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# الأمر النصي للإغلاق
@bot.command(name="إغلاق")
async def close(ctx):
    if not ctx.channel.name.startswith("ticket-"): return
    
    await ctx.send("⏳ جاري حفظ السجل وإغلاق التذكرة...")
    try:
        transcript = await chat_exporter.export(ctx.channel)
        if transcript:
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                file = discord.File(transcript, filename=f"{ctx.channel.name}.html")
                await log_channel.send(f"📄 سجل تذكرة: {ctx.channel.name}", file=file)
        await ctx.channel.delete()
    except Exception as e:
        await ctx.send(f"⚠️ حدث خطأ أثناء الإغلاق: {str(e)}")

@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title="نظام التذاكر", description="للطلب أو الاستفسار، افتح تذكرة عبر القائمة.", color=0x808080)
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    await bot.tree.sync()
    print(f'✅ البوت جاهز ويعمل كـ {bot.user}')

bot.run(os.environ.get('DISCORD_TOKEN'))
