# Heroku Management Telegram Bot

A powerful and secure Telegram bot that lets you manage your Heroku applications directly from your phone. Built with **Python** and [`python-telegram-bot`](https://python-telegram-bot.org/), utilizing the official [`heroku3`](https://pypi.org/project/heroku3/) library.

This bot features an intuitive inline button interface and robust password protection, ensuring only authorized users can access your Heroku management functions.

---

## Features

- **Secure Access**: Password-protected bot. Only users who provide the correct password can operate the bot.
- **List Applications**: View a clear list of all your Heroku apps.
- **Restart Dynos**: Restart all dynos for any application in just two taps.
- **View Logs**: Fetch and view the last 100 lines of logs for any app—right within Telegram.
- **Manage Environment Variables (ENVs)**:
  - View all ENVs in a beautifully formatted and aligned list.
  - Sensitive variables (containing `KEY`, `TOKEN`, `SECRET`, etc.) are masked for security.
  - Add new variables or update existing ones.
  - Delete variables with a confirmation step to prevent accidents.

---

## Setup and Installation

### 1. Prerequisites

- Python 3.8+
- **Telegram Bot Token**: Obtain one from [@BotFather](https://t.me/BotFather) on Telegram.
- **Heroku Auth Token**: Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) and run  
  ```bash
  heroku auth:token
  ```
  in your terminal.

### 2. Clone the Repository

```bash
git clone https://github.com/RHiNo410/heroku-tg-bridge
cd heroku-tg-bridge
```

### 3. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Set Environment Variables

For security, all configuration is loaded from environment variables. **Do not hardcode credentials in the scripts.**

#### On Linux/macOS:

```sh
export TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
export HEROKU_AUTH_TOKEN="YOUR_HEROKU_AUTH_TOKEN"
export BOT_PASSWORD="CHOOSE_A_STRONG_PASSWORD"
```

#### On Windows (Command Prompt):

```cmd
set TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
set HEROKU_AUTH_TOKEN="YOUR_HEROKU_AUTH_TOKEN"
set BOT_PASSWORD="CHOOSE_A_STRONG_PASSWORD"
```

---

## Running the Bot

Once the environment variables are set, start the bot with:

```bash
python3 bot.py
```

The bot will now be running and listening for commands on Telegram.

---

## How to Use

1. Open Telegram and find the bot you created.
2. Send the `/start` command.
3. The bot will prompt you for the password you set in the `BOT_PASSWORD` environment variable.
4. After successful authentication, the main menu will appear with all management options.

---

## Security Notes

- **Never share your Heroku or Telegram tokens.**
- **Always use a strong, unique password for `BOT_PASSWORD`.**
- All sensitive environment variable values are masked in the bot interface.

---

## License

[MIT](LICENSE)

---

## Credits

- [python-telegram-bot](https://python-telegram-bot.org/)
- [heroku3 on PyPI](https://pypi.org/project/heroku3/)

---

Happy Heroku managing! 🚀
