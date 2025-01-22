import json
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import MessageEntityType
from telegram.ext import MessageHandler, filters

TOKEN = "7578907008:AAE-9JSmGaqm3fDR8yAlsBm-8CNo8Ui6x-Q"
DATA_FILE = "habit_data.json"


# Загрузка данных из файла
def load_data():
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Сохранение данных в файл
def save_data():
    with open(DATA_FILE, "w") as file:
        json.dump(habit_data, file, indent=4)

habit_data = load_data()

# Напоминание в 21:00
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = str(datetime.date.today())

    for user_id, data in habit_data.items():
        if data["last_report_date"] != today or not data["habit_done"]:
            try:
                await context.bot.send_message(chat_id=user_id, text="Напоминание! Отметь, ел ли ты сахар, используя /done.")
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

# Фиксация "не выполнено" в 00:00
async def finalize_day(context: ContextTypes.DEFAULT_TYPE):
    today = str(datetime.date.today())

    for user_id, data in habit_data.items():
        if data["last_report_date"] != today or not data["habit_done"]:
            data["days_participated"] += 1
            data["current_streak"] = 0
        data["habit_done"] = False
    save_data()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"
    if user_id not in habit_data:
        habit_data[user_id] = {
            "username": username,
            "days_participated": 0,
            "days_no_sugar": 0,
            "current_streak": 0,
            "last_report_date": None,
            "habit_done": False
        }
    save_data()
    await update.message.reply_text(f"Привет, {username}! Каждый день отмечай, ел ли ты сахар, используя /done. Если забудешь, я напомню!")

# Команда /done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"
    today = str(datetime.date.today())

    if user_id not in habit_data:
        habit_data[user_id] = {
            "username": username,
            "days_participated": 0,
            "days_no_sugar": 0,
            "current_streak": 0,
            "last_report_date": None,
            "habit_done": False
        }
    else:
        if "username" not in habit_data[user_id] or habit_data[user_id]["username"] != username:
            habit_data[user_id]["username"] = username
            save_data()

    if habit_data[user_id]["last_report_date"] == today:
        await update.message.reply_text("Ты уже отметил выполнение привычки сегодня.")
        return

    habit_data[user_id]["last_report_date"] = today
    habit_data[user_id]["habit_done"] = True
    habit_data[user_id]["days_participated"] += 1
    habit_data[user_id]["days_no_sugar"] += 1
    habit_data[user_id]["current_streak"] += 1
    save_data()
    await update.message.reply_text(f"Отлично, {username}! Ты не ел сахар сегодня!")

# Команда /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in habit_data:
        await update.message.reply_text("Ты ещё не зарегистрировался. Используй /start.")
        return

    user_data = habit_data[user_id]
    message = (
        f"Статистика:\n"
        f"Дней в программе: {user_data['days_participated']}\n"
        f"Дней без сахара: {user_data['days_no_sugar']}\n"
        f"Текущая серия: {user_data['current_streak']} дней"
    )
    await update.message.reply_text(message)

# Команда /leaderboard
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not habit_data:
        await update.message.reply_text("Ещё никто не участвует в программе.")
        return

    streak_leaders = sorted(
        habit_data.items(),
        key=lambda x: x[1].get("current_streak", 0),
        reverse=True
    )[:3]

    sugar_free_leaders = sorted(
        habit_data.items(),
        key=lambda x: x[1].get("days_no_sugar", 0),
        reverse=True
    )[:3]

    streak_message = "Лидеры по текущему стрику:\n"
    for i, (user_id, data) in enumerate(streak_leaders, start=1):
        username = data.get("username", f"User {user_id}")
        streak_message += f"{i}. {username}: {data['current_streak']} дней подряд\n"

    sugar_free_message = "Лидеры по дням без сахара:\n"
    for i, (user_id, data) in enumerate(sugar_free_leaders, start=1):
        username = data.get("username", f"User {user_id}")
        sugar_free_message += f"{i}. {username}: {data['days_no_sugar']} дней\n"

    await update.message.reply_text(f"{streak_message}\n{sugar_free_message}")

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Доступные команды:\n"
        "/start - Зарегистрироваться в программе.\n"
        "/done - Отметить, что ты не ел сахар сегодня.\n"
        "/stats - Показать твою статистику (дни участия, дни без сахара, текущая серия).\n"
        "/leaderboard - Показать лидеров программы (по текущему стрику и дням без сахара).\n"
        "/help - Показать эту подсказку."
    )
    await update.message.reply_text(help_text)

# Обработчик для удаления команд
async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == MessageEntityType.BOT_COMMAND:
                command = update.message.text.split()[0]
                if command != "/done":
                    try:
                        await update.message.delete()
                        print(f"Удалена команда: {command}")
                    except Exception as e:
                        print(f"Ошибка при удалении команды: {e}")
                return

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.COMMAND, handle_commands))

    job_queue = application.job_queue
    job_queue.run_daily(send_reminders, time=datetime.time(21, 0, 0))
    job_queue.run_daily(finalize_day, time=datetime.time(0, 0, 0))

    application.run_polling()

if __name__ == "__main__":
    main()