import logging, os
from dotenv import load_dotenv
from upload_handler import TelegramUploader
from apscheduler.schedulers.background import BackgroundScheduler
from utils import (
    load_connections,
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
BOT_TOKEN = '8139886917:AAFeNBYQf7vKRGDRSPp_Kft9woGoiLedsW4'
APP_API_KEY = os.getenv("APP_API_KEY")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

telegram_uploader = TelegramUploader(
    TELEGRAM_API, 
    TELEGRAM_HASH, 
    BOT_TOKEN, 
    logger=logger
)
scheduler = BackgroundScheduler()

# Initialize the scheduler
def init_scheduler():
    if not scheduler.running:
        initialize_scheduler(
            scheduler,
            load_connections(),
            backup_database,
            telegram_uploader,
            CHAT_ID
        )
        if not scheduler.running:
            scheduler.start()
        for sch in scheduler.get_jobs():
            logger.info(f'The back up task: {sch}')
        logger.info("Scheduler initialized and started")

    

init_scheduler()
telegram_uploader.client.run()