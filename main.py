import os
import random
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

LEVELS = [
    {"level": 1, "good": 5, "total": 10, "multiplier": 1.2, "prob": 50.0},
    {"level": 2, "good": 4, "total": 9, "multiplier": 1.8, "prob": 44.4},
    {"level": 3, "good": 3, "total": 8, "multiplier": 2.5, "prob": 37.5},
    {"level": 4, "good": 2, "total": 7, "multiplier": 3.5, "prob": 28.6},
    {"level": 5, "good": 1, "total": 6, "multiplier": 5.0, "prob": 16.7},
    {"level": 6, "good": 1, "total": 5, "multiplier": 7.0, "prob": 20.0},
    {"level": 7, "good": 1, "total": 4, "multiplier": 10.0, "prob": 25.0},
    {"level": 8, "good": 1, "total": 3, "multiplier": 15.0, "prob": 33.3},
    {"level": 9, "good": 1, "total": 2, "multiplier": 25.0, "prob": 50.0},
    {"level": 10, "good": 1, "total": 1, "multiplier": 50.0, "prob": 100.0},
]

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

BET, PLAYING = range(2)

user_games = {}


def get_level(level_num: int):
    return LEVELS[level_num - 1]


def build_apple_keyboard(level_num: int):
    buttons = [
        InlineKeyboardButton("🍎", callback_data=f"pick_{level_num}_{i}")
        for i in range(5)
    ]
    return InlineKeyboardMarkup([buttons])


def build_cashout_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Cash Out (Take Money)", callback_data="cashout")],
        [InlineKeyboardButton("🍏 Continue", callback_data="continue")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍎 **Apple of Fortune Bot** 🍎\n\n"
        "Bienvenue ! Ce bot simule le jeu Apple of Fortune.\n"
        "Règles :\n"
        "- 10 niveaux, 5 pommes par niveau\n"
        "- Choisis une bonne pomme pour avancer\n"
        "- Une pomme pourrie = tu perds tout\n"
        "- Cash out à tout moment pour empocher tes gains\n\n"
        "Utilise /play pour commencer !",
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_games[user_id] = {"level": 1, "bet": 0.0}
    await update.message.reply_text("💰 Quel est ton montant de mise ? (ex: 100)")
    return BET


async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = float(update.message.text)
        if bet <= 0:
            raise ValueError
        user_games[user_id]["bet"] = bet
        return await send_level(update, context, user_id)
    except ValueError:
        await update.message.reply_text("❌ Entre un nombre valide positif. (ex: 100)")
        return BET


async def send_level(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    game = user_games.get(user_id)
    if not game:
        await update.message.reply_text("Erreur. Utilise /play pour recommencer.")
        return ConversationHandler.END

    level_num = game["level"]
    cfg = get_level(level_num)
    current_win = game["bet"] * cfg["multiplier"]

    text = (
        f"🎯 **Niveau {level_num}/10**\n"
        f"🍏 Bonnes pommes : {cfg['good']}/{cfg['total']}\n"
        f"📊 Chance de succès : {cfg['prob']}%\n"
        f"🎰 Multiplicateur : {cfg['multiplier']}x\n"
        f"💰 Gain potentiel : **{current_win:.2f}**\n\n"
        f"Choisis une pomme ! 🍎"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=build_apple_keyboard(level_num),
        )
    else:
        await update.message.reply_text(
            text, reply_markup=build_apple_keyboard(level_num),
        )
    return PLAYING


async def handle_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    game = user_games.get(user_id)

    if not game:
        await query.edit_message_text("Partie introuvable. Utilise /play.")
        return ConversationHandler.END

    parts = query.data.split("_")
    level_num = int(parts[1])

    if level_num != game["level"]:
        await query.edit_message_text("Ce niveau n'est plus actuel. Utilise /play.")
        return PLAYING

    cfg = get_level(level_num)
    win = random.random() < (cfg["good"] / cfg["total"])

    if win:
        winnings = game["bet"] * cfg["multiplier"]
        if level_num == 10:
            await query.edit_message_text(
                f"🎉🎉 **FÉLICITATIONS ! TU AS GAGNÉ !** 🎉🎉\n\n"
                f"Tu as complété les 10 niveaux !\n"
                f"💰 Gain total : **{winnings:.2f}**\n"
                f"🏆 Multiplicateur : {cfg['multiplier']}x\n\n"
                f"Utilise /play pour rejouer."
            )
            del user_games[user_id]
            return ConversationHandler.END
        else:
            game["level"] += 1
            await query.edit_message_text(
                f"✅ **Bonne pomme !** Tu passes au niveau {level_num + 1} !\n\n"
                f"💰 Gain actuel : **{winnings:.2f}**\n"
                f"Que veux-tu faire ?",
                reply_markup=build_cashout_keyboard(),
            )
            return PLAYING
    else:
        bet = game["bet"]
        del user_games[user_id]
        await query.edit_message_text(
            f"💀 **POMME POURRIE !** Tu as tout perdu ! 💀\n\n"
            f"😢 Mise perdue : **{bet:.2f}**\n\n"
            f"Utilise /play pour réessayer."
        )
        return ConversationHandler.END


async def handle_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    game = user_games.get(user_id)

    if not game:
        await query.edit_message_text("Partie introuvable. Utilise /play.")
        return ConversationHandler.END

    cfg = get_level(game["level"])
    winnings = game["bet"] * cfg["multiplier"]
    level_reached = game["level"]
    del user_games[user_id]

    await query.edit_message_text(
        f"💰💰 **CASH OUT RÉUSSI !** 💰💰\n\n"
        f"Tu empoches **{winnings:.2f}** !\n"
        f"Niveau atteint : {level_reached}/10\n\n"
        f"Utilise /play pour rejouer."
    )
    return ConversationHandler.END


async def handle_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    game = user_games.get(user_id)

    if not game:
        await query.edit_message_text("Partie introuvable. Utilise /play.")
        return ConversationHandler.END

    return await send_level(update, context, user_id)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_games:
        del user_games[user_id]
    await update.message.reply_text("Partie annulée. Utilise /play pour recommencer.")
    return ConversationHandler.END


def main():
    if not BOT_TOKEN:
        print("ERREUR : Variable d'environnement TELEGRAM_BOT_TOKEN manquante.")
        print("Crée un bot sur @BotFather et définis la variable.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("play", play)],
        states={
            BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet)],
            PLAYING: [
                CallbackQueryHandler(handle_pick, pattern=r"^pick_\d+_\d+$"),
                CallbackQueryHandler(handle_cashout, pattern="^cashout$"),
                CallbackQueryHandler(handle_continue, pattern="^continue$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("[BOT] Apple of Fortune demarre !")
    app.run_polling()


if __name__ == "__main__":
    main()
