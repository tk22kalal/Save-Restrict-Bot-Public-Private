import logging
import time
import os
import sys
import asyncio
import json
import pymongo
import zipfile
import requests
import shutil
import re

from .. import bot as gagan
from .. import userbot, Bot, AUTH, SUDO_USERS, API_ID, API_HASH

from main.plugins.pyroplug import check, get_bulk_msg
from main.plugins.helpers import get_link, screenshot

from telethon import events, Button, errors
from telethon.tl.types import DocumentAttributeVideo

from pyrogram import Client
from pyrogram.errors import FloodWait


def get_user_session(user_id):
    """Read per-user session string from JSON file (no cross-plugin import needed)."""
    if os.path.exists("user_sessions.json"):
        try:
            with open("user_sessions.json", "r") as _f:
                return json.load(_f).get(str(user_id))
        except Exception:
            return None
    return None

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)

def save_batch_data(batch_data):
    with open("batch_data.json", "w") as f:
        json.dump(batch_data, f)

def load_batch_data():
    if os.path.exists("batch_data.json"):
        with open("batch_data.json", "r") as f:
            return json.load(f)
    else:
        return {}

batch_data = load_batch_data()

def save_ids_data(ids_data):
    with open("ids_data.json", "w") as f:
        json.dump(ids_data, f)

def load_ids_data():
    if os.path.exists("ids_data.json"):
        with open("ids_data.json", "r") as f:
            return json.load(f)
    else:
        return {}

ids_data = load_ids_data()

# active_batches: user_id -> True means cancelled, False means running
active_batches = {}


# ── Supergroup topic helpers ────────────────────────────────────────────────────

def _parse_supergroup_link(link: str):
    """
    Parse a supergroup topic link with an optional start-end range:
        https://t.me/c/CHATID/TOPICID/STARTMSG
        https://t.me/c/CHATID/TOPICID/STARTMSG-ENDMSG

    Returns (chat_id_with_minus100, topic_id, start_msg, end_msg) or None.
    end_msg == start_msg when no range is given.
    """
    # Must have at least CHATID/TOPICID/MSGID  (7 parts when split by '/')
    # Typical: https://t.me/c/3281835444/9212/9507  or .../9507-9550
    if "t.me/c/" not in link:
        return None

    clean = link.rstrip("/")
    parts = clean.split("/")
    # parts: ['https:', '', 't.me', 'c', 'CHATID', 'TOPICID', 'MSGPART']
    if len(parts) < 7:
        return None

    try:
        chat_id = int("-100" + parts[4])
        topic_id = int(parts[5])
        msg_part = parts[6].replace("?single", "")

        if "-" in msg_part:
            segments = msg_part.split("-", 1)
            start_msg = int(segments[0])
            end_msg = int(segments[1])
        else:
            start_msg = int(msg_part)
            end_msg = start_msg

        return chat_id, topic_id, start_msg, end_msg
    except (ValueError, IndexError):
        return None


def _is_in_topic(msg, topic_id: int) -> bool:
    """
    Return True if a Pyrogram message belongs to a specific supergroup topic.
    """
    if msg is None or getattr(msg, "empty", False):
        return False
    if msg.id == topic_id:
        return True
    top = getattr(msg, "reply_to_top_message_id", None)
    if top == topic_id:
        return True
    rep = getattr(msg, "reply_to_message_id", None)
    if rep == topic_id and top is None:
        return True
    return False


# ── /cancel ─────────────────────────────────────────────────────────────────────

@gagan.on(events.NewMessage(incoming=True, pattern='/cancel'))
async def cancel_command(event):
    user_id = event.sender_id
    cancelled = False

    # Cancel supergroup active batch
    if active_batches.get(user_id) is False:
        active_batches[user_id] = True
        cancelled = True

    # Cancel classic batch
    if str(user_id) in ids_data:
        del ids_data[str(user_id)]
        save_ids_data(ids_data)
        if str(user_id) in batch_data:
            del batch_data[str(user_id)]
            save_batch_data(batch_data)
        cancelled = True

    if cancelled:
        await event.respond("✅ Operation cancelled.")
    else:
        await event.respond("There is no operation to cancel.")


# ── Log file helpers ─────────────────────────────────────────────────────────────

temp_log_file = "logs.txt"

if not os.path.exists(temp_log_file):
    with open(temp_log_file, "w"):
        pass


class StreamToLogger:
    def __init__(self, logger, log_level, log_file):
        self.logger = logger
        self.log_level = log_level
        self.log_file = log_file

    def write(self, buf):
        with open(self.log_file, 'a') as f:
            f.write(buf)
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

    def fileno(self):
        return 0


for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(filename=temp_log_file, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

stdout_logger = logging.getLogger('STDOUT')
sl_out = StreamToLogger(stdout_logger, logging.INFO, temp_log_file)
sys.stdout = sl_out

stderr_logger = logging.getLogger('STDERR')
sl_err = StreamToLogger(stderr_logger, logging.ERROR, temp_log_file)
sys.stderr = sl_err


def reset_log_file():
    try:
        if os.path.exists(temp_log_file):
            os.remove(temp_log_file)
        with open(temp_log_file, "w"):
            pass
        recreate_log_handlers()
    except Exception as e:
        print("Error resetting log file:", e)


def recreate_log_handlers():
    global sl_out, sl_err
    stdout_logger = logging.getLogger('STDOUT')
    sl_out = StreamToLogger(stdout_logger, logging.INFO, temp_log_file)
    sys.stdout = sl_out
    stderr_logger = logging.getLogger('STDERR')
    sl_err = StreamToLogger(stderr_logger, logging.ERROR, temp_log_file)
    sys.stderr = sl_err
    logging.root.handlers = []
    logging.basicConfig(filename=temp_log_file, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')


recreate_log_handlers()


async def schedule_log_reset():
    while True:
        await asyncio.sleep(180)
        reset_log_file()


asyncio.ensure_future(schedule_log_reset())


@gagan.on(events.NewMessage(incoming=True, pattern='/logs'))
async def send_log(event):
    user_id = event.sender_id
    if os.path.exists(temp_log_file):
        await gagan.send_file(user_id, temp_log_file,
                              caption="Here is the log file of last 2 min.")
    else:
        await event.respond("Log file not found.")


# ── /batch ───────────────────────────────────────────────────────────────────────

@gagan.on(events.NewMessage(incoming=True, pattern='/batch'))
async def _bulk(event):
    user_id = event.sender_id

    # Block if a classic batch is already running
    if str(user_id) in batch_data:
        return await event.reply(
            "You've already started one batch, wait for it to complete!"
        )
    # Block if a supergroup batch is already running
    if active_batches.get(user_id) is False:
        return await event.reply(
            "A batch is already running. Use /cancel to stop it first."
        )

    async with gagan.conversation(event.chat_id, timeout=120) as conv:
        try:
            await conv.send_message(
                "Send me the message link to start from.\n\n"
                "**Supported formats:**\n"
                "• `t.me/c/CHATID/MSGID` — private channel\n"
                "• `t.me/c/CHATID/TOPICID/MSGID` — supergroup topic (start only)\n"
                "• `t.me/c/CHATID/TOPICID/STARTMSG-ENDMSG` — supergroup topic range\n"
                "• `t.me/USERNAME/MSGID` — public channel",
                buttons=Button.force_reply()
            )
            link_msg = await conv.get_reply()

            try:
                _link = get_link(link_msg.text) or link_msg.text.strip()
            except Exception:
                await conv.send_message("No link found.")
                return

            if not _link:
                await conv.send_message("No valid link found.")
                return

            # Detect supergroup topic link
            supergroup_parsed = _parse_supergroup_link(_link)

            if supergroup_parsed:
                chat_id, topic_id, start_msg, end_msg = supergroup_parsed

                # If no end_msg in link, ask for it
                if end_msg == start_msg:
                    await conv.send_message(
                        f"Starting message ID: `{start_msg}`\n\n"
                        "Send the **ending message ID** (or 0 to process just this one):",
                        buttons=Button.force_reply()
                    )
                    try:
                        end_msg_reply = await conv.get_reply()
                        end_val = int(end_msg_reply.text.strip())
                        if end_val > 0:
                            end_msg = end_val
                    except Exception:
                        await conv.send_message("Invalid end message ID. Aborting.")
                        return

                total = end_msg - start_msg + 1
                if total < 1:
                    await conv.send_message("End message ID must be >= start message ID.")
                    return
                if total > 10000:
                    await conv.send_message("Max range is 10000 messages per batch.")
                    return

                active_batches[user_id] = False
                await conv.send_message(
                    f"🚀 Starting supergroup topic batch\n"
                    f"Chat: `{chat_id}` | Topic: `{topic_id}`\n"
                    f"Range: `{start_msg}` → `{end_msg}` ({total} msg IDs)\n\n"
                    f"Use /cancel to stop.",
                    buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
                )

            else:
                # Classic batch — ask for range
                await conv.send_message(
                    "Send me the number of files/range you want to save from the given message.",
                    buttons=Button.force_reply()
                )
                _range = await conv.get_reply()
                try:
                    value = int(_range.text.strip())
                    if value > 10000:
                        await conv.send_message(
                            "You can only get up to 10000 files in a single batch."
                        )
                        return
                    if value < 1:
                        await conv.send_message("Range must be at least 1.")
                        return
                except ValueError:
                    await conv.send_message("Range must be an integer!")
                    return

                ids_data[str(user_id)] = list(range(value))
                save_ids_data(ids_data)

                s, r = await check(userbot, Bot, _link)
                if s is not True:
                    await conv.send_message(r)
                    del ids_data[str(user_id)]
                    save_ids_data(ids_data)
                    return

                batch_data[str(user_id)] = True
                save_batch_data(batch_data)

                cd = await conv.send_message(
                    "**Batch process ongoing...**\n\nProcess completed: 0",
                    buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
                )

        except asyncio.TimeoutError:
            await event.respond("Conversation timed out. Please try /batch again.")
            return
        except Exception as e:
            logger.info(e)
            await event.respond(f"Error: {e}")
            return

    # ── Resolve which account to use ──────────────────────────────────────────
    user_session_str = get_user_session(user_id)
    personal_acc = None

    if user_session_str:
        try:
            personal_acc = Client(
                f"batch_user_{user_id}",
                session_string=user_session_str,
                api_id=int(API_ID),
                api_hash=API_HASH,
                in_memory=True
            )
            await personal_acc.start()
        except Exception as e:
            await Bot.send_message(
                user_id,
                f"⚠️ Could not start your personal session: `{e}`\n"
                "Falling back to global userbot."
            )
            personal_acc = None

    acc = personal_acc if personal_acc else userbot

    if acc is None:
        active_batches.pop(user_id, None)
        batch_data.pop(str(user_id), None)
        save_batch_data(batch_data)
        ids_data.pop(str(user_id), None)
        save_ids_data(ids_data)
        return await Bot.send_message(
            user_id,
            "❌ No user session available.\n"
            "Use /login to log in with your phone number first."
        )

    # ── Run the appropriate batch ─────────────────────────────────────────────
    try:
        if supergroup_parsed:
            await run_supergroup_topic_batch(
                acc, Bot, user_id, chat_id, topic_id, start_msg, end_msg
            )
        else:
            co = await r_batch(acc, Bot, user_id, cd, _link)
            try:
                if co == -2:
                    await Bot.send_message(user_id, "✅ Batch successfully completed!")
                    await cd.edit(
                        f"**Batch process completed.**\n\n"
                        f"Process completed: {value}\n\n✅ Batch successfully completed!"
                    )
            except Exception:
                await Bot.send_message(
                    user_id, "❌ ERROR! Maybe the last message didn't exist."
                )
    finally:
        if personal_acc:
            try:
                await personal_acc.stop()
            except Exception:
                pass
        active_batches.pop(user_id, None)
        batch_data.pop(str(user_id), None)
        save_batch_data(batch_data)
        ids_data.pop(str(user_id), None)
        save_ids_data(ids_data)


# ── Classic batch runner ──────────────────────────────────────────────────────

async def r_batch(acc, client, sender, countdown, link):
    for i in range(len(ids_data[str(sender)])):
        timer = 30

        if i < 25:
            timer = 20
        elif 25 <= i < 100:
            timer = 25
        elif 100 <= i < 1000:
            timer = 30
        elif 1000 <= i < 5000:
            timer = 35
        elif 5000 <= i < 10000:
            timer = 40
        elif i >= 10000:
            timer = 45

        if 't.me/c/' not in link:
            timer = 10 if i < 500 else 30

        try:
            integer = int(link.split("/")[-1]) + int(ids_data[str(sender)][i])
            count_down = (
                f"**Batch process ongoing.**\n\n"
                f"Process completed: {i + 1}\n"
                f"Current Msg ID: `{integer}`"
            )
            await get_bulk_msg(acc, client, sender, link, integer)
            protection = await client.send_message(
                sender,
                f"Sleeping for `{timer}` seconds to avoid FloodWait..."
            )
            await countdown.edit(
                count_down,
                buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
            )
            await asyncio.sleep(timer)
            await protection.delete()

        except IndexError as ie:
            await client.send_message(sender, f"{i} {ie}\n\nBatch ended!")
            await countdown.delete()
            break
        except FloodWait as fw:
            fw_val = int(fw.value) if hasattr(fw, 'value') else int(fw.x)
            if fw_val > 300:
                await client.send_message(
                    sender,
                    f"FloodWait of {fw_val}s — cancelling batch."
                )
                ids_data.pop(str(sender), None)
                break
            else:
                fw_alert = await client.send_message(
                    sender,
                    f"Sleeping {fw_val + 15}s due to Telegram FloodWait."
                )
                await asyncio.sleep(fw_val + 5)
                await fw_alert.delete()
                try:
                    await get_bulk_msg(acc, client, sender, link, integer)
                except Exception as e:
                    logger.info(e)
                if countdown.text != count_down:
                    await countdown.edit(
                        count_down,
                        buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
                    )
        except Exception as e:
            if countdown.text != count_down:
                await countdown.edit(
                    count_down,
                    buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
                )

        n = i + 1
        if n == len(ids_data[str(sender)]):
            return -2


# ── Supergroup topic batch runner ─────────────────────────────────────────────

async def run_supergroup_topic_batch(
    acc, client, sender, chat_id: int, topic_id: int, start_msg: int, end_msg: int
):
    """
    Iterate message IDs from start_msg to end_msg (inclusive).
    Skip any message that does not belong to topic_id.
    Show the current message ID being processed.
    """
    total_range = end_msg - start_msg + 1
    processed = 0
    skipped = 0

    # Live status message
    status_msg = await client.send_message(
        sender,
        f"🔍 **Supergroup Topic Batch Started**\n"
        f"Chat: `{chat_id}` | Topic: `{topic_id}`\n"
        f"Range: `{start_msg}` → `{end_msg}` ({total_range} IDs)\n\n"
        f"⏳ Starting...",
        buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
    )

    for msg_id in range(start_msg, end_msg + 1):
        if active_batches.get(sender):
            await client.send_message(sender, "✅ Batch cancelled.")
            return

        # Update live status with current msg ID
        try:
            await status_msg.edit(
                f"🔄 **Supergroup Topic Batch**\n"
                f"Chat: `{chat_id}` | Topic: `{topic_id}`\n"
                f"Range: `{start_msg}` → `{end_msg}`\n\n"
                f"📌 **Current Msg ID:** `{msg_id}`\n"
                f"✅ Saved: `{processed}` | ⏭️ Skipped: `{skipped}`",
                buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
            )
        except Exception:
            pass

        # Fetch the message
        try:
            msg = await acc.get_messages(chat_id, msg_id)
        except FloodWait as fw:
            fw_val = int(fw.value) if hasattr(fw, 'value') else int(fw.x)
            if fw_val > 299:
                await client.send_message(
                    sender,
                    f"⏳ FloodWait > 5 min ({fw_val}s). Cancelling batch."
                )
                return
            fw_alert = await client.send_message(
                sender, f"⏳ FloodWait {fw_val}s, waiting..."
            )
            await asyncio.sleep(fw_val + 3)
            await fw_alert.delete()
            try:
                msg = await acc.get_messages(chat_id, msg_id)
            except Exception as e:
                logger.info(f"Supergroup batch retry error at {msg_id}: {e}")
                skipped += 1
                continue
        except Exception as e:
            logger.info(f"Supergroup batch fetch error at {msg_id}: {e}")
            skipped += 1
            continue

        # Skip empty / service messages
        if msg is None or getattr(msg, "empty", False):
            skipped += 1
            continue

        # Skip messages not in this topic
        if not _is_in_topic(msg, topic_id):
            skipped += 1
            continue

        processed += 1

        # Determine timer based on count
        if processed < 25:
            timer = 5
        elif processed < 50:
            timer = 10
        else:
            timer = 15

        # Build a standard t.me/c link (2-segment) so get_bulk_msg parses correctly
        raw_chat_id = str(chat_id).replace("-100", "")
        link_str = f"https://t.me/c/{raw_chat_id}/{msg_id}"

        try:
            await get_bulk_msg(acc, client, sender, link_str, msg_id)
        except FloodWait as fw:
            fw_val = int(fw.value) if hasattr(fw, 'value') else int(fw.x)
            if fw_val > 299:
                await client.send_message(
                    sender, f"⏳ FloodWait > 5 min. Cancelling batch."
                )
                return
            fw_alert = await client.send_message(
                sender, f"⏳ FloodWait {fw_val}s, waiting..."
            )
            await asyncio.sleep(fw_val + 5)
            await fw_alert.delete()
            try:
                await get_bulk_msg(acc, client, sender, link_str, msg_id)
            except Exception as e:
                logger.info(f"Supergroup batch process error at {msg_id}: {e}")
        except Exception as e:
            logger.info(f"Supergroup batch process error at {msg_id}: {e}")

        # Sleep between files (skip sleep after last one)
        if msg_id < end_msg:
            sleep_msg = await client.send_message(
                sender,
                f"⏳ Sleeping `{timer}s`... "
                f"({processed} saved / {skipped} skipped so far)"
            )
            await asyncio.sleep(timer)
            try:
                await sleep_msg.delete()
            except Exception:
                pass

    # Final summary
    if not active_batches.get(sender):
        try:
            await status_msg.edit(
                f"✅ **Supergroup Topic Batch Complete!**\n"
                f"Chat: `{chat_id}` | Topic: `{topic_id}`\n"
                f"Range: `{start_msg}` → `{end_msg}`\n\n"
                f"📦 **Saved:** `{processed}`\n"
                f"⏭️ **Skipped** (other topic / empty): `{skipped}`",
                buttons=[[Button.url("Join Channel", url="https://t.me/devggn")]]
            )
        except Exception:
            await client.send_message(
                sender,
                f"✅ Supergroup topic batch done!\n"
                f"Saved: {processed} | Skipped: {skipped}"
            )
