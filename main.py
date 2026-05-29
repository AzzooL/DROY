import discord
from discord.ext import commands
from discord import app_commands
import os
import base64
import json
import io
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def decode_token(encoded: str) -> str:
    """
    يقبل التوكن سواء كان plain text أو base64.
    توكنات Discord دائماً تحتوي نقطة (.) — نستخدمها للتمييز.
    """
    if not encoded:
        return encoded
    # لو فيه نقطة → توكن مباشر (plain text)
    if "." in encoded:
        return encoded
    # لو ما فيه نقطة → نجرب base64
    try:
        decoded = base64.b64decode(encoded.encode()).decode("utf-8")
        if "." in decoded:
            return decoded
    except Exception:
        pass
    return encoded


_raw_token            = os.getenv("TOKEN", "")
TOKEN                 = decode_token(_raw_token)
GUILD_ID              = int(os.getenv("GUILD_ID", 0))
LOG_CHANNEL_ID        = int(os.getenv("LOG_CHANNEL_ID", 0))
SUPPORT_ROLE_ID       = int(os.getenv("SUPPORT_ROLE_ID", 0))
TICKET_CATEGORY_ID    = int(os.getenv("TICKET_CATEGORY_ID", 0))   # احتياطي لو ما ضبطت الأنواع
INQUIRY_CATEGORY_ID   = int(os.getenv("INQUIRY_CATEGORY_ID", 0))  # كاتيغوري تذاكر الاستفسار
BUY_CATEGORY_ID       = int(os.getenv("BUY_CATEGORY_ID", 0))      # كاتيغوري تذاكر الشراء
ARCHIVE_CHANNEL_ID    = int(os.getenv("ARCHIVE_CHANNEL_ID", 0))   # قناة حفظ السجلات
BANNER_URL            = os.getenv("BANNER_URL", "")
STATS_FILE            = "stats.json"
BANNER_FILE           = os.path.join(os.path.dirname(__file__), "droy_banner.png")

intents = discord.Intents.default()
intents.members         = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── البيانات المستمرة ───────────────────────────────────────────────────────

def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total_opened": 0,
        "total_closed": 0,
        "ratings": [],
        "ticket_counter": 0,
        "open_tickets": {},
    }


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


# ─── إدارة open_tickets مع الحفظ الدائم ─────────────────────────────────────

def _load_open_tickets() -> dict:
    """يحمّل قاموس open_tickets من الملف (مفاتيحه int)."""
    data = load_stats()
    raw = data.get("open_tickets", {})
    return {int(k): int(v) for k, v in raw.items()}


def _save_open_tickets(tickets: dict):
    data = load_stats()
    data["open_tickets"] = {str(k): v for k, v in tickets.items()}
    save_stats(data)


# القاموس الحي في الذاكرة – يُزامَن مع الملف عند كل تغيير
open_tickets: dict[int, int] = {}


def ot_add(user_id: int, channel_id: int):
    open_tickets[user_id] = channel_id
    _save_open_tickets(open_tickets)


def ot_remove(user_id: int):
    open_tickets.pop(user_id, None)
    _save_open_tickets(open_tickets)


# ─── أنواع التذاكر ───────────────────────────────────────────────────────────
# (الاسم، الإيموجي، القيمة، الوصف، env_var_للكاتيغوري)

TICKET_TYPES = [
    ("استفسار",   "❓", "inquiry", "", "INQUIRY_CATEGORY_ID"),
    ("شراء منتج", "🛒", "buy",     "", "BUY_CATEGORY_ID"),
]

def get_category_id(ticket_value: str) -> int:
    """يرجع الـ category ID المناسب لنوع التذكرة."""
    mapping = {
        "inquiry": INQUIRY_CATEGORY_ID,
        "buy":     BUY_CATEGORY_ID,
    }
    return mapping.get(ticket_value, TICKET_CATEGORY_ID) or TICKET_CATEGORY_ID

# ─── لوج ────────────────────────────────────────────────────────────────────


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

# ─── ترانسكريبت ──────────────────────────────────────────────────────────────


async def generate_transcript(channel: discord.TextChannel) -> discord.File:
    lines = [f"=== سجل التذكرة: #{channel.name} ===\n"]
    async for msg in channel.history(limit=500, oldest_first=True):
        ts      = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        name    = msg.author.display_name
        content = msg.content or "[مرفق/embed]"
        lines.append(f"[{ts}] {name}: {content}")
    text = "\n".join(lines)
    buf  = io.BytesIO(text.encode("utf-8"))
    return discord.File(buf, filename=f"transcript-{channel.name}.txt")

# ─── View التقييم ────────────────────────────────────────────────────────────


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
    async def r1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rate(interaction, 1, "1")

    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary, custom_id="rate_2")
    async def r2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rate(interaction, 2, "2")

    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary, custom_id="rate_3")
    async def r3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rate(interaction, 3, "3")

    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary,   custom_id="rate_4")
    async def r4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rate(interaction, 4, "4")

    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success,   custom_id="rate_5")
    async def r5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rate(interaction, 5, "5")

# ─── منطق إغلاق التذكرة ──────────────────────────────────────────────────────


async def close_ticket_logic(
    channel: discord.TextChannel,
    guild: discord.Guild,
    closer: discord.Member,
):
    owner_id = next((uid for uid, cid in open_tickets.items() if cid == channel.id), None)
    owner    = guild.get_member(owner_id) if owner_id else None

    transcript = await generate_transcript(channel)

    # احذف من القاموس واحفظ
    ot_remove(owner_id)
    increment_stat("total_closed")

    # ─── أرسل للوج ──────────────────────────────────────────────────────────
    # نحتاج نسختين من الملف (Discord File لا يُعاد استخدامه)
    transcript2 = await generate_transcript(channel)

    await log_action(
        guild, "🔒 تذكرة مغلقة",
        owner or closer, channel,
        color=0xE74C3C,
        extra=f"أُغلقت بواسطة {closer.mention}",
        file=transcript,
    )

    # ─── أرسل السجل لقناة الأرشيف ───────────────────────────────────────────
    if ARCHIVE_CHANNEL_ID:
        archive_ch = guild.get_channel(ARCHIVE_CHANNEL_ID)
        if archive_ch:
            archive_embed = discord.Embed(
                title="📁 سجل تذكرة محفوظة",
                color=0x95A5A6,
            )
            archive_embed.add_field(
                name="التذكرة",
                value=channel.name,
                inline=True,
            )
            archive_embed.add_field(
                name="صاحب التذكرة",
                value=f"{owner.mention} ({owner.id})" if owner else "غير معروف",
                inline=True,
            )
            archive_embed.add_field(
                name="أُغلقت بواسطة",
                value=closer.mention,
                inline=True,
            )
            archive_embed.set_footer(
                text=f"Droy Store • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            await archive_ch.send(embed=archive_embed, file=transcript2)

    # ─── أرسل طلب التقييم بالـ DM ────────────────────────────────────────────
    if owner:
        try:
            rating_embed = discord.Embed(
                title="⭐ قيّم تجربتك مع الدعم",
                description=(
                    f"شكراً لتواصلك معنا في تذكرة **{channel.name}**\n"
                    "كيف كانت تجربتك مع فريق الدعم؟"
                ),
                color=0xF1C40F,
            )
            await owner.send(embed=rating_embed, view=RatingView(owner.id, channel.name))
        except discord.Forbidden:
            pass

    await channel.delete(reason=f"تذكرة مغلقة بواسطة {closer.display_name}")

# ─── Select إجراءات التذكرة ───────────────────────────────────────────────────


class TicketActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="إغلاق",
                description="من أجل قفل التذكرة الحالية.",
                emoji="🔒",
                value="close",
            ),
            discord.SelectOption(
                label="تنبيه صاحب التذكرة",
                description="من أجل إرسال إشعار للعضو.",
                emoji="🔔",
                value="notify",
            ),
            discord.SelectOption(
                label="إضافة شخص للتذكرة",
                description="من أجل إضافة عضو للتذكرة.",
                emoji="➕",
                value="add",
            ),
        ]
        super().__init__(
            placeholder="اختار الإجراء المناسب",
            min_values=1,
            max_values=1,
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
                await interaction.response.send_message(
                    "❌ ما عندك صلاحية تغلق هذا التيكت.", ephemeral=True
                )
                return
            await interaction.response.send_message("🔒 جاري إغلاق التذكرة وحفظ السجل...")
            await close_ticket_logic(channel, guild, user)

        elif value == "notify":
            if not is_support and not is_admin:
                await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)
                return
            owner = guild.get_member(owner_id) if owner_id else None
            if owner:
                await interaction.response.send_message(
                    f"🔔 {owner.mention} تم تنبيهك من قِبل الدعم في تذكرتك."
                )
            else:
                await interaction.response.send_message(
                    "❌ ما لقيت صاحب التذكرة.", ephemeral=True
                )

        elif value == "add":
            if not is_support and not is_admin:
                await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)
                return
            await interaction.response.send_message(
                "📝 منشن العضو اللي تبيه يُضاف للتذكرة (عندك 30 ثانية):",
                ephemeral=True,
            )

            def check(m):
                return m.author == user and m.channel == channel and m.mentions

            try:
                msg    = await bot.wait_for("message", check=check, timeout=30)
                member = msg.mentions[0]
                await channel.set_permissions(
                    member,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )
                await channel.send(f"✅ تم إضافة {member.mention} للتذكرة.")
                await msg.delete()
            except Exception:
                pass


class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketActionSelect())

# ─── Select نوع التذكرة ───────────────────────────────────────────────────────


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=name,
                description=desc if desc else None,
                emoji=emoji,
                value=value,
            )
            for name, emoji, value, desc, _ in TICKET_TYPES
        ]
        super().__init__(
            placeholder="اختار القائمة المناسبة لك  ˅",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select",
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user  = interaction.user

        # تحقق من وجود تذكرة مفتوحة
        if user.id in open_tickets:
            existing = guild.get_channel(open_tickets[user.id])
            if existing:
                await interaction.response.send_message(
                    f"❌ عندك تذكرة مفتوحة بالفعل: {existing.mention}", ephemeral=True
                )
                return
            else:
                # القناة اتحذفت يدوياً – نظّف الإدخال القديم
                ot_remove(user.id)

        ticket_type  = self.values[0]
        type_label   = next((n for n, e, v, d, _ in TICKET_TYPES if v == ticket_type), ticket_type)
        ticket_count = increment_stat("total_opened")

        # اختر الكاتيغوري المناسب لنوع التذكرة
        cat_id       = get_category_id(ticket_type)
        category     = guild.get_channel(cat_id) if cat_id else None
        support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

        channel = await guild.create_text_channel(
            name=f"تذكرة-{ticket_count:04d}-{user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"تذكرة #{ticket_count:04d} | {type_label} | {user.display_name} | ID: {user.id}",
        )

        # احفظ التذكرة المفتوحة بشكل دائم
        ot_add(user.id, channel.id)

        embed = discord.Embed(
            description=(
                "مرحباً بك في نظام تذاكر **Droy Store** 🛍️\n\n"
                "تم فتح تذكرتك بنجاح، يُرجى توضيح طلبك أو مشكلتك\n"
                "بأكبر قدر من التفاصيل حتى يتمكن فريقنا من مساعدتك\n"
                "بالشكل الأمثل وفي أسرع وقت ممكن.\n\n"
                "📎 يمكنك إرفاق صور أو ملفات لتوضيح طلبك.\n"
                "⏳ سيرد عليك فريق الدعم في أقرب وقت."
            ),
            color=0x95A5A6,
        )
        embed.set_author(name=f"تـذكـرة Droy Store ✦ #{ticket_count:04d}")
        embed.set_footer(text="Droy Store • نظام التذاكر")

        mention_text = user.mention
        if support_role:
            mention_text += f" {support_role.mention}"

        banner_file = discord.File(BANNER_FILE, filename="droy_banner.png") if os.path.exists(BANNER_FILE) else None
        if banner_file:
            embed.set_image(url="attachment://droy_banner.png")
        elif BANNER_URL:
            embed.set_image(url=BANNER_URL)
            banner_file = None

        await channel.send(content=mention_text, embed=embed, file=banner_file, view=TicketActionView())

        # ─── رسالة ترحيبية بالمنشن ──────────────────────────────────────────
        welcome_embed = discord.Embed(
            description=(
                f"أهلاً وسهلاً {user.mention} 👋\n\n"
                f"مرحباً بك في تذكرتك، نوع طلبك: **{type_label}**\n"
                "يُرجى شرح طلبك أو مشكلتك وسيرد عليك فريق الدعم في أقرب وقت 🕐"
            ),
            color=0x2ECC71,
        )
        welcome_embed.set_footer(text="Droy Store • نظام التذاكر")
        await channel.send(embed=welcome_embed)

        await interaction.response.send_message(
            f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True
        )
        await log_action(
            guild, f"🎫 تذكرة مفتوحة #{ticket_count:04d}",
            user, channel,
            color=0x2ECC71,
            extra=f"النوع: {type_label}",
        )


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

# ─── الأحداث ─────────────────────────────────────────────────────────────────


@bot.event
async def on_ready():
    # حمّل التذاكر المفتوحة المحفوظة
    global open_tickets
    open_tickets.update(_load_open_tickets())

    # سجّل الـ Views الدائمة حتى تعمل بعد إعادة التشغيل
    bot.add_view(TicketPanelView())
    bot.add_view(TicketActionView())

    await bot.tree.sync()
    print(f"✅ بوت التذاكر شغّال! تسجيل دخول كـ: {bot.user}")
    print(f"   تذاكر محفوظة مُسترجَعة: {len(open_tickets)}")

# ─── معالج أخطاء الـ Slash Commands ─────────────────────────────────────────


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ ما عندك صلاحية لتنفيذ هذا الأمر."
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = "❌ البوت ما عنده الصلاحيات الكافية لتنفيذ هذا الأمر."
    else:
        msg = f"❌ حدث خطأ: {error}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

# ─── الأوامر ─────────────────────────────────────────────────────────────────


@bot.tree.command(name="setup_ticket", description="⚙️ إعداد لوحة فتح التذاكر")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        description=(
            "مرحباً بك في نظام تذاكر **Droy Store** 🛍️\n\n"
            "للطلب أو الاستفسار أو الدعم الفني، يُرجى فتح تذكرة\n"
            "عبر النظام المخصص حتى يتمكن فريقنا من خدمتك\n"
            "بالشكل الأمثل وفي أسرع وقت ممكن.\n\n"
            "📎 يمكنك إرفاق صور أو ملفات لتوضيح طلبك.\n"
            "⏳ سيرد عليك فريق الدعم في أقرب وقت."
        ),
        color=0x95A5A6,
    )
    embed.set_author(name="تـذكـرة Droy Store ✦")
    embed.set_footer(text="Droy Store • نظام التذاكر")

    banner_file = discord.File(BANNER_FILE, filename="droy_banner.png") if os.path.exists(BANNER_FILE) else None
    if banner_file:
        embed.set_image(url="attachment://droy_banner.png")
    elif BANNER_URL:
        embed.set_image(url=BANNER_URL)
        banner_file = None

    await interaction.channel.send(embed=embed, file=banner_file, view=TicketPanelView())
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
        await interaction.response.send_message(
            "❌ ما عندك صلاحية تغلق هذه التذكرة.", ephemeral=True
        )
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
    embed.add_field(name="⭐ متوسط التقييم",   value=f"{avg}/5 {stars}",              inline=True)
    embed.add_field(name="📝 عدد التقييمات",   value=str(len(ratings)),               inline=True)
    embed.set_footer(text=f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    await interaction.response.send_message(embed=embed)


# ─── تشغيل البوت ─────────────────────────────────────────────────────────────

bot.run(TOKEN)
