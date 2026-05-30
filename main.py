"""
Droy Store — بوت تذاكر Discord
تشغيل: python main.py
متطلبات: discord.py>=2.3  python-dotenv (اختياري)
"""

import asyncio
import base64
import io
import json
import os
import re
from datetime import datetime

import discord
from discord.ext import commands

# ═══════════════════════════════════════════════════════════════════════════════
#  ██  ضع الـ IDs هنا  ██
# ═══════════════════════════════════════════════════════════════════════════════

GUILD_ID            = 1502777009087185056   # ID السيرفر
LOG_CHANNEL_ID      = 1510100222272077926   # قناة اللوج
ARCHIVE_CHANNEL_ID  = 1510100058320933054   # قناة الأرشيف
SUPPORT_ROLE_ID     = 1508308453615996938   # رول الدعم
INQUIRY_CATEGORY_ID = 1508308534381514834   # كاتيغوري الاستفسار ❓
BUY_CATEGORY_ID     = 1508308491788484648   # كاتيغوري الشراء 🛒

# ═══════════════════════════════════════════════════════════════════════════════

# توكن البوت (من ملف .env أو متغير البيئة)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _decode_token(encoded: str) -> str:
    if not encoded:
        return encoded
    if "." in encoded:
        return encoded
    try:
        decoded = base64.b64decode(encoded.encode()).decode("utf-8")
        if "." in decoded:
            return decoded
    except Exception:
        pass
    return encoded


TOKEN       = _decode_token(os.getenv("TOKEN", ""))
BANNER_URL  = os.getenv("BANNER_URL", "https://cdn.discordapp.com/attachments/1492835931688927342/1510101824445612142/vzzhwk6.png?ex=6a1b976b&is=6a1a45eb&hm=abc6f9ba0c6d9854c484eec7f38f36713552aeb4933c1e8caca184e3a02191bd&")

_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATS_FILE  = os.path.join(_BASE_DIR, "stats.json")
BANNER_FILE = os.path.join(_BASE_DIR, "droy_banner.png")

if not TOKEN:
    raise RuntimeError(
        "❌ متغير البيئة TOKEN غير موجود.\n"
        "أضفه في ملف .env بالصيغة:  TOKEN=توكن_البوت"
    )

# ─── البوت ───────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members         = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── أنواع التذاكر ───────────────────────────────────────────────────────────

# (الاسم، الإيموجي، value، description|None، category_id_var)
TICKET_TYPES: list[tuple[str, str, str, str | None, int]] = [
    ("استفسار",   "❓", "inquiry", None, INQUIRY_CATEGORY_ID),
    ("شراء منتج", "🛒", "buy",     None, BUY_CATEGORY_ID),
]


def get_category_id(ticket_value: str) -> int:
    return next((cat for _, _, v, _, cat in TICKET_TYPES if v == ticket_value), 0)


def sanitize_channel_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\u0600-\u06ff\-_]", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name[:32] or "user"

# ─── البيانات المستمرة ───────────────────────────────────────────────────────

_DEFAULTS: dict = {
    "total_opened":   0,
    "total_closed":   0,
    "ratings":        [],
    "ticket_counter": 0,
    "open_tickets":   {},
}


def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in _DEFAULTS.items():
                data.setdefault(k, v)
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def save_stats(data: dict) -> None:
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[WARN] تعذّر حفظ stats.json: {e}")


def increment_stat(key: str) -> int:
    data = load_stats()
    data[key] = data.get(key, 0) + 1
    save_stats(data)
    return data[key]


def add_rating(score: int) -> None:
    data = load_stats()
    data.setdefault("ratings", []).append(score)
    save_stats(data)

# ─── إدارة التذاكر المفتوحة ──────────────────────────────────────────────────

open_tickets: dict[int, int] = {}


def _load_open_tickets() -> dict[int, int]:
    raw = load_stats().get("open_tickets", {})
    result: dict[int, int] = {}
    for k, v in raw.items():
        try:
            result[int(k)] = int(v)
        except (ValueError, TypeError):
            pass
    return result


def _save_open_tickets(t: dict[int, int]) -> None:
    data = load_stats()
    data["open_tickets"] = {str(k): v for k, v in t.items()}
    save_stats(data)


def ot_add(user_id: int, channel_id: int) -> None:
    open_tickets[user_id] = channel_id
    _save_open_tickets(open_tickets)


def ot_remove(user_id: int | None) -> None:
    if user_id is None:
        return
    open_tickets.pop(user_id, None)
    _save_open_tickets(open_tickets)


def get_owner_id_for_channel(channel_id: int) -> int | None:
    owner_id = next((uid for uid, cid in open_tickets.items() if cid == channel_id), None)
    if owner_id is None:
        saved    = _load_open_tickets()
        owner_id = next((uid for uid, cid in saved.items() if cid == channel_id), None)
        if owner_id:
            open_tickets.update(saved)
    return owner_id


def user_has_open_ticket(user_id: int, guild: discord.Guild) -> discord.TextChannel | None:
    open_tickets.update(_load_open_tickets())
    channel_id = open_tickets.get(user_id)
    if channel_id is None:
        return None
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel
    ot_remove(user_id)
    return None

# ─── اللوج ───────────────────────────────────────────────────────────────────


async def log_action(
    guild:   discord.Guild,
    action:  str,
    user:    discord.Member,
    channel: discord.TextChannel | str,
    color:   int = 0x5865F2,
    extra:   str = "",
    file:    discord.File | None = None,
) -> None:
    if not LOG_CHANNEL_ID:
        return
    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    if not isinstance(log_ch, discord.TextChannel):
        return
    embed = discord.Embed(title=action, color=color)
    embed.add_field(name="العضو",  value=f"{user.mention} ({user.id})", inline=True)
    ch_val = channel.mention if isinstance(channel, discord.TextChannel) else str(channel)
    embed.add_field(name="القناة", value=ch_val, inline=True)
    if extra:
        embed.add_field(name="تفاصيل", value=extra, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    try:
        await log_ch.send(embed=embed, file=file)
    except discord.HTTPException as e:
        print(f"[WARN] تعذّر إرسال اللوج: {e}")

# ─── الترانسكريبت ─────────────────────────────────────────────────────────────


async def build_transcript_bytes(channel: discord.TextChannel) -> bytes:
    lines = [f"=== سجل التذكرة: #{channel.name} ===\n"]
    try:
        async for msg in channel.history(limit=500, oldest_first=True):
            ts      = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            name    = msg.author.display_name
            content = msg.content or "[مرفق/embed]"
            lines.append(f"[{ts}] {name}: {content}")
    except discord.HTTPException:
        lines.append("[تعذّر قراءة الرسائل]")
    return "\n".join(lines).encode("utf-8")


def make_transcript_file(raw: bytes, channel_name: str) -> discord.File:
    return discord.File(io.BytesIO(raw), filename=f"transcript-{channel_name}.txt")

# ─── View التقييم ────────────────────────────────────────────────────────────


class RatingView(discord.ui.View):
    def __init__(self, owner_id: int, ticket_name: str) -> None:
        super().__init__(timeout=600)
        self.owner_id    = owner_id
        self.ticket_name = ticket_name
        self.rated       = False

    async def _rate(self, interaction: discord.Interaction, score: int, label: str) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ هذا التقييم مو لك.", ephemeral=True)
            return
        if self.rated:
            await interaction.response.send_message("✅ لقد قيّمت مسبقاً.", ephemeral=True)
            return
        self.rated = True
        add_rating(score)
        for child in self.children:
            child.disabled = True  # type: ignore
        await interaction.response.edit_message(
            content=f"شكراً على تقييمك! أعطيت **{label}** ⭐",
            view=self,
        )

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.danger,    custom_id="rate_1")
    async def r1(self, i: discord.Interaction, b: discord.ui.Button) -> None:
        await self._rate(i, 1, "1")

    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary, custom_id="rate_2")
    async def r2(self, i: discord.Interaction, b: discord.ui.Button) -> None:
        await self._rate(i, 2, "2")

    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.secondary, custom_id="rate_3")
    async def r3(self, i: discord.Interaction, b: discord.ui.Button) -> None:
        await self._rate(i, 3, "3")

    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary,   custom_id="rate_4")
    async def r4(self, i: discord.Interaction, b: discord.ui.Button) -> None:
        await self._rate(i, 4, "4")

    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success,   custom_id="rate_5")
    async def r5(self, i: discord.Interaction, b: discord.ui.Button) -> None:
        await self._rate(i, 5, "5")

# ─── منطق إغلاق التذكرة ──────────────────────────────────────────────────────


async def close_ticket_logic(
    channel: discord.TextChannel,
    guild:   discord.Guild,
    closer:  discord.Member,
) -> None:
    owner_id = get_owner_id_for_channel(channel.id)
    owner    = guild.get_member(owner_id) if owner_id else None

    transcript_bytes = await build_transcript_bytes(channel)
    t_log     = make_transcript_file(transcript_bytes, channel.name)
    t_archive = make_transcript_file(transcript_bytes, channel.name)

    ot_remove(owner_id)
    increment_stat("total_closed")

    await log_action(
        guild, "🔒 تذكرة مغلقة",
        owner or closer, channel,
        color=0xE74C3C,
        extra=f"أُغلقت بواسطة {closer.mention}",
        file=t_log,
    )

    if ARCHIVE_CHANNEL_ID:
        archive_ch = guild.get_channel(ARCHIVE_CHANNEL_ID)
        if isinstance(archive_ch, discord.TextChannel):
            embed = discord.Embed(title="📁 سجل تذكرة محفوظة", color=0x95A5A6)
            embed.add_field(name="التذكرة",       value=channel.name,                                              inline=True)
            embed.add_field(name="صاحب التذكرة",  value=f"{owner.mention} ({owner.id})" if owner else "غير معروف", inline=True)
            embed.add_field(name="أُغلقت بواسطة", value=closer.mention,                                           inline=True)
            embed.set_footer(text=f"Droy Store • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            try:
                await archive_ch.send(embed=embed, file=t_archive)
            except discord.HTTPException as e:
                print(f"[WARN] تعذّر إرسال الأرشيف: {e}")

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
        except (discord.Forbidden, discord.HTTPException):
            pass

    try:
        await channel.delete(reason=f"تذكرة مغلقة بواسطة {closer.display_name}")
    except discord.NotFound:
        pass
    except discord.HTTPException as e:
        print(f"[WARN] تعذّر حذف القناة: {e}")

# ─── Select إجراءات التذكرة ───────────────────────────────────────────────────


class TicketActionSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="اختار الإجراء المناسب",
            min_values=1,
            max_values=1,
            custom_id="ticket_action_select",
            options=[
                discord.SelectOption(label="إغلاق",              description="قفل التذكرة وحفظ السجل.",        emoji="🔒", value="close"),
                discord.SelectOption(label="تنبيه صاحب التذكرة", description="إرسال إشعار للعضو في التذكرة.", emoji="🔔", value="notify"),
                discord.SelectOption(label="إضافة شخص للتذكرة", description="إضافة عضو إلى قناة التذكرة.",   emoji="➕", value="add"),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        value   = self.values[0]
        channel = interaction.channel
        guild   = interaction.guild
        user    = interaction.user

        if not isinstance(channel, discord.TextChannel) or guild is None:
            await interaction.response.send_message("❌ خطأ: هذا الأمر يعمل فقط داخل قنوات التذاكر.", ephemeral=True)
            return

        support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
        is_support   = bool(support_role and support_role in user.roles)
        is_admin     = user.guild_permissions.administrator
        owner_id     = get_owner_id_for_channel(channel.id)
        is_owner     = owner_id == user.id

        if value == "close":
            if not (is_owner or is_support or is_admin):
                await interaction.response.send_message("❌ ما عندك صلاحية تغلق هذا التيكت.", ephemeral=True)
                return
            await interaction.response.send_message("🔒 جاري إغلاق التذكرة وحفظ السجل...")
            await close_ticket_logic(channel, guild, user)

        elif value == "notify":
            if not (is_support or is_admin):
                await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)
                return
            owner = guild.get_member(owner_id) if owner_id else None
            if owner:
                await interaction.response.send_message(f"🔔 {owner.mention} تم تنبيهك من قِبل الدعم في تذكرتك.")
            else:
                await interaction.response.send_message("❌ ما لقيت صاحب التذكرة.", ephemeral=True)

        elif value == "add":
            if not (is_support or is_admin):
                await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)
                return
            await interaction.response.send_message(
                "📝 منشن العضو اللي تبيه يُضاف للتذكرة (عندك 30 ثانية):",
                ephemeral=True,
            )

            def check(m: discord.Message) -> bool:
                return m.author == user and m.channel == channel and bool(m.mentions)

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
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
            except asyncio.TimeoutError:
                pass


class TicketActionView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(TicketActionSelect())

# ─── Select نوع التذكرة ───────────────────────────────────────────────────────


class TicketTypeSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="اختار القائمة المناسبة لك  ˅",
            min_values=1,
            max_values=1,
            custom_id="ticket_type_select",
            options=[
                discord.SelectOption(label=name, description=desc, emoji=emoji, value=value)
                for name, emoji, value, desc, _ in TICKET_TYPES
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        user  = interaction.user

        if guild is None:
            await interaction.response.send_message("❌ هذا الأمر يعمل فقط داخل السيرفر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        existing = user_has_open_ticket(user.id, guild)
        if existing:
            await interaction.followup.send(
                f"❌ عندك تذكرة مفتوحة بالفعل: {existing.mention}", ephemeral=True
            )
            return

        ticket_type = self.values[0]
        type_label  = next((n for n, e, v, d, _ in TICKET_TYPES if v == ticket_type), ticket_type)

        increment_stat("total_opened")
        ticket_count = increment_stat("ticket_counter")

        cat_id   = get_category_id(ticket_type)
        category = guild.get_channel(cat_id) if cat_id else None
        if not isinstance(category, discord.CategoryChannel):
            category = None

        support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

        safe_name = sanitize_channel_name(user.name)
        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{ticket_count:04d}-{safe_name}",
                category=category,
                overwrites=overwrites,
                topic=f"تذكرة #{ticket_count:04d} | {type_label} | {user.display_name} | ID: {user.id}",
            )
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ تعذّر إنشاء قناة التذكرة: {e}", ephemeral=True)
            return

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

        banner_file: discord.File | None = None
        if os.path.exists(BANNER_FILE):
            banner_file = discord.File(BANNER_FILE, filename="droy_banner.png")
            embed.set_image(url="attachment://droy_banner.png")
        elif BANNER_URL:
            embed.set_image(url=BANNER_URL)

        await channel.send(content=mention_text, embed=embed, file=banner_file, view=TicketActionView())

        welcome = discord.Embed(
            description=(
                f"أهلاً وسهلاً {user.mention} 👋\n\n"
                f"مرحباً بك في تذكرتك، نوع طلبك: **{type_label}**\n"
                "يُرجى شرح طلبك أو مشكلتك وسيرد عليك فريق الدعم في أقرب وقت 🕐"
            ),
            color=0x2ECC71,
        )
        welcome.set_footer(text="Droy Store • نظام التذاكر")
        await channel.send(embed=welcome)

        await interaction.followup.send(f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True)
        await log_action(
            guild, f"🎫 تذكرة مفتوحة #{ticket_count:04d}",
            user, channel,
            color=0x2ECC71,
            extra=f"النوع: {type_label}",
        )


class TicketPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

# ─── الأحداث ─────────────────────────────────────────────────────────────────


@bot.event
async def on_ready() -> None:
    global open_tickets
    open_tickets.update(_load_open_tickets())

    bot.add_view(TicketPanelView())
    bot.add_view(TicketActionView())

    print(f"✅ بوت التذاكر شغّال! — {bot.user}")
    print(f"   تذاكر مُسترجَعة: {len(open_tickets)}")


# ─── معالج أخطاء الأوامر ─────────────────────────────────────────────────────

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ما عندك صلاحية لتنفيذ هذا الأمر.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ البوت ما عنده الصلاحيات الكافية.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ ناقص: `{error.param.name}`")
    elif not isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ خطأ: {error}")

# ─── الأوامر (prefix !) ───────────────────────────────────────────────────────


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx: commands.Context) -> None:
    """!setup — ينشر لوحة فتح التذاكر في القناة الحالية"""
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

    banner_file: discord.File | None = None
    if os.path.exists(BANNER_FILE):
        banner_file = discord.File(BANNER_FILE, filename="droy_banner.png")
        embed.set_image(url="attachment://droy_banner.png")
    elif BANNER_URL:
        embed.set_image(url=BANNER_URL)

    await ctx.send(embed=embed, file=banner_file, view=TicketPanelView())
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass


@bot.command(name="close")
async def close_cmd(ctx: commands.Context) -> None:
    """!close — يغلق التذكرة الحالية"""
    channel = ctx.channel
    guild   = ctx.guild
    user    = ctx.author

    if not isinstance(channel, discord.TextChannel) or guild is None:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل قنوات التذاكر.")
        return

    owner_id = get_owner_id_for_channel(channel.id)
    if owner_id is None:
        await ctx.send("❌ هذه القناة ليست تذكرة مفتوحة.")
        return

    support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
    is_support   = bool(support_role and support_role in user.roles)
    is_owner     = owner_id == user.id

    if not (is_owner or is_support or user.guild_permissions.administrator):
        await ctx.send("❌ ما عندك صلاحية تغلق هذه التذكرة.")
        return

    await ctx.send("🔒 جاري إغلاق التذكرة وحفظ السجل...")
    await close_ticket_logic(channel, guild, user)


@bot.command(name="stats")
@commands.has_permissions(administrator=True)
async def stats_cmd(ctx: commands.Context) -> None:
    """!stats — إحصائيات التذاكر"""
    data    = load_stats()
    ratings = data.get("ratings", [])
    avg     = round(sum(ratings) / len(ratings), 2) if ratings else 0
    stars   = "⭐" * round(avg) if avg else "لا يوجد"

    embed = discord.Embed(title="📊 إحصائيات التذاكر", color=0x5865F2)
    embed.add_field(name="🎫 إجمالي المفتوحة", value=str(data.get("total_opened",  0)), inline=True)
    embed.add_field(name="🔒 إجمالي المغلقة",  value=str(data.get("total_closed",  0)), inline=True)
    embed.add_field(name="📂 مفتوحة حالياً",   value=str(len(open_tickets)),            inline=True)
    embed.add_field(name="⭐ متوسط التقييم",   value=f"{avg}/5 {stars}",               inline=True)
    embed.add_field(name="📝 عدد التقييمات",   value=str(len(ratings)),                inline=True)
    embed.set_footer(text=f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    await ctx.send(embed=embed)

# ─── تشغيل البوت ─────────────────────────────────────────────────────────────

bot.run(TOKEN)
