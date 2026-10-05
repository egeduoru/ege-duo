import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docx_parser import find_explanation
from aiogram import Bot


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "Переменная окружения BOT_TOKEN не установлена."
    )

bot = Bot(token=BOT_TOKEN)

app = FastAPI()


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://egeduoru.github.io"
    ],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ============================================================
# ДАННЫЕ ЗАПРОСА
# ============================================================

class WrongAnswer(BaseModel):
    word: str
    initData: str


# ============================================================
# ПРОВЕРКА TELEGRAM INIT DATA
# ============================================================

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

        received_hash = parsed.pop("hash", None)

        if not received_hash:
            raise HTTPException(
                status_code=400,
                detail="Hash отсутствует"
            )

        auth_date = int(
            parsed.get("auth_date", "0")
        )

        # initData старше 24 часов не принимаем
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

        user = json.loads(user_json)

        user_id = user.get("id")

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


# ============================================================
# ОШИБКА В ТРЕНАЖЁРЕ
# ============================================================

@app.post("/wrong-answer")
async def wrong_answer(data: WrongAnswer):

    word = data.word.strip()

    if not word:
        raise HTTPException(
            status_code=400,
            detail="Слово не указано"
        )

    # Определяем пользователя Telegram
    user_id = validate_init_data(
        data.initData
    )

    print(
        f"Получена ошибка: {word}"
    )

    print(
        f"Telegram user ID: {user_id}"
    )

    # Ищем объяснение в prepri.docx
    explanation = find_explanation(word)

    if not explanation:

        print(
            f"Объяснение для «{word}» не найдено"
        )

        return {
            "ok": False,
            "message": "Объяснение не найдено"
        }

    # Отправляем объяснение в Telegram
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


# ============================================================
# ПРОВЕРКА СЕРВЕРА
# ============================================================

@app.get("/")
async def root():

    return {
        "ok": True,
        "service": "EGE Duo backend"
    }

