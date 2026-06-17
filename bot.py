import os
import json
import logging
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
COMMANDS_URL = os.getenv("COMMANDS_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global cache for custom commands
custom_commands = {}

async def load_custom_commands() -> str:
    """Load custom commands from remote URL or fall back to local file. Returns status string."""
    global custom_commands
    if COMMANDS_URL:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(COMMANDS_URL, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    custom_commands = data
                    logger.info("Successfully loaded custom commands from URL.")
                    return f"Loaded {len(custom_commands)} custom commands from URL."
                else:
                    logger.error("JSON at COMMANDS_URL is not a dictionary.")
                    return "Error: Remote JSON must be a key-value dictionary."
        except Exception as e:
            logger.error(f"Error loading custom commands from URL: {e}")
            return f"Error loading from URL: {e}"
    else:
        # Fallback to local file
        commands_path = os.path.join(os.path.dirname(__file__), "commands.json")
        if os.path.exists(commands_path):
            try:
                with open(commands_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    custom_commands = data
                    logger.info("Successfully loaded custom commands from local file.")
                    return f"Loaded {len(custom_commands)} custom commands from local commands.json."
                else:
                    logger.error("local commands.json is not a dictionary.")
                    return "Error: local commands.json must be a dictionary."
            except Exception as e:
                logger.error(f"Error loading custom commands from local file: {e}")
                return f"Error loading local file: {e}"
        else:
            custom_commands = {}
            logger.info("No local commands.json or COMMANDS_URL found.")
            return "No commands configured."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat = update.effective_chat
    # In groups, we want to know if it's a group or supergroup
    if chat.type in ["group", "supergroup"]:
        await update.message.reply_html(
            "Hello friends! I am your bot. Use /help to see what I can do."
        )
    else:
        await update.message.reply_html(
            f"Hello {user.mention_html()}! Add me to a group as an admin, and I can respond to commands there."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    # Start with core commands
    help_text = (
        "Here are the commands you can use:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/ping - Check if the bot is online\n"
        "/whois - See details about the member who sent the command\n"
        "/reload - Reload custom commands from the remote URL/file"
    )
    
    if custom_commands:
        help_text += "\n\nCustom group commands:\n"
        for cmd in sorted(custom_commands.keys()):
            preview = str(custom_commands[cmd]).split("\n")[0]
            if len(preview) > 40:
                preview = preview[:37] + "..."
            help_text += f"/{cmd} - {preview}\n"

    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to /ping command."""
    await update.message.reply_text("Pong! 🏓 I am online and responding.")

async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retrieve details about the user who triggered the command."""
    user = update.effective_user
    chat = update.effective_chat
    
    response = (
        f"👤 **User Info:**\n"
        f"• Name: {user.full_name}\n"
        f"• Username: @{user.username if user.username else 'None'}\n"
        f"• User ID: `{user.id}`\n\n"
        f"💬 **Chat Info:**\n"
        f"• Chat Type: {chat.type.capitalize()}\n"
        f"• Chat Title: {chat.title if chat.title else 'Private Chat'}"
    )
    await update.message.reply_text(response, parse_mode="Markdown")

async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reload custom commands from remote URL or local file."""
    status = await load_custom_commands()
    await update.message.reply_text(f"🔄 Custom commands reload status:\n`{status}`", parse_mode="Markdown")

async def dynamic_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle custom commands defined dynamically."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text.startswith("/"):
        return

    # Extract the command name (e.g., "/rules@bot_username" -> "rules")
    parts = text.split()
    command_part = parts[0][1:]  # remove leading "/"
    command_name = command_part.split("@")[0].lower()

    # Core commands are handled by their own specific handlers, so ignore them
    if command_name in ["start", "help", "ping", "whois", "reload"]:
        return

    if command_name in custom_commands:
        response = custom_commands[command_name]
        await update.message.reply_text(response)

async def post_init(application: Application) -> None:
    """Post-initialization hook to load custom commands at startup."""
    status = await load_custom_commands()
    logger.info(f"Startup dynamic command load status: {status}")

def main() -> None:
    """Start the bot."""
    if not TOKEN or TOKEN == "your_bot_token_here":
        logger.error("Error: TELEGRAM_BOT_TOKEN is not set in the .env file.")
        print("\n[ERROR] TELEGRAM_BOT_TOKEN is not set in the .env file.")
        print("Please edit the .env file in the project folder and paste your bot token.")
        print("You can get a token by messaging @BotFather on Telegram.\n")
        return

    import asyncio
    
    # Fix for Python 3.10+ event loop issues
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Create the Application
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    # Register core command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("whois", whois_command))
    application.add_handler(CommandHandler("reload", reload_command))

    # Register the catch-all custom command handler
    application.add_handler(MessageHandler(filters.COMMAND, dynamic_command_handler))

    # Start the bot based on environment settings
    if WEBHOOK_URL:
        PORT = int(os.environ.get("PORT", 8000))
        webhook_path = f"webhook/{TOKEN}"
        full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}/{webhook_path}"
        
        logger.info(f"Starting bot in Webhook mode. Port: {PORT}")
        logger.info(f"Setting webhook URL to: {full_webhook_url}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=webhook_path,
            webhook_url=full_webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        logger.info("Starting bot in local Polling mode.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
