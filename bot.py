import json
import datetime
import os
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Загружаем конфиг из файла
CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print("❌ Ошибка: config.json не найден или поврежден!")
        return {}

# Загружаем токен
config = load_config()
TOKEN = config.get("BOT_TOKEN", "")

if not TOKEN:
    raise ValueError("❌ Ошибка: Токен бота не найден в config.json!")

DATA_FILE = "habit_data.json"

# Базовый часовой пояс — UTC+0
UTC_TZ = pytz.utc

# Функции для работы с файлами
def load_data():
    try:
        with open(DATA_FILE, "r") as file:
            data = json.load(file)
            
            # Проверяем, есть ли у всех пользователей нужные ключи
            for user_id in data:
                data[user_id].setdefault("days_tracked", 1)
                data[user_id].setdefault("days_no_sugar", 0)
                data[user_id].setdefault("current_streak", 0)
                data[user_id].setdefault("record_streak", 0)
                data[user_id].setdefault("first_day", None)
                data[user_id].setdefault("last_report_date", None)
                data[user_id].setdefault("habit_done", False)
                data[user_id].setdefault("previous_streak", 0)
            
            return data
    except FileNotFoundError:
        return {}

def save_data():
    with open(DATA_FILE, "w") as file:
        json.dump(habit_data, file, indent=4)

habit_data = load_data()

# Функция для отправки кнопок с действиями
async def send_action_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Отметить день", callback_data="done")],
        [InlineKeyboardButton("📊 Посмотреть статистику", callback_data="stats")],
        [InlineKeyboardButton("🔄 Восстановить рекордную серию", callback_data="restore_streak")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

# Обработчик нажатий на кнопки
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждение клика

    if query.data == "done":
        await done(update, context)
    elif query.data == "stats":
        await stats(update, context)
    elif query.data == "restore_streak":
        await restore_streak(update, context)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"
    
    # Получаем текущую дату в UTC
    today = datetime.datetime.now(UTC_TZ).date().isoformat()

    # Если пользователя нет в базе, создаем его профиль
    if user_id not in habit_data:
        habit_data[user_id] = {
            "username": username,
            "days_tracked": 1,  # Начинаем учет с 1 дня
            "days_no_sugar": 1,  # Первый день без сахара
            "current_streak": 1,  # Начальный стрик
            "record_streak": 1,  # Начальный рекордный стрик
            "first_day": today,  # Дата первого использования
            "last_report_date": today,
            "habit_done": True,
            "previous_streak": 0  # Сохраняем стрик на случай восстановления
        }
    else:
        # Если уже отмечался сегодня
        if habit_data[user_id]["last_report_date"] == today:
            await update.callback_query.message.reply_text("Ты уже отметила выполнение привычки сегодня.")
            return

        # Обновляем данные пользователя
        habit_data[user_id]["days_tracked"] += 1
        habit_data[user_id]["days_no_sugar"] += 1

        # Проверяем, был ли пропущен день
        last_date = datetime.date.fromisoformat(habit_data[user_id]["last_report_date"])
        yesterday = (datetime.datetime.now(UTC_TZ) - datetime.timedelta(days=1)).date()

        if last_date == yesterday:  # Если отметился вчера
            habit_data[user_id]["current_streak"] += 1
        else:  # Если был пропущенный день
            habit_data[user_id]["previous_streak"] = habit_data[user_id]["current_streak"]
            habit_data[user_id]["current_streak"] = 1  # Начинаем новый стрик

        # Проверяем рекордный стрик
        if habit_data[user_id]["current_streak"] > habit_data[user_id]["record_streak"]:
            habit_data[user_id]["record_streak"] = habit_data[user_id]["current_streak"]

        habit_data[user_id]["last_report_date"] = today
        habit_data[user_id]["habit_done"] = True

    save_data()
    await update.callback_query.message.reply_text(f"Отлично, {username}! Ты не ела сахар сегодня! 🔥")

# Команда /stats (исправлено)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in habit_data:
        await update.callback_query.message.reply_text("Ты ещё не зарегистрировалась. Используй /start.")
        return

    user_data = habit_data[user_id]

    # Если у пользователя нет ни одного дня без сахара
    if user_data.get("days_no_sugar", 0) == 0:
        await update.callback_query.message.reply_text(f"{username}, мы пока не собрали данных о тебе. Начни отмечать дни, используя /done!")
        return

    # Проверяем, есть ли все нужные ключи
    user_data.setdefault("days_tracked", 1)
    user_data.setdefault("days_no_sugar", 0)
    user_data.setdefault("current_streak", 0)
    user_data.setdefault("record_streak", 0)

    message = (
        f"📊 Твоя статистика:\n"
        f"📅 Дней ведется учет: {user_data['days_tracked']}\n"
        f"🍏 Дней без сахара: {user_data['days_no_sugar']}\n"
        f"🔥 Текущий серия без сахара: {user_data['current_streak']} дней подряд\n"
        f"🏆 Рекорд: {user_data['record_streak']} дней подряд"
    )
    await update.callback_query.message.reply_text(message)

async def restore_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    today = datetime.datetime.now(UTC_TZ).date().isoformat()
    yesterday = (datetime.datetime.now(UTC_TZ) - datetime.timedelta(days=1)).date().isoformat()

    if user_id not in habit_data:
        await update.callback_query.message.reply_text("Ты ещё не зарегистрировалась. Используй /start.")
        return

    user_data = habit_data[user_id]

    if user_data["last_report_date"] == yesterday and user_data["current_streak"] == 0:
        user_data["current_streak"] = user_data["previous_streak"]  # Восстанавливаем предыдущий стрик
        user_data["last_report_date"] = today  # Фиксируем, что пользователь "отметился"
        save_data()
        await update.callback_query.message.reply_text("✅ Последовательность восстановлена!")
    else:
        await update.callback_query.message.reply_text("❌ Невозможно восстановить последовательность. Ты либо не пропускала день, либо прошло слишком много времени.")

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now(UTC_TZ).date().isoformat()

    for user_id, data in habit_data.items():
        if data["last_report_date"] != today or not data["habit_done"]:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="📢 Напоминание! Отметь, ела ли ты сахар, используя /done."
                )
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

async def finalize_day(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now(UTC_TZ).date().isoformat()

    for user_id, data in habit_data.items():
        if data["last_report_date"] != today:
            data["days_tracked"] += 1
            data["current_streak"] = 0
            data["habit_done"] = False

    save_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрирует пользователя, если он новый, и отправляет меню кнопок."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or f"User {user_id}"
    today = datetime.datetime.now(UTC_TZ).date().isoformat()

    # Проверяем, зарегистрирован ли пользователь
    if user_id not in habit_data:
        habit_data[user_id] = {
            "username": username,
            "days_tracked": 1,  # Начинаем учет с 1 дня
            "days_no_sugar": 0,  # Пока нет отмеченных дней без сахара
            "current_record": 0,  # Текущий рекорд
            "best_record": 0,  # Максимальный рекорд
            "first_day": today,  # Дата начала
            "last_report_date": None,
            "habit_done": False,
            "previous_record": 0
        }
        save_data()
        await update.message.reply_text(f"Привет, {username}! 🎉\nТы зарегистрирована в боте!\n\nТеперь ты можешь отмечать дни без сахара и следить за своей статистикой. Давай начнем!")

    else:
        await update.message.reply_text(f"Привет снова, {username}! 😊")

    # Отправляем кнопки с действиями
    await send_action_buttons(update, context)

def main():
    application = Application.builder().token(TOKEN).build()

    # JobQueue для задач
    job_queue = application.job_queue
    if job_queue is None:
        raise RuntimeError("JobQueue не была инициализирована!")

    # Регистрация команд
    application.add_handler(CommandHandler("start", send_action_buttons))
    application.add_handler(CallbackQueryHandler(button_click))

    # Планирование задач (в UTC)
    job_queue.run_daily(send_reminders, time=datetime.time(21, 0, tzinfo=UTC_TZ))
    job_queue.run_daily(finalize_day, time=datetime.time(0, 0, tzinfo=UTC_TZ))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()