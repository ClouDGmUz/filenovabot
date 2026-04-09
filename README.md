# Instagram & YouTube Downloader Telegram Bot

A feature-rich Telegram bot that downloads Instagram posts, reels, carousels, and YouTube videos with comprehensive user tracking and analytics.

## ✨ Features

### 🎯 Core Features
- **Instagram Downloads**: Posts, reels, carousels, and stories
- **YouTube Downloads**: Videos, shorts, and live streams
- **Multi-Platform Support**: Automatic platform detection from URLs
- **Progress Indicators**: Real-time download progress with spinners
- **Rate Limiting**: Prevents abuse (10 downloads/minute/user)

### 📊 User Features
- **Download History**: Track all your downloads with timestamps
- **Personal Statistics**: View your download stats and activity
- **User Registration**: Automatic user tracking
- **Enhanced Error Handling**: Clear error messages for failures

### 🔧 Admin Features
- **Bot Statistics**: Overall usage analytics and metrics
- **User Management**: View, ban, and unban users
- **Top Users**: See most active users by download count
- **Daily Activity**: Track bot usage over time
- **Database Management**: Clean old data, check database size
- **User Data Export**: Export complete user history

### 💾 Database
- **Local SQLite Database**: Automatic setup and management
- **User Tracking**: Registration, activity, and preferences
- **Download History**: Complete audit trail of all downloads
- **Analytics Platform**: Comprehensive statistics and reporting

## 📋 Commands

### User Commands
- `/start` - Start the bot and see your stats
- `/help` - Show help information
- `/history` - View your recent downloads (default: 10, max: 50)
- `/stats` - View your download statistics
- `/clear` - Clear download history

### Admin Commands
- `/admin` - Show admin menu
- `/stats` - Bot-wide statistics
- `/users [limit]` - List recent users
- `/userinfo <id>` - Detailed user information
- `/topusers [limit]` - Top users by downloads
- `/activity [days]` - Daily activity report
- `/ban <id>` - Ban a user
- `/unban <id>` - Unban a user
- `/cleanup [days]` - Clean old download records
- `/dbsize` - Show database size
- `/export <id>` - Export user data as JSON

## 🚀 Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Get a bot token**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Create a new bot and copy the token

3. **Configure environment**:
   Create a `.env` file in the project root:
   ```env
   TG_BOT_TOKEN=your_bot_token_here
   ```

4. **Configure admin access** (optional):
   Edit `admin.py` and add your Telegram user ID:
   ```python
   ADMIN_IDS = [123456789, 987654321]
   ```

5. **Run the bot**:
   ```bash
   python main.py
   ```

## 📁 Project Structure

```
DWbot/
├── main.py           # Main bot logic and handlers
├── database.py       # SQLite database management
├── utils.py          # Utility functions and helpers
├── admin.py          # Admin commands and handlers
├── requirements.txt  # Python dependencies
├── README.md         # This file
└── bot_database.db   # Auto-created SQLite database
```

## 🗄️ Database Schema

The bot automatically creates and manages the following tables:

- **users**: User registration and activity tracking
- **download_history**: Complete download audit trail
- **user_preferences**: User settings and preferences
- **bot_stats**: Bot-wide statistics and metrics

## ⚙️ Configuration

### Rate Limiting
Default: 10 downloads per minute per user

Modify in `main.py`:
```python
rate_limiter = RateLimiter(max_calls=10, period=60)
```

### Data Retention
Default: 365 days for download history

Clean old data with `/cleanup 365` command or use:
```python
db.cleanup_old_data(days=365)
```

## 🔒 Security

- User banning support
- Rate limiting to prevent abuse
- Admin-only commands protected by ID whitelist
- Automatic user registration
- URL sanitization and validation

## 🛠️ Technical Details

### URL Validation
- Automatic platform detection (Instagram, YouTube, TikTok, Twitter)
- URL sanitization removes tracking parameters
- Support for multiple URL formats per platform

### File Management
- Temporary files automatically cleaned up
- File size tracking and reporting
- Support for videos and images
- Multi-file carousels supported

### Analytics
- Per-user download tracking
- Platform-specific statistics
- Daily activity reports
- Data transfer volume tracking

## 📝 Example Usage

1. **Start the bot**:
   ```
   /start
   ```

2. **Download content**:
   ```
   https://www.instagram.com/p/ABC123/
   https://www.youtube.com/watch?v=XYZ789
   ```

3. **View history**:
   ```
   /history 20
   ```

4. **Check stats**:
   ```
   /stats
   ```

## 🐛 Troubleshooting

- **Bot doesn't respond**: Check `TG_BOT_TOKEN` in `.env`
- **Download fails**: Verify the URL is public and accessible
- **Admin commands don't work**: Add your user ID to `ADMIN_IDS` in `admin.py`
- **Database errors**: Delete `bot_database.db` and restart (will recreate)

## 📈 Future Enhancements

- [ ] TikTok downloads
- [ ] Twitter/X downloads
- [ ] Quality selection for videos
- [ ] Batch URL processing
- [ ] Web dashboard for analytics
- [ ] User preferences (quality, format)
- [ ] Scheduled downloads
- [ ] Proxy support

## 📄 License

MIT License

## 🤝 Contributing

Pull requests welcome! Please ensure to:
- Follow existing code style
- Add tests for new features
- Update documentation

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review bot logs for error details
3. Open an issue on GitHub
