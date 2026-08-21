import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

# Вставьте ваш ТОКЕН от @BotFather вместо указанного ниже
BOT_TOKEN = "8795582059:AAHr_o8ndJ8OxzG0k3sjI7y-wJh-_h-k7Yg"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Привет! Добро пожаловать в бот знакомств!")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())