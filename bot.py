import os
import io
import logging
from PIL import Image
import google.generativeai as genai
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

# 🔧 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔑 Secrets from Render environment
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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


