import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# লগিং সেটআপ 
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment Variable থেকে টোকেন
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_ENDPOINT = "https://gold-newt-367030.hostingersite.com/tera.php?url="

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"👋 **স্বাগতম, {user_name}!**\n\n"
        "আমি আপনার **TeraBox Downloader** বট।\n"
        "যেকোনো TeraBox বা NephoBox লিঙ্ক এখানে পেস্ট করুন, আমি আপনাকে সরাসরি ডাউনলোড এবং স্ট্রিম লিঙ্ক দিয়ে দেব।"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def handle_terabox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # লিঙ্ক ভ্যালিডেশন
    if "terabox" not in url and "nephobox" not in url:
        await update.message.reply_text("❌ এটি সঠিক TeraBox লিঙ্ক নয়। অনুগ্রহ করে সঠিক লিঙ্ক দিন।")
        return

    status_msg = await update.message.reply_text("🔎 **লিঙ্ক প্রসেসিং হচ্ছে... একটু অপেক্ষা করুন।**")

    try:
        # API কল করা
        response = requests.get(f"{API_ENDPOINT}{url}", timeout=15).json()
        
        if response.get("success"):
            file_data = response["data"][0]
            
            # মেসেজ সাজানো
            caption = (
                f"✅ **ফাইল পাওয়া গেছে!**\n\n"
                f"📂 **নাম:** `{file_data['file_name']}`\n"
                f"⚖️ **সাইজ:** {file_data['file_size']}\n"
                f"🆔 **ID:** `{file_data['share_id']}`"
            )

            # বাটন তৈরি (স্ট্রিমিং হবে Mini App এ, ডাউনলোড হবে ব্রাউজারে)
            keyboard = [
                [InlineKeyboardButton("📺 অনলাইন স্ট্রিম (Mini App)", web_app=WebAppInfo(url=file_data['stream_final_url']))],
                [InlineKeyboardButton("📥 সরাসরি ডাউনলোড", url=file_data['download_url'])]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await status_msg.delete() 
            await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await status_msg.edit_text("❌ দুঃখিত! ফাইলটি খুঁজে পাওয়া যায়নি বা লিঙ্কটি এক্সপায়ার হয়ে গেছে।")

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await status_msg.edit_text("⚠️ সার্ভারে সমস্যা হচ্ছে। অনুগ্রহ করে একটু পর আবার চেষ্টা করুন।")

if __name__ == "__main__":
    # টোকেন চেক করা
    if not TOKEN:
        print("❌ Error: TELEGRAM_TOKEN environment variable is missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_terabox))
        
        print("✅ Bot is running successfully...")
        app.run_polling()
      
