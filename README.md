# ORB Trading Bot

An automated Opening Range Breakout (ORB) trading bot that monitors stock prices and sends Telegram notifications when breakout conditions are met.

## Features

- **Opening Range Breakout Strategy**: Monitors the first 15 minutes of trading to establish support/resistance levels
- **Real-time Price Monitoring**: Tracks live prices using Angel One API
- **Telegram Notifications**: Sends buy/sell signals and status updates
- **Web Interface**: Health check endpoints for monitoring
- **Environment-based Configuration**: Secure credential management
- **Modern Python**: Updated to use latest libraries and async/await patterns

## Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd orb-trading-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.template .env
   # Edit .env with your actual credentials
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## Environment Variables

Create a `.env` file with the following variables:

```env
# Angel One API Configuration
API_KEY=your_api_key_here
CLIENT_ID=your_client_id_here
PIN=your_pin_here
TOTP_SECRET=your_totp_secret_here

# Trading Configuration
SYMBOL=RELIANCE-EQ
SYMBOL_TOKEN=2885
EXCHANGE=NSE
INTERVAL=FIFTEEN_MINUTE

# Telegram Configuration
TELEGRAM_TOKEN=your_telegram_bot_token_here
CHAT_ID=your_chat_id_here

# Server Configuration
FLASK_PORT=8080
FLASK_HOST=0.0.0.0
```

## Telegram Commands

- `/startbot` - Activate the trading bot
- `/stopbot` - Deactivate the trading bot
- `/status` - Check current bot status
- `/ltp` - Get current Last Traded Price
- `/holidaycheck` - Check if market is open
- `/help` - Show available commands

## How It Works

1. **Market Open**: Bot waits for market to open at 9:15 AM
2. **ORB Calculation**: Calculates high/low from 9:15-9:30 AM
3. **Signal Generation**: Monitors for breakouts above high or below low
4. **Notifications**: Sends Telegram alerts when signals are triggered

## API Endpoints

- `GET /` - Health check
- `GET /status` - Bot status and configuration

## Deployment

### Heroku
```bash
heroku create your-app-name
heroku config:set API_KEY=your_key
# Set all other environment variables
git push heroku main
```

### Railway/Render
1. Connect your GitHub repository
2. Set environment variables in the dashboard
3. Deploy

## Upgrades Made

1. **Python**: Updated to 3.11.9
2. **Telegram Bot**: Upgraded to python-telegram-bot v21.3 with async support
3. **Environment Variables**: Added python-dotenv for secure config management
4. **Error Handling**: Improved error handling and logging
5. **Code Structure**: Refactored into classes for better organization
6. **Session Management**: Added API session management for better reliability
7. **Web Interface**: Enhanced Flask endpoints for monitoring
8. **Async Support**: Converted to async/await pattern for better performance

## Security Notes

- Never commit your `.env` file
- Use environment variables for all sensitive data
- Regularly rotate your API keys and tokens
- Monitor your bot's activity through the web interface

## License

This project is for educational purposes. Please ensure compliance with your broker's API terms and local trading regulations.
