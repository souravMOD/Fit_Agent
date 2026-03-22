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

from telegram.ext import ConversationHandler

# Conversation states
ASKING_CALORIES, ASKING_PROTEIN, ASKING_CARBS, ASKING_FAT = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    name = update.effective_user.first_name or "User"
    user_id = db.get_or_create_user(telegram_id=telegram_id, name=name)
    context.user_data["user_id"] = user_id

    # Check if user already has custom targets
    targets = db.get_user_targets(user_id)
    if targets and targets.get("calorie_target") != 2200:
        await update.message.reply_text(
            f"Welcome back {name}! 💪\n"
            f"Your targets: {targets['calorie_target']} kcal, {targets['protein_target']}g protein\n\n"
            f"Send me a meal photo or type /help"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Hey {name}! 💪 Let's set up your nutrition targets.\n\n"
        f"What's your daily calorie target? (e.g. 2000)"
    )
    return ASKING_CALORIES


async def set_calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        calories = int(update.message.text.strip())
        if calories < 500 or calories > 10000:
            await update.message.reply_text("Please enter a number between 500 and 10000:")
            return ASKING_CALORIES
        context.user_data["cal_target"] = calories
        await update.message.reply_text(f"Got it: {calories} kcal/day.\n\nDaily protein target in grams? (e.g. 150)")
        return ASKING_PROTEIN
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 2000):")
        return ASKING_CALORIES


async def set_protein(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        protein = int(update.message.text.strip())
        context.user_data["pro_target"] = protein
        await update.message.reply_text(f"Protein: {protein}g/day.\n\nDaily carbs target in grams? (e.g. 250)")
        return ASKING_CARBS
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 150):")
        return ASKING_PROTEIN


async def set_carbs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        carbs = int(update.message.text.strip())
        context.user_data["carb_target"] = carbs
        await update.message.reply_text(f"Carbs: {carbs}g/day.\n\nDaily fat target in grams? (e.g. 70)")
        return ASKING_FAT
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 250):")
        return ASKING_CARBS


async def set_fat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        fat = int(update.message.text.strip())
        user_id = context.user_data["user_id"]
        db.update_user_targets(
            user_id,
            calories=context.user_data["cal_target"],
            protein=context.user_data["pro_target"],
            carbs=context.user_data["carb_target"],
            fat=fat,
        )
        await update.message.reply_text(
            f"All set! Your daily targets:\n"
            f"🔥 {context.user_data['cal_target']} kcal\n"
            f"🥩 {context.user_data['pro_target']}g protein\n"
            f"🍞 {context.user_data['carb_target']}g carbs\n"
            f"🧈 {fat}g fat\n\n"
            f"Send me a meal photo to start tracking! 📷\n"
            f"Use /settings to change targets later."
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 70):")
        return ASKING_FAT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Setup cancelled. Using default targets. Type /start to try again.")
    return ConversationHandler.END

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

    # Onboarding conversation
    onboarding = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("settings", start)],
        states={
            ASKING_CALORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_calories)],
            ASKING_PROTEIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_protein)],
            ASKING_CARBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_carbs)],
            ASKING_FAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_fat)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(onboarding)

    # Commands
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("week", week_command))
    app.add_handler(CommandHandler("goals", goals_command))

    # Messages
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running!")
    app.run_polling()


if __name__ == "__main__":
    main()