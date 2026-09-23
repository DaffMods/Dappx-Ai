import os
import logging
from collections import defaultdict, deque

from dotenv import load_dotenv
from openai import AsyncOpenAI

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# LOAD ENVIRONMENT
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "").strip()

PORT = int(os.getenv("PORT", "10000"))

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")


# =========================================================
# VALIDATION
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN belum diisi.")

if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY belum diisi.")

if not AI_MODEL:
    raise RuntimeError(
        "AI_MODEL belum diisi. "
        "Masukkan model AI di Environment Variables Render."
    )

if not RENDER_URL:
    raise RuntimeError(
        "RENDER_EXTERNAL_URL tidak ditemukan. "
        "Pastikan aplikasi dijalankan sebagai Render Web Service."
    )


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# OPENAI CLIENT
# =========================================================

client = AsyncOpenAI(
    api_key=AI_API_KEY
)


# =========================================================
# CURRENT MODEL
# =========================================================

current_model = AI_MODEL


# =========================================================
# MEMORY
# =========================================================

conversation_memory = defaultdict(
    lambda: deque(maxlen=20)
)


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
Kamu adalah AI assistant Telegram yang cerdas, ramah,
natural, santai, dan membantu.

Gunakan bahasa yang sama dengan pengguna.

Jika pengguna menggunakan bahasa Indonesia,
jawab dalam bahasa Indonesia.

Jika pengguna menggunakan bahasa Inggris,
jawab dalam bahasa Inggris.

Jawaban harus jelas dan mudah dipahami.

Jangan mengaku sebagai manusia.

Jika pengguna meminta penjelasan detail,
berikan penjelasan lengkap.

Jika pertanyaan sederhana,
jawab secara singkat dan langsung.
"""


# =========================================================
# ASK AI
# =========================================================

async def ask_ai(chat_id: int, user_message: str):

    history = conversation_memory[chat_id]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    messages.extend(history)

    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    try:

        response = await client.chat.completions.create(
            model=current_model,
            messages=messages,
        )

        answer = response.choices[0].message.content

        if not answer:
            return "Maaf, AI tidak memberikan jawaban."

        # Simpan percakapan
        history.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        return answer

    except Exception as e:

        logger.exception("AI ERROR")

        return (
            "❌ Terjadi error ketika menghubungi AI.\n\n"
            f"`{str(e)[:700]}`"
        )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    await update.message.reply_text(
        f"👋 Halo {user.first_name}!\n\n"

        "🤖 Gua AI assistant lu.\n\n"

        "💬 Kirim pesan untuk mulai ngobrol.\n\n"

        "Command:\n"
        "/start — mulai bot\n"
        "/help — bantuan\n"
        "/models — cek model\n"
        "/setmodel — ganti model\n"
        "/newchat — hapus memory\n\n"

        f"🧠 Model aktif:\n"
        f"`{current_model}`",

        parse_mode="Markdown",
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 *AI Telegram Bot*\n\n"

        "Cukup kirim pesan untuk berbicara dengan AI.\n\n"

        "*Command:*\n\n"

        "`/start`\n"
        "Memulai bot.\n\n"

        "`/models`\n"
        "Melihat model yang tersedia.\n\n"

        "`/setmodel nama_model`\n"
        "Mengganti model AI.\n\n"

        "`/newchat`\n"
        "Menghapus memory percakapan.\n\n"

        "`/help`\n"
        "Menampilkan bantuan.\n\n"

        f"*Model aktif:*\n"
        f"`{current_model}`",

        parse_mode="Markdown",
    )


# =========================================================
# /MODELS
# =========================================================

async def models_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔎 Mengecek model yang tersedia..."
    )

    try:

        models = await client.models.list()

        model_list = sorted(
            model.id
            for model in models.data
        )

        if not model_list:

            await update.message.reply_text(
                "❌ Tidak ada model yang ditemukan."
            )

            return

        text = "🤖 *Model yang tersedia:*\n\n"

        for model in model_list:

            if model == current_model:

                text += (
                    f"✅ `{model}` ← AKTIF\n"
                )

            else:

                text += (
                    f"• `{model}`\n"
                )

        text += (
            "\nUntuk mengganti model:\n"
            "`/setmodel nama_model`"
        )

        MAX_LENGTH = 4000

        for i in range(
            0,
            len(text),
            MAX_LENGTH
        ):

            await update.message.reply_text(
                text[i:i + MAX_LENGTH],
                parse_mode="Markdown"
            )

    except Exception as e:

        logger.exception(
            "MODEL LIST ERROR"
        )

        await update.message.reply_text(
            "❌ Gagal mengambil daftar model.\n\n"
            f"`{str(e)[:700]}`",
            parse_mode="Markdown",
        )


# =========================================================
# /SETMODEL
# =========================================================

async def set_model(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global current_model

    if not context.args:

        await update.message.reply_text(
            "❌ Masukkan nama model.\n\n"
            "Contoh:\n"
            "`/setmodel nama-model`",
            parse_mode="Markdown",
        )

        return

    requested_model = " ".join(
        context.args
    ).strip()

    await update.message.reply_text(
        "🔎 Memeriksa model..."
    )

    try:

        models = await client.models.list()

        model_list = [
            model.id
            for model in models.data
        ]

        matching_model = None

        for model in model_list:

            if model.lower() == requested_model.lower():

                matching_model = model
                break

        if not matching_model:

            await update.message.reply_text(
                "❌ Model tidak ditemukan.\n\n"
                "Gunakan `/models` untuk melihat "
                "model yang tersedia.",
                parse_mode="Markdown",
            )

            return

        current_model = matching_model

        await update.message.reply_text(
            "✅ Model berhasil diganti!\n\n"
            f"🤖 Model aktif:\n"
            f"`{current_model}`",
            parse_mode="Markdown",
        )

    except Exception as e:

        logger.exception(
            "SET MODEL ERROR"
        )

        await update.message.reply_text(
            "❌ Gagal mengganti model.\n\n"
            f"`{str(e)[:700]}`",
            parse_mode="Markdown",
        )


# =========================================================
# /NEWCHAT
# =========================================================

async def new_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    conversation_memory.pop(
        chat_id,
        None
    )

    await update.message.reply_text(
        "🔄 *Percakapan baru dimulai!*\n\n"
        "Memory percakapan sebelumnya "
        "sudah dihapus.",
        parse_mode="Markdown",
    )


# =========================================================
# NORMAL MESSAGE
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    chat_id = update.effective_chat.id

    user_message = update.message.text.strip()

    if not user_message:
        return

    # Typing indicator
    try:

        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
        )

    except Exception:
        pass

    # Kirim ke AI
    answer = await ask_ai(
        chat_id,
        user_message
    )

    # Telegram message limit
    MAX_LENGTH = 4000

    for i in range(
        0,
        len(answer),
        MAX_LENGTH
    ):

        chunk = answer[
            i:i + MAX_LENGTH
        ]

        await update.message.reply_text(
            chunk
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error
    )


# =========================================================
# POST INIT
# =========================================================

async def post_init(
    application: Application
):

    print("=" * 60)
    print("AI TELEGRAM BOT")
    print("=" * 60)

    print(
        f"Render URL : {RENDER_URL}"
    )

    print(
        f"Port       : {PORT}"
    )

    print(
        f"AI Model   : {current_model}"
    )

    print("=" * 60)

    # URL webhook Telegram
    webhook_url = (
        f"{RENDER_URL}/telegram"
    )

    print(
        f"Webhook URL: {webhook_url}"
    )

    # Set webhook
    await application.bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
    )

    print(
        "✅ Telegram webhook berhasil dipasang."
    )


# =========================================================
# POST SHUTDOWN
# =========================================================

async def post_shutdown(
    application: Application
):

    try:

        await application.bot.delete_webhook()

        print(
            "Telegram webhook dihapus."
        )

    except Exception as e:

        print(
            f"Gagal menghapus webhook: {e}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "Starting AI Telegram Bot..."
    )

    # Build Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "models",
            models_command
        )
    )

    application.add_handler(
        CommandHandler(
            "setmodel",
            set_model
        )
    )

    application.add_handler(
        CommandHandler(
            "newchat",
            new_chat
        )
    )

    # Normal messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    # Error handler
    application.add_error_handler(
        error_handler
    )

    # =====================================================
    # RENDER WEBHOOK
    # =====================================================

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="telegram",
        webhook_url=f"{RENDER_URL}/telegram",
        drop_pending_updates=True,
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()