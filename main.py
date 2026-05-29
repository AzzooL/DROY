import os
import discord
import chat_exporter # تأكد من وجوده في requirements.txt
from discord.ext import commands
from discord.ui import View, Select

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# القنوات
LOG_CHANNEL_ID = 1508308536298311750
OPEN_CHANNEL_ID = 1508308491788484648

def get_next_number():
    if not os.path.exists("counter.txt"):
        with open("counter.txt", "w") as f: f.write("18")
    with open("counter.txt", "r") as f:
        num = int(f.read().strip())
    with open("counter.txt", "w") as f:
        f.write(str(num + 1))
    return num

class TicketSelect(Select):
    def __init__(self):
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=[
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ], custom_id="ticket_menu")

    async def callback(self, interaction: discord.Interaction):
        # رد فوري لمنع الخطأ
        await interaction.response.send_message("⏳ جاري إنشاء التذكرة...", ephemeral=True)
        
        try:
            num = get_next_number()
            channel = await interaction.guild.create_text_channel(
                name=f"ticket-ipn-{num}",
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
            )
            notify_channel = interaction.guild.get_channel(OPEN_CHANNEL_ID)
            if notify_channel:
                await notify_channel.send(f"تم فتح تذكرة جديدة: {channel.mention}")

            await interaction.edit_original_response(content=f"✅ تم فتح تذكرتك: {channel.mention}")
            await channel.send(f"أهلاً {interaction.user.mention}، سيصلك الدعم قريباً.\nلإغلاق التذكرة اكتب: **!إغلاق**")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ خطأ: {e}")

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.command(name="إغلاق")
async def close(ctx):
    if not ctx.channel.name.startswith("ticket-"): return
    await ctx.send("⏳ جاري الحفظ والإغلاق...")
    try:
        transcript = await chat_exporter.export(
