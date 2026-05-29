import os
import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from discord import app_commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- كلاس زر الإغلاق ---
class CloseButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        # التحقق من الرتبة (استبدل '1234567890' بـ ID رتبة الإدارة الخاصة بك)
        admin_role_id = 1234567890 
        
        # التأكد أن المستخدم لديه رتبة الإدارة أو هو صاحب التذكرة
        if any(role.id == admin_role_id for role in interaction.user.roles) or interaction.user.id == interaction.channel.owner_id:
            await interaction.response.send_message("سيتم إغلاق القناة في غضون 5 ثوانٍ...")
            await asyncio.sleep(5)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("عذراً، ليس لديك صلاحية لإغلاق هذه التذكرة.", ephemeral=True)

# --- كلاس القائمة ---
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
        
        # رسالة ترحيبية تشبه التي أرسلتها
        embed = discord.Embed(
            title="نظام التذاكر",
            description=f"أهلاً {interaction.user.mention}، سيقوم فريق الدعم بمساعدتك قريباً.\n\nللإغلاق اضغط على الزر أدناه.",
            color=discord.Color.green()
        )
        
        await channel.send(embed=embed, view=CloseButton())
        await interaction.response.send_message(f"تم فتح تذكرتك: {channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# --- الأوامر ---
@bot.tree.command(name="ticket", description="إرسال رسالة التذاكر")
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title="تذكرة...", description="للطلب أو الاستفسار، افتح تذكرة عبر القائمة.", color=0x8B4513)
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.event
async def on_ready():
    # تسجيل الـ Views للعمل عند إعادة تشغيل البوت
    bot.add_view(CloseButton())
    bot.add_view(TicketView())
    await bot.tree.sync()
    print(f'البوت يعمل كـ {bot.user}')

bot.run(os.environ.get('DISCORD_TOKEN'))
