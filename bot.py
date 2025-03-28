from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from flask import Flask, request
import threading
import os
from datetime import datetime, timedelta

# إعدادات التوكنات
TWILIO_ACCOUNT_SID = 'AC82a9ac4f93dcb0a58f1efe9e0dddc0ae'
TWILIO_AUTH_TOKEN = '9d3b9a71dbb817a03af8d2ca12db9cdc'
TWILIO_PHONE_NUMBER = '+17074566030'
TELEGRAM_BOT_TOKEN = '7740770829:AAHln4sG5uHfXuf-E_HsKs7fTiWRsaiOQNs'
SERVER_URL = 'https://your-server-url.com'  # استبدل برابط خادمك

# تهيئة العملاء
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = Flask(__name__)

# متغير لتخزين حالات المكالمات
call_statuses = {}

# دوال التليجرام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('مرحباً! أرسل لي رقم الهاتف وسأقوم بالاتصال به وتسجيل المكالمة.')

async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    phone_number = update.message.text
    chat_id = update.message.chat_id

    if not phone_number.startswith('+'):
        await update.message.reply_text("❌ الرجاء كتابة الرقم مع رمز الدولة (مثال: +964123456789)")
        return

    try:
        # تخزين وقت بدء المكالمة
        call_statuses[chat_id] = {
            'status': 'calling',
            'start_time': datetime.now()
        }

        call = twilio_client.calls.create(
            url=f'{SERVER_URL}/twiml?user_id={chat_id}',
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            record=True,
            status_callback=f'{SERVER_URL}/status_callback?user_id={chat_id}',
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        
        await update.message.reply_text(f"✅ تم بدء الاتصال بالرقم {phone_number}.")
        
        # بدء مؤقت لمتابعة عدم الرد
        threading.Timer(15, check_call_status, args=[chat_id]).start()
        
    except Exception as e:
        await update.message.reply_text(f"❌ فشل الاتصال. الخطأ: {str(e)}")

def check_call_status(chat_id):
    if chat_id in call_statuses and call_statuses[chat_id]['status'] == 'calling':
        send_telegram_message(chat_id, "⏳ لم يتم الرد على الاتصال بعد 15 ثانية")

# واجهات ويب لـ Twilio
@app.route('/twiml', methods=['GET'])
def generate_twiml():
    response = VoiceResponse()
    response.say("مرحباً، هذه مكالمة مسجلة. سيتم تسجيل هذه المحادثة.")
    response.record(timeout=10, playBeep=True, action='/recording')
    return str(response)

@app.route('/status_callback', methods=['POST'])
def status_callback():
    call_status = request.form.get('CallStatus')
    chat_id = request.args.get('user_id')
    
    if chat_id not in call_statuses:
        return 'OK', 200
    
    if call_status == 'answered':
        call_statuses[chat_id]['status'] = 'answered'
        send_telegram_message(chat_id, "📞 تم الرد على الاتصال")
    elif call_status == 'completed':
        duration = request.form.get('CallDuration')
        if duration == '0':
            send_telegram_message(chat_id, "❌ تم رفض الاتصال")
        call_statuses.pop(chat_id, None)
    
    return 'OK', 200

@app.route('/recording', methods=['POST'])
def handle_recording():
    recording_url = request.form.get('RecordingUrl')
    chat_id = request.args.get('user_id')
    
    if recording_url and chat_id:
        send_recording_to_telegram(chat_id, recording_url + ".mp3")
    
    return 'OK', 200

# إرسال رسائل للتليجرام
def send_telegram_message(chat_id, text):
    try:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={'chat_id': chat_id, 'text': text}
        )
    except Exception as e:
        print(f"Failed to send message: {e}")

def send_recording_to_telegram(chat_id, recording_url):
    try:
        audio_data = requests.get(recording_url).content
        files = {'audio': ('call_recording.mp3', audio_data, 'audio/mpeg')}
        data = {'chat_id': chat_id}
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio',
            files=files,
            data=data
        )
    except Exception as e:
        print(f"Failed to send recording: {e}")

# تشغيل الخادمين
def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))
    
    print("✅ البوت يعمل على الخادم!")
    application.run_polling()