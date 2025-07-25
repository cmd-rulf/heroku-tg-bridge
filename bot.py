import os
import logging
import heroku3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
HEROKU_AUTH_TOKEN = os.environ.get("HEROKU_AUTH_TOKEN")
BOT_PASSWORD = os.environ.get("BOT_PASSWORD")

(
    SELECTING_ACTION,
    SELECTING_APP,
    SELECTING_APP_FOR_ENV,
    SELECTING_ENV_ACTION,
    ENTERING_ENV_KEY,
    ENTERING_ENV_VALUE,
    CONFIRM_ENV_DELETE,
    SELECTING_APP_FOR_LOGS,
    SELECTING_APP_FOR_RESTART,
) = range(9)


def get_heroku_conn():
    if not HEROKU_AUTH_TOKEN:
        logger.error("HEROKU_AUTH_TOKEN not set!")
        return None
    try:
        return heroku3.from_key(HEROKU_AUTH_TOKEN)
    except Exception as e:
        logger.error(f"Failed to connect to Heroku: {e}")
        return None

user_authenticated = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    if user_id in user_authenticated and user_authenticated[user_id]:
        await show_main_menu(update, context)
        return SELECTING_ACTION

    await update.message.reply_text(
        "Welcome to the Heroku Bot Manager!\n\n"
        "Please enter the password to continue."
    )
    return "PASSWORD"


async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    provided_password = update.message.text

    if provided_password == BOT_PASSWORD:
        user_authenticated[user_id] = True
        await update.message.reply_text("Authentication successful!")
        await show_main_menu(update, context)
        return SELECTING_ACTION
    else:
        await update.message.reply_text("Incorrect password. Please try again.")
        return "PASSWORD"


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Restart Dynos", callback_data="restart_dynos")],
        [InlineKeyboardButton("View Logs", callback_data="view_logs")],
        [InlineKeyboardButton("Manage ENVs", callback_data="manage_envs")],
        [InlineKeyboardButton("List Apps", callback_data="list_apps")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Please choose an action:", reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Please choose an action:", reply_markup=reply_markup)


async def list_apps_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await query.edit_message_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        apps = heroku_conn.apps()
        if not apps:
            await query.edit_message_text("You have no applications on Heroku.")
            return ConversationHandler.END

        message = "Your Heroku Apps:\n\n"
        for app in apps:
            message += f"- `{app.name}`\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error listing apps: {e}")
        await query.edit_message_text("An error occurred while fetching your apps.")

    return SELECTING_ACTION


async def ask_for_app_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, next_state: int, action_text: str) -> int:
    query = update.callback_query
    await query.answer()

    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await query.edit_message_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        apps = heroku_conn.apps()
        if not apps:
            await query.edit_message_text("You have no applications on Heroku.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(app.name, callback_data=f"app_{app.id}")] for app in apps
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(f"Please select an app to {action_text}:", reply_markup=reply_markup)
        return next_state

    except Exception as e:
        logger.error(f"Error fetching apps for selection: {e}")
        await query.edit_message_text("An error occurred while fetching your apps.")
        return ConversationHandler.END


async def restart_dynos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await ask_for_app_selection(update, context, SELECTING_APP_FOR_RESTART, "restart dynos for")

async def restart_selected_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    app_id = query.data.split("app_")[1]

    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await query.edit_message_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        app = heroku_conn.app(app_id)
        await query.edit_message_text(f"Restarting all dynos for `{app.name}`...", parse_mode='Markdown')
        app.restart()
        await query.edit_message_text(f"✅ Successfully restarted all dynos for `{app.name}`.", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error restarting dynos for app {app_id}: {e}")
        await query.edit_message_text("An error occurred while restarting the dynos.")
    
    await show_main_menu(update, context)
    return SELECTING_ACTION


async def view_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await ask_for_app_selection(update, context, SELECTING_APP_FOR_LOGS, "view logs for")

async def show_logs_for_selected_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    app_id = query.data.split("app_")[1]

    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await query.edit_message_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        app = heroku_conn.app(app_id)
        await query.edit_message_text(f"Fetching logs for `{app.name}`...", parse_mode='Markdown')
        
        logs = app.get_log(lines=100)

        if not logs:
            await query.edit_message_text(f"No logs found for `{app.name}`.", parse_mode='Markdown')
        else:
            log_message = f"Logs for `{app.name}`:\n\n```\n{logs}\n```"
            if len(log_message) > 4096:
                await query.edit_message_text(f"Logs for `{app.name}` are too long. Sending the last 4000 characters.", parse_mode='Markdown')
                await context.bot.send_message(chat_id=query.message.chat_id, text=f"```\n{logs[-4000:]}\n```", parse_mode='Markdown')
            else:
                 await query.edit_message_text(log_message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching logs for app {app_id}: {e}")
        await query.edit_message_text("An error occurred while fetching the logs.")

    await show_main_menu(update, context)
    return SELECTING_ACTION


async def manage_envs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await ask_for_app_selection(update, context, SELECTING_APP_FOR_ENV, "manage environment variables for")

async def show_env_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    app_id = query.data.split("app_")[1]
    context.user_data['selected_app_id'] = app_id

    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await query.edit_message_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        app = heroku_conn.app(app_id)
        config = app.config()
        config_dict = config.to_dict()

        message = f"ENVs for `{app.name}`:\n\n"
        if config_dict:
            max_key_length = max(len(key) for key in config_dict.keys()) if config_dict else 0
            
            env_lines = []
            for key, value in sorted(config_dict.items()):
                display_value = '********' if any(s in key.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']) else value
                padded_key = key.ljust(max_key_length)
                env_lines.append(f"{padded_key} = {display_value}")
            
            formatted_envs = "\n".join(env_lines)
            message += f"```\n{formatted_envs}\n```"
        else:
            message += "No environment variables found.\n"

        keyboard = [
            [
                InlineKeyboardButton("Add/Update ENV", callback_data="add_env"),
                InlineKeyboardButton("Delete ENV", callback_data="delete_env"),
            ],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        return SELECTING_ENV_ACTION

    except Exception as e:
        logger.error(f"Error fetching ENVs for app {app_id}: {e}")
        await query.edit_message_text("An error occurred while fetching environment variables.")
        return SELECTING_ACTION

async def ask_for_env_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['env_action'] = query.data
    
    prompt_text = "Please send the ENV variable key you want to add/update."
    if query.data == 'delete_env':
        prompt_text = "Please send the ENV variable key you want to delete."

    await query.edit_message_text(text=prompt_text)
    return ENTERING_ENV_KEY

async def ask_for_env_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['env_key'] = update.message.text
    
    if context.user_data.get('env_action') == 'delete_env':
        key_to_delete = context.user_data['env_key']
        app_id = context.user_data['selected_app_id']
        heroku_conn = get_heroku_conn()
        app = heroku_conn.app(app_id)

        keyboard = [
            [
                InlineKeyboardButton("Yes, Delete it", callback_data=f"confirm_delete_{key_to_delete}"),
                InlineKeyboardButton("No, Cancel", callback_data="cancel_delete"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Are you sure you want to delete the ENV var `{key_to_delete}` from `{app.name}`?", reply_markup=reply_markup, parse_mode='Markdown')
        return CONFIRM_ENV_DELETE

    await update.message.reply_text(f"OK. Now send the value for `{context.user_data['env_key']}`.")
    return ENTERING_ENV_VALUE

async def set_env_variable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    env_value = update.message.text
    env_key = context.user_data['env_key']
    app_id = context.user_data['selected_app_id']

    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await update.message.reply_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        app = heroku_conn.app(app_id)
        await update.message.reply_text(f"Setting `{env_key}` for `{app.name}`...", parse_mode='Markdown')
        
        config = app.config()
        config[env_key] = env_value
        
        await update.message.reply_text(f"✅ Successfully set `{env_key}` for `{app.name}`.", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error setting ENV for app {app_id}: {e}")
        await update.message.reply_text("An error occurred while setting the environment variable.")

    await show_main_menu(update, context)
    return SELECTING_ACTION

async def confirm_delete_env(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_delete":
        await query.edit_message_text("Deletion cancelled.")
        await show_main_menu(update, context)
        return SELECTING_ACTION

    key_to_delete = query.data.split("confirm_delete_")[1]
    app_id = context.user_data['selected_app_id']
    
    heroku_conn = get_heroku_conn()
    if not heroku_conn:
        await query.edit_message_text("Error: Heroku connection failed.")
        return ConversationHandler.END

    try:
        app = heroku_conn.app(app_id)
        await query.edit_message_text(f"Deleting `{key_to_delete}` from `{app.name}`...", parse_mode='Markdown')
        
        config = app.config()
        del config[key_to_delete]

        await query.edit_message_text(f"✅ Successfully deleted `{key_to_delete}` from `{app.name}`.", parse_mode='Markdown')

    except KeyError:
        await query.edit_message_text(f"Error: ENV var `{key_to_delete}` not found.", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error deleting ENV for app {app_id}: {e}")
        await query.edit_message_text("An error occurred while deleting the environment variable.")

    await show_main_menu(update, context)
    return SELECTING_ACTION


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)
    return SELECTING_ACTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    await show_main_menu(update, context)
    return ConversationHandler.END

def main() -> None:
    if not all([TELEGRAM_BOT_TOKEN, HEROKU_AUTH_TOKEN, BOT_PASSWORD]):
        logger.critical(
            "FATAL: Missing one or more required environment variables: "
            "TELEGRAM_BOT_TOKEN, HEROKU_AUTH_TOKEN, BOT_PASSWORD"
        )
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            "PASSWORD": [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            SELECTING_ACTION: [
                CallbackQueryHandler(restart_dynos_handler, pattern="^restart_dynos$"),
                CallbackQueryHandler(view_logs_handler, pattern="^view_logs$"),
                CallbackQueryHandler(manage_envs_handler, pattern="^manage_envs$"),
                CallbackQueryHandler(list_apps_callback, pattern="^list_apps$"),
                CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
            ],
            SELECTING_APP_FOR_RESTART: [
                CallbackQueryHandler(restart_selected_app, pattern="^app_"),
                CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
            ],
            SELECTING_APP_FOR_LOGS: [
                CallbackQueryHandler(show_logs_for_selected_app, pattern="^app_"),
                CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
            ],
            SELECTING_APP_FOR_ENV: [
                CallbackQueryHandler(show_env_options, pattern="^app_"),
                CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
            ],
            SELECTING_ENV_ACTION: [
                CallbackQueryHandler(ask_for_env_key, pattern="^(add|delete)_env$"),
                CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
            ],
            ENTERING_ENV_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_for_env_value)],
            ENTERING_ENV_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_env_variable)],
            CONFIRM_ENV_DELETE: [
                CallbackQueryHandler(confirm_delete_env, pattern="^confirm_delete_"),
                CallbackQueryHandler(back_to_main_menu, pattern="^cancel_delete$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        per_user=True,
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
