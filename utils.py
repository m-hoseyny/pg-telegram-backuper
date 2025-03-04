import json
import re
import os
import logging
import subprocess
import gzip
import tempfile
import time
import random
from urllib.parse import urlparse
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger


logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# Define data directory path
DATA_DIR = './data'
CONNECTIONS_FILE = os.path.join(DATA_DIR, 'connections.json')

def ensure_data_dir():
    """Ensure data directory and connections.json exist"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONNECTIONS_FILE):
        with open(CONNECTIONS_FILE, 'w') as f:
            json.dump({"connections": []}, f, indent=4)

def load_connections():
    """Load connections from the JSON file"""
    ensure_data_dir()
    try:
        with open(CONNECTIONS_FILE, 'r') as f:
            data = json.load(f)
            # Ensure authorized_users exists
            if "authorized_users" not in data:
                data["authorized_users"] = []
            if "connections" not in data:
                data["connections"] = []
            return data
    except FileNotFoundError:
        return {"connections": [], "authorized_users": []}

def is_user_authorized(chat_id):
    """Check if a user is authorized"""
    data = load_connections()
    return str(chat_id) in data.get("authorized_users", [])

def add_authorized_user(chat_id):
    """Add a user to the authorized users list"""
    data = load_connections()
    if str(chat_id) not in data["authorized_users"]:
        data["authorized_users"].append(str(chat_id))
        save_connections(data)
        return True
    return False

def save_connections(data):
    """Save connections to the JSON file"""
    ensure_data_dir()
    with open(CONNECTIONS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def validate_cron(cron_expression):
    """Validate cron expression using regex pattern.
    Supports standard cron format: minute hour day_of_month month day_of_week
    Values allowed:
    - Minutes: 0-59
    - Hours: 0-23
    - Day of Month: 1-31
    - Month: 1-12 or JAN-DEC
    - Day of Week: 0-6 or SUN-SAT
    Supports: *, */n, 1-10, 1,2,3
    """
    if not cron_expression:
        return False
        
    # Split expression into its components
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return False
        
    patterns = {
        'minute': r'^(\*|([0-9]|[1-5][0-9])(-([0-9]|[1-5][0-9]))?(,([0-9]|[1-5][0-9]))*|\*/[1-9][0-9]?)$',
        'hour': r'^(\*|([0-9]|1[0-9]|2[0-3])(-([0-9]|1[0-9]|2[0-3]))?(,([0-9]|1[0-9]|2[0-3]))*|\*/[1-9][0-9]?)$',
        'day_of_month': r'^(\*|([1-9]|[12][0-9]|3[01])(-([1-9]|[12][0-9]|3[01]))?(,([1-9]|[12][0-9]|3[01]))*|\*/[1-9][0-9]?)$',
        'month': r'^(\*|([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(-([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))?(,([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))*|\*/[1-9][0-9]?)$',
        'day_of_week': r'^(\*|([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT)(-([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT))?(,([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT))*|\*/[1-9][0-9]?)$'
    }
    
    # Check each part against its corresponding pattern
    for part, pattern in zip(parts, patterns.values()):
        if not re.match(pattern, part.upper()):
            return False
            
    return True

def parse_db_url(db_url):
    """Parse database URL into components"""
    parsed = urlparse(db_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path[1:],  # Remove leading slash
        'user': parsed.username,
        'password': parsed.password
    }

def mask_db_url(db_url):
    """Mask username and password in database URL"""
    try:
        # Parse the URL
        parts = db_url.split('@')
        if len(parts) != 2:
            return db_url
            
        credentials = parts[0].split('//')[-1].split(':')
        if len(credentials) != 2:
            return db_url
            
        # Mask username and password
        username = '*' * len(credentials[0])
        password = '*' * len(credentials[1])
        
        # Reconstruct the URL with masked credentials
        return f"{parts[0].split('//')[0]}//{username}:{password}@{parts[1]}"
    except:
        return db_url

def backup_database(connection, telegram_uploader, default_chat_id):
    """Execute database backup for a given connection"""
    try:
        
        # Parse database URL and prepare backup
        db_info = parse_db_url(connection['db_url'])
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        backup_filename = f"{connection['name']}_{timestamp}"
        
        # Create temporary directory for backup
        with tempfile.TemporaryDirectory(dir='./data/backups') as temp_dir:
            # Set PostgreSQL environment variables
            env = os.environ.copy()
            env['PGPASSWORD'] = db_info['password']
            
            # Backup file paths
            backup_path = os.path.join(temp_dir, f"{backup_filename}.sql")
            compressed_path = os.path.join(temp_dir, f"{backup_filename}.sql.gz")
            
            # Run pg_dump
            logger.info(f"Starting backup for database: {connection['name']}")
            pg_dump_cmd = [
                'pg_dump',
                '-h', db_info['host'],
                '-p', str(db_info['port']),
                '-U', db_info['user'],
                '-d', db_info['database'],
                '-f', backup_path,
                '-v'  # Add verbose output
            ]
            
            try:
                result = subprocess.run(
                    pg_dump_cmd,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"pg_dump output: {result.stdout}")
            except subprocess.CalledProcessError as e:
                error_msg = f"pg_dump failed:\nCommand: {' '.join(pg_dump_cmd)}\nError: {e.stderr}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Compress the backup file
            logger.info(f"Compressing backup file for: {connection['name']}")
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # Upload to Telegram
            chat_id = connection.get('chat_id', default_chat_id)
            reply_to = int(connection.get('reply_to_message_id'))
            telegram_uploader.upload_file(
                compressed_path,
                chat_id,
                caption=f"Backup for {connection['name']} completed at {timestamp}",
                reply_to_message_id=reply_to,
                added_by=connection.get('added_by', default_chat_id)
            )

        # Update last run timestamp
        connections = load_connections()
        try:
            for conn in connections['connections']:
                if conn['id'] == connection['id']:
                    conn['last_run_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                    save_connections(connections)
                    break
        except Exception as e:
            logger.error('Error in reading files')
            time.sleep(random.random() * 2)
            
        return True
            
    except Exception as e:
        logger.error(f"Backup failed for {connection['name']}: {str(e)}")
        raise e

def initialize_scheduler(scheduler, connections, backup_callback, telegram_uploader, CHAT_ID):
    """Initialize the scheduler with existing connections"""
    logger.info("Initializing scheduler...")
    
    # Clear any existing jobs
    scheduler.remove_all_jobs()
    
    # Add jobs for each connection
    for connection in connections['connections']:
        job_id = f"backup_{connection['id']}"
        
        # Check if this is the first run (no last_run_at)
        if 'last_run_at' not in connection:
            connection['last_run_at'] = None
        
        scheduler.add_job(
            backup_callback,
            CronTrigger.from_crontab(connection['cron_schedule']),
            id=job_id,
            args=[connection, telegram_uploader, CHAT_ID],
            replace_existing=True
        )
        logger.info(f"Scheduled backup job for {connection['name']} with schedule: {connection['cron_schedule']}")
    
    # Start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")
