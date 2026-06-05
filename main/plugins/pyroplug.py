# Join t.me/dev_gagan

import asyncio, time, os

from pyrogram.enums import ParseMode, MessageMediaType

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

from .. import Bot, bot
from main.plugins.progress import progress_for_pyrogram
from main.plugins.helpers import screenshot

from pyrogram import Client, filters
from pyrogram.errors import ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid, FloodWait
from main.plugins.helpers import video_metadata
from telethon import events

import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("telethon").setLevel(logging.INFO)

user_chat_ids = {}

def thumbnail(sender):
    return f'{sender}.jpg' if os.path.exists(f'{sender}.jpg') else f'thumb.jpg'


async def _get_thumb(acc, msg, sender, file, duration):
    """
    Return a thumbnail path, tried in priority order:
      1. User's custom thumbnail  ({sender}.jpg)
      2. Original message's embedded thumbnail (downloaded from Telegram)
      3. Screenshot generated from the video file via FFmpeg
      4. None  (Telegram will show a black/blank frame — last resort)
    """
    # 1. Custom user thumbnail set via the bot
    if os.path.exists(f'{sender}.jpg'):
        return f'{sender}.jpg'

    # 2. Download the thumbnail that was embedded in the original message
    try:
        media = msg.video or msg.document or msg.animation
        if media and getattr(media, 'thumbs', None):
            t = await acc.download_media(media.thumbs[-1])
            if t and os.path.exists(str(t)):
                return str(t)
    except Exception:
        pass

    # 3. Generate a screenshot from the local video file
    try:
        t = await screenshot(file, duration, sender)
        if t and os.path.exists(str(t)):
            return str(t)
    except Exception:
        pass

    return None


async def copy_message_with_chat_id(client, sender, chat_id, message_id, target_override=None):
    target_chat_id = target_override if target_override else user_chat_ids.get(sender, sender)
    try:
        await client.copy_message(target_chat_id, chat_id, message_id)
    except Exception as e:
        error_message = f"Error occurred while sending message to chat ID {target_chat_id}: {str(e)}"
        await client.send_message(sender, error_message)
        await client.send_message(sender, f"Make Bot admin in your Channel - {target_chat_id} and restart the process after /cancel")

async def send_message_with_chat_id(client, sender, message, parse_mode=None):
    chat_id = user_chat_ids.get(sender, sender)
    try:
        await client.send_message(chat_id, message, parse_mode=parse_mode)
    except Exception as e:
        error_message = f"Error occurred while sending message to chat ID {chat_id}: {str(e)}"
        await client.send_message(sender, error_message)
        await client.send_message(sender, f"Make Bot admin in your Channel - {chat_id} and restart the process after /cancel")

@bot.on(events.NewMessage(incoming=True, pattern='/setchat'))
async def set_chat_id(event):
    try:
        chat_id = int(event.raw_text.split(" ", 1)[1])
        user_chat_ids[event.sender_id] = chat_id
        await event.reply("Chat ID set successfully!")
    except ValueError:
        await event.reply("Invalid chat ID!")

async def send_video_with_chat_id(client, sender, path, caption, duration, hi, wi, thumb_path, upm):
    chat_id = user_chat_ids.get(sender, sender)
    try:
        await client.send_video(
            chat_id=chat_id,
            video=path,
            caption=caption,
            supports_streaming=True,
            duration=duration,
            height=hi,
            width=wi,
            thumb=thumb_path,
            progress=progress_for_pyrogram,
            progress_args=(
                client,
                '**__Uploading: [Team SPY](https://t.me/dev_gagan)__**\n ',
                upm,
                time.time()
            )
        )
    except Exception as e:
        error_message = f"Error occurred while sending video to chat ID {chat_id}: {str(e)}"
        await client.send_message(sender, error_message)
        await client.send_message(sender, f"Make Bot admin in your Channel - {chat_id} and restart the process after /cancel")


async def send_document_with_chat_id(client, sender, path, caption, thumb_path, upm):
    chat_id = user_chat_ids.get(sender, sender)
    try:
        await client.send_document(
            chat_id=chat_id,
            document=path,
            caption=caption,
            thumb=thumb_path,
            progress=progress_for_pyrogram,
            progress_args=(
                client,
                '**__Uploading:__**\n**__Bot made by [Team SPY](https://t.me/dev_gagan)__**',
                upm,
                time.time()
            )
        )
    except Exception as e:
        error_message = f"Error occurred while sending document to chat ID {chat_id}: {str(e)}"
        await client.send_message(sender, error_message)
        await client.send_message(sender, f"Make Bot admin in your Channel - {chat_id} and restart the process after /cancel")

async def check(userbot, client, link):
    logging.info(link)
    msg_id = 0
    try:
        msg_id = int(link.split("/")[-1])
    except ValueError:
        if '?single' not in link:
            return False, "**Invalid Link!**"
        link_ = link.split("?single")[0]
        msg_id = int(link_.split("/")[-1])
    if 't.me/c/' in link:
        if userbot is None:
            return False, "❌ No global session available. Please use /login first."
        try:
            chat = int('-100' + str(link.split("/")[-2]))
            await userbot.get_messages(chat, msg_id)
            return True, None
        except ValueError:
            return False, "**Invalid Link!**"
        except Exception as e:
            logging.info(e)
            return False, "Have you joined the channel?"
    else:
        try:
            chat = str(link.split("/")[-2])
            await client.get_messages(chat, msg_id)
            return True, None
        except Exception as e:
            logging.info(e)
            return False, "Maybe bot is banned from the chat, or your link is invalid!"

async def get_msg(userbot, client, sender, edit_id, msg_link, i, file_n, target_override=None):
    edit = ""
    chat = ""
    msg_id = int(i)
    if msg_id == -1:
        await client.edit_message_text(sender, edit_id, "**Invalid Link!**")
        return False   # return success flag
    if 't.me/c/' in msg_link or 't.me/b/' in msg_link:
        if userbot is None:
            await client.edit_message_text(
                sender, edit_id,
                "❌ No session to access this restricted channel.\nUse /login to authenticate."
            )
            return False
        if "t.me/b" not in msg_link:
            chat = int('-100' + str(msg_link.split("/")[-2]))
        else:
            chat = int(msg_link.split("/")[-2])
        file = ""
        try:
            msg = await userbot.get_messages(chat_id=chat, message_ids=msg_id)
            logging.info(msg)
            if msg.service is not None:
                await client.delete_messages(chat_id=sender, message_ids=edit_id)
                return False
            # 🔧 FIXED: empty check should be a boolean test
            if msg.empty:
                await client.delete_messages(chat_id=sender, message_ids=edit_id)
                return False

            # Text-only messages
            if not msg.media and msg.text:
                a = b = True
                edit = await client.edit_message_text(sender, edit_id, "Cloning.")
                if hasattr(msg.text, 'html') and ('--' in msg.text.html or '**' in msg.text.html or '__' in msg.text.html or '~~' in msg.text.html or '||' in msg.text.html or '```' in msg.text.html or '`' in msg.text.html):
                    await send_message_with_chat_id(client, sender, msg.text.html, parse_mode=ParseMode.HTML)
                    a = False
                if hasattr(msg.text, 'markdown') and ('<b>' in msg.text.markdown or '<i>' in msg.text.markdown or '<em>' in msg.text.markdown or '<u>' in msg.text.markdown or '<s>' in msg.text.markdown or '<spoiler>' in msg.text.markdown):
                    await send_message_with_chat_id(client, sender, msg.text.markdown, parse_mode=ParseMode.MARKDOWN)
                    b = False
                if a and b:
                    await send_message_with_chat_id(client, sender, msg.text.markdown, parse_mode=ParseMode.MARKDOWN)
                await edit.delete()
                return True

            if msg.media == MessageMediaType.POLL:
                await client.edit_message_text(sender, edit_id, 'poll media cant be saved')
                return False

            if msg.media:
                edit = await client.edit_message_text(sender, edit_id, "Trying to Download.")
                try:
                    file = await userbot.download_media(
                        msg,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            "**__Unrestricting__: __[Team SPY](https://t.me/dev_gagan)__**\n ",
                            edit,
                            time.time()
                        )
                    )

                    if not file or not os.path.exists(str(file)) or os.path.getsize(str(file)) == 0:
                        await client.edit_message_text(sender, edit_id, "⚠️ Download failed or file is empty, skipping.")
                        return False

                    path = file
                    await edit.delete()
                    upm = await client.send_message(sender, '__Preparing to Upload!__')

                    caption = str(file)
                    if msg.caption is not None:
                        caption = msg.caption

                    if str(file).split(".")[-1] in ['mkv', 'mp4', 'webm', 'mpe4', 'mpeg', 'ts', 'avi', 'flv', 'org']:
                        if str(file).split(".")[-1] in ['webm', 'mkv', 'mpe4', 'mpeg', 'ts', 'avi', 'flv', 'org']:
                            path = str(file).split(".")[0] + ".mp4"
                            os.rename(file, path)
                            file = str(file).split(".")[0] + ".mp4"
                        data = video_metadata(file)
                        duration = data["duration"]
                        wi = data["width"]
                        hi = data["height"]
                        logging.info(data)

                        if file_n != '':
                            if '.' in file_n:
                                path = os.path.join(DOWNLOADS_DIR, file_n)
                            else:
                                path = os.path.join(DOWNLOADS_DIR, file_n + '.' + str(file).split(".")[-1])
                            os.rename(file, path)
                            file = path

                        thumb_path = await _get_thumb(userbot, msg, sender, file, duration)

                        caption = f"{msg.caption}\n\n__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__" if msg.caption else "__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__"
                        await send_video_with_chat_id(client, sender, path, caption, duration, hi, wi, thumb_path, upm)

                    elif str(file).split(".")[-1] in ['jpg', 'jpeg', 'png', 'webp']:
                        if file_n != '':
                            if '.' in file_n:
                                path = os.path.join(DOWNLOADS_DIR, file_n)
                            else:
                                path = os.path.join(DOWNLOADS_DIR, file_n + '.' + str(file).split(".")[-1])
                            os.rename(file, path)
                            file = path
                        caption = f"{msg.caption}\n\n__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__" if msg.caption else "__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__"
                        await upm.edit("__Uploading photo...__")
                        await bot.send_file(sender, path, caption=caption)

                    else:
                        if file_n != '':
                            if '.' in file_n:
                                path = os.path.join(DOWNLOADS_DIR, file_n)
                            else:
                                path = os.path.join(DOWNLOADS_DIR, file_n + '.' + str(file).split(".")[-1])
                            os.rename(file, path)
                            file = path
                        thumb_path = "thumb.jpg"
                        caption = f"{msg.caption}\n\n__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__" if msg.caption else "__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__"
                        await send_document_with_chat_id(client, sender, path, caption, thumb_path, upm)

                    if os.path.exists(file):
                        os.remove(file)
                    await upm.delete()
                    return True
                except Exception as e:
                    logging.error(f"Error downloading media: {str(e)}")
                    await client.edit_message_text(sender, edit_id, f"Could not download media: {str(e)[:100]}")
                    return False
        except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid):
            await client.edit_message_text(sender, edit_id, "Bot is not in that channel/group.\nSend the invite link so the bot can join.")
            return False

    else:
        # ── Public channel: download & re-upload via bot ──────────────────────
        edit = await client.edit_message_text(sender, edit_id, "Fetching.")
        chat = msg_link.split("/")[-2]
        target_chat_id = target_override if target_override else user_chat_ids.get(sender, sender)
        file = None
        upm = None

        try:
            msg = await client.get_messages(chat, msg_id)
        except Exception as e:
            await client.edit_message_text(sender, edit_id, f"Could not fetch message: {str(e)[:100]}")
            return False

        if msg is None or msg.empty:
            await client.delete_messages(chat_id=sender, message_ids=edit_id)
            return False

        # Service messages (pins, joins, etc.) — skip
        if getattr(msg, 'service', None) is not None:
            await client.delete_messages(chat_id=sender, message_ids=edit_id)
            return False

        # Text-only messages
        if not msg.media and msg.text:
            try:
                await client.send_message(target_chat_id, msg.text.markdown, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await client.send_message(target_chat_id, str(msg.text))
            await edit.delete()
            return True

        if msg.media == MessageMediaType.POLL:
            await client.edit_message_text(sender, edit_id, 'poll media cannot be saved')
            return False

        if msg.media:
            await client.edit_message_text(sender, edit_id, "Trying to Download.")
            try:
                file = await client.download_media(
                    msg,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        client,
                        "**__Downloading...__**\n ",
                        edit,
                        time.time()
                    )
                )

                if not file or not os.path.exists(str(file)) or os.path.getsize(str(file)) == 0:
                    await client.edit_message_text(sender, edit_id, "⚠️ Download failed or file is empty, skipping.")
                    return False

                path = file
                await edit.delete()
                upm = await client.send_message(sender, '__Preparing to Upload!__')

                caption = msg.caption if msg.caption else ""
                ext = str(file).split(".")[-1].lower()

                # ── Video ─────────────────────────────────────────────────────
                if ext in ['mkv', 'mp4', 'webm', 'mpe4', 'mpeg', 'ts', 'avi', 'flv', 'org']:
                    if ext in ['webm', 'mkv', 'mpe4', 'mpeg', 'ts', 'avi', 'flv', 'org']:
                        path = str(file).split(".")[0] + ".mp4"
                        os.rename(file, path)
                        file = path

                    if file_n != '':
                        new_name = file_n if '.' in file_n else file_n + '.' + str(path).split(".")[-1]
                        new_path = os.path.join(DOWNLOADS_DIR, new_name)
                        os.rename(path, new_path)
                        path = new_path
                        file = path

                    data = video_metadata(file)
                    duration = data["duration"]
                    wi = data["width"]
                    hi = data["height"]
                    logging.info(data)

                    thumb_path = await _get_thumb(client, msg, sender, file, duration)

                    await client.send_video(
                        chat_id=target_chat_id,
                        video=path,
                        caption=caption,
                        supports_streaming=True,
                        duration=duration,
                        height=hi,
                        width=wi,
                        thumb=thumb_path,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            '**__Uploading: [Team SPY](https://t.me/dev_gagan)__**\n ',
                            upm,
                            time.time()
                        )
                    )

                # ── Photo ─────────────────────────────────────────────────────
                elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                    if file_n != '':
                        new_name = file_n if '.' in file_n else file_n + '.' + ext
                        new_path = os.path.join(DOWNLOADS_DIR, new_name)
                        os.rename(path, new_path)
                        path = new_path
                        file = path
                    await upm.edit("__Uploading photo...__")
                    await client.send_photo(chat_id=target_chat_id, photo=path, caption=caption)

                # ── Document / audio / other ──────────────────────────────────
                else:
                    if file_n != '':
                        new_name = file_n if '.' in file_n else file_n + '.' + ext
                        new_path = os.path.join(DOWNLOADS_DIR, new_name)
                        os.rename(path, new_path)
                        path = new_path
                        file = path
                    thumb_path = thumbnail(sender)
                    await client.send_document(
                        chat_id=target_chat_id,
                        document=path,
                        caption=caption,
                        thumb=thumb_path,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            '**__Uploading: [Team SPY](https://t.me/dev_gagan)__**\n ',
                            upm,
                            time.time()
                        )
                    )

                if os.path.exists(file):
                    os.remove(file)
                await upm.delete()
                return True

            except Exception as e:
                logging.error(f"Error processing public msg {msg_id}: {str(e)}")
                await client.send_message(sender, f"Error on msg {msg_id}: {str(e)[:100]}")
                return False
        else:
            await edit.delete()
            return False


async def get_bulk_msg(userbot, client, sender, msg_link, i, target_override=None):
    x = await client.send_message(sender, "Processing!")
    file_name = ''
    # Return the success flag from get_msg so we can count correctly
    result = await get_msg(userbot, client, sender, x.id, msg_link, i, file_name, target_override=target_override)
    # Clean up the "Processing!" message if it still exists
    try:
        await x.delete()
    except Exception:
        pass
    return result


async def ggn_new(userbot, client, sender, edit_id, msg_link, i, file_n):
    edit = ""
    chat = ""
    msg_id = int(i)
    if msg_id == -1:
        await client.edit_message_text(sender, edit_id, "**Invalid Link!**")
        return None
    if 't.me/c/' in msg_link or 't.me/b/' in msg_link:
        if "t.me/b" not in msg_link:
            parts = msg_link.split("/")
            chat = int('-100' + str(parts[4]))
        else:
            chat = int(msg_link.split("/")[-2])
        file = ""
        try:
            msg = await userbot.get_messages(chat_id=chat, message_ids=msg_id)
            logging.info(msg)
            if msg.service is not None:
                await client.delete_messages(chat_id=sender, message_ids=edit_id)
                return None
            # 🔧 FIXED: same empty check
            if msg.empty:
                await client.delete_messages(chat_id=sender, message_ids=edit_id)
                return None

            # Text-only messages
            if not msg.media and msg.text:
                a = b = True
                edit = await client.edit_message_text(sender, edit_id, "Cloning.")
                if hasattr(msg.text, 'html') and ('--' in msg.text.html or '**' in msg.text.html or '__' in msg.text.html or '~~' in msg.text.html or '||' in msg.text.html or '```' in msg.text.html or '`' in msg.text.html):
                    await send_message_with_chat_id(client, sender, msg.text.html, parse_mode=ParseMode.HTML)
                    a = False
                if hasattr(msg.text, 'markdown') and ('<b>' in msg.text.markdown or '<i>' in msg.text.markdown or '<em>' in msg.text.markdown or '<u>' in msg.text.markdown or '<s>' in msg.text.markdown or '<spoiler>' in msg.text.markdown):
                    await send_message_with_chat_id(client, sender, msg.text.markdown, parse_mode=ParseMode.MARKDOWN)
                    b = False
                if a and b:
                    await send_message_with_chat_id(client, sender, msg.text.markdown, parse_mode=ParseMode.MARKDOWN)
                await edit.delete()
                return None

            if msg.media == MessageMediaType.POLL:
                await client.edit_message_text(sender, edit_id, 'poll media cant be saved')
                return None

            if msg.media:
                edit = await client.edit_message_text(sender, edit_id, "Trying to Download.")
                try:
                    file = await userbot.download_media(
                        msg,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            "**__Unrestricting__: __[Team SPY](https://t.me/dev_gagan)__**\n ",
                            edit,
                            time.time()
                        )
                    )

                    if not file or not os.path.exists(str(file)) or os.path.getsize(str(file)) == 0:
                        await client.edit_message_text(sender, edit_id, "⚠️ Download failed or file is empty, skipping.")
                        return None

                    path = file
                    await edit.delete()
                    upm = await client.send_message(sender, '__Preparing to Upload!__')

                    caption = str(file)
                    if msg.caption is not None:
                        caption = msg.caption

                    if str(file).split(".")[-1] in ['mkv', 'mp4', 'webm', 'mpe4', 'mpeg', 'ts', 'avi', 'flv', 'org']:
                        if str(file).split(".")[-1] in ['webm', 'mkv', 'mpe4', 'mpeg', 'ts', 'avi', 'flv', 'org']:
                            path = str(file).split(".")[0] + ".mp4"
                            os.rename(file, path)
                            file = str(file).split(".")[0] + ".mp4"
                        data = video_metadata(file)
                        duration = data["duration"]
                        wi = data["width"]
                        hi = data["height"]
                        logging.info(data)

                        if file_n != '':
                            if '.' in file_n:
                                path = os.path.join(DOWNLOADS_DIR, file_n)
                            else:
                                path = os.path.join(DOWNLOADS_DIR, file_n + '.' + str(file).split(".")[-1])
                            os.rename(file, path)
                            file = path

                        thumb_path = await _get_thumb(userbot, msg, sender, file, duration)

                        caption = f"{msg.caption}\n\n__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__" if msg.caption else "__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__"
                        await send_video_with_chat_id(client, sender, path, caption, duration, hi, wi, thumb_path, upm)

                    elif str(file).split(".")[-1] in ['jpg', 'jpeg', 'png', 'webp']:
                        if file_n != '':
                            if '.' in file_n:
                                path = os.path.join(DOWNLOADS_DIR, file_n)
                            else:
                                path = os.path.join(DOWNLOADS_DIR, file_n + '.' + str(file).split(".")[-1])
                            os.rename(file, path)
                            file = path
                        caption = f"{msg.caption}\n\n__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__" if msg.caption else "__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__"
                        await upm.edit("__Uploading photo...__")
                        await bot.send_file(sender, path, caption=caption)

                    else:
                        if file_n != '':
                            if '.' in file_n:
                                path = os.path.join(DOWNLOADS_DIR, file_n)
                            else:
                                path = os.path.join(DOWNLOADS_DIR, file_n + '.' + str(file).split(".")[-1])
                            os.rename(file, path)
                            file = path
                        thumb_path = "thumb.jpg"
                        caption = f"{msg.caption}\n\n__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__" if msg.caption else "__Unrestricted by **[Team SPY](https://t.me/dev_gagan)**__"
                        await send_document_with_chat_id(client, sender, path, caption, thumb_path, upm)

                    if os.path.exists(file):
                        os.remove(file)
                    await upm.delete()
                    return None
                except Exception as e:
                    logging.error(f"Error downloading media: {str(e)}")
                    await client.edit_message_text(sender, edit_id, f"Could not download media: {str(e)[:100]}")
                    return None
        except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid):
            await client.edit_message_text(sender, edit_id, "Bot is not in that channel/group.\nSend the invite link so the bot can join.")
            return None
    else:
        edit = await client.edit_message_text(sender, edit_id, "Cloning.")
        chat = msg_link.split("/")[-2]
        await copy_message_with_chat_id(client, sender, chat, msg_id)
        await edit.delete()
        return None
