import discord
from discord.ext import commands
from discord import app_commands
import os
import base64
import json
import io
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def decode_token(encoded: str) -> str:
    try:
        return base64.b64decode(encoded.encode()).decode()
    except Exception:
        return encoded

_raw_token          = os.getenv("TOKEN", "")
TOKEN               = decode_token(_raw_token)
GUILD_ID            = int(os.getenv("GUILD_ID", 0))
LOG_CHANNEL_ID      = int(os.getenv("LOG_CHANNEL_ID", 0))
SUPPORT_ROLE_ID     = int(os.getenv("SUPPORT_ROLE_ID", 0))
TICKET_CATEGORY_ID  = int(os.getenv("TICKET_CATEGORY_ID", 0))
BANNER_URL          = os.getenv("BANNER_URL", "")
STATS_FILE          = "stats.json"

intents = discord.Intents.default()
intents.members      = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

open_tickets: dict[int, int] = {}

TICKET_TYPES = [
    ("استفسار",   "❓", "inquiry", ""),
    ("شراء منتج", "🛒", "buy",     ""),
]


def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"total_opened": 0, "total_closed": 0, "ratings": [], "ticket_counter": 0}


def save_stats(data: dict):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def increment_stat(key: str):
    data = load_stats()
    data[key] = data.get(key, 0) + 1
    save_stats(data)
    return data[key]


def add_rating(score: int):
    data = load_stats()
    data.setdefault("ratings", []).append(score)
    save_stats(data)


async def log_action(
    guild: discord.Guild,
    action: str,
    user: discord.Member,
    channel,
    color: int = 0x5865F2,
    extra: str = "",
    file: discord.File = None,
):
    if not LOG_CHANNEL_ID:
        return
    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    if not log_ch:
        return
    embed = discord.Embed(title=action, color=color)
    embed.add_field(name="العضو",  value=f"{user.mention} ({user.id})", inline=True)
    ch_val = channel.mention if isinstance(channel, discord.TextChannel) else str(channel)
    embed.add_field(name="القناة", value=ch_val, inline=True)
    if extra:
        embed.add_field(name="تفاصيل", value=extra, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await log_ch.send(embed=embed, file=file)


async def generate_transcript(channel: discord.TextChannel) -> discord.File:
    lines = [f"=== سجل التذكرة: #{channel.name} ===\n"]
    async for msg in channel.history(limit=500, oldest_first=True):
        ts   = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        name = msg.author.display_name
        content = msg.content or "[مرفق/embed]"
        lines.append(f"[{ts}] {name}: {content}")
    text = "\n".join(lines)
    buf  = io.BytesIO(text.encode("utf-8"))
    return discord.File(buf, filename=f"transcript-{channel.name}.txt")


class RatingView(discord.ui.View):
    def __init__(self, owner_id: int, ticket_name: str):
        super().__init__(timeout=120)
        self.owner_id    = owner_id
        self.ticket_name = ticket_name

    async def _rate(self, interaction: discord.Interaction, score: int, label: str):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ هذا التقييم مو لك.", ephemeral=True)
            return
        add_rating(score)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"شكراً على تقييمك! أعطيت **{label}** ⭐",
            view=self,
        )

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.danger,   custom_id="rate_1")
    async def r1(self, i, b): await self._rate(i, 1, "1")

    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary, custom_id="rate_2")
    async def r2(self, i, b): await self._rate(i, 2, "2")

    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary, custom_id="rate_3")
    async def r3(self, i, b): await self._rate(i, 3, "3")

    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary,   custom_id="rate_4")
    async def r4(self, i, b): await self._rate(i, 4, "4")

    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success,   custom_id="rate_5")
    async def r5(self, i, b): await self._rate(i, 5, "5")


async def close_ticket_logic(
    channel: discord.TextChannel,
    guild: discord.Guild,
    closer: discord.Member,
):
    owner_id = next((uid for uid, cid in open_tickets.items() if cid == channel.id), None)
    owner    = guild.get_member(owner_id) if owner_id else None

    transcript = await generate_transcript(channel)

    open_tickets.pop(owner_id, None)
    increment_stat("total_closed")

    await log_action(
        guild, "🔒 تذكرة مغلقة",
        owner or closer, channel,
        color=0xE74C3C,
        extra=f"أُغلقت بواسطة {closer.mention}",
        file=transcript,
    )

    if owner:
        try:
            rating_embed = discord.Embed(
                title="⭐ قيّم تجربتك مع الدعم",
                description=f"شكراً لتواصلك معنا في تذكرة **{channel.name}**\nكيف كانت تجربتك مع فريق الدعم؟",
                color=0xF1C40F,
            )
            await owner.send(embed=rating_embed, view=RatingView(owner.id, channel.name))
        except discord.Forbidden:
            pass

    await channel.delete(reason=f"تذكرة مغلقة بواسطة {closer.display_name}")


class TicketActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="إغلاق",                description="من أجل قفل التذكرة الحالية.",   emoji="🔒", value="close"),
            discord.SelectOption(label="تنبيه صاحب التذكرة",  description="من أجل أرسال أشعار للعضو.",      emoji="🔔", value="notify"),
            discord.SelectOption(label="إضافة شخص للتذكرة",   description="من أجل إضافة عضو للتذكرة.",      emoji="➕", value="add"),
        ]
        super().__init__(
            placeholder="اختار الإجراء المناسب",
            min_values=1, max_values=1,
            options=options,
            custom_id="ticket_action_select",
        )

    async def callback(self, interaction: discord.Interaction):
        value   = self.values[0]
        channel = interaction.channel
        guild   = interaction.guild
        user    = interaction.user

        support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
        is_support   = support_role and support_role in user.roles
        owner_id     = next((uid for uid, cid in open_tickets.items() if cid == channel.id), None)
        is_owner     = owner_id == user.id
        is_admin     = user.guild_permissions.administrator

        if value == "close":
            if not is_owner and not is_support and not is_admin:
                await interaction.response.send_message("❌ ما عندك صلاحية تغلق هذا التيكت.", ephemeral=True)
                return
            await interaction.response.send_message("🔒 جاري إغلاق التذكرة وحفظ السجل...")
            await close_ticket_logic(channel, guild, user)

        elif value == "notify":
            if not is_support and not is_admin:
                await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)
                return
            owner = guild.get_member(owner_id) if owner_id else None
            if owner:
                await interaction.response.send_message(f"🔔 {owner.mention} تم تنبيهك من قِبل الدعم في تذكرتك.")
            else:
                await interaction.response.send_message("❌ ما لقيت صاحب التذكرة.", ephemeral=True)

        elif value == "add":
            if not is_support and not is_admin:
                await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)
                return
            await interaction.response.send_message("📝 منشن العضو اللي تبيه يُضاف للتذكرة (عندك 30 ثانية):", ephemeral=True)

            def check(m):
                return m.author == user and m.channel == channel and m.mentions

            try:
                msg    = await bot.wait_for("message", check=check, timeout=30)
                member = msg.mentions[0]
                await channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
                await channel.send(f"✅ تم إضافة {member.mention} للتذكرة.")
                await msg.delete()
            except Exception:
                pass


class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketActionSelect())


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, description=desc if desc else None, emoji=emoji, value=value)
            for name, emoji, value, desc in TICKET_TYPES
        ]
        super().__init__(
            placeholder="اختار القائمة المناسبة لك  ˅",
            min_values=1, max_values=1,
            options=options,
            custom_id="ticket_type_select",
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user  = interaction.user

        if user.id in open_tickets:
            existing = guild.get_channel(open_tickets[user.id])
            if existing:
                await interaction.response.send_message(f"❌ عندك تذكرة مفتوحة بالفعل: {existing.mention}", ephemeral=True)
                return

        ticket_type  = self.values[0]
        type_label   = next((n for n, e, v, d in TICKET_TYPES if v == ticket_type), ticket_type)
        ticket_count = increment_stat("total_opened")

        category     = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
        support_role = guild.get_role(SUPPORT_ROLE_ID)        if SUPPORT_ROLE_ID   else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user:               discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(
            name=f"تذكرة-{ticket_count:04d}-{user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"تذكرة #{ticket_count:04d} | {type_label} | {user.display_name} | ID: {user.id}",
        )

        open_tickets[user.id] = channel.id

        embed = discord.Embed(
            description=(
                "للطلب أو الاستفسار أو الدعم الفني\n"
                "نرجو منك فتح تذكرة عبر النظام المخصص حق يتمكن فريق\n"
                "العمل من خدمتك بالشكل الأفضل.\n\n"
                "عند فتح التذكرة، برجو توضيح جميع التفاصيل المتعلقة بطلبك\n"
                "أو مشكلتك، مع إضافة أي مرفقات أو معلومات قد تساعد فريق\n"
                "العمل على فهم الموضوع بشكل أدق."
            ),
            color=0x8B1A1A,
        )
        embed.set_author(name=f"تـذكـرة... #{ticket_count:04d}")
        if BANNER_URL:
            embed.set_image(url=BANNER_URL)

        mention_text = user.mention
        if support_role:
            mention_text += f" {support_role.mention}"

        await channel.send(content=mention_text, embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True)
        await log_action(guild, f"🎫 تذكرة مفتوحة #{ticket_count:04d}", user, channel,
                         color=0x2ECC71, extra=f"النوع: {type_label}")


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(TicketActionView())
    await bot.tree.sync()
    print(f"✅ بوت التذاكر شغّال! تسجيل دخول كـ: {bot.user}")


@bot.tree.command(name="setup_ticket", description="⚙️ إعداد لوحة فتح التذاكر")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        description=(
            "للطلب أو الاستفسار أو الدعم الفني\n"
            "نرجو منك فتح تذكرة عبر النظام المخصص حق يتمكن فريق\n"
            "العمل من خدمتك بالشكل الأفضل.\n\n"
            "عند فتح التذكرة، برجو توضيح جميع التفاصيل المتعلقة بطلبك\n"
            "أو مشكلتك، مع إضافة أي مرفقات أو معلومات قد تساعد فريق\n"
            "العمل على فهم الموضوع بشكل أدق."
        ),
        color=0x8B1A1A,
    )
    embed.set_author(name="تـذكـرة...")
    if BANNER_URL:
        embed.set_image(url=BANNER_URL)
    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ تم إعداد لوحة التذاكر!", ephemeral=True)


@bot.tree.command(name="close", description="🔒 إغلاق التذكرة الحالية")
async def close(interaction: discord.Interaction):
    channel = interaction.channel
    guild   = interaction.guild
    user    = interaction.user

    support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
    is_support   = support_role and support_role in user.roles
    owner_id     = next((uid for uid, cid in open_tickets.items() if cid == channel.id), None)
    is_owner     = owner_id == user.id

    if not is_owner and not is_support and not user.guild_permissions.administrator:
        await interaction.response.send_message("❌ ما عندك صلاحية تغلق هذه التذكرة.", ephemeral=True)
        return

    await interaction.response.send_message("🔒 جاري إغلاق التذكرة وحفظ السجل...")
    await close_ticket_logic(channel, guild, user)


@bot.tree.command(name="stats", description="📊 إحصائيات التذاكر")
@app_commands.checks.has_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    data    = load_stats()
    ratings = data.get("ratings", [])
    avg     = round(sum(ratings) / len(ratings), 2) if ratings else 0
    stars   = "⭐" * round(avg) if avg else "لا يوجد"

    embed = discord.Embed(title="📊 إحصائيات التذاكر", color=0x5865F2)
    embed.add_field(name="🎫 إجمالي المفتوحة", value=str(data.get("total_opened", 0)), inline=True)
    embed.add_field(name="🔒 إجمالي المغلقة",  value=str(data.get("total_closed", 0)), inline=True)
    embed.add_field(name="⭐ متوسط التقييم",   value=f"{avg}/5 {stars}", inline=True)
    embed.add_field(name="📝 عدد التقييمات",   value=str(len(ratings)), inline=True)
    embed.set_footer(text=f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    await interaction.response.send_message(embed=embed)


bot.run(TOKEN)
