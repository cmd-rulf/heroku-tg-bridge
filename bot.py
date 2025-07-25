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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
HEROKU_AUTH_TOKEN = os.environ.get("HEROKU_AUTH_TOKEN")
BOT_PASSWORD = os.environ.get("BOT_PASSWORD")
ENVS_PER_PAGE = 10

(
    SELECTING_ACTION,
    SELECTING_APP_FOR_ENV,
    SELECTING_ENV_ACTION,
    ENTERING_ENV_KEY_ADD,
    ENTERING_ENV_VALUE_ADD,
    ENTERING_ENV_KEY_DELETE,
    CONFIRM_ENV_DELETE,
    SELECTING_APP_FOR_LOGS,
    SELECTING_APP_FOR_RESTART,
    AWAITING_NEW_VALUE,
    CONFIRM_UPDATE,
) = range(11)


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
    context.user_data.pop('env_vars', None)
    context.user_data.pop('selected_app_id', None)
    
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
            log_message = f"No logs found for `{app.name}`."
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

async def show_env_options(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    
    if 'env_vars' not in context.user_data:
        app_id = context.user_data.get('selected_app_id')
        
        if not app_id and query:
            try:
                app_id = query.data.split("app_")[1]
                context.user_data['selected_app_id'] = app_id
            except IndexError:
                await query.edit_message_text("Error: Could not determine the application. Please go back and try again.")
                return SELECTING_ACTION
        elif not app_id and not query:
             await update.message.reply_text("Error: Session expired. Please start over.")
             return ConversationHandler.END

        heroku_conn = get_heroku_conn()
        if not heroku_conn:
            await query.edit_message_text("Error: Heroku connection failed.")
            return ConversationHandler.END
        try:
            app = heroku_conn.app(app_id)
            context.user_data['app_name'] = app.name
            config = app.config()
            context.user_data['env_vars'] = sorted(config.to_dict().items())
        except Exception as e:
            logger.error(f"Error fetching ENVs for app {app_id}: {e}")
            await query.edit_message_text("An error occurred while fetching ENVs.")
            return SELECTING_ACTION

    env_vars = context.user_data['env_vars']
    app_name = context.user_data['app_name']
    
    start_index = page * ENVS_PER_PAGE
    end_index = start_index + ENVS_PER_PAGE
    paginated_vars = env_vars[start_index:end_index]

    keyboard = []
    if paginated_vars:
        for key, value in paginated_vars:
            display_value = '********' if any(s in key.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']) else value
            keyboard.append([
                InlineKeyboardButton(f"{key}", callback_data="noop"),
                InlineKeyboardButton(f"{display_value}", callback_data=f"update_env_{key}")
            ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"env_page_{page - 1}"))
    if end_index < len(env_vars):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"env_page_{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([
        InlineKeyboardButton("➕ Add New", callback_data="add_env"),
        InlineKeyboardButton("➖ Delete", callback_data="delete_env"),
    ])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    total_pages = (len(env_vars) + ENVS_PER_PAGE - 1) // ENVS_PER_PAGE or 1
    message_text = f"ENVs for `{app_name}` (Page {page + 1}/{total_pages}):"

    if query:
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return SELECTING_ENV_ACTION

async def env_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    page = int(query.data.split("_")[-1])
    return await show_env_options(update, context, page=page)

async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()

async def start_env_update_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key_to_update = query.data.split("update_env_")[1]
    context.user_data['key_to_update'] = key_to_update
    await query.edit_message_text(f"Please send the new value for `{key_to_update}`.", parse_mode='Markdown')
    return AWAITING_NEW_VALUE

async def get_new_value_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_value = update.message.text
    key_to_update = context.user_data.get('key_to_update')
    context.user_data['new_value'] = new_value
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_update"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_update"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Are you sure you want to set `{key_to_update}` to this new value?\n\n`{new_value}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return CONFIRM_UPDATE

async def process_env_update_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "cancel_update":
        await query.edit_message_text("Update cancelled.")
        context.user_data.pop('env_vars', None)
        return await show_env_options(update, context)

    app_id = context.user_data['selected_app_id']
    key = context.user_data['key_to_update']
    new_value = context.user_data['new_value']
    heroku_conn = get_heroku_conn()
    try:
        app = heroku_conn.app(app_id)
        await query.edit_message_text(f"Updating `{key}` for `{app.name}`...", parse_mode='Markdown')
        config = app.config()
        config[key] = new_value
        await query.edit_message_text(f"✅ Successfully updated `{key}`. Refreshing list...")
    except Exception as e:
        logger.error(f"Error updating ENV for app {app_id}: {e}")
        await query.edit_message_text("An error occurred while updating the ENV.")
    
    context.user_data.pop('env_vars', None)
    return await show_env_options(update, context)

async def add_env_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please send the key for the new environment variable.")
    return ENTERING_ENV_KEY_ADD

async def add_env_get_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_env_key'] = update.message.text
    await update.message.reply_text(f"OK. Now send the value for `{context.user_data['new_env_key']}`.")
    return ENTERING_ENV_VALUE_ADD

async def add_env_get_value_and_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_env_value = update.message.text
    new_env_key = context.user_data['new_env_key']
    app_id = context.user_data['selected_app_id']
    heroku_conn = get_heroku_conn()
    try:
        app = heroku_conn.app(app_id)
        await update.message.reply_text(f"Adding `{new_env_key}` to `{app.name}`...", parse_mode='Markdown')
        config = app.config()
        config[new_env_key] = new_env_value
        await update.message.reply_text(f"✅ Successfully added `{new_env_key}`. Refreshing list...")
    except Exception as e:
        logger.error(f"Error adding ENV for app {app_id}: {e}")
        await update.message.reply_text("An error occurred while adding the environment variable.")
    
    context.user_data.pop('env_vars', None)
    return await show_env_options(update, context)

async def delete_env_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please send the key of the environment variable you want to delete.")
    return ENTERING_ENV_KEY_DELETE

async def delete_env_get_key_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    key_to_delete = update.message.text
    context.user_data['key_to_delete'] = key_to_delete
    app_name = context.user_data['app_name']
    keyboard = [
        [
            InlineKeyboardButton("Yes, Delete it", callback_data="confirm_delete"),
            InlineKeyboardButton("No, Cancel", callback_data="cancel_delete"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Are you sure you want to delete `{key_to_delete}` from `{app_name}`?", reply_markup=reply_markup, parse_mode='Markdown')
    return CONFIRM_ENV_DELETE

async def process_delete_env_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "cancel_delete":
        await query.edit_message_text("Deletion cancelled.")
        context.user_data.pop('env_vars', None)
        return await show_env_options(update, context)
    
    key_to_delete = context.user_data['key_to_delete']
    app_id = context.user_data['selected_app_id']
    heroku_conn = get_heroku_conn()
    try:
        app = heroku_conn.app(app_id)
        await query.edit_message_text(f"Deleting `{key_to_delete}` from `{app.name}`...", parse_mode='Markdown')
        config = app.config()
        del config[key_to_delete]
        await query.edit_message_text(f"✅ Successfully deleted `{key_to_delete}`. Refreshing list...")
    except KeyError:
        await query.edit_message_text(f"Error: ENV var `{key_to_delete}` not found.")
    except Exception as e:
        logger.error(f"Error deleting ENV for app {app_id}: {e}")
        await query.edit_message_text("An error occurred while deleting the ENV.")
    
    context.user_data.pop('env_vars', None)
    return await show_env_options(update, context)

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)
    return SELECTING_ACTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    if update.callback_query:
        await show_main_menu(update, context)
    return ConversationHandler.END

def main() -> None:
    if not all([TELEGRAM_BOT_TOKEN, HEROKU_AUTH_TOKEN, BOT_PASSWORD]):
        logger.critical("FATAL: Missing required environment variables.")
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
            ],
            SELECTING_APP_FOR_RESTART: [CallbackQueryHandler(restart_selected_app, pattern="^app_")],
            SELECTING_APP_FOR_LOGS: [CallbackQueryHandler(show_logs_for_selected_app, pattern="^app_")],
            SELECTING_APP_FOR_ENV: [CallbackQueryHandler(show_env_options, pattern="^app_")],
            SELECTING_ENV_ACTION: [
                CallbackQueryHandler(env_page_callback, pattern="^env_page_"),
                CallbackQueryHandler(start_env_update_flow, pattern="^update_env_"),
                CallbackQueryHandler(add_env_start, pattern="^add_env$"),
                CallbackQueryHandler(delete_env_start, pattern="^delete_env$"),
                CallbackQueryHandler(noop_callback, pattern="^noop$"),
                CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
            ],
            AWAITING_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_value_and_confirm)],
            CONFIRM_UPDATE: [CallbackQueryHandler(process_env_update_confirmation, pattern="^(confirm|cancel)_update$")],
            ENTERING_ENV_KEY_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_env_get_key)],
            ENTERING_ENV_VALUE_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_env_get_value_and_set)],
            ENTERING_ENV_KEY_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_env_get_key_and_confirm)],
            CONFIRM_ENV_DELETE: [CallbackQueryHandler(process_delete_env_confirmation, pattern="^(confirm|cancel)_delete$")],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(back_to_main_menu, pattern="^main_menu$"),
        ],
        per_user=True,
    )

    application.add_handler(conv_handler)
    
    logger.warning("Bot started successfully. Listening for updates...")
    
    application.run_polling()


if __name__ == "__main__":
    main()
