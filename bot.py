import os
import telebot
import requests
import pymongo
import pandas as pd
import io
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

# --- API Endpoints from Document ---
# [span_0](start_span)[span_1](start_span)Thai Stock 2D API Document အရ လိပ်စာများကို မှန်ကန်အောင် ပြင်ဆင်ထားသည်[span_0](end_span)[span_1](end_span)
LIVE_API = "https://api.thaistock2d.com/live" 
HISTORY_API = "https://api.thaistock2d.com/2d_result" 

# --- Database & User Functions ---
def register_user(m):
    user_data = {
        "_id": m.chat.id,
        "username": m.from_user.username or "N/A",
        "name": m.from_user.first_name or "N/A",
        "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active"
    }
    users_col.update_one({"_id": m.chat.id}, {"$set": user_data}, upsert=True)

# --- Keyboard Menus ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 2D History", "📊 3D History")
    markup.add("👤 User Info", "⚙️ Admin Panel")
    return markup

# --- Result Alert Functions ---
def send_auto_result():
    try:
        # [span_2](start_span)API.thaistock2d.com/live မှ ဒေတာရယူခြင်း[span_2](end_span)
        data = requests.get(LIVE_API).json()
        live = data['live']
        # [span_3](start_span)Live result တွင် SET, Value နှင့် 2D ရလဒ်များ ပါဝင်သည်[span_3](end_span)
        msg = (f"🎯 2D Live Result ({live['time']})\n\n"
               f"SET: {live['set']}\nVALUE: {live['value']}\n"
               f"2D: {live['twod']}")
        
        active_users = users_col.find({"status": "active"})
        for user in active_users:
            try:
                bot.send_message(user['_id'], msg)
            except:
                users_col.update_one({"_id": user['_id']}, {"$set": {"status": "blocked"}})
    except Exception as e:
        print(f"Alert error: {e}")

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
def welcome(m):
    register_user(m)
    bot.send_message(m.chat.id, "2D/3D Bot မှ ကြိုဆိုပါသည်။", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📊 2D History")
def history_2d(m):
    bot.send_message(m.chat.id, "နောက်ဆုံး ၁၀ ရက်စာ 2D ရလဒ်များကို ဆွဲယူနေပါသည်။")
    try:
        # [span_4](start_span)2D result API သည် နောက်ဆုံး ၁၀ ရက်စာ မှတ်တမ်းကို ပေးနိုင်သည်[span_4](end_span)
        data = requests.get(HISTORY_API).json()
        res_text = "📊 2D Result History (Last 10 Days)\n\n"
        for day in data[:5]:
            res_text += f"📅 Date: {day.get('date', 'N/A')}\n"
            for c in day.get('child', []):
                res_text += f"⏰ {c['time']}: {c['twod']}\n"
            res_text += "------------------\n"
        bot.send_message(m.chat.id, res_text)
    except:
        bot.send_message(m.chat.id, "မှတ်တမ်း ရယူ၍ မရနိုင်ပါ။")

@bot.message_handler(func=lambda m: m.text == "📊 3D History")
def history_3d(m):
    bot.send_message(m.chat.id, "3D မှတ်တမ်း Feature ကို မကြာမီ ထည့်သွင်းပေးပါမည်။")

@bot.message_handler(func=lambda m: m.text == "👤 User Info")
def user_info(m):
    user = users_col.find_one({"_id": m.chat.id})
    if user:
        info = (f"👤 **User Info**\n\n"
                f"🆔 ID: `{user['_id']}`\n"
                f"🏷 Name: {user['name']}\n"
                f"🔗 Username: @{user['username']}\n"
                f"📅 Join Date: {user['joined_at']}\n"
                f"🟢 Status: {user['status']}")
        bot.send_message(m.chat.id, info, parse_mode="Markdown")

# --- Admin Panel & Broadcast ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_panel(m):
    if m.chat.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Broadcast (Ads)", callback_data="bc"))
    markup.add(types.InlineKeyboardButton("📥 Export Users (CSV)", callback_data="csv"))
    bot.send_message(m.chat.id, "Admin Control Panel", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def admin_actions(call):
    if call.data == "bc":
        msg = bot.send_message(call.message.chat.id, "📢 ကြော်ငြာရန် ပုံ သို့မဟုတ် စာ ပို့ပေးပါ။ (Caption ထည့်နိုင်သည်)")
        bot.register_next_step_handler(msg, do_broadcast)
    elif call.data == "csv":
        users = list(users_col.find())
        df = pd.DataFrame(users)
        stream = io.BytesIO()
        df.to_csv(stream, index=False)
        stream.seek(0)
        bot.send_document(call.message.chat.id, stream, visible_file_name="users.csv")

def do_broadcast(m):
    users = users_col.find({"status": "active"})
    success = 0
    for u in users:
        try:
            if m.content_type == 'photo':
                bot.send_photo(u['_id'], m.photo[-1].file_id, caption=m.caption)
            else:
                bot.send_message(u['_id'], m.text)
            success += 1
        except:
            users_col.update_one({"_id": u['_id']}, {"$set": {"status": "blocked"}})
    bot.send_message(ADMIN_ID, f"ကြော်ငြာပို့ပြီးပါပြီ။ အောင်မြင်သူ: {success}")

# --- Scheduler ---
scheduler = BackgroundScheduler()
# နေ့စဉ် ၁၂:၀၁ နှင့် ၄:၃၀ တွင် ရလဒ်ပို့ပေးရန်
scheduler.add_job(send_auto_result, 'cron', hour=12, minute=1)
scheduler.add_job(send_auto_result, 'cron', hour=16, minute=30)
scheduler.start()

if __name__ == "__main__":
    print("Bot is started...")
    bot.infinity_polling()
