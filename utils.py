import json
import re
import logging
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

def load_connections():
    """Load connections from the JSON file"""
    try:
        with open('connections.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"connections": []}

def save_connections(data):
    """Save connections to the JSON file"""
    with open('connections.json', 'w') as f:
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

def backup_database(connection, telegram_uploader, chat_id):
    """Execute database backup for a given connection"""
    try:
        # Update last_run_at in connections.json
        connections = load_connections()
        for conn in connections['connections']:
            if conn['id'] == connection['id']:
                conn['last_run_at'] = datetime.now().isoformat()
                save_connections(connections)
                break
        
        # TODO: Implement actual database backup logic here
        logger.info(f"Backing up database: {connection['name']}")
        # For now, just send a message to telegram
        telegram_uploader.client.send_message(
            chat_id=chat_id, 
            text=f"Database backup triggered for {connection['name']} at {datetime.now().isoformat()}"
        )
    except Exception as e:
        logger.error(f"Error backing up database {connection['name']}: {str(e)}")

def initialize_scheduler(scheduler, connections, backup_callback):
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
            args=[connection],
            replace_existing=True
        )
        logger.info(f"Scheduled backup job for {connection['name']} with schedule: {connection['cron_schedule']}")
    
    # Start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")
