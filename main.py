import os
import logging
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters
)
from handlers import handle_homework
from utils import get_bot_info, get_dynamic_greeting, load_config

# --- Load Environment Variables ---
load_dotenv()
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Aiohttp Web App ---
web_app = web.Application()

# --- Global application placeholder ---
application = None  # Define globally so it can be accessed in webhooks

async def send_startup_message(app):
    bot_version, bt_time = get_bot_info()
    greeting = get_dynamic_greeting().split(" -")[0]
    routes = app.bot_data.get("ROUTES_MAP", {})
    admins = app.bot_data.get("ADMIN_CHAT_IDS", [])
    message = (
        f"{greeting}\n"
        f"<b>Homework Forwarder Bot</b>\n"
        f"✅ Online (v{bot_version})\n"
        f"🕒 Time: {bt_time} (BTT)\n"
        f"📬 Routes: {len(routes)} active\n"
        f"🌐 Webhook: {WEBHOOK_URL}"
    )
    for admin_id in admins:
        try:
            await app.bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send startup message to {admin_id}: {e}")

def create_telegram_webhook(app_instance):
    async def telegram_webhook(request):
        try:
            data = await request.json()
            update = Update.de_json(data, app_instance.bot)
            await app_instance.process_update(update)
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
        return web.Response()

    return telegram_webhook


# --- Startup & Shutdown Hooks ---
async def on_startup(app):
    await send_startup_message(application)

async def on_shutdown(app):
    logger.info("Shutting down bot...")

async def main():
    global application
    # Load bot info and .env values
    bot_version, bt_time = get_bot_info()
    bot_token, chat_id, admin_chat_ids, routes_map = load_config()

    # Build Application with token
    application = (
        ApplicationBuilder()
        .token(bot_token)
        .build()
    )

    # Inject bot_data
    application.bot_data["ROUTES_MAP"] = {
        int(source.strip()): int(target.strip())
        for pair in routes_map if ":" in pair
        for source, target in [pair.split(":")]
    }
    application.bot_data["ADMIN_CHAT_IDS"] = [int(id.strip()) for id in admin_chat_ids if id.strip()]
    application.bot_data["FORWARDED_LOGS"] = []

    # Add handler
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO,
        handle_homework
    ))

    # Add Telegram webhook endpoint
    web_app.router.add_post("/webhook", create_telegram_webhook(application))  # ✅ Route for Telegram

    # Start web server
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"Bot running at http://0.0.0.0:{PORT}")
    while True:
        await asyncio.sleep(3600)  # Keeps the bot alive


# --- Run App ---
if __name__ == "__main__":
    asyncio.run(main())
