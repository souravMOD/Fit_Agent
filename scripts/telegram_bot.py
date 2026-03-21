import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.agent.graph import agent
from src.database.meal_db import MealDatabase
from src.tools.agent_tools import set_current_user
from src.config import TELEGRAM_BOT_TOKEN, MEAL_IMAGES_DIR

MEAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
db = MealDatabase()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    name = update.effective_user.first_name or "User"
    user_id = db.get_or_create_user(telegram_id=telegram_id, name=name)

    await update.message.reply_text(
        f"Hey {name}! 💪 I'm FitAgent.\n\n"
        f"Send me a photo of your meal and I'll track your nutrition.\n\n"
        f"Commands:\n"
        f"/today - Today's summary\n"
        f"/week - Weekly trends\n"
        f"/goals - Check progress vs targets\n"
        f"/help - Show this message"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    name = update.effective_user.first_name or "User"
    user_id = db.get_or_create_user(telegram_id=telegram_id, name=name)
    set_current_user(user_id)

    await update.message.reply_text("📷 Analyzing your meal...")

    # Download photo
    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = MEAL_IMAGES_DIR / f"tg_{telegram_id}_{timestamp}.jpg"
    await file.download_to_drive(str(image_path))

    # Run agent
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"I just ate this meal. Please analyze and log it. Image path: {image_path}"
        }]
    })

    # Get final response
    response = ""
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            response = msg.content

    if response:
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Meal logged! ✅")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    name = update.effective_user.first_name or "User"
    user_id = db.get_or_create_user(telegram_id=telegram_id, name=name)
    set_current_user(user_id)

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": update.message.text
        }]
    })

    response = ""
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            response = msg.content

    if response:
        await update.message.reply_text(response)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    user_id = db.get_or_create_user(telegram_id=telegram_id)
    set_current_user(user_id)
    targets = db.get_user_targets(user_id)
    summary = db.get_daily_summary(user_id)

    if summary["meal_count"] == 0:
        await update.message.reply_text("No meals logged today yet. Send me a food photo! 📷")
        return

    text = f"📊 *Today's Summary*\n\n"
    text += f"🔥 Calories: {summary['total_calories']} / {targets['calorie_target']} kcal\n"
    text += f"🥩 Protein: {summary['total_protein_g']}g / {targets['protein_target']}g\n"
    text += f"🍞 Carbs: {summary['total_carbs_g']}g / {targets['carbs_target']}g\n"
    text += f"🧈 Fat: {summary['total_fat_g']}g / {targets['fat_target']}g\n"
    text += f"\n🍽️ Meals: {summary['meal_count']}\n"

    remaining = targets['calorie_target'] - summary['total_calories']
    if remaining > 0:
        text += f"\n✅ {remaining} kcal remaining today"
    else:
        text += f"\n⚠️ {abs(remaining)} kcal over target"

    await update.message.reply_text(text, parse_mode="Markdown")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    user_id = db.get_or_create_user(telegram_id=telegram_id)
    set_current_user(user_id)

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Show me my weekly nutrition history and trends"
        }]
    })

    response = ""
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            response = msg.content

    await update.message.reply_text(response or "No data for this week yet.")


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    user_id = db.get_or_create_user(telegram_id=telegram_id)
    targets = db.get_user_targets(user_id)
    summary = db.get_daily_summary(user_id)

    cal_pct = int(summary['total_calories'] / targets['calorie_target'] * 100) if targets['calorie_target'] > 0 else 0
    pro_pct = int(summary['total_protein_g'] / targets['protein_target'] * 100) if targets['protein_target'] > 0 else 0

    text = f"🎯 *Goal Progress*\n\n"
    text += f"Calories: {'█' * (cal_pct // 10)}{'░' * (10 - cal_pct // 10)} {cal_pct}%\n"
    text += f"Protein:  {'█' * (pro_pct // 10)}{'░' * (10 - pro_pct // 10)} {pro_pct}%\n"

    remaining_cal = targets['calorie_target'] - summary['total_calories']
    remaining_pro = targets['protein_target'] - summary['total_protein_g']

    if remaining_cal > 0:
        text += f"\nYou can still eat ~{remaining_cal} kcal and ~{remaining_pro}g protein today."
    else:
        text += f"\nYou've reached your calorie target for today!"

    await update.message.reply_text(text, parse_mode="Markdown")


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Set TELEGRAM_BOT_TOKEN in your .env file")
        return

    print("Starting FitAgent Telegram bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("week", week_command))
    app.add_handler(CommandHandler("goals", goals_command))

    # Messages
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running! Send a meal photo on Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()