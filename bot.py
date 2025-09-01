import os
import io
import logging
from PIL import Image
import google.generativeai as genai
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# 🔧 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔑 Secrets from Render environment
TELEGRAM_BOT_TOKEN = os.getenv("7626755337:AAHse-ET97CuyMpvZDOFkhAGHasKt8f5zaY")
GEMINI_API_KEY = os.getenv("AIzaSyDZFTrMyrF4Zi3JqcvLZIuU_lXbV_tyFE4")

# --- Google Drive Setup ---
gauth = GoogleAuth()
gauth.LoadSettingsFile("settings.yaml")   # load service account config
gauth.ServiceAuth()                       # authenticate with service account
drive = GoogleDrive(gauth)

if gauth.credentials is None:
    gauth.LocalWebserverAuth()   # first run locally
elif gauth.access_token_expired:
    gauth.Refresh()
else:
    gauth.Authorize()

drive = GoogleDrive(gauth)

# 🔁 Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemma-3-27b-it")

# 📸 Handler for incoming photos
def handle_photo(update: Update, context: CallbackContext):
    logger.info("📷 Photo received")
    photo_file = update.message.photo[-1].get_file()
    byte_data = photo_file.download_as_bytearray()

    # Save to temporary file
    tmp_path = f"/tmp/{photo_file.file_id}.jpg"
    with open(tmp_path, "wb") as f:
        f.write(byte_data)

    # Upload to Google Drive
    gfile = drive.CreateFile({'title': f"{photo_file.file_id}.jpg"})
    gfile.SetContentFile(tmp_path)
    gfile.Upload()
    logger.info("✅ Uploaded to Google Drive")

    # Open image with PIL
    image = Image.open(io.BytesIO(byte_data))

    # Gemini prompt
    prompt = """
    You're given an image of a Turkish receipt. Extract the following:
    - Date (in dd/mm/yyyy)
    - Place (shop name)
    - Location (location/address)
    - Total Amount (currency + value)

    Reply only in this format:
    Date: ...
    Place: ...
    Location: ...
    Total: ...
    """

    try:
        response = model.generate_content([prompt, image])
        result = response.text or "No response from Gemini."
    except Exception as e:
        result = f"❌ Error: {e}"
        logger.error(e)

    # Reply to Telegram user
    update.message.reply_text("✅ Uploaded to Drive\n\n" + result)

# 🚀 Start bot
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))

    updater.start_polling()
    logger.info("🤖 Bot started...")
    updater.idle()

if __name__ == "__main__":
    main()