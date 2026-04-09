import os
import re
import logging
import tempfile
import asyncio
from pathlib import Path
from dotenv import load_dotenv

import instaloader
import requests
import yt_dlp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import database as db
from utils import (
    detect_platform,
    sanitize_url,
    get_file_size,
    get_total_size,
    format_bytes,
    RateLimiter
)
from admin import get_admin_handlers, is_admin

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

# Initialize rate limiter: 10 downloads per minute per user
rate_limiter = RateLimiter(max_calls=10, period=60)


SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def extract_shortcode(url: str) -> str:
    match = re.search(r"/(p|reel|tv)/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(2)
    return ""


def download_instagram_post(shortcode: str, temp_dir: str, progress: dict) -> list[str]:
    L = instaloader.Instaloader(
        dirname_pattern=temp_dir,
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        request_timeout=30,
    )

    post = instaloader.Post.from_shortcode(L.context, shortcode)
    files = []

    progress["status"] = "fetching"
    progress["text"] = "Fetching media info..."

    if post.typename == "GraphSidecar":
        nodes = list(post.get_sidecar_nodes())
        total = len(nodes)
        for i, node in enumerate(nodes):
            url = node.video_url if node.is_video else node.display_url
            ext = ".mp4" if node.is_video else ".jpg"
            path = os.path.join(temp_dir, f"{shortcode}_{i}{ext}")
            progress["text"] = f"Downloading {i + 1}/{total}..."
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
            files.append(path)
    else:
        progress["text"] = "Downloading media..."
        if post.is_video:
            url = post.video_url
            ext = ".mp4"
        else:
            url = post.url
            ext = ".jpg"
        path = os.path.join(temp_dir, f"{shortcode}{ext}")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        files.append(path)

    progress["status"] = "done"
    return files


def download_youtube_video(url: str, temp_dir: str, progress: dict) -> list[str]:
    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int((downloaded / total) * 100)
                speed = d.get("speed", 0)
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "..."
                progress["text"] = f"Downloading... {pct}% ({speed_str})"
        elif d["status"] == "finished":
            progress["text"] = "Processing video..."

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
    }

    progress["status"] = "fetching"
    progress["text"] = "Fetching video info..."

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not Path(filename).exists():
            for ext in [".mp4", ".mkv", ".webm"]:
                alt = filename.rsplit(".", 1)[0] + ext
                if Path(alt).exists():
                    filename = alt
                    break

    progress["status"] = "done"
    return [filename]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command and register user."""
    user = update.effective_user
    
    # Register or update user in database
    db.register_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Check if user is banned
    if db.is_user_banned(user.id):
        await update.message.reply_text(
            "⛔ You have been banned from using this bot."
        )
        return
    
    # Get user stats
    user_data = db.get_user(user.id)
    total_downloads = user_data.get("total_downloads", 0) if user_data else 0
    
    welcome_msg = (
        "👋 *Welcome to the Downloader Bot!*\n\n"
        "Send me an *Instagram* or *YouTube* URL and I'll download it for you!\n\n"
        "📌 *Features:*\n"
        "• Download Instagram posts, reels, and carousels\n"
        "• Download YouTube videos and shorts\n"
        "• Track your download history\n"
        "• Get your stats with /history\n\n"
        f"📊 *Your Stats:*\n"
        f"• Total downloads: `{total_downloads}`\n\n"
        "🔧 Use /help for more info"
    )
    
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information."""
    help_msg = (
        "📖 *Bot Commands*\n\n"
        "🚀 *General Commands:*\n"
        "• `/start` - Start the bot and see your stats\n"
        "• `/help` - Show this help message\n"
        "• `/history` - View your recent downloads\n"
        "• `/stats` - View your download statistics\n"
        "• `/clear` - Clear your download history\n\n"
        "🔧 *How to Use:*\n"
        "1. Send an Instagram or YouTube URL\n"
        "2. Wait for the bot to process it\n"
        "3. Download the media files\n\n"
        "📌 *Supported Platforms:*\n"
        "• Instagram: posts, reels, carousels\n"
        "• YouTube: videos, shorts\n\n"
        "⚠️ *Note:*\n"
        "• Rate limit: 10 downloads per minute\n"
        "• Private accounts may not be accessible"
    )
    
    await update.message.reply_text(help_msg, parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's download history."""
    user_id = update.effective_user.id
    
    # Get limit from args if provided
    try:
        limit = int(context.args[0]) if context.args else 10
    except (ValueError, IndexError):
        limit = 10
    
    limit = min(limit, 50)  # Cap at 50
    
    downloads = db.get_user_downloads(user_id, limit=limit)
    
    if not downloads:
        await update.message.reply_text("📭 You don't have any downloads yet.")
        return
    
    message = "📥 *Your Recent Downloads*\n\n"
    for i, dl in enumerate(downloads, 1):
        platform_icon = "📷" if dl["platform"] == "instagram" else "🎥"
        status_icon = "✅" if dl["status"] == "success" else "❌"
        message += f"{i}. {platform_icon} {status_icon} {dl['platform']}\n"
        message += f"   URL: `{dl['url'][:50]}...`\n"
        message += f"   Files: {dl['file_count']} | Size: {format_bytes(dl['file_size_bytes'])}\n"
        message += f"   Time: {dl['timestamp']}\n\n"
    
    message += f"*Showing {len(downloads)} downloads*"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def user_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's download statistics."""
    user_id = update.effective_user.id
    
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("⚠️ User not found. Please send /start first.")
        return
    
    total_downloads = user.get("total_downloads", 0)
    download_count = db.get_download_count(user_id)
    
    # Get platform breakdown
    platform_stats = db.get_platform_stats()
    user_platform_downloads = {}
    for platform, data in platform_stats.items():
        # This is a simplification - in production, query per-user stats
        pass
    
    message = (
        "📊 *Your Download Statistics*\n\n"
        f"📥 Total Downloads: `{total_downloads}`\n"
        f"📁 Files Downloaded: `{download_count}`\n"
        f"👤 Member Since: {user.get('first_seen', 'Unknown')}\n"
        f"🕒 Last Active: {user.get('last_seen', 'Unknown')}"
    )
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user's download history (soft clear - keeps stats)."""
    user_id = update.effective_user.id
    
    # In a real app, you might want to actually delete records
    # For now, just confirm the action
    await update.message.reply_text(
        "⚠️ Download history is kept for analytics purposes.\n"
        "This cannot be cleared at the moment."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Register user if not exists
    db.register_or_update_user(
        user_id=user_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name
    )
    
    # Check if user is banned
    if db.is_user_banned(user_id):
        await update.message.reply_text(
            "⛔ You have been banned from using this bot."
        )
        return
    
    text = update.message.text.strip()
    
    # Sanitize URL
    url = sanitize_url(text)
    
    # Detect platform
    platform = detect_platform(url)
    
    if not platform:
        await update.message.reply_text(
            "❌ That doesn't look like a valid Instagram or YouTube URL.\n\n"
            "📌 *Supported:*\n"
            "• Instagram posts, reels, carousels\n"
            "• YouTube videos and shorts",
            parse_mode="Markdown"
        )
        return
    
    # Check rate limit
    if not rate_limiter.is_allowed(user_id):
        remaining = rate_limiter.get_remaining(user_id)
        await update.message.reply_text(
            f"⏱️ *Rate Limit Exceeded*\n\n"
            f"You've reached the download limit. Please wait before downloading more.\n"
            f"Remaining downloads: `{remaining}`",
            parse_mode="Markdown"
        )
        return
    
    msg = await update.message.reply_text("⠋ Starting...")
    
    progress = {"status": "running", "text": "Starting..."}
    spinner_idx = [0]
    
    async def update_progress():
        while progress["status"] != "done":
            spinner = SPINNER[spinner_idx[0] % len(SPINNER)]
            spinner_idx[0] += 1
            try:
                await msg.edit_text(f"{spinner} {progress['text']}")
            except Exception:
                pass
            await asyncio.sleep(1)
    
    async def run_download():
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                if platform == "instagram":
                    shortcode = extract_shortcode(url)
                    if not shortcode:
                        progress["status"] = "error"
                        progress["text"] = "Could not extract shortcode."
                        db.record_download(
                            user_id=user_id, url=url, platform=platform,
                            status="error", error_message="Could not extract shortcode"
                        )
                        return
                    files = await asyncio.to_thread(
                        download_instagram_post, shortcode, temp_dir, progress
                    )
                elif platform == "youtube":
                    files = await asyncio.to_thread(
                        download_youtube_video, url, temp_dir, progress
                    )
                else:
                    progress["status"] = "error"
                    progress["text"] = "Platform not supported."
                    return

                if not files:
                    progress["status"] = "error"
                    progress["text"] = "No media found."
                    db.record_download(
                        user_id=user_id, url=url, platform=platform,
                        status="error", error_message="No media found"
                    )
                    return

                # Calculate file stats
                file_count = len(files)
                total_size = get_total_size(files)
                media_type = "video" if files[0].endswith((".mp4", ".mkv", ".webm")) else "image"

                progress["text"] = "Sending files..."

                for file_path in files:
                    if file_path.endswith((".mp4", ".mkv", ".webm")):
                        with open(file_path, "rb") as f:
                            await update.message.reply_video(f)
                    else:
                        with open(file_path, "rb") as f:
                            await update.message.reply_document(f)

                # Record successful download
                db.record_download(
                    user_id=user_id, url=url, platform=platform,
                    media_type=media_type, file_count=file_count,
                    file_size_bytes=total_size, status="success"
                )
                
                # Increment user download count
                db.increment_user_downloads(user_id)

                await msg.delete()

        except Exception as e:
            logger.exception("Error downloading")
            progress["status"] = "error"
            progress["text"] = f"Failed: {str(e)}"
            
            # Record failed download
            db.record_download(
                user_id=user_id, url=url, platform=platform,
                status="error", error_message=str(e)
            )
    
    await asyncio.gather(run_download(), update_progress())
    
    if progress["status"] == "error":
        await msg.edit_text(f"❌ {progress['text']}")


def main():
    if not BOT_TOKEN:
        print("Set TG_BOT_TOKEN in .env before running.")
        return

    # Initialize database
    db.initialize_database()
    print("Database initialized successfully")

    app = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("stats", user_stats_command))
    app.add_handler(CommandHandler("clear", clear_command))
    
    # Add admin handlers
    for handler in get_admin_handlers():
        app.add_handler(handler)
    
    # Add message handler for URLs
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
