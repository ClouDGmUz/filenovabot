"""
Database module for user history tracking and analytics.
Uses SQLite for local storage with automatic schema management.
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_database.db")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def initialize_database():
    """Create database tables if they don't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_downloads INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0
            )
        """)
        
        # Download history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                platform TEXT NOT NULL,
                media_type TEXT,
                file_count INTEGER DEFAULT 0,
                file_size_bytes INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                preference_key TEXT NOT NULL,
                preference_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Bot statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_key TEXT UNIQUE NOT NULL,
                stat_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_download_user_id 
            ON download_history(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_download_timestamp 
            ON download_history(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_download_platform 
            ON download_history(platform)
        """)
        
        logger.info("Database initialized successfully")


# ==================== User Management ====================

def register_or_update_user(user_id: int, username: str = None, 
                           first_name: str = None, last_name: str = None):
    """Register a new user or update existing user information."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, last_seen)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = COALESCE(excluded.username, username),
                first_name = COALESCE(excluded.first_name, first_name),
                last_name = COALESCE(excluded.last_name, last_name),
                last_seen = CURRENT_TIMESTAMP
        """, (user_id, username, first_name, last_name))


def increment_user_downloads(user_id: int):
    """Increment the download count for a user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET total_downloads = total_downloads + 1,
                last_seen = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def get_user(user_id: int) -> Optional[dict]:
    """Get user information by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_users(limit: int = 100, offset: int = 0) -> list[dict]:
    """Get all users with pagination."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users 
            ORDER BY last_seen DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]


def ban_user(user_id: int):
    """Ban a user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET is_banned = 1 WHERE user_id = ?
        """, (user_id,))


def unban_user(user_id: int):
    """Unban a user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET is_banned = 0 WHERE user_id = ?
        """, (user_id,))


def is_user_banned(user_id: int) -> bool:
    """Check if a user is banned."""
    user = get_user(user_id)
    return user.get("is_banned", 0) == 1 if user else False


# ==================== Download History ====================

def record_download(user_id: int, url: str, platform: str, 
                   media_type: str = None, file_count: int = 0,
                   file_size_bytes: int = 0, status: str = "success",
                   error_message: str = None):
    """Record a download in history."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO download_history 
            (user_id, url, platform, media_type, file_count, file_size_bytes, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, url, platform, media_type, file_count, file_size_bytes, 
              status, error_message))


def get_user_downloads(user_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
    """Get download history for a specific user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM download_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]


def get_download_count(user_id: int) -> int:
    """Get total download count for a user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM download_history 
            WHERE user_id = ?
        """, (user_id,))
        return cursor.fetchone()["count"]


# ==================== Statistics & Analytics ====================

def get_platform_stats(days: int = 30) -> dict:
    """Get download statistics by platform."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                platform,
                COUNT(*) as total_downloads,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(file_count) as avg_files,
                SUM(file_size_bytes) as total_size
            FROM download_history
            WHERE timestamp >= datetime('now', ?)
            GROUP BY platform
        """, (f"-{days} days",))
        
        stats = {}
        for row in cursor.fetchall():
            stats[row["platform"]] = {
                "total_downloads": row["total_downloads"],
                "unique_users": row["unique_users"],
                "avg_files": round(row["avg_files"], 2),
                "total_size_bytes": row["total_size"] or 0
            }
        return stats


def get_overall_stats() -> dict:
    """Get overall bot statistics."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()["count"]
        
        # Active users (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE last_seen >= datetime('now', '-7 days')
        """)
        active_users = cursor.fetchone()["count"]
        
        # Total downloads
        cursor.execute("SELECT COUNT(*) as count FROM download_history")
        total_downloads = cursor.fetchone()["count"]
        
        # Downloads in last 24 hours
        cursor.execute("""
            SELECT COUNT(*) as count FROM download_history 
            WHERE timestamp >= datetime('now', '-1 days')
        """)
        recent_downloads = cursor.fetchone()["count"]
        
        # Total data transferred
        cursor.execute("SELECT SUM(file_size_bytes) as total FROM download_history")
        total_size = cursor.fetchone()["total"] or 0
        
        return {
            "total_users": total_users,
            "active_users_7d": active_users,
            "total_downloads": total_downloads,
            "downloads_24h": recent_downloads,
            "total_data_transferred_bytes": total_size
        }


def get_top_users(limit: int = 10) -> list[dict]:
    """Get top users by download count."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.*, 
                   COUNT(dh.id) as download_count
            FROM users u
            LEFT JOIN download_history dh ON u.user_id = dh.user_id
            GROUP BY u.user_id
            ORDER BY download_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_daily_activity(days: int = 30) -> list[dict]:
    """Get daily download activity."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as downloads,
                COUNT(DISTINCT user_id) as users
            FROM download_history
            WHERE timestamp >= datetime('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, (f"-{days} days",))
        return [dict(row) for row in cursor.fetchall()]


# ==================== User Preferences ====================

def set_user_preference(user_id: int, key: str, value: str):
    """Set a user preference."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_preferences (user_id, preference_key, preference_value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                preference_key = excluded.preference_key,
                preference_value = excluded.preference_value,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, key, value))


def get_user_preference(user_id: int, key: str) -> Optional[str]:
    """Get a user preference."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT preference_value FROM user_preferences 
            WHERE user_id = ? AND preference_key = ?
        """, (user_id, key))
        row = cursor.fetchone()
        return row["preference_value"] if row else None


# ==================== Utility Functions ====================

def format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.2f} KB"
    elif bytes < 1024 ** 3:
        return f"{bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{bytes / (1024 ** 3):.2f} GB"


def get_database_size() -> str:
    """Get the size of the database file."""
    if os.path.exists(DB_PATH):
        size = os.path.getsize(DB_PATH)
        return format_bytes(size)
    return "0 B"


def export_user_data(user_id: int) -> dict:
    """Export all data for a specific user."""
    user = get_user(user_id)
    if not user:
        return {}
    
    downloads = get_user_downloads(user_id, limit=1000)
    
    return {
        "user": user,
        "download_history": downloads,
        "exported_at": datetime.now().isoformat()
    }


def cleanup_old_data(days: int = 365):
    """Clean up download history older than specified days."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM download_history 
            WHERE timestamp < datetime('now', ?)
        """, (f"-{days} days",))
        deleted = cursor.rowcount
        logger.info(f"Cleaned up {deleted} old download records")
        return deleted
