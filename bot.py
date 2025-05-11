#!/usr/bin/env python3
"""
telegram_global_reposter_v2.py
──────────────────────────────
• В Saved Messages:
    /set /status /stop /help  — управление (см. /help)

• Супер-быстрый выбор:
    В нужном чате напишите  ...   ← три точки без пробелов
    Бот мгновенно запоминает этот чат и стирает «...».

• После выбора публикует каждое новое сообщение, которое видит
  (DM, группы, каналы), в целевом чате от вашего имени.
"""

import os, re, logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType

# ───── 1. конфигурация ──────────────────────────────────────────
load_dotenv()
API_ID, API_HASH = int(os.getenv("API_ID")), os.getenv("API_HASH")
PHONE            = os.getenv("PHONE")
SESSION          = os.getenv("LOGIN", "userbot")

CMD_PREFIX = "/"

# ───── 2. логи ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ───── 3. клиент ────────────────────────────────────────────────
app = Client(SESSION, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE)

MY_ID: int | None             = None
TARGET_CHAT_ID: int | None    = None
TARGET_CHAT_TITLE: str | None = None
CHAT_ID_RE = re.compile(r"chat\s*id\s*[:=]\s*(-?\d+)", re.I)

# ───── 4. утилиты ───────────────────────────────────────────────
async def me_id():
    global MY_ID
    if MY_ID is None:
        MY_ID = (await app.get_me()).id
    return MY_ID

def chat_name(entity):
    if getattr(entity, "title", None):
        return entity.title
    fn = getattr(entity, "first_name", "") or ""
    ln = getattr(entity, "last_name", "") or ""
    return (fn + " " + ln).strip() or "Без названия"

async def msg_me(txt: str):
    await app.send_message("me", txt)

async def resolve_peer(raw: str):
    if raw.startswith("@"): return await app.get_chat(raw)
    if raw.lstrip("-").isdigit(): return await app.get_chat(int(raw))
    return await app.get_chat(raw)

def set_target(cid: int | None, ttl: str | None):
    global TARGET_CHAT_ID, TARGET_CHAT_TITLE
    TARGET_CHAT_ID, TARGET_CHAT_TITLE = cid, ttl

# ───── 5. Saved Messages – команды ─────────────────────────────
saved_filter = filters.private & filters.chat("me")

@ app.on_message(saved_filter)
async def saved_commands(_, m):
    if m.text and m.text.startswith(CMD_PREFIX):
        cmd, *rest = m.text.lstrip(CMD_PREFIX).split(maxsplit=1)
        arg = rest[0] if rest else ""
        cmd = cmd.lower()

        if cmd == "help":
            return await msg_me(
                "/set  @chat | /set -100…  – выбрать чат\n"
                "/status – проверить\n"
                "/stop   – выключить\n"
                "Быстрый способ: в нужном чате отправьте  ...  (три точки)"
            )

        if cmd == "stop":
            set_target(None, None)
            return await msg_me("⏹ Копирование выключено.")

        if cmd == "status":
            txt = "Копирование: " + (f"→ «{TARGET_CHAT_TITLE}»" if TARGET_CHAT_ID else "выключено")
            return await msg_me(txt)

        if cmd == "set":
            if not arg:
                return await msg_me("Формат: /set @chat | /set -100…")
            try:
                chat = await resolve_peer(arg)
                set_target(chat.id, chat_name(chat))
                return await msg_me(f"✅ Чат «{TARGET_CHAT_TITLE}» выбран.")
            except Exception as e:
                return await msg_me(f"❌ Не удалось: {e}")

        return await msg_me("Неизвестная команда. /help")

    # пересланное сообщение → авто-выбор
    origin = m.forward_from_chat or m.forward_from or m.sender_chat
    if origin:
        set_target(origin.id, chat_name(origin))
        return await msg_me(f"✅ Чат «{TARGET_CHAT_TITLE}» выбран.")

    # chat id в тексте
    if m.text:
        mt = CHAT_ID_RE.search(m.text)
        if mt:
            cid = int(mt.group(1))
            set_target(cid, f"ID {cid}")
            return await msg_me(f"✅ Чат с ID {cid} выбран.")

    await msg_me("⚠️ Перешлите сообщение с открытым автором или /set @chat.")

# ───── 6. Быстрый выбор через «...», пишем от себя ──────────────
@ app.on_message(filters.me & ~saved_filter)
async def quick_select(_, m):
    """Если мы написали '...' в любом чате → выбрать его как цель."""
    if m.text and m.text.strip() == "...":
        set_target(m.chat.id, chat_name(m.chat))
        # удалить точки, чтобы не мешали диалогу
        try: await m.delete()
        except: pass
        await msg_me(f"✅ Чат «{TARGET_CHAT_TITLE}» выбран (быстрый способ).")

# ───── 7. Глобальное копирование ────────────────────────────────
@ app.on_message(filters.incoming & ~saved_filter)
async def global_copy(_, m):
    if TARGET_CHAT_ID is None or m.chat.id == TARGET_CHAT_ID:
        return
    # игнорируем сервисные и веб-превью
    if m.service or m.media == MessageMediaType.WEB_PAGE:
        return

    try:
        if m.media:
            await m.copy(TARGET_CHAT_ID)
        else:
            await app.send_message(TARGET_CHAT_ID, m.text, entities=m.entities)
    except Exception as e:
        log.error("Ошибка копирования: %s", e)
        await msg_me(f"❌ Ошибка копирования: {e}")

# ───── 8. старт ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting Telegram Global Reposter…  Ctrl-C to stop.")
    app.run()
