"""
Admin commands and handlers for bot management.
Provides statistics, user management, and maintenance functions.
"""

import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import BadRequest

import database as db
from utils import (
    create_stats_message, 
    create_user_info_message,
    format_bytes,
    truncate_text
)

logger = logging.getLogger(__name__)

# Admin user IDs - Add your Telegram user ID here
ADMIN_IDS = [5627225073]  # Example: [123456789, 987654321]


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    return user_id in ADMIN_IDS


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin menu."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    menu = (
        "🔧 *Admin Menu*\n\n"
        "📊 /stats - Bot statistics\n"
        "👥 /users - List users\n"
        "👤 /userinfo <id> - User details\n"
        "🔝 /topusers - Top users by downloads\n"
        "📈 /activity - Daily activity\n"
        "🚫 /ban <id> - Ban a user\n"
        "✅ /unban <id> - Unban a user\n"
        "🗑 /cleanup - Clean old data\n"
        "💾 /dbsize - Database size\n"
        "📤 /export <id> - Export user data"
    )
    
    await update.message.reply_text(menu, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    stats = db.get_overall_stats()
    message = create_stats_message(stats)
    
    # Add platform breakdown
    platform_stats = db.get_platform_stats()
    if platform_stats:
        message += "\n\n*Platform Breakdown:*\n"
        for platform, data in platform_stats.items():
            icon = "📷" if platform == "instagram" else "🎥" if platform == "youtube" else "📱"
            message += f"\n{icon} {platform.title()}: `{data['total_downloads']}` downloads"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List recent users."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    # Get limit from args if provided
    try:
        limit = int(context.args[0]) if context.args else 10
    except (ValueError, IndexError):
        limit = 10
    
    limit = min(limit, 50)  # Cap at 50
    
    users = db.get_all_users(limit=limit)
    
    if not users:
        await update.message.reply_text("No users found.")
        return
    
    message = "👥 *Recent Users*\n\n"
    for user in users:
        name = user.get('first_name', 'Unknown')
        username = f" (@{user['username']})" if user.get('username') else ""
        downloads = user.get('total_downloads', 0)
        banned = " 🚫" if user.get('is_banned') else ""
        message += f"• `{user['user_id']}` - {name}{username} - {downloads} downloads{banned}\n"
    
    message += f"\n*Showing {len(users)} users*"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed user information."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /userinfo <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number.")
        return
    
    user = db.get_user(target_user_id)
    if not user:
        await update.message.reply_text("User not found.")
        return
    
    downloads = db.get_user_downloads(target_user_id, limit=5)
    message = create_user_info_message(user, downloads)
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def topusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users by download count."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    try:
        limit = int(context.args[0]) if context.args else 10
    except (ValueError, IndexError):
        limit = 10
    
    limit = min(limit, 20)
    
    top_users = db.get_top_users(limit)
    
    if not top_users:
        await update.message.reply_text("No users found.")
        return
    
    message = "🔝 *Top Users by Downloads*\n\n"
    for i, user in enumerate(top_users, 1):
        name = user.get('first_name', 'Unknown')
        username = f" (@{user['username']})" if user.get('username') else ""
        downloads = user.get('total_downloads', 0)
        message += f"{i}. {name}{username} - `{downloads}` downloads\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def activity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show daily activity."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    try:
        days = int(context.args[0]) if context.args else 7
    except (ValueError, IndexError):
        days = 7
    
    days = min(days, 30)
    
    activity = db.get_daily_activity(days)
    
    if not activity:
        await update.message.reply_text("No activity recorded yet.")
        return
    
    message = "📈 *Daily Activity*\n\n"
    for day in activity:
        message += f"📅 {day['date']}: `{day['downloads']}` downloads by `{day['users']}` users\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    
    if target_user_id in ADMIN_IDS:
        await update.message.reply_text("⛔ Cannot ban an admin!")
        return
    
    db.ban_user(target_user_id)
    await update.message.reply_text(f"✅ User `{target_user_id}` has been banned.", parse_mode="Markdown")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    
    db.unban_user(target_user_id)
    await update.message.reply_text(f"✅ User `{target_user_id}` has been unbanned.", parse_mode="Markdown")


async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clean up old data."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    try:
        days = int(context.args[0]) if context.args else 365
    except (ValueError, IndexError):
        days = 365
    
    deleted = db.cleanup_old_data(days)
    await update.message.reply_text(f"🗑 Cleaned up `{deleted}` old download records.", parse_mode="Markdown")


async def dbsize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show database size."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    size = db.get_database_size()
    await update.message.reply_text(f"💾 Database size: `{size}`", parse_mode="Markdown")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export user data."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /export <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    
    user_data = db.export_user_data(target_user_id)
    
    if not user_data:
        await update.message.reply_text("User not found.")
        return
    
    # Format as JSON-like text
    import json
    export_text = json.dumps(user_data, indent=2, default=str)
    
    # Truncate if too long for Telegram message
    if len(export_text) > 4000:
        export_text = export_text[:4000] + "\n\n... (truncated)"
    
    message = f"📤 *User Data Export*\n\n```json\n{export_text}\n```"
    
    await update.message.reply_text(message, parse_mode="Markdown")


def get_admin_handlers() -> list:
    """Get all admin command handlers."""
    return [
        CommandHandler("admin", admin_start),
        CommandHandler("stats", stats_command),
        CommandHandler("users", users_command),
        CommandHandler("userinfo", userinfo_command),
        CommandHandler("topusers", topusers_command),
        CommandHandler("activity", activity_command),
        CommandHandler("ban", ban_command),
        CommandHandler("unban", unban_command),
        CommandHandler("cleanup", cleanup_command),
        CommandHandler("dbsize", dbsize_command),
        CommandHandler("export", export_command),
    ]
