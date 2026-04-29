import os
import logging
import requests
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0)) # এডমিন আইডি Environment Variable থেকে নেবে
API_ENDPOINT = "https://gold-newt-367030.hostingersite.com/tera.php?url="

# ================= ডাটাবেস সেটআপ =================
def init_db():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    referred_by INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    premium_until TEXT,
                    links_today INTEGER DEFAULT 0,
                    last_link_date TEXT
                )''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_user(user_id, referred_by=None):
    if not get_user(user_id):
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referred_by))
        conn.commit()
        conn.close()
        return True
    return False

def add_premium(user_id, days):
    user = get_user(user_id)
    if user:
        current_premium = user[3]
        if current_premium and datetime.fromisoformat(current_premium) > datetime.now():
            new_date = datetime.fromisoformat(current_premium) + timedelta(days=days)
        else:
            new_date = datetime.now() + timedelta(days=days)
        
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute("UPDATE users SET premium_until=? WHERE user_id=?", (new_date.isoformat(), user_id))
        conn.commit()
        conn.close()

# ================= ইউজার কমান্ডস =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # রেফারেল চেক
    referred_by = None
    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user_id:
            referred_by = ref_id

    # নতুন ইউজার হলে ডাটাবেসে যুক্ত করা
    if add_user(user_id, referred_by):
        if referred_by:
            # রেফারার এর রেফার কাউন্ট বাড়ানো
            conn = sqlite3.connect('bot_database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?", (referred_by,))
            conn.commit()
            
            # রেফারার এর ৩ টা রেফারেল পূর্ণ হলে ৭ দিন প্রিমিয়াম
            ref_user = get_user(referred_by)
            if ref_user and ref_user[2] % 3 == 0:
                add_premium(referred_by, 7)
                try:
                    await context.bot.send_message(chat_id=referred_by, text="🎉 **অভিনন্দন!** আপনার ৩টি রেফারেল পূর্ণ হয়েছে। আপনি ৭ দিনের জন্য **Premium** পেয়েছেন!")
                except:
                    pass
            conn.close()

    welcome_text = (
        f"👋 **স্বাগতম, {update.effective_user.first_name}!**\n\n"
        "আমি TeraBox Downloader বট।\n"
        "🔸 **ফ্রি ইউজার:** দিনে ৫টি লিঙ্ক খুলতে পারবেন।\n"
        "🔸 **প্রিমিয়াম ইউজার:** আনলিমিটেড!\n\n"
        "আপনার রেফারেল লিঙ্ক পেতে `/myaccount` টাইপ করুন।"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        return await update.message.reply_text("দয়া করে আগে /start কমান্ড দিন।")

    bot_username = context.bot.username
    refer_link = f"https://t.me/{bot_username}?start={user_id}"
    
    is_premium = False
    if user[3] and datetime.fromisoformat(user[3]) > datetime.now():
        is_premium = True
        prem_date = datetime.fromisoformat(user[3]).strftime('%Y-%m-%d %H:%M')
    
    status = "🌟 Premium" if is_premium else "👤 Free User"
    validity = f"পর্যন্ত: {prem_date}" if is_premium else "(দিনে ৫টি লিঙ্ক)"
    
    msg = (
        f"📊 **আপনার একাউন্ট তথ্য:**\n\n"
        f"**স্ট্যাটাস:** {status} {validity}\n"
        f"**আজকের লিঙ্ক ব্যবহার:** {user[4]}/5\n"
        f"**মোট রেফার করেছেন:** {user[2]} জন\n\n"
        f"🎁 **আপনার রেফারেল লিঙ্ক:**\n`{refer_link}`\n\n"
        f"*(৩ জনকে রেফার করলেই পাবেন ৭ দিনের ফ্রি প্রিমিয়াম!)*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= মূল ডাউনলোডার =================
async def handle_terabox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text
    
    if "terabox" not in url and "nephobox" not in url:
        return await update.message.reply_text("❌ এটি সঠিক TeraBox লিঙ্ক নয়।")

    user = get_user(user_id)
    if not user:
        add_user(user_id)
        user = get_user(user_id)

    today_str = datetime.now().date().isoformat()
    is_premium = user[3] and datetime.fromisoformat(user[3]) > datetime.now()
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()

    # দিন পার হলে লিমিট রিসেট করা
    if user[5] != today_str:
        c.execute("UPDATE users SET links_today=0, last_link_date=? WHERE user_id=?", (today_str, user_id))
        conn.commit()
        user = get_user(user_id) # রিফ্রেশ

    # লিমিট চেক
    if not is_premium and user[4] >= 5:
        conn.close()
        return await update.message.reply_text("⚠️ **আপনার আজকের ৫টি ফ্রি লিঙ্কের লিমিট শেষ!**\n\nআনলিমিটেড লিঙ্ক খুলতে আপনার বন্ধুদের রেফার করুন। রেফার লিঙ্ক পেতে `/myaccount` এ ক্লিক করুন।", parse_mode="Markdown")

    status_msg = await update.message.reply_text("🔎 **প্রসেসিং হচ্ছে...**")

    try:
        response = requests.get(f"{API_ENDPOINT}{url}", timeout=15).json()
        if response.get("success"):
            # লিঙ্ক সাকসেস হলে লিমিট ১ বাড়ানো
            if not is_premium:
                c.execute("UPDATE users SET links_today = links_today + 1 WHERE user_id=?", (user_id,))
                conn.commit()

            file_data = response["data"][0]
            caption = (f"✅ **ফাইল পাওয়া গেছে!**\n\n📂 **নাম:** `{file_data['file_name']}`\n⚖️ **সাইজ:** {file_data['file_size']}")
            keyboard = [
                [InlineKeyboardButton("📺 অনলাইন স্ট্রিম", web_app=WebAppInfo(url=file_data['stream_final_url']))],
                [InlineKeyboardButton("📥 ডাউনলোড", url=file_data['download_url'])]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await status_msg.delete()
            await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await status_msg.edit_text("❌ ফাইলটি খুঁজে পাওয়া যায়নি বা লিঙ্কটি এক্সপায়ার হয়ে গেছে।")
    except Exception as e:
        await status_msg.edit_text("⚠️ সার্ভারে সমস্যা হচ্ছে। পরে চেষ্টা করুন।")
    finally:
        conn.close()

# ================= এডমিন প্যানেল =================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"📈 **বট স্ট্যাটাস:**\nমোট ইউজার: {total_users} জন", parse_mode="Markdown")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg_to_send = " ".join(context.args)
    if not msg_to_send:
        return await update.message.reply_text("ব্যবহারের নিয়ম: `/broadcast আপনাদের মেসেজ এখানে`", parse_mode="Markdown")
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()

    success, fail = 0, 0
    await update.message.reply_text("📢 ব্রডকাস্ট শুরু হয়েছে...")
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=msg_to_send)
            success += 1
        except:
            fail += 1
    await update.message.reply_text(f"✅ ব্রডকাস্ট শেষ!\nসফল: {success}\nব্যর্থ: {fail}")

if __name__ == "__main__":
    init_db()
    if not TOKEN:
        print("❌ Error: TELEGRAM_TOKEN missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("myaccount", my_account))
        app.add_handler(CommandHandler("stats", admin_stats))
        app.add_handler(CommandHandler("broadcast", admin_broadcast))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_terabox))
        print("✅ Bot with DB is running...")
        app.run_polling()
  
