# PostgreSQL Telegram Backup Bot 🤖

A Telegram bot that helps you manage and automate PostgreSQL database backups. The bot can handle multiple database connections, schedule backups using cron expressions, and send the backup files directly to specified Telegram chats.

## Features ✨

- 🔄 Automated backups using cron schedules
- 📦 Support for multiple database connections
- 💬 Custom Telegram chat destinations for each backup
- ↩️ Reply-to message support for organized backup history
- 🔐 Secure credential management through environment variables
- 🐳 Docker support for easy deployment

## Prerequisites 📋

Before you begin, you'll need:

1. PostgreSQL database(s) you want to backup
2. Telegram account
3. Docker (optional, for containerized deployment)

## Telegram Setup 🔑

1. **Get API Credentials**:
   - Visit [my.telegram.org](https://my.telegram.org)
   - Log in with your phone number
   - Go to 'API development tools'
   - Create a new application
   - Copy the `api_id` and `api_hash`

2. **Create Telegram Bot**:
   - Open Telegram and message [@BotFather](https://t.me/botfather)
   - Send `/newbot` command
   - Follow instructions to create your bot
   - Copy the provided bot token

3. **Get Chat ID**:
   - Start a chat with your bot
   - Send the `/start` command
   - The bot will show you your chat ID and message ID

## Environment Setup 🛠️

Create a `.env` file in the project root:

```env
# Telegram Settings
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_DEFAULT_CHAT_ID=default_chat_id
```

## Installation & Running 🚀

### Using Docker Compose (Recommended)

1. Make sure you have Docker Compose installed
2. Create and configure your `.env` file
3. Run:
```bash
docker-compose up -d
```

To view logs:
```bash
docker-compose logs -f
```

To stop the service:
```bash
docker-compose down
```

### Using Docker

1. Build the Docker image:
```bash
docker build -t pg-telegram-backuper .
```

2. Run the container:
```bash
docker run -d \
  --name pg-backup-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  pg-telegram-backuper
```

### Manual Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the bot:
```bash
python app.py
```

## Bot Commands 🤖

- `/start` - Show welcome message and get chat/message IDs
- `/list` - List all database connections
- `/add` - Add a new database connection
- `/update <connection_id>` - Update a database connection
- `/delete <connection_id>` - Delete a database connection
- `/backup [connection_id]` - Run backup for specific or all connections

### Adding a Database Connection

Use the `/add` command with the following format:
```
/add name|db_url|cron_schedule|[chat_id]|[reply_to_message_id]
```

Example:
```
/add MyDB|postgres://user:pass@host:5432/dbname|0 0 * * *|123456789|42
```

Parameters:
- `name`: A friendly name for the connection
- `db_url`: PostgreSQL connection URL
- `cron_schedule`: Backup schedule in cron format
- `chat_id`: (Optional) Telegram chat ID for backups
- `reply_to_message_id`: (Optional) Message ID to reply to for group topics

## Data Storage 💾

- Database connections are stored in `data/connections.json`
- Backups are temporarily stored in `data/backups` before being sent to Telegram

## Security Notes 🔒

- Never share your API credentials
- Use strong passwords in database URLs
- Keep your `.env` file secure and never commit it to version control
- Consider using environment-specific connection strings

## Contributing 🤝

Feel free to open issues or submit pull requests if you have suggestions for improvements!

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.
