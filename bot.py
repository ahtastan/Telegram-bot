import os
from telegram.ext import Updater, MessageHandler, Filters
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# --- Google Drive Setup ---
gauth = GoogleAuth()
gauth.LoadCredentialsFile("credentials.json")

if gauth.credentials is None:
    gauth.LocalWebserverAuth()   # first run locally
elif gauth.access_token_expired:
    gauth.Refresh()
else:
    gauth.Authorize()

drive = GoogleDrive(gauth)

# --- Telegram Bot ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

def handle_photo(update, context):
    file = update.message.photo[-1].get_file()
    file_path = f"/tmp/{file.file_id}.jpg"
    file.download(file_path)

    gfile = drive.CreateFile({'title': f"{file.file_id}.jpg"})
    gfile.SetContentFile(file_path)
    gfile.Upload()
    update.message.reply_text("✅ Uploaded to Google Drive!")

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(MessageHandler(Filters.photo, handle_photo))

updater.start_polling()
updater.idle()