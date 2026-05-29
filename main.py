import os
import discord
import chat_exporter
import asyncio
from discord.ext import commands
from discord.ui import View, Select

# إعداد الصلاحيات
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# المتغيرات الخاصة بك
LOG_CHANNEL_ID = 1508308536298311750 
OPEN_CHANNEL_ID = 1508308491788484648 
ticket_counter = 18 

class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="استفسار", value="inquiry"),
            discord.SelectOption(label="شراء منتج", value="purchase"),
        ]
        super().__init__(placeholder="أختر القائمة المناسبة لك", options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_counter
        channel_name = f"ticket-{interaction.user.name}-{ticket_counter}"
        
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        
        open_channel = interaction.guild.get_channel(OPEN_CHANNEL_ID)
        if open_channel:
            await open_channel.send(f"تم فتح تذكرة جديدة بواسطة {interaction.user.mention}: {channel.mention}")

        ticket_counter += 1
        await interaction.response.send_message(f"تم فتح تذكرتك: {channel.mention}", ephemeral=True)
        await channel.send(f"أهلاً {interaction.user.mention}، سيصلك الدعم قريباً.\nلإغلاق التذكرة اكتب: **!إغلاق**")

@bot.command(name="إغلاق")
async def close(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        return
    
    # تأكد من تغيير ID الرتبة هنا
    admin_role_id = 1508308453615996938 
    if not any(role.id == admin_role_id for role in ctx.author.roles):
        return await ctx.send("لا تملك صلاحية الإغلاق.")

    await ctx.send("يتم الآن حفظ السجل وإغلاق التذكرة...")
    transcript = await chat_exporter.export(ctx.channel)
    if transcript:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            file = discord.File(transcript, filename=f"{ctx.channel.name}.html")
            await log_channel.send(f"تم حفظ تذكرة: {ctx.channel.name}", file=file)
    await ctx.channel.delete()

@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    view = View(timeout=None)
    view.add_item(TicketSelect())
    
    # هنا تم تغيير اللون إلى الرصاصي (0x808080)
    embed = discord.Embed(
        title="نظام التذاكر", 
        description="للطلب أو الاستفسار، نرجو منك فتح تذكرة عبر النظام المخصص حتى يتمكن فريق العمل من خدمتك.", 
        color=0x808080
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'البوت جاهز: {bot.user}')

bot.run(os.environ.get('DISCORD_TOKEN'))
