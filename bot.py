import os
import telebot
import requests
import pymongo
import pandas as pd
import io
import threading
import time
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask
from datetime import datetime
from telebot import types
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler

# --- Environment Variables ---
TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(TOKEN)
client = MongoClient(MONGO_URI)
db = client['lottery_db']
users_col = db['users']

app = Flask(__name__)
scraper = cloudscraper.create_scraper()

@app.route('/')
def home():
    return "Bot is active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Endpoints ---
LIVE_2D_API = "https://api.thaistock2d.com/live"
HISTORY_2D_API = "https://api.thaistock2d.com/2d_result"
THREED_URL = "https://www.thaistock2d.com/threedResult"

# --- 3D Scraping Function ---
def get_3d_from_web():
    try:
        res = scraper.get(THREED_URL, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        # ဝဘ်ဆိုဒ်၏ table ထဲမှ ပထမဆုံး row ရှိ 3D ဂဏန်းကို ရှာခြင်း
        rows = soup.find_all('tr')
        if len(rows) > 1:
            cols = rows[1].find_all('td')
            if len(cols) >= 2:
                date = cols[0].text.strip()
                result = cols[1].text.strip()
                return f"📅 နေ့စွဲ: {date}\n🎯 3D ရလဒ်: **{result}**"
        return "ယနေ့အတွက် 3D ရလဒ် မထွက်သေးပါ။"
    except:
        return "❌ 3D ဝဘ်ဆိုဒ်ကို ချိတ်ဆက်၍ မရနိုင်ပါ။"

# --- Menus ---
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 2D History", "📊 3D History")
    if user_id == ADMIN_ID:
        markup.add("👤 My Info", "⚙️ Admin Panel")
    else:
        markup.add("👤 My Info")
    return markup

# --- Auto Alert (2D/3D) ---
def send_auto_result():
    try:
        # 2D Alert
        data = requests.get(LIVE_2D_API).json()
        live = data['live']
        msg_2d = (f"🎯 **2D Live Update**\n\n"
                  f"⏰ အချိန်: {live['time']}\n"
                  f"🔢 2D: **{live['twod']}**\n"
                  f"📊 SET: {live['set']} | VALUE: {live['value']}")
        
        # 3D Alert (Web Scraping)
        threed_msg = get_3d_from_web()
        
        active_users = users_col.find({"status": "active"})
        for user in active_users:
            try:
                bot.send_message(user['_id'], f"{msg_2d}\n\n------------------\n📊 **3D Status**\n{threed_msg}", parse_mode="Markdown")
            except:
                users_col.update_one({"_id": user['_id']}, {"$set": {"status": "blocked"}})
    except Exception as e:
        print(f"Alert error: {e}")

# --- Handlers ---
@bot.message_handler(commands=['start'])
def welcome(m):
    user_data = {"_id": m.chat.id, "username": m.from_user.username or "N/A", "name": m.from_user.first_name or "N/A", "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
    users_col.update_one({"_id": m.chat.id}, {"$set": user_data}, upsert=True)
    
    greeting = (f"🙏 **မင်္ဂလာပါ {m.from_user.first_name}!**\n\n"
                "ယခုအချိန်မှစတင်ပြီး နေ့စဉ် **2D/3D Results** များကို "
                "သင့်ထံသို့ တိကျမှန်ကန်စွာ အခမဲ့ ပေးပို့ပေးသွားပါမည်။\n\n"
                "⏰ 11:00 AM | 12:01 PM\n"
                "⏰ 03:00 PM | 04:30 PM")
    bot.send_message(m.chat.id, greeting, reply_markup=get_main_menu(m.chat.id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 2D History")
def h2d(m):
    bot.send_message(m.chat.id, "⌛ 2D မှတ်တမ်းများကို ဆွဲယူနေပါသည်။")
    try:
        data = requests.get(HISTORY_2D_API).json()
        res_text = "📊 **2D Result History (Last 10 Days)**\n\n"
        for day in data[:7]:
            res_text += f"📅 **{day.get('date', 'N/A')}**\n"
            for c in day.get('child', []):
                res_text += f"🔹 {c['time']}: `{c['twod']}`\n"
            res_text += "------------------\n"
        bot.send_message(m.chat.id, res_text, parse_mode="Markdown")
    except: bot.send_message(m.chat.id, "❌ 2D မှတ်တမ်း မရရှိနိုင်ပါ။")

@bot.message_handler(func=lambda m: m.text == "📊 3D History")
def h3d(m):
    bot.send_message(m.chat.id, "⌛ 3D နောက်ဆုံးရလဒ်ကို ဆွဲယူနေပါသည်။")
    res = get_3d_from_web()
    bot.send_message(m.chat.id, f"📊 **3D History/Result**\n\n{res}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 My Info")
def user_info(m):
    user = users_col.find_one({"_id": m.chat.id})
    if user:
        info = (f"👤 **Account Info**\n🆔 ID: `{user['_id']}`\n🏷 Name: {user['name']}\n🟢 Status: {user['status']}")
        bot.send_message(m.chat.id, info, parse_mode="Markdown")

# --- Admin Panel ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_p(m):
    if m.chat.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Broadcast (Ads)", callback_data="bc"))
    markup.add(types.InlineKeyboardButton("📥 Export CSV", callback_data="csv"))
    bot.send_message(m.chat.id, "🛠 **Admin Panel**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def admin_call(call):
    if call.data == "bc":
        msg = bot.send_message(call.message.chat.id, "📢 ကြော်ငြာရန် ပုံ သို့မဟုတ် စာ ပို့ပေးပါ။")
        bot.register_next_step_handler(msg, do_broadcast)
    elif call.data == "csv":
        df = pd.DataFrame(list(users_col.find()))
        stream = io.BytesIO()
        df.to_csv(stream, index=False)
        stream.seek(0)
        bot.send_document(call.message.chat.id, stream, visible_file_name="users.csv")

def do_broadcast(m):
    start_time = time.time()
    all_users = list(users_col.find())
    success, blocked, failed = 0, 0, 0
    
    for u in all_users:
        try:
            if m.content_type == 'photo': bot.send_photo(u['_id'], m.photo[-1].file_id, caption=m.caption)
            else: bot.send_message(u['_id'], m.text)
            success += 1
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403:
                blocked += 1
                users_col.update_one({"_id": u['_id']}, {"$set": {"status": "blocked"}})
            else: failed += 1
        except: failed += 1
    
    duration = round(time.time() - start_time, 2)
    report = (f"✅ **Broadcast Completed!**\n\n"
              f"⏱ Time: {duration}s\n"
              f"👥 Total Users: {len(all_users)}\n"
              f"✅ Success: {success}\n"
              f"🚫 Blocked (Skipped): {blocked}\n"
              f"❌ Failed: {failed}")
    bot.send_message(ADMIN_ID, report, parse_mode="Markdown")

# --- Scheduler ---
scheduler = BackgroundScheduler()
# API ထွက်ချိန်များ (11:02, 12:02, 15:02, 16:32)
alert_times = [("11", "02"), ("12", "02"), ("15", "02"), ("16", "32")]
for h, mi in alert_times:
    scheduler.add_job(send_auto_result, 'cron', hour=h, minute=mi)
scheduler.start()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
