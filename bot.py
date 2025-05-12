#!/usr/bin/env python3
"""
link_bot.py  —  управляемые «ссылки» на чаты

• В Saved Messages (только владелец):
    #link  Название      – начать создание ссылки
                         → бот попросит отправить  ...  в целевом чате
    #list                – список ссылок (№, имя, chat_id)
    #del   №             – удалить ссылку
• Быстрый выбор: в нужном чате (от имени бота) написать  ...
  ─ если был активный #link – создаётся ссылка

• Любой юзер в DM:
    #list                – список (№, имя) без chat_id
    #<№>  текст          – бот публикует текст в связанном чате
"""

import os, json, re, logging
from pathlib import Path
from dotenv import load_dotenv
from pyrogram import Client, filters

# ─────────── 1. конфиг ───────────────────────────────────────────
load_dotenv()
API_ID, API_HASH = int(os.getenv("API_ID")), os.getenv("API_HASH")
PHONE            = os.getenv("PHONE")
SESSION          = os.getenv("LOGIN", "linkbot")

LINKS_FILE = Path("links.json")

CMD_LINK  = re.compile(r"#link\s+(.+)", re.I)
CMD_DEL   = re.compile(r"#del\s+(\d+)", re.I)
CMD_SEND  = re.compile(r"#(\d+)\s+(.+)", re.S)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("linkbot")

# ─────────── 2. загрузка/сохранение ссылок ──────────────────────
def load_links():
    if LINKS_FILE.exists():
        with LINKS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return []            # list[dict{id,name}]

def save_links(data):
    with LINKS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

links = load_links()       # в памяти

def add_link(chat_id: int, name: str):
    links.append({"id": chat_id, "name": name})
    save_links(links)

def delete_link(idx: int):
    if 0 <= idx < len(links):
        links.pop(idx)
        save_links(links)
        return True
    return False

# ─────────── 3. клиент ──────────────────────────────────────────
app = Client(SESSION, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE)

MY_ID: int | None       = None
pending_name: str | None = None    # ждём «...»

# ─────────── 4. фильтры ─────────────────────────────────────────
owner_saved = filters.private & filters.chat("me")
owner_out   = filters.me & ~filters.chat("me")      # исходящие в других чатах

# ─────────── 5. хендлер Saved Messages ──────────────────────────
@ app.on_message(owner_saved)
async def owner_commands(_, m):
    global pending_name
    if m.text:
        if m.text.lower().strip() == "#list":
            msg = "\n".join(f"{i+1}. {l['name']}  (ID {l['id']})"
                            for i, l in enumerate(links)) or "Пусто."
            return await m.reply(msg)

        if m.text.lower().startswith("#link"):
            mo = CMD_LINK.match(m.text)
            if not mo:
                return await m.reply("Формат: #link Название")
            pending_name = mo.group(1).strip()
            return await m.reply("Теперь перейдите в целевой чат и отправьте `...`.")

        if m.text.lower().startswith("#del"):
            mo = CMD_DEL.match(m.text)
            if not mo: return await m.reply("Формат: #del №")
            idx = int(mo.group(1)) - 1
            if delete_link(idx):
                await m.reply("✅ Удалено.")
            else:
                await m.reply("❌ Нет такого номера.")
            return

        await m.reply("Неизвестная команда. #help")

# ─────────── 6. ловим «...» для создания ссылки ─────────────────
@ app.on_message(owner_out)
async def catch_dots(_, m):
    global pending_name
    if pending_name and m.text and m.text.strip() == "...":
        add_link(m.chat.id, pending_name)
        await m.delete(revoke=True)           # убрать «...»
        await app.send_message("me", f"✅ Ссылка «{pending_name}» создана.")
        pending_name = None

# ─────────── 7. команды от других пользователей ─────────────────
@ app.on_message(filters.private & ~owner_saved)
async def user_panel(_, m):
    if not m.text: return

    if m.text.lower().strip() == "#list":
        txt = "\n".join(f"{i+1}. {l['name']}" for i, l in enumerate(links)) or "Пусто."
        return await m.reply(txt)

    mo = CMD_SEND.match(m.text)
    if mo:
        idx = int(mo.group(1)) - 1
        if 0 <= idx < len(links):
            chat_id = links[idx]["id"]
            text = mo.group(2).strip()
            try:
                await app.send_message(chat_id, text)
                await m.reply("✅ Отправлено.")
            except Exception as e:
                await m.reply(f"❌ Ошибка: {e}")
        else:
            await m.reply("❌ Нет такого номера.")
        return

# ─────────── 8. запуск ──────────────────────────────────────────
if __name__ == "__main__":
    print("Link-Bot running…  Ctrl-C to exit.")
    app.run()
