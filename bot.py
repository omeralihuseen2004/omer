import asyncio
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Record
from flask import Flask, request
import requests
from datetime import datetime

# التوكنات (يجب تغييرها لمتغيرات البيئة في الإنتاج)
TWILIO_ACCOUNT_SID = 'AC82a9ac4f93dcb0a58f1efe9e0dddc0ae'
TWILIO_AUTH_TOKEN = '9d3b9a71dbb817a03af8d2ca12db9cdc'
TWILIO_PHONE_NUMBER = '+17074566030'
TELEGRAM_BOT_TOKEN = '7740770829:AAHln4sG5uHfXuf-E_HsKs7fTiWRsaiOQNs'
PUBLIC_URL = 'https://demo.twilio.com/welcome/voice/'  # يجب استبداله برابطك

# تهيئة Flask
app = Flask(__name__)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

class BotRunner:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        self.telegram_app.add_handler(CommandHandler("start", self.start))
        self.telegram_app.add_handler(MessageHandler(filters.TEXT, self.handle_call))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("أرسل رقم الهاتف (+966...) ليتصل البوت ويسجل المكالمة")

    async def handle_call(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        phone = update.message.text
        if not phone.startswith('+'):
            await update.message.reply_text("⚠️ استخدم الصيغة الدولية (+966...)")
            return
        
        try:
            call = twilio_client.calls.create(
                record=True,
                recording_status_callback=f'{PUBLIC_URL}/recording_callback?chat_id={update.message.chat_id}',
                url=f'{PUBLIC_URL}/twiml?chat_id={update.message.chat_id}',
                to=phone,
                from_=TWILIO_PHONE_NUMBER
            )
            await update.message.reply_text(f"🎙️ جاري الاتصال بـ {phone}...")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")

    def run_bot(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.telegram_app.run_polling())

# --- مسارات Flask ---
@app.route('/twiml', methods=['GET'])
def twiml():
    chat_id = request.args.get('chat_id')
    response = VoiceResponse()
    response.say("مرحبًا، هذه مكالمة مسجلة. سيبدأ التسجيل بعد الصافرة", voice='woman', language='ar-SA')
    response.pause(length=2)
    response.record(
        action=f'{PUBLIC_URL}/recording_end?chat_id={chat_id}',
        playBeep=True,
        maxLength=300
    )
    return str(response)

@app.route('/recording_end', methods=['POST'])
def recording_end():
    chat_id = request.args.get('chat_id')
    recording_url = request.form.get('RecordingUrl')
    
    if recording_url:
        recording_details = {
            'url': recording_url,
            'duration': request.form.get('RecordingDuration'),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': f'🎧 تم تسجيل المكالمة:\n⏳ المدة: {recording_details["duration"]} ثانية\n📅 التاريخ: {recording_details["timestamp"]}\n🔗 الرابط: {recording_url}'
            }
        )
    
    response = VoiceResponse()
    response.say("شكرًا لك، تم إنهاء المكالمة", voice='woman', language='ar-SA')
    response.hangup()
    return str(response)

@app.route('/recording_callback', methods=['POST'])
def recording_callback():
    recording_url = request.form.get('RecordingUrl')
    chat_id = request.args.get('chat_id')
    
    if recording_url and chat_id:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': f'✅ تم اكتمال تسجيل المكالمة:\n🔗 {recording_url}'
            }
        )
    return '', 200

def run_flask():
    app.run(host='0.0.0.0', port=8080, use_reloader=False)

# جعل المتغيرات متاحة للاستيراد
flask_thread = None
bot_runner = None

if __name__ == '__main__':
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot_runner = BotRunner()
    bot_runner.run_bot()