from pyrogram import Client, filters, enums
import os
from datetime import datetime
from typing import Optional
import requests
import logging
from dotenv import load_dotenv
from utils import (
    load_connections,
    save_connections,
    validate_cron,
    backup_database,
    is_user_authorized,
    add_authorized_user,
    mask_db_url
)
import uuid
import json

logger = logging.getLogger(__name__)
load_dotenv()
CHAT_ID = int(os.getenv("TELEGRAM_DEFAULT_CHAT_ID"))

class TelegramUploader:
    def __init__(self, api_id: str, api_hash: str, bot_token: str, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.client = Client('./data/pg-uploader', 
                            bot_token=bot_token,
                            api_id=int(api_id), api_hash=api_hash)
        self.client.set_parse_mode(enums.ParseMode.MARKDOWN)

        # Custom filter for authorized users
        def authorized_user_filter(_, __, message):
            return is_user_authorized(message.chat.id) or message.chat.id == CHAT_ID

        authorized_only = filters.create(authorized_user_filter)

        # Register command handlers
        @self.client.on_message(filters.command("start"))
        def start_command(client, message):
            chat_id = message.chat.id
            if not is_user_authorized(chat_id) and chat_id != CHAT_ID:
                unauthorized_text = (
                    "⚠️ You are not authorized to use this bot.\n\n"
                    "Your Chat ID: `{}`\n\n"
                    "Please contact the admin to get authorized."
                    .format(chat_id)
                )
                message.reply_text(unauthorized_text)
                return

            welcome_text = (
                "👋 Welcome to PostgreSQL Backup Bot!\n\n"
                "I can help you backup your PostgreSQL databases and send them here.\n\n"
                "Available commands:\n"
                "/start - Show this welcome message\n"
                "/list - List all database connections\n"
                "/add - Add a new database connection\n"
                "/update <connection_id> - Update a database connection\n"
                "/delete <connection_id> - Delete a database connection\n"
                "/backup [connection_id] - Run backup for specific or all connections\n"
                "{}"
                "\nYour Chat ID: `{}`\n"
                "This Message ID: `{}`\n"
                "Use these IDs in your backup configuration to control where backups are sent and which message they reply to."
                .format(
                    "/authorize <chat_id> - Authorize a user (Admin only)\n" if chat_id == CHAT_ID else "",
                    message.chat.id, 
                    message.id
                )
            )
            message.reply_text(welcome_text)

        @self.client.on_message(filters.command("authorize") & authorized_only)
        def authorize_command(client, message):
            # Split message into parts
            parts = message.text.split()
            
            # Check if chat_id was provided
            if len(parts) != 2:
                message.reply_text("Usage: /authorize <chat_id>")
                return
            
            try:
                chat_id = parts[1]
                if add_authorized_user(chat_id):
                    message.reply_text(f"✅ User `{chat_id}` has been authorized successfully.")
                else:
                    message.reply_text(f"ℹ️ User `{chat_id}` is already authorized.")
            except Exception as e:
                logger.error(f"Error in authorize command: {e}")
                message.reply_text("❌ Failed to authorize user. Please try again.")

        @self.client.on_message(filters.command("list") & authorized_only)
        def list_connections_command(client, message):
            data = load_connections()
            if not data['connections']:
                message.reply_text("No database connections found.")
                return

            response = "📋 Database Connections:\n\n"
            for conn in data['connections']:
                response += (
                    f"🔹 ID: `{conn['id']}`\n"
                    f"📝 Name: `{conn['name']}`\n"
                    f"🔗 URL: `{mask_db_url(conn['db_url'])}`\n"
                    f"⏰ Schedule: `{conn['cron_schedule']}`\n"
                    f"💬 Chat ID: `{conn.get('chat_id', 'Default')}`\n"
                    f"↩️ Reply To: `{conn.get('reply_to_message_id', 'None')}`\n"
                    "➖➖➖➖➖➖➖➖➖➖\n"
                )
            message.reply_text(response)

        @self.client.on_message(filters.command("add") & authorized_only)
        def add_connection_command(client, message):
            try:
                # Format: /add name|db_url|cron_schedule|[chat_id]|[reply_to_message_id]
                command_text = message.text.split(maxsplit=1)
                if len(command_text) != 2:
                    message.reply_text(
                        "❌ Invalid format. Use:\n"
                        "/add name|db_url|cron_schedule|[chat_id]|[reply_to_message_id]\n\n"
                        "Example:\n"
                        "/add MyDB|postgres://user:pass@host:5432/dbname|0 0 * * *|123456789|42\n"
                        "Note: chat_id and reply_to_message_id are optional."
                    )
                    return

                # Split the parameters by |
                params = command_text[1].split('|')
                if len(params) < 3 or len(params) > 5:
                    message.reply_text(
                        "❌ Invalid format. Use:\n"
                        "/add name|db_url|cron_schedule|[chat_id]|[reply_to_message_id]\n\n"
                        "Example:\n"
                        "/add MyDB|postgres://user:pass@host:5432/dbname|0 0 * * *|123456789|42\n"
                        "Note: chat_id and reply_to_message_id are optional."
                    )
                    return

                # Parse parameters
                params = [p.strip() for p in params]
                name = params[0]
                db_url = params[1]
                cron_schedule = params[2]
                chat_id = params[3] if len(params) > 3 else None
                reply_to = int(params[4]) if len(params) > 4 else None

                # Validate cron
                if not validate_cron(cron_schedule):
                    message.reply_text("❌ Invalid cron schedule format")
                    return

                # Add connection
                data = load_connections()
                new_connection = {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "db_url": db_url,
                    "cron_schedule": cron_schedule,
                    "chat_id": chat_id,
                    "reply_to_message_id": reply_to,
                    "created_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    "last_run_at": None
                }
                data['connections'].append(new_connection)
                save_connections(data)

                chat_info = f"Chat ID: {chat_id}" if chat_id else "Using default chat"
                reply_info = f"\nReply to message: {reply_to}" if reply_to else ""
                message.reply_text(
                    f"✅ Connection added successfully!\n"
                    f"ID: `{new_connection['id']}`\n"
                    f"{chat_info}{reply_info}"
                )

            except Exception as e:
                message.reply_text(f"❌ Error: {str(e)}")

        @self.client.on_message(filters.command("update") & authorized_only)
        def update_connection_command(client, message):
            try:
                # Format: /update connection_id name db_url cron_schedule
                parts = message.text.split(maxsplit=5)[1:]
                if len(parts) != 4:
                    message.reply_text(
                        "❌ Invalid format. Use:\n"
                        "/update <connection_id> <name> <db_url> <cron_schedule>"
                    )
                    return

                connection_id, name, db_url, cron_schedule = parts

                # Validate cron
                if not validate_cron(cron_schedule):
                    message.reply_text("❌ Invalid cron schedule format")
                    return

                # Update connection
                data = load_connections()
                for conn in data['connections']:
                    if conn['id'] == connection_id:
                        conn['name'] = name
                        conn['db_url'] = db_url
                        conn['cron_schedule'] = cron_schedule
                        save_connections(data)
                        message.reply_text("✅ Connection updated successfully!")
                        return

                message.reply_text("❌ Connection not found")

            except Exception as e:
                message.reply_text(f"❌ Error: {str(e)}")

        @self.client.on_message(filters.command("delete") & authorized_only)
        def delete_connection_command(client, message):
            try:
                # Format: /delete connection_id
                parts = message.text.split()
                if len(parts) != 2:
                    message.reply_text("❌ Please provide connection ID: /delete <connection_id>")
                    return

                connection_id = parts[1]
                data = load_connections()
                initial_count = len(data['connections'])
                data['connections'] = [c for c in data['connections'] if c['id'] != connection_id]

                if len(data['connections']) == initial_count:
                    message.reply_text("❌ Connection not found")
                    return

                save_connections(data)
                message.reply_text("✅ Connection deleted successfully!")

            except Exception as e:
                message.reply_text(f"❌ Error: {str(e)}")

        @self.client.on_message(filters.command("backup") & authorized_only)
        def backup_command(client, message):
            try:
                # Format: /backup [connection_id]
                parts = message.text.split()
                connection_id = parts[1] if len(parts) > 1 else None

                data = load_connections()
                results = []

                if connection_id:
                    # Backup specific connection
                    connection = next((c for c in data['connections'] if c['id'] == connection_id), None)
                    if not connection:
                        message.reply_text("❌ Connection not found")
                        return

                    message.reply_text(f"🔄 Starting backup for {connection['name']}...")
                    try:
                        backup_database(connection, self, connection.get('chat_id', CHAT_ID))
                        results.append({"id": connection['id'], "status": "success"})
                    except Exception as e:
                        results.append({"id": connection['id'], "status": "error", "error": str(e)})

                else:
                    # Backup all connections
                    message.reply_text("🔄 Starting backup for all connections...")
                    for connection in data['connections']:
                        try:
                            backup_database(connection, self, connection.get('chat_id', CHAT_ID))
                            results.append({"id": connection['id'], "status": "success"})
                        except Exception as e:
                            results.append({"id": connection['id'], "status": "error", "error": str(e)})

                # Report results
                response = "📋 Backup Results:\n\n"
                for result in results:
                    conn = next(c for c in data['connections'] if c['id'] == result['id'])
                    if result['status'] == 'success':
                        response += f"✅ {conn['name']}: Success\n"
                    else:
                        response += f"❌ {conn['name']}: Failed - {result.get('error', 'Unknown error')}\n"

                message.reply_text(response)

            except Exception as e:
                message.reply_text(f"❌ Error: {str(e)}")

    def stop(self):
        """Stop the client if started"""
        self.client.stop()
            
    @staticmethod
    def download_file_url(file_url: str, dest_path: str):
        """Download a file from URL to destination path"""
        response = requests.get(file_url)
        response.raise_for_status()
        
        with open(dest_path, 'wb') as f:
            f.write(response.content)
            
    def upload_file(self, file_path: str, chat_id: str, caption: Optional[str] = None, reply_to_message_id: Optional[int] = None):
        """Upload a file to Telegram chat
        
        Args:
            file_path (str): Path to file to upload
            chat_id (str): Telegram chat ID where to upload the file
            caption (str, optional): Caption for the uploaded file
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get file name from path
            file_name = os.path.basename(file_path)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Log upload attempt
            self.logger.info(f"Uploading {file_name} ({file_size} bytes) to chat {chat_id}")
            
            # Upload the file
            chat_id = chat_id
            self.client.send_document(
                chat_id=chat_id,
                document=file_path,
                reply_to_message_id=reply_to_message_id,
                caption=caption
            )
                
            self.logger.info(f"Successfully uploaded {file_name}")
            
        except Exception as e:
            error_msg = f"Failed to upload {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
