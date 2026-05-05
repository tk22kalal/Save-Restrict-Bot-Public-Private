#Join me at telegram @dev_gagan

import os

from pyrogram import Client

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

import logging, time, sys
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)

# ── Credentials: read from environment variables, fall back to hardcoded values ──
API_ID   = int(os.environ.get("API_ID",   "24058425"))
API_HASH = os.environ.get("API_HASH",     "694b063e55c24287a3d30aed90191373")
BOT_TOKEN = os.environ.get("BOT_TOKEN",   "7361789777:AAEq1ooR7hsC8d5oRVGclmHYylAQwH7emOM")
SESSION   = os.environ.get("SESSION",     "BQFvGjkAlFyGh7l6ebfKNOpt1lMjjbW8457Oh9nTUGJ3Aeee6ufAqEs9AHL0GsnME58ZtwaQJvexJCI1ogGnJYcJ6XRePpd3ag_lnwpQladACxTJ_F2QOPVZR3EoldQOS6q4Y5kt_2YwlfdWil-yRezW60p_-O1cBWx1_eVg4wc0yLucM8QYq9RkcKd1bnQe9hpJZL64aSFnV7fuk60GA0NVyysf3pBbF1yRTqy1Om5ojtkdCpHGTWRc9PN1mX-azSbENmSXOgJeCT32MXhvlwS8r1Abg2uQDNEth3lphho7jeOG_4xvmAz_CWaoehx5jpIZmlJOiiRwMW-JxzdfwNgwkXxDEwAAAAGUl4H8AA")
FORCESUB  = os.environ.get("FORCESUB",   "forcesubpavo3")
AUTH      = os.environ.get("AUTH",        "6356781743")

SUDO_USERS = []

if len(AUTH) != 0:
    SUDO_USERS = {int(x.strip()) for x in AUTH.split()}
else:
    SUDO_USERS = set()

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

userbot = Client("myacc", api_id=API_ID, api_hash=API_HASH, session_string=SESSION)

try:
    userbot.start()
except BaseException:
    print("Your session expired please re add that... thanks @dev_gagan.")
    sys.exit(1)

Bot = Client(
    "SaveRestricted",
    bot_token=BOT_TOKEN,
    api_id=int(API_ID),
    api_hash=API_HASH
)

try:
    Bot.start()
except Exception as e:
    sys.exit(1)
