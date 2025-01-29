import json
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import MessageEntityType

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

async def eda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    today = str(datetime.date.today())
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"

    # Убедимся, что пользователь зарегистрирован
    if user_id not in habit_data:
        habit_data[user_id] = {
            "username": username,
            "days_participated": 0,
            "days_no_sugar": 0,
            "current_streak": 0,
            "last_report_date": None,
            "habit_done": False,
            "daily_scores": {},  # Для хранения оценок по дням
            "weekly_score": 0   # Сумма оценок за текущую неделю
        }

    # Проверяем корректность ввода
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Пожалуйста, укажите оценку от 1 до 10. Пример: /eda 8")
        return

    score = int(context.args[0])
    if score < 1 or score > 10:
        await update.message.reply_text("Оценка должна быть числом от 1 до 10.")
        return

    # Проверяем, есть ли оценка на сегодня
    if today in habit_data[user_id]["daily_scores"]:
        await update.message.reply_text("Ты уже добавил оценку за сегодня.")
        return

    # Добавляем оценку
    habit_data[user_id]["daily_scores"][today] = score
    habit_data[user_id]["weekly_score"] += score
    save_data()

    # Формируем сообщение для пользователя
    total_score = habit_data[user_id]["weekly_score"]
    message = (
        f"Твоя оценка за сегодня: {score}\n"
        f"Сумма баллов за текущую неделю (включая сегодня): {total_score}"
    )

    await update.message.reply_text(message)

# Еженедельный сброс и публикация топа
async def reset_weekly_scores(context: ContextTypes.DEFAULT_TYPE):
    if not habit_data:
        return

    # Формируем список лидеров по итогам недели
    leaderboard = sorted(
        habit_data.items(),
        key=lambda x: x[1].get("weekly_score", 0),
        reverse=True
    )

    # Формируем сообщение с топом
    message = "Топ пользователей за эту неделю:\n"
    for i, (user_id, data) in enumerate(leaderboard, start=1):
        message += f"{i}. {data['username']}: {data['weekly_score']} баллов\n"

    # Сбрасываем недельные баллы
    for user_id, data in habit_data.items():
        data["weekly_score"] = 0
        data["daily_scores"] = {}
    save_data()

    # Отправляем сообщение в общий чат
    try:
        await context.bot.send_message(chat_id=context.job.chat_id, text=message)
    except Exception as e:
        print(f"Ошибка отправки сообщения с топом: {e}")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)  # ID пользователя
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"  # Никнейм или имя
    if user_id not in habit_data:
        habit_data[user_id] = {
            "username": username,
            "days_participated": 0,
            "days_no_sugar": 0,
            "current_streak": 0,
            "last_report_date": None,
            "habit_done": False,
            "daily_scores": {},  # Для хранения оценок по дням
            "weekly_score": 0   # Сумма оценок за текущую неделю
        }
    save_data()
    await update.message.reply_text("Привет, {username}! Каждый день отмечай, ел ли ты сахар, используя /done. Если забудешь, я напомню!")

# Команда /done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"
    today = str(datetime.date.today())

    # Если пользователя нет в словаре, регистрируем его
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
        # Обновляем username, если его нет или он изменился
        if "username" not in habit_data[user_id] or habit_data[user_id]["username"] != username:
            habit_data[user_id]["username"] = username
            save_data()        

    # Проверяем, отмечал ли пользователь сегодня
    if habit_data[user_id]["last_report_date"] == today:
        await update.message.reply_text("Ты уже отметил выполнение привычки сегодня.")
        return

    # Обновляем данные
    habit_data[user_id]["last_report_date"] = today
    habit_data[user_id]["habit_done"] = True
    habit_data[user_id]["days_participated"] += 1
    habit_data[user_id]["days_no_sugar"] += 1
    habit_data[user_id]["current_streak"] += 1
    save_data()  # Сохраняем изменения
    await update.message.reply_text(f"Отлично, {username}! Ты не ел сахар сегодня!")

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

    # Лидеры по текущему стрику
    streak_leaders = sorted(
        habit_data.items(),
        key=lambda x: x[1].get("current_streak", 0),
        reverse=True
    )[:3]

    # Лидеры по дням без сахара
    sugar_free_leaders = sorted(
        habit_data.items(),
        key=lambda x: x[1].get("days_no_sugar", 0),
        reverse=True
    )[:3]

    # Формируем сообщение для вывода
    streak_message = "Лидеры по текущему стрику:\n"
    for i, (user_id, data) in enumerate(streak_leaders, start=1):
        username = data.get("username", f"User {user_id}")
        streak_message += f"{i}. {username}: {data['current_streak']} дней подряд\n"

    sugar_free_message = "Лидеры по дням без сахара:\n"
    for i, (user_id, data) in enumerate(sugar_free_leaders, start=1):
        username = data.get("username", f"User {user_id}")
        sugar_free_message += f"{i}. {username}: {data['days_no_sugar']} дней\n"

    # Отправляем сообщение
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

async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, есть ли в сообщении команды
    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == MessageEntityType.BOT_COMMAND:  # Проверяем, является ли это командой
                command = update.message.text.split()[0]  # Получаем текст команды
                if command != "/done":  # Если команда не /done
                    try:
                        await update.message.delete()  # Удаляем сообщение
                        print(f"Удалена команда: {command}")
                    except Exception as e:
                        print(f"Ошибка при удалении команды: {e}")
                return  # Завершаем обработку после удаления

def main():
    application = Application.builder().token(TOKEN).build()

    # JobQueue для задач
    job_queue = application.job_queue
    if job_queue is None:
        raise RuntimeError("JobQueue не была инициализирована!")

    # Регистрация команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("eda", eda))
    application.add_handler(MessageHandler(filters.COMMAND, handle_commands))

    # Планирование задач
    job_queue.run_daily(send_reminders, time=datetime.time(21, 0))
    job_queue.run_daily(finalize_day, time=datetime.time(0, 0))
    job_queue.run_daily(reset_weekly_scores, time=datetime.time(12, 0), days=[6])  # Каждую субботу

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()