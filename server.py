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


# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена.")

WEBAPP_URL = "https://egeduoru.github.io/ege-duo/"


# =========================
# TELEGRAM BOT
# =========================

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


# =========================
# TELEGRAM POLLING
# =========================

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


# =========================
# FASTAPI LIFESPAN
# =========================

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


# =========================
# FASTAPI
# =========================

app = FastAPI(
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://egeduoru.github.io"
    ],
    allow_credentials=False,
    allow_methods=[
        "POST",
        "OPTIONS"
    ],
    allow_headers=[
        "Content-Type"
    ],
)


# =========================
# DATA MODEL
# =========================

class WrongAnswer(BaseModel):
    word: str
    initData: str


# =========================
# TELEGRAM INIT DATA
# =========================

def validate_init_data(init_data: str):

    print("=== DEBUG initData ===")

    print(
        "initData length:",
        len(init_data) if init_data else 0
    )

    # Проверяем, что initData вообще пришёл
    if not init_data:

        print(
            "ОШИБКА: initData пустой"
        )

        raise HTTPException(
            status_code=400,
            detail="Telegram initData отсутствует"
        )

    try:

        # Разбираем параметры Telegram
        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )

        print(
            "initData keys:",
            list(parsed.keys())
        )

        # Получаем hash
        received_hash = parsed.pop(
            "hash",
            None
        )

        if not received_hash:

            print(
                "ОШИБКА: hash отсутствует"
            )

            raise HTTPException(
                status_code=400,
                detail="Hash отсутствует"
            )

        # Проверяем дату
        auth_date = int(
            parsed.get(
                "auth_date",
                "0"
            )
        )

        if time.time() - auth_date > 86400:

            print(
                "ОШИБКА: initData устарел"
            )

            raise HTTPException(
                status_code=403,
                detail="Telegram initData устарел"
            )

        # Формируем строку проверки
        data_check_string = "\n".join(
            f"{key}={parsed[key]}"
            for key in sorted(
                parsed.keys()
            )
        )

        # Секретный ключ Telegram Web Apps
        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Проверяем подпись
        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):

            print(
                "ОШИБКА: неверная подпись Telegram"
            )

            print(
                "Полученный hash:",
                received_hash
            )

            print(
                "Вычисленный hash:",
                calculated_hash
            )

            raise HTTPException(
                status_code=403,
                detail="Неверная подпись Telegram"
            )

        # Получаем пользователя
        user_json = parsed.get(
            "user"
        )

        if not user_json:

            print(
                "ОШИБКА: user отсутствует"
            )

            raise HTTPException(
                status_code=400,
                detail="Данные пользователя отсутствуют"
            )

        # Разбираем JSON пользователя
        user = json.loads(
            user_json
        )

        user_id = user.get(
            "id"
        )

        if not user_id:

            print(
                "ОШИБКА: ID пользователя отсутствует"
            )

            raise HTTPException(
                status_code=400,
                detail="ID пользователя отсутствует"
            )

        print(
            "Telegram user ID:",
            user_id
        )

        return user_id

    except HTTPException:
        raise

    except Exception as error:

        print(
            "ОШИБКА проверки initData:",
            repr(error)
        )

        raise HTTPException(
            status_code=400,
            detail="Некорректные данные Telegram"
        )


# =========================
# WRONG ANSWER
# =========================

@app.post("/wrong-answer")
async def wrong_answer(
    data: WrongAnswer
):

    print(
        "=== WRONG ANSWER ==="
    )

    word = data.word.strip()

    print(
        "Слово:",
        word
    )

    if not word:

        raise HTTPException(
            status_code=400,
            detail="Слово не указано"
        )

    # Проверяем Telegram initData
    user_id = validate_init_data(
        data.initData
    )

    print(
        "Получена ошибка:",
        word
    )

    print(
        "Telegram user ID:",
        user_id
    )

    # Ищем объяснение в DOCX
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

    # Отправляем объяснение пользователю
    try:

        await bot.send_message(
            chat_id=user_id,
            text=(
                "📚 Разбор ошибки\n\n"
                + explanation
            )
        )

        print(
            "Объяснение отправлено пользователю",
            user_id
        )

    except Exception as error:

        print(
            "Ошибка отправки сообщения:",
            repr(error)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Не удалось отправить сообщение "
                "в Telegram"
            )
        )

    return {
        "ok": True
    }


# =========================
# MAIN PAGE
# =========================

@app.get("/")
async def root():

    return {
        "ok": True,
        "service": "EGE Duo backend"
    }
