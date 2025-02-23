import logging, os
import uuid
from flask import Flask, request
from pyrogram import Client
from dotenv import load_dotenv
from upload_handler import TelegramUploader

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


# Load environment variables
load_dotenv()

# Get configuration from environment variables
TELEGRAM_API = os.getenv("TELEGRAM_API_ID")
TELEGRAM_HASH = os.getenv("TELEGRAM_API_HASH")
CHAT_ID = int(os.getenv("TELEGRAM_DEFAULT_CHAT_ID"))
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
APP_API_KEY = os.getenv("APP_API_KEY")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

telegram_uploader = TelegramUploader(TELEGRAM_API, TELEGRAM_HASH, BOT_TOKEN, logger=logger)

app = Flask(__name__)


@app.route('/send_msg')
def send_message():
    data = request.json
    if data.get('key') != APP_API_KEY:
        return {'status': 'failed'}, 500
    logger.info(data)
    chat_id = data.get('peer')
    text = data.get('text')
    telegram_uploader.client.send_message(chat_id=chat_id, text=text)
    return {'status': 'ok'}


@app.route('/send_file', methods=['POST'])
def upload_file():
    data = request.json
    logger.info(data)
    if data.get('key') != APP_API_KEY:
        return {'status': 'failed', 'error': 'invalid key'}, 500
    if not data.get('peer'):
        return {'status': 'failed', 'error': 'peer is required'}, 500
    if not data.get('file_path') and not data.get('file_url'):
        return {'status': 'failed', 'error': 'file_path or file_url is required'}, 500
    
    chat_id = data.get('peer')
    if data.get('file_url'):
        file_url = data.get('file_url')
        file_path = telegram_uploader.download_file_url(file_url, '{}.txt'.format(uuid.uuid4()))
    else:
        file_path = data.get('file_path')
    telegram_uploader.upload_file(file_path, chat_id)
    return {'status': 'ok', 'message': 'file has been uploaded to {}'.format(chat_id)}


@app.route('/')
def index():
    telegram_uploader.client.send_message(chat_id=CHAT_ID, text='Health Checker')
    return {'status': 'ok'}

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)