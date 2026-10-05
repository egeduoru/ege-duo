import sys
sys.path.append(r"C:\Users\PC\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages")

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, WebAppData
from docx_parser import find_explanation


TOKEN = "8816383632:AAGfqKX5xv5W6icp-kJmCTl7mXi9U2E8BUY"

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🚀 Открыть приложение",
                    web_app=WebAppInfo(
                        url="https://egeduoru.github.io/ege-duo/"
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

@dp.message(lambda message: message.web_app_data is not None)
async def web_app_data_handler(message: Message):

    data = message.web_app_data.data

    if data.startswith("wrong:"):

        word = data.replace("wrong:", "", 1).strip()

        explanation = find_explanation(word)

        if explanation:
            await message.answer(
                "📚 Объяснение\n\n" + explanation
            )
        else:
            await message.answer(
                f"❌ Не удалось найти объяснение для слова «{word}»."
            )

@dp.message()
async def buttons(message: Message):
    if message.text == "📚 Начать тренировку":
        await message.answer(
            "📚 Отлично! Начинаем тренировку!"
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

