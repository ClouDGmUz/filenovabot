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

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

INSTAGRAM_PATTERN = re.compile(
    r"(https?://)?(www\.)?instagram\.com/(p|reel|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)

YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[A-Za-z0-9_-]+",
    re.IGNORECASE,
)

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
    await update.message.reply_text(
        "Send me an Instagram or YouTube URL and I'll download it for you!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    is_instagram = INSTAGRAM_PATTERN.match(text)
    is_youtube = YOUTUBE_PATTERN.match(text)

    if not is_instagram and not is_youtube:
        await update.message.reply_text(
            "That doesn't look like a valid Instagram or YouTube URL."
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
                if is_instagram:
                    shortcode = extract_shortcode(text)
                    if not shortcode:
                        progress["status"] = "error"
                        progress["text"] = "Could not extract shortcode."
                        return
                    files = await asyncio.to_thread(
                        download_instagram_post, shortcode, temp_dir, progress
                    )
                else:
                    files = await asyncio.to_thread(
                        download_youtube_video, text, temp_dir, progress
                    )

                if not files:
                    progress["status"] = "error"
                    progress["text"] = "No media found."
                    return

                progress["text"] = "Sending files..."

                for file_path in files:
                    if file_path.endswith((".mp4", ".mkv", ".webm")):
                        with open(file_path, "rb") as f:
                            await update.message.reply_video(f)
                    else:
                        with open(file_path, "rb") as f:
                            await update.message.reply_document(f)

                await msg.delete()

        except Exception as e:
            logger.exception("Error downloading")
            progress["status"] = "error"
            progress["text"] = f"Failed: {str(e)}"

    await asyncio.gather(run_download(), update_progress())

    if progress["status"] == "error":
        await msg.edit_text(f"❌ {progress['text']}")


def main():
    if not BOT_TOKEN:
        print("Set TG_BOT_TOKEN in .env before running.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
