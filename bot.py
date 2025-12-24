import os
import telebot
import requests
import pymongo
import pandas as pd
import io
import threading
import time
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

@app.route('/')
def home():
    return "Bot is active and running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Thai Stock 2D API Endpoints ---
[span_3](start_span)LIVE_API = "https://api.thaistock2d.com/live"[span_3](end_span)
[span_4](start_span)HISTORY_2D_API = "https://api.thaistock2d.com/2d_result"[span_4](end_span)

# --- Keyboard Menus (Admin/User ခွဲခြားခြင်း) ---
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 2D History", "📊 3D History")
    if user_id == ADMIN_ID:
        markup.add("👤 My Info", "⚙️ Admin Panel")
    else:
        markup.add("👤 My Info")
    return markup

# --- Result Alert Functions ---
def send_auto_result():
    try:
        [span_5](start_span)data = requests.get(LIVE_API).json()[span_5](end_span)
        [span_6](start_span)live = data['live'][span_6](end_span)
        msg = (f"🔔 **2D/3D ထွက်ဂဏန်း အချက်ပေးစနစ်**\n\n"
               f"📅 နေ့စွဲ: {live['time']}\n"
               f"--------------------------\n"
               f"🎯 2D: **{live['twod']}**\n"
               f"📊 SET: {live['set']}\n"
               f"💰 VALUE: {live['value']}\n"
               f"--------------------------\n"
               [span_7](start_span)[span_8](start_span)f"နေ့စဉ် 11:00, 12:01, 3:00, 4:30 တို့တွင် အခမဲ့ ပို့ပေးပါမည်။")[span_7](end_span)[span_8](end_span)
        
        active_users = users_col.find({"status": "active"})
        for user in active_users:
            try:
                bot.send_message(user['_id'], msg, parse_mode="Markdown")
            except:
                users_col.update_one({"_id": user['_id']}, {"$set": {"status": "blocked"}})
    except Exception as e:
        print(f"Alert error: {e}")

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
def welcome(m):
    # Register User
    user_data = {
        "_id": m.chat.id,
        "username": m.from_user.username or "N/A",
        "name": m.from_user.first_name or "N/A",
        "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active"
    }
    users_col.update_one({"_id": m.chat.id}, {"$set": user_data}, upsert=True)
    
    greeting = (f"🙏 **မင်္ဂလာပါ {m.from_user.first_name}!**\n\n"
                "ယခုအချိန်မှစတင်၍ နေ့စဉ် ထွက်ရှိသမျှသော **2D/3D Results** များကို "
                [span_9](start_span)"အောက်ပါအချိန်များအတိုင်း တိကျမှန်ကန်စွာ အခမဲ့ ပေးပို့ပေးသွားပါမည်။[span_9](end_span)\n\n"
                "⏰ 11:00 AM | 12:01 PM\n"
                "⏰ 03:00 PM | 04:30 PM\n\n"
                [span_10](start_span)"အောက်ပါ Menu ခလုတ်များကို အသုံးပြု၍ မှတ်တမ်းများကို ကြည့်ရှုနိုင်ပါသည်။")[span_10](end_span)
    bot.send_message(m.chat.id, greeting, reply_markup=get_main_menu(m.chat.id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 2D History")
def h2d(m):
    bot.send_message(m.chat.id, "⌛ 2D မှတ်တမ်းများကို ဆွဲယူနေပါသည်။")
    try:
        [span_11](start_span)data = requests.get(HISTORY_2D_API).json()[span_11](end_span)
        [span_12](start_span)res_text = "📊 **2D Result History (နောက်ဆုံး ၁၀ ရက်)**\n\n"[span_12](end_span)
        for day in data[:7]:
            res_text += f"📅 **{day.get('date', 'N/A')}**\n"
            for c in day.get('child', []):
                res_text += f"🔹 {c['time']}: `{c['twod']}`\n"
            res_text += "------------------\n"
        bot.send_message(m.chat.id, res_text, parse_mode="Markdown")
    except:
        bot.send_message(m.chat.id, "❌ မှတ်တမ်း ရယူ၍ မရနိုင်ပါ။")

@bot.message_handler(func=lambda m: m.text == "📊 3D History")
def h3d(m):
    bot.send_message(m.chat.id, "⌛ 3D မှတ်တမ်းများကို ဆွဲယူနေပါသည်။")
    try:
        # Live API ထဲမှ Result data များကို အခြေခံ၍ ပြသခြင်း
        [span_13](start_span)data = requests.get(LIVE_API).json()[span_13](end_span)
        res_text = "📊 **လက်ရှိ 3D/Result အခြေအနေ**\n\n"
        res_text += f"🕒 အချိန်: {data['live']['time']}\n"
        [span_14](start_span)res_text += f"🎯 ထွက်ဂဏန်း: `{data['live']['twod']}`"[span_14](end_span)
        bot.send_message(m.chat.id, res_text, parse_mode="Markdown")
    except:
        bot.send_message(m.chat.id, "❌ 3D မှတ်တမ်း ရယူရန် အခက်အခဲ ရှိနေပါသည်။")

@bot.message_handler(func=lambda m: m.text == "👤 User Info")
def user_info(m):
    user = users_col.find_one({"_id": m.chat.id})
    if user:
        info = (f"👤 **Your Account Info**\n\n"
                f"🆔 ID: `{user['_id']}`\n"
                f"🏷 Name: {user['name']}\n"
                f"📅 Join Date: {user['joined_at']}\n"
                f"🟢 Status: {user['status']}")
        bot.send_message(m.chat.id, info, parse_mode="Markdown")

# --- Admin Panel ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_p(m):
    if m.chat.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Broadcast (Ads)", callback_data="bc"))
    markup.add(types.InlineKeyboardButton("📥 Export CSV", callback_data="csv"))
    bot.send_message(m.chat.id, "🛠 **Admin Control Panel**", reply_markup=markup, parse_mode="Markdown")

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
        bot.send_document(call.message.chat.id, stream, visible_file_name="users_report.csv")

def do_broadcast(m):
    start_time = time.time()
    all_users = list(users_col.find())
    total = len(all_users)
    success, blocked, failed = 0, 0, 0
    
    for u in all_users:
        try:
            if m.content_type == 'photo':
                bot.send_photo(u['_id'], m.photo[-1].file_id, caption=m.caption)
            else:
                bot.send_message(u['_id'], m.text)
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
              f"👥 Total Users: {total}\n"
              f"✅ Success: {success}\n"
              f"🚫 Blocked (Skipped): {blocked}\n"
              f"❌ Failed: {failed}")
    bot.send_message(ADMIN_ID, report, parse_mode="Markdown")

# --- Scheduler ---
scheduler = BackgroundScheduler()
# [span_15](start_span)နေ့စဉ်ရလဒ်များကို အချိန်မှန်ပို့ပေးရန် (API Document ပါ အချိန်များ)[span_15](end_span)
times = [("11", "05"), ("12", "05"), ("15", "05"), ("16", "35")]
for h, m in times:
    scheduler.add_job(send_auto_result, 'cron', hour=h, minute=m)
scheduler.start()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
