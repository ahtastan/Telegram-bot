import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from openpyxl import Workbook, load_workbook
import msal
import requests
from datetime import datetime
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET')
TENANT_ID = os.getenv('AZURE_TENANT_ID')

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

class OneDriveManager:
    def __init__(self):
        self.authority = f"https://login.microsoftonline.com/{TENANT_ID}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.app = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=self.authority, client_credential=CLIENT_SECRET
        )
    
    def get_access_token(self):
        result = self.app.acquire_token_for_client(scopes=self.scope)
        return result.get('access_token')
    
    def upload_excel(self, file_content, filename="receipts.xlsx"):
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{filename}:/content"
        response = requests.put(url, headers=headers, data=file_content)
        return response.status_code == 200 or response.status_code == 201

class ReceiptProcessor:
    def __init__(self):
        self.onedrive = OneDriveManager()
    
    async def process_receipt_image(self, image_path):
        """Extract receipt data using Gemini Vision"""
        prompt = """
        Analyze this receipt image and extract the following information in JSON format:
        {
            "merchant_name": "store name",
            "date": "YYYY-MM-DD",
            "total_amount": "amount as number",
            "currency": "currency code",
            "items": [
                {"name": "item name", "price": "price as number", "quantity": "qty"}
            ],
            "tax_amount": "tax as number",
            "payment_method": "cash/card/etc"
        }
        
        If any field is not clearly visible, use "N/A" or 0 for numbers.
        """
        
        try:
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()
            
            response = model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            # Parse JSON response
            receipt_data = json.loads(response.text.strip('```json\n').strip('```'))
            return receipt_data
        except Exception as e:
            print(f"Error processing receipt: {e}")
            return None
    
    def save_to_excel(self, receipt_data):
        """Save receipt data to Excel and upload to OneDrive"""
        try:
            # Create or load workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Receipts"
            
            # Headers
            headers = ["Date", "Merchant", "Total Amount", "Currency", 
                      "Items", "Tax", "Payment Method", "Processed At"]
            
            # Check if file exists on OneDrive (simplified for demo)
            ws.append(headers)
            
            # Add receipt data
            items_str = "; ".join([f"{item['name']} ({item['quantity']}x${item['price']})" 
                                 for item in receipt_data.get('items', [])])
            
            row = [
                receipt_data.get('date', 'N/A'),
                receipt_data.get('merchant_name', 'N/A'),
                receipt_data.get('total_amount', 0),
                receipt_data.get('currency', 'USD'),
                items_str,
                receipt_data.get('tax_amount', 0),
                receipt_data.get('payment_method', 'N/A'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            ws.append(row)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                wb.save(tmp.name)
                with open(tmp.name, 'rb') as f:
                    file_content = f.read()
                
                # Upload to OneDrive
                success = self.onedrive.upload_excel(file_content)
                os.unlink(tmp.name)  # Clean up temp file
                
                return success
        except Exception as e:
            print(f"Error saving to Excel: {e}")
            return False

# Initialize processor
processor = ReceiptProcessor()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_msg = """
🧾 **Receipt Processing Bot** 🧾

Send me a photo of your receipt and I'll:
✅ Extract all the information using AI
✅ Save it to your Excel file on OneDrive
✅ Keep your expenses organized!

Just send a photo to get started! 📸
    """
    await update.message.reply_text(welcome_msg)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle receipt photos"""
    try:
        await update.message.reply_text("📸 Processing your receipt... Please wait!")
        
        # Download photo
        photo = update.message.photo[-1]  # Get highest resolution
        file = await context.bot.get_file(photo.file_id)
        
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            await file.download_to_drive(tmp.name)
            
            # Process receipt
            receipt_data = await processor.process_receipt_image(tmp.name)
            os.unlink(tmp.name)  # Clean up
            
            if receipt_data:
                # Save to Excel
                success = processor.save_to_excel(receipt_data)
                
                if success:
                    response = f"""
✅ **Receipt Processed Successfully!**

🏪 **Merchant:** {receipt_data.get('merchant_name', 'N/A')}
📅 **Date:** {receipt_data.get('date', 'N/A')}
💰 **Total:** ${receipt_data.get('total_amount', 0)}
💳 **Payment:** {receipt_data.get('payment_method', 'N/A')}

📊 Data saved to your OneDrive Excel file!
                    """
                else:
                    response = "❌ Failed to save to OneDrive. Please try again."
            else:
                response = "❌ Could not process the receipt. Please ensure it's clear and try again."
                
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing receipt: {str(e)}")

def main():
    """Start the bot"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Start bot
    print("🤖 Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
