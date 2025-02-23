from pyrogram import Client
import os
from datetime import datetime
from typing import Optional
import requests

class TelegramUploader:
    def __init__(self, api_id: str, api_hash: str, bot_token: str, logger):
        """
        Initialize the Telegram uploader
        
        Args:
            api_id (str): Telegram API ID
            api_hash (str): Telegram API Hash
            bot_token (str): Telegram Bot Token
        """
        self.logger = logger
        self.client = Client('pg-uploader', 
                            bot_token=bot_token,
                            api_id=int(api_id), api_hash=api_hash)

        self.client.start()

    def stop(self):
        """Stop the client if started"""
        if self._started:
            self.client.stop()
            self._started = False
            
    @staticmethod
    def download_file_url(file_url: str, dest_path: str):
        """
        Download a file from a URL to a destination path
        
        Args:
            file_url (str): URL of the file to download
            dest_path (str): Path to the destination file
        """
        try:
            response = requests.get(file_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return dest_path
        except Exception as e:
            raise Exception(f"Failed to download file: {str(e)}")
    
    def upload_file(self, file_path: str, chat_id: int, caption: Optional[str] = None):
        """
        Upload a file to Telegram
        
        Args:
            file_path (str): Path to the file to upload
            chat_id (str): Telegram chat ID where to upload the file
            caption (str, optional): Caption for the uploaded file
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            # Get file name and size
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            self.logger.info(f"Starting upload of {file_name} ({file_size} bytes)")
            
            # Prepare caption
            if caption is None:
                caption = f"File uploaded at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Upload the file
            chat_id = int(chat_id)
            self.client.send_document(
                chat_id=chat_id,
                document=file_path,
                caption=caption
            )
                
            print(f"Successfully uploaded {file_name}")
            
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            # Clean up the temporary file
            try:
                os.unlink(file_path)
            except:
                pass
