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
# LOAD CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "").strip()


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN belum diisi di .env")

if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY belum diisi di .env")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# AI CLIENT
# =========================================================

client = AsyncOpenAI(
    api_key=AI_API_KEY
)


# =========================================================
# MEMORY
# =========================================================

# Memory terpisah untuk setiap chat Telegram.
#
# maxlen=20 berarti maksimal 20 message disimpan.
#
# Contoh:
# user
# assistant
# user
# assistant
# ...
#
# Setelah lebih dari 20 message, yang paling lama otomatis
# dibuang agar penggunaan token tidak terlalu besar.

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
berikan penjelasan yang lebih lengkap.

Jika pengguna hanya bertanya sederhana,
jawab secara singkat dan langsung.

Jika Pengguna Menanyakan Siapakah Pembuat Dirimu,
Jawab secara singkat saja bahwa kamu diciptakan oleh Dappx Dan Berikan Username Telegram nya @dapppx.
"""


# =========================================================
# CURRENT MODEL
# =========================================================

# Model yang sedang digunakan.
#
# Kalau AI_MODEL kosong, bot akan mencoba mencari model
# yang tersedia dari API.

current_model = AI_MODEL


# =========================================================
# GET AVAILABLE MODELS
# =========================================================

async def get_available_models():

    try:

        models = await client.models.list()

        model_list = sorted(
            [
                model.id
                for model in models.data
            ]
        )

        return model_list

    except Exception as e:

        logger.exception(
            "Gagal mengambil daftar model"
        )

        return []


# =========================================================
# INITIALIZE MODEL
# =========================================================

async def initialize_model():

    global current_model

    # Kalau model sudah ditentukan di .env
    if current_model:
        print(
            f"[AI] Model dari .env: {current_model}"
        )
        return

    print(
        "[AI] AI_MODEL kosong."
    )

    print(
        "[AI] Mencari model yang tersedia..."
    )

    models = await get_available_models()

    if not models:

        raise RuntimeError(
            "Tidak dapat menemukan model AI. "
            "Periksa AI_API_KEY."
        )

    current_model = models[0]

    print(
        f"[AI] Model otomatis dipilih: {current_model}"
    )


# =========================================================
# ASK AI
# =========================================================

async def ask_ai(
    chat_id: int,
    user_message: str
):

    history = conversation_memory[chat_id]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # Tambahkan memory
    messages.extend(history)

    # Tambahkan pesan terbaru
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

            return (
                "Maaf, AI tidak memberikan jawaban."
            )

        # Simpan user message
        history.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        # Simpan AI response
        history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        return answer

    except Exception as e:

        logger.exception(
            "AI REQUEST ERROR"
        )

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

        "🤖 Gua AI assistant Telegram lu.\n\n"

        "💬 Kirim pesan untuk mulai ngobrol.\n\n"

        "Command:\n"
        "• /start — mulai bot\n"
        "• /help — bantuan\n"
        "• /models — lihat model AI\n"
        "• /setmodel — ganti model AI\n"
        "• /newchat — hapus memory chat\n\n"

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

        "Cukup kirim pesan untuk berbicara "
        "dengan AI.\n\n"

        "*Command:*\n\n"

        "`/start`\n"
        "Memulai bot.\n\n"

        "`/models`\n"
        "Melihat model AI yang tersedia.\n\n"

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

    models = await get_available_models()

    if not models:

        await update.message.reply_text(
            "❌ Tidak berhasil mendapatkan daftar model.\n\n"
            "Kemungkinan API key tidak valid atau "
            "API tidak bisa diakses."
        )

        return

    text = (
        "🤖 *Model yang tersedia:*\n\n"
    )

    for model in models:

        if model == current_model:

            text += (
                f"✅ `{model}` "
                f"← AKTIF\n"
            )

        else:

            text += (
                f"• `{model}`\n"
            )

    text += (
        "\nUntuk mengganti model:\n"
        "`/setmodel nama_model`"
    )

    # Telegram message limit
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

    models = await get_available_models()

    if not models:

        await update.message.reply_text(
            "❌ Gagal mengambil daftar model."
        )

        return

    # Cek exact match
    if requested_model not in models:

        # Coba case-insensitive
        matching_model = None

        for model in models:

            if model.lower() == requested_model.lower():

                matching_model = model
                break

        if matching_model:

            requested_model = matching_model

        else:

            await update.message.reply_text(

                "❌ Model tidak ditemukan.\n\n"

                "Gunakan `/models` "
                "untuk melihat model yang tersedia.",

                parse_mode="Markdown",
            )

            return

    current_model = requested_model

    await update.message.reply_text(

        "✅ Model berhasil diganti!\n\n"

        f"🤖 Model aktif:\n"
        f"`{current_model}`",

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
        "🔄 *Percakapan baru dimulai.*\n\n"
        "Memory percakapan sebelumnya "
        "sudah dihapus.",
        parse_mode="Markdown",
    )


# =========================================================
# MESSAGE HANDLER
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

    user_message = (
        update.message.text.strip()
    )

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
# MAIN
# =========================================================

def main():

    print("=" * 55)

    print(
        "        AI TELEGRAM BOT"
    )

    print("=" * 55)

    print(
        f"Model awal : {current_model or 'AUTO'}"
    )

    print(
        "Status     : Starting..."
    )

    print("=" * 55)

    # Build application
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # =============================================
    # COMMANDS
    # =============================================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    app.add_handler(
        CommandHandler(
            "models",
            models_command
        )
    )

    app.add_handler(
        CommandHandler(
            "setmodel",
            set_model
        )
    )

    app.add_handler(
        CommandHandler(
            "newchat",
            new_chat
        )
    )

    # =============================================
    # MESSAGE HANDLER
    # =============================================

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_message
        )
    )

    # =============================================
    # ERROR HANDLER
    # =============================================

    app.add_error_handler(
        error_handler
    )

    print(
        "Bot berhasil dijalankan."
    )

    print(
        "Menunggu pesan Telegram..."
    )

    # Long polling
    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# POST INIT
# =========================================================

async def post_init(
    application: Application
):

    await initialize_model()

    print(
        f"[AI] Model aktif: {current_model}"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()