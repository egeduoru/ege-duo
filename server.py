import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docx_parser import find_explanation
from bot import bot


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = "8816383632:AAGfqKX5xv5W6icp-kJmCTl7mXi9U2E8BUY"


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI()


# Разрешаем GitHub Pages обращаться к backend

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
# МОДЕЛЬ ЗАПРОСА
# =========================================================

class WrongAnswer(BaseModel):

    word: str

    initData: str


# =========================================================
# ПРОВЕРКА TELEGRAM INIT DATA
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


        # Проверяем актуальность initData.
        # 24 часа достаточно для нашего приложения.

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


        # Формируем data-check-string

        data_check_string = "\n".join(
            f"{key}={parsed[key]}"
            for key in sorted(parsed.keys())
        )


        # Секретный ключ Telegram WebApp

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


        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):

            raise HTTPException(
                status_code=403,
                detail="Неверная подпись Telegram"
            )


        # Получаем пользователя

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
            "Ошибка проверки initData:",
            error
        )

        raise HTTPException(
            status_code=400,
            detail="Некорректные данные Telegram"
        )


# =========================================================
# ПРИЁМ НЕПРАВИЛЬНОГО ОТВЕТА
# =========================================================

@app.post("/wrong-answer")
async def wrong_answer(data: WrongAnswer):

    word = data.word.strip()


    if not word:

        raise HTTPException(
            status_code=400,
            detail="Слово не указано"
        )


    # -----------------------------------------------------
    # Проверяем Telegram
    # -----------------------------------------------------

    user_id = validate_init_data(
        data.initData
    )


    print(
        f"Получена ошибка: {word}"
    )

    print(
        f"Telegram user ID: {user_id}"
    )


    # -----------------------------------------------------
    # Ищем карточку в DOCX
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # Отправляем объяснение пользователю
    # -----------------------------------------------------

    try:

        await bot.send_message(
            chat_id=user_id,
            text=(
                "📚 Разбор ошибки\n\n"
                + explanation
            )
        )


        print(
            f"Объяснение отправлено пользователю {user_id}"
        )


    except Exception as error:

        print(
            "Ошибка отправки сообщения:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Не удалось отправить сообщение в Telegram"
        )


    return {
        "ok": True
    }


# =========================================================
# ПРОВЕРКА BACKEND
# =========================================================

@app.get("/")
async def root():

    return {
        "ok": True,
        "service": "EGE Duo backend"
    }
