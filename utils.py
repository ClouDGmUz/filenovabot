"""
Utility functions for the downloader bot.
Includes URL validation, file operations, format conversion, and helpers.
"""

import os
import re
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ==================== URL Validation & Detection ====================

def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL."""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url is not None and url_pattern.match(url)


def detect_platform(url: str) -> Optional[str]:
    """Detect which platform a URL belongs to."""
    instagram_patterns = [
        r'instagram\.com/(p|reel|tv)/',
        r'instagram\.com/stories/',
    ]
    
    youtube_patterns = [
        r'(youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/)',
        r'youtube\.com/live/',
        r'youtube\.com/embed/',
    ]
    
    tiktok_patterns = [
        r'tiktok\.com/@',
        r'vm\.tiktok\.com/',
    ]
    
    twitter_patterns = [
        r'twitter\.com/\w+/status/',
        r'x\.com/\w+/status/',
    ]
    
    for pattern in instagram_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return "instagram"
    
    for pattern in youtube_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return "youtube"
    
    for pattern in tiktok_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return "tiktok"
    
    for pattern in twitter_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return "twitter"
    
    return None


def sanitize_url(url: str) -> str:
    """Clean and normalize a URL."""
    # Remove tracking parameters
    url = re.sub(r'[\?&](utm_source|utm_medium|utm_campaign|igshid|share_id)=[^&]*', '', url)
    # Remove trailing slashes
    url = url.rstrip('/')
    return url.strip()


# ==================== File Operations ====================

def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def get_total_size(file_paths: list[str]) -> int:
    """Get total size of multiple files in bytes."""
    return sum(get_file_size(f) for f in file_paths)


def count_files(file_paths: list[str]) -> int:
    """Count number of files."""
    return len(file_paths)


def safe_delete(file_path: str):
    """Safely delete a file if it exists."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Deleted file: {file_path}")
    except OSError as e:
        logger.error(f"Failed to delete file {file_path}: {e}")


def cleanup_temp_files(file_paths: list[str], max_age_hours: int = 1):
    """Clean up temporary files older than specified hours."""
    current_time = datetime.now().timestamp()
    max_age_seconds = max_age_hours * 3600
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    safe_delete(file_path)
        except OSError as e:
            logger.error(f"Error checking file {file_path}: {e}")


# ==================== Format Conversion ====================

def format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    if bytes < 0:
        return "0 B"
    elif bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.2f} KB"
    elif bytes < 1024 ** 3:
        return f"{bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{bytes / (1024 ** 3):.2f} GB"


def format_duration(seconds: int) -> str:
    """Format seconds into HH:MM:SS format."""
    if seconds < 0:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_timestamp(timestamp: str) -> str:
    """Format a timestamp string into readable format."""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return timestamp


# ==================== Text Formatting ====================

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """Escape special markdown characters for Telegram."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def create_stats_message(stats: dict) -> str:
    """Create a formatted statistics message."""
    messages = []
    messages.append("📊 *Bot Statistics*")
    messages.append("")
    messages.append(f"👥 Total Users: `{stats.get('total_users', 0)}`")
    messages.append(f"🟢 Active (7 days): `{stats.get('active_users_7d', 0)}`")
    messages.append(f"📥 Total Downloads: `{stats.get('total_downloads', 0)}`")
    messages.append(f"⚡ Last 24h: `{stats.get('downloads_24h', 0)}`")
    messages.append(f"💾 Data Transferred: `{format_bytes(stats.get('total_data_transferred_bytes', 0))}`")
    
    return "\n".join(messages)


def create_user_info_message(user: dict, downloads: list = None) -> str:
    """Create a formatted user info message."""
    messages = []
    messages.append("👤 *User Information*")
    messages.append("")
    
    name = user.get('first_name', 'Unknown')
    if user.get('last_name'):
        name += f" {user['last_name']}"
    if user.get('username'):
        name += f" (@{user['username']})"
    
    messages.append(f"*Name:* {escape_markdown(name)}")
    messages.append(f"*ID:* `{user.get('user_id', 'Unknown')}`")
    messages.append(f"*Total Downloads:* `{user.get('total_downloads', 0)}`")
    messages.append(f"*First Seen:* {format_timestamp(user.get('first_seen', ''))}")
    messages.append(f"*Last Seen:* {format_timestamp(user.get('last_seen', ''))}")
    
    if downloads:
        messages.append("")
        messages.append(f"*Recent Downloads:* {len(downloads)}")
        for dl in downloads[:5]:  # Show last 5 downloads
            platform_icon = "📷" if dl['platform'] == "instagram" else "🎥"
            messages.append(f"  {platform_icon} {dl['platform']} - {format_timestamp(dl['timestamp'])}")
    
    return "\n".join(messages)


# ==================== Hashing & Caching ====================

def calculate_file_hash(file_path: str, algorithm: str = "md5") -> str:
    """Calculate hash of a file."""
    hash_func = hashlib.new(algorithm)
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except OSError as e:
        logger.error(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def generate_url_hash(url: str) -> str:
    """Generate a hash for a URL (useful for caching)."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


# ==================== Validation Helpers ====================

def is_valid_telegram_id(user_id) -> bool:
    """Check if a value is a valid Telegram user ID."""
    try:
        user_id = int(user_id)
        return user_id > 0
    except (ValueError, TypeError):
        return False


def validate_file_type(file_path: str, allowed_extensions: list[str]) -> bool:
    """Check if a file has an allowed extension."""
    ext = Path(file_path).suffix.lower()
    return ext in allowed_extensions


# ==================== Rate Limiting Helpers ====================

class RateLimiter:
    """Simple rate limiter for bot commands."""
    
    def __init__(self, max_calls: int = 10, period: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the period
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = {}  # user_id -> list of timestamps
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if a user is allowed to make a call."""
        now = datetime.now().timestamp()
        
        if user_id not in self.calls:
            self.calls[user_id] = []
        
        # Remove old calls outside the period
        self.calls[user_id] = [
            t for t in self.calls[user_id] 
            if now - t < self.period
        ]
        
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        
        self.calls[user_id].append(now)
        return True
    
    def get_remaining(self, user_id: int) -> int:
        """Get remaining calls for a user."""
        now = datetime.now().timestamp()
        
        if user_id not in self.calls:
            return self.max_calls
        
        # Remove old calls
        self.calls[user_id] = [
            t for t in self.calls[user_id] 
            if now - t < self.period
        ]
        
        return max(0, self.max_calls - len(self.calls[user_id]))
