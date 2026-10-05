import asyncio
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docx_parser import find_explanation


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "Переменная окружения BOT_TOKEN не установлена."
    )


WEBAPP_URL = "https://egeduoru.github.io/ege-duo/"


# =========================================================
# TELEGRAM BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🚀 Открыть приложение",
                    web_app=WebAppInfo(
                        url=WEBAPP_URL
                    )
                )
            ]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🇷🇺 Привет!\n\n"
        "Добро пожаловать в тренажёр ЕГЭ по русскому языку!",
        reply_markup=keyboard
    )


# =========================================================
# TELEGRAM POLLING
# =========================================================

polling_task = None


async def run_bot():
    print("Telegram bot polling started")

    try:
        await dp.start_polling(bot)

    except asyncio.CancelledError:
        print("Telegram bot polling stopped")
        raise

    except Exception as error:
        print(
            "Ошибка Telegram polling:",
            repr(error)
        )
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):

    global polling_task

    polling_task = asyncio.create_task(
        run_bot()
    )

    yield

    if polling_task:
        polling_task.cancel()

        try:
            await polling_task
        except asyncio.CancelledError:
            pass

    await bot.session.close()


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://egeduoru.github.io"
    ],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# =========================================================
# DATA
# =========================================================

class WrongAnswer(BaseModel):
    word: str
    initData: str


# =========================================================
# TELEGRAM INIT DATA
# =========================================================

def validate_init_data(init_data: str):

    if not init_data:
        raise HTTPException(
            status_code=400,
            detail="Telegram initData отсутствует"
        )

    try:

        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )

        received_hash = parsed.pop(
            "hash",
            None
        )

        if not received_hash:
            raise HTTPException(
                status_code=400,
                detail="Hash отсутствует"
            )

        auth_date = int(
            parsed.get(
                "auth_date",
                "0"
            )
        )

        if time.time() - auth_date > 86400:

            raise HTTPException(
                status_code=403,
                detail="Telegram initData устарел"
            )

        data_check_string = "\n".join(
            f"{key}={parsed[key]}"
            for key in sorted(parsed.keys())
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):

            raise HTTPException(
                status_code=403,
                detail="Неверная подпись Telegram"
            )

        user_json = parsed.get("user")

        if not user_json:

            raise HTTPException(
                status_code=400,
                detail="Данные пользователя отсутствуют"
            )

        user = json.loads(
            user_json
        )

        user_id = user.get(
            "id"
        )

        if not user_id:

            raise HTTPException(
                status_code=400,
                detail="ID пользователя отсутствует"
            )

        return user_id

    except HTTPException:
        raise

    except Exception as error:

        print(
            "Ошибка проверки Telegram initData:",
            error
        )

        raise HTTPException(
            status_code=400,
            detail="Некорректные данные Telegram"
        )


# =========================================================
# WRONG ANSWER
# =========================================================

@app.post("/wrong-answer")
async def wrong_answer(data: WrongAnswer):

    word = data.word.strip()

    if not word:

        raise HTTPException(
            status_code=400,
            detail="Слово не указано"
        )

    user_id = validate_init_data(
        data.initData
    )

    print(
        f"Получена ошибка: {word}"
    )

    print(
        f"Telegram user ID: {user_id}"
    )

    explanation = find_explanation(
        word
    )

    if not explanation:

        print(
            f"Объяснение для «{word}» не найдено"
        )

        return {
            "ok": False,
            "message": "Объяснение не найдено"
        }

    try:

        await bot.send_message(
            chat_id=user_id,
            text=(
                "📚 Разбор ошибки\n\n"
                + explanation
            )
        )

        print(
            f"Объяснение отправлено пользователю "
            f"{user_id}"
        )

    except Exception as error:

        print(
            "Ошибка отправки сообщения:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Не удалось отправить "
                "сообщение в Telegram"
            )
        )

    return {
        "ok": True
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
async def root():

    return {
        "ok": True,
        "service": "EGE Duo backend"
    }
