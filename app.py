import logging, os
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from upload_handler import TelegramUploader
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils import (
    load_connections,
    save_connections,
    validate_cron,
    backup_database,
    initialize_scheduler
)

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
scheduler = BackgroundScheduler()

app = Flask(__name__)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {'status': 'failed', 'error': 'Missing or invalid Authorization header. Use Bearer token'}, 401
        
        token = auth_header.split('Bearer ')[1].strip()
        if token != APP_API_KEY:
            return {'status': 'failed', 'error': 'Invalid API key'}, 401
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/send_msg')
@require_api_key
def send_message():
    data = request.json
    logger.info(data)
    chat_id = data.get('peer')
    text = data.get('text')
    telegram_uploader.client.send_message(chat_id=chat_id, text=text)
    return {'status': 'ok'}

@app.route('/send_file', methods=['POST'])
@require_api_key
def upload_file():
    data = request.json
    logger.info(data)
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

@app.route('/connections', methods=['GET'])
@require_api_key
def list_connections():
    data = load_connections()
    return jsonify(data)

@app.route('/connections', methods=['POST'])
@require_api_key
def add_connection():
    data = request.json
    if not all(k in data for k in ['name', 'db_url', 'cron_schedule']):
        return {'status': 'failed', 'error': 'Missing required fields'}, 400
    
    if not validate_cron(data['cron_schedule']):
        return {'status': 'failed', 'error': 'Invalid cron expression'}, 400
    
    connections = load_connections()
    new_connection = {
        'id': str(uuid.uuid4()),
        'name': data['name'],
        'db_url': data['db_url'],
        'cron_schedule': data['cron_schedule'],
        'created_at': datetime.now().isoformat(),
        'last_run_at': None
    }
    
    connections['connections'].append(new_connection)
    save_connections(connections)
    
    # Schedule the new connection
    job_id = f"backup_{new_connection['id']}"
    scheduler.add_job(
        lambda conn: backup_database(conn, telegram_uploader, CHAT_ID),
        trigger=CronTrigger.from_crontab(new_connection['cron_schedule']),
        id=job_id,
        args=[new_connection],
        replace_existing=True
    )
    
    return {'status': 'ok', 'connection': new_connection}

@app.route('/connections/<connection_id>', methods=['PUT'])
@require_api_key
def update_connection(connection_id):
    data = request.json
    connections = load_connections()
    
    for conn in connections['connections']:
        if conn['id'] == connection_id:
            if 'name' in data:
                conn['name'] = data['name']
            if 'db_url' in data:
                conn['db_url'] = data['db_url']
            if 'cron_schedule' in data:
                if not validate_cron(data['cron_schedule']):
                    return {'status': 'failed', 'error': 'Invalid cron expression'}, 400
                conn['cron_schedule'] = data['cron_schedule']
                
                # Update the scheduler
                job_id = f"backup_{conn['id']}"
                scheduler.add_job(
                    lambda c: backup_database(c, telegram_uploader, CHAT_ID),
                    trigger=CronTrigger.from_crontab(conn['cron_schedule']),
                    id=job_id,
                    args=[conn],
                    replace_existing=True
                )
            
            save_connections(connections)
            return {'status': 'ok', 'connection': conn}
    
    return {'status': 'failed', 'error': 'Connection not found'}, 404

@app.route('/connections/<connection_id>', methods=['DELETE'])
@require_api_key
def delete_connection(connection_id):
    connections = load_connections()
    connections['connections'] = [c for c in connections['connections'] if c['id'] != connection_id]
    save_connections(connections)
    
    # Remove the job from scheduler
    job_id = f"backup_{connection_id}"
    scheduler.remove_job(job_id)
    
    return {'status': 'ok'}

@app.route('/backup/run', methods=['POST'])
@require_api_key
def run_backup():
    """Trigger immediate backup for specific connection or all connections"""
    data = request.json
    connection_id = data.get('connection_id')  # Optional: if not provided, backup all
    
    connections = load_connections()
    results = []
    
    if connection_id:
        # Backup specific connection
        connection = next((c for c in connections['connections'] if c['id'] == connection_id), None)
        if not connection:
            return {'status': 'failed', 'error': f'Connection {connection_id} not found'}, 404
            
        try:
            backup_database(connection, telegram_uploader, CHAT_ID)
            results.append({
                'connection_id': connection['id'],
                'name': connection['name'],
                'status': 'success'
            })
        except Exception as e:
            results.append({
                'connection_id': connection['id'],
                'name': connection['name'],
                'status': 'failed',
                'error': str(e)
            })
    else:
        # Backup all connections
        for connection in connections['connections']:
            try:
                backup_database(connection, telegram_uploader, CHAT_ID)
                results.append({
                    'connection_id': connection['id'],
                    'name': connection['name'],
                    'status': 'success'
                })
            except Exception as e:
                results.append({
                    'connection_id': connection['id'],
                    'name': connection['name'],
                    'status': 'failed',
                    'error': str(e)
                })
    
    return {
        'status': 'ok',
        'results': results
    }

if __name__ == "__main__":
    # Initialize the scheduler before starting the app
    initialize_scheduler(
        scheduler,
        load_connections(),
        lambda conn: backup_database(conn, telegram_uploader, CHAT_ID)
    )
    app.run(host=HOST, port=PORT)