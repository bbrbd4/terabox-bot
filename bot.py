import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Get bot token from Railway environment variable
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found. Set it in Railway environment variables.")

API_URL = "https://gold-newt-367030.hostingersite.com/tera.php?url={}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌪 **Terabox Downloader Bot**\n\nSend me any Terabox link and I'll provide:\n✅ Direct download links\n✅ File size & name\n✅ Thumbnail (if available)\n\n**Example:**\n`https://teraboxshare.com/s/xxxxx`",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()

    if "terabox" not in text.lower():
        await msg.reply_text("❌ Please send a valid Terabox link.")
        return

    processing = await msg.reply_text("⏳ **Fetching your file...**", parse_mode="Markdown")

    try:
        response = requests.get(API_URL.format(text), timeout=30)
        data = response.json()

        if data.get("success") and data.get("data"):
            file_data = data["data"][0]
            file_name = file_data.get("file_name", "Unknown")
            file_size = file_data.get("file_size", "Unknown")
            download_url = file_data.get("download_url")
            stream_url = file_data.get("stream_final_url") or file_data.get("stream_url")
            thumbnail = file_data.get("thumbnail")
            extension = file_data.get("extension", "")

            caption = f"📁 **{file_name}**\n💾 **Size:** {file_size}\n📎 **Type:** {extension or 'File'}"

            keyboard = []
            if download_url:
                keyboard.append([InlineKeyboardButton("📥 Download", url=download_url)])
            if stream_url:
                keyboard.append([InlineKeyboardButton("🎬 Stream", url=stream_url)])

            # Send with thumbnail if available
            if thumbnail:
                try:
                    thumb_req = requests.get(thumbnail, timeout=10)
                    if thumb_req.status_code == 200:
                        await msg.reply_photo(
                            photo=thumb_req.content,
                            caption=caption,
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                        )
                    else:
                        await msg.reply_text(
                            caption,
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                            disable_web_page_preview=True
                        )
                except:
                    await msg.reply_text(
                        caption,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                        disable_web_page_preview=True
                    )
            else:
                await msg.reply_text(
                    caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                    disable_web_page_preview=True
                )
        else:
            await processing.edit_text("❌ Failed to fetch file.\nPossible reasons:\n- Invalid link\n- API limit reached\n- Try again later")

    except Exception as e:
        print(f"Error: {e}")
        await processing.edit_text("⚠️ An error occurred. Please try again later.")

    await processing.delete()

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
