#Join me at telegram @dev_gagan

from pyrogram import Client

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from decouple import config
import logging, time, sys
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)

# variables
API_ID = 24058425
API_HASH = "694b063e55c24287a3d30aed90191373"
BOT_TOKEN = "7361789777:AAEq1ooR7hsC8d5oRVGclmHYylAQwH7emOM"
SESSION = "BQFvGjkAMagL7iFZ_3DtnyQFVf_Zbaps424QSgZZ3_fKjqQVSxGCbWMMdXzfdaPEnZpqp0G9ZlrehS6GWXLLHuSZzjkhCN5RuVF-d3TXUlXhk4IT2uSIo7xxb6Z-LfFFlG6TzgENHMtHFePAnalx86TnzMnd-QKAxQuzRSLh4Pf7RtohuIYriir4bv4_1Ma_YScxjsKhOyZADuIV3Uzky6KdSFFVKEt7BvJIQaT73LcTLeS34dLKLb-TtOfPVxcGaRWc4jJCq_Cf039aHWllCY6Wo6hrzpdgy_DQw-79QSUOKFQ1qPKRRedUNpsTNHsB_VakpYQBeKwMpTOq4kI6tCa56WzAnAAAAAGUl4H8AA"
FORCESUB = "forcesubpavo3"
AUTH = "6356781743"

SUDO_USERS = []

if len(AUTH) != 0:
    SUDO_USERS = {int(AUTH.strip()) for AUTH in AUTH.split()}
else:
    SUDO_USERS = set()

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN) 

userbot = Client("myacc",api_id=API_ID,api_hash=API_HASH,session_string=SESSION)

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
    # print(e)
    # logger.info(e)
    sys.exit(1)
