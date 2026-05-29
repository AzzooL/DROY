import os
import discord
import chat_exporter
from discord.ext import commands
from discord.ui import View, Select

# 1. إعدادات قوية جداً
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# المتغيرات (تأكد من صحتها)
LOG_CHANNEL_ID = 1508308536298311750
OPEN_CHANNEL_ID = 1508308491788484648

# دالة الترقيم الدائم
def get_next_number():
    if not os.path.exists("counter.txt"):
        with open("counter.txt", "w") as f: f.write("18")
    with open("counter.txt", "r") as f:
        num = int(f.read().strip())
    with open("counter.txt", "w") as f:
        f.write(str(num + 1))
    return num

# --- كلاس التذاكر ---
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # القائمة المنسدلة
        select = Select(placeholder="أختر القائمة المناسبة لك", custom_id="ticket_menu", options=[
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ])
        
        async def callback(interaction: discord.Interaction):
            # استخدام defer لعدم إظهار خطأ "فشل التفاعل"
            await interaction.response.defer(ephemeral=True)
            
            num = get_next_number()
            guild = interaction.guild
            
            # إنشاء القناة
            channel = await guild.create_text_channel(
                name=f"ticket-ipn-{num}",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
            )
            
            # إشعار قناة الفتح
            notify_channel = guild.get_channel(OPEN_CHANNEL_ID)
            if notify_channel:
                await notify_channel.send(f"تم فتح تذكرة: {channel.mention} بواسطة {interaction.user.mention}")

            await interaction.followup.send(f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True)
            await channel.send(f"👋 أهلاً {interaction.user.mention}، سيصلك الدعم قريباً.\nلإغلاق التذكرة اكتب: **!إغلاق**")

        select.callback = callback
        self.add_item(select)

# --- أوامر البوت ---

@bot.command(name="إغلاق")
async def close(ctx):
    # تحقق من أننا داخل تذكرة
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
        await ctx.send(f"⚠️ حدث خطأ: {e}")

@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title="نظام التذاكر", description="للطلب أو الاستفسار، افتح تذكرة عبر القائمة.", color=0x808080)
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.event
async def on_ready():
    bot.add_view(TicketView()) # تسجيل القائمة لتعمل دائماً
    await bot.tree.sync()
    print(f'✅ البوت يعمل!')

bot.run(os.environ.get('DISCORD_TOKEN'))
