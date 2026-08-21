import asyncio
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

BOT_TOKEN = "8795582059:AAHm7a0uKXK0mH7Iat19ARAlXJ8TvWI9gYU"  # Вставьте ваш действующий токен

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- База Данных ---
def init_db():
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            bio TEXT,
            photo_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user_id INTEGER,
            to_user_id INTEGER,
            UNIQUE(from_user_id, to_user_id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- FSM Состояния ---
class Registration(StatesGroup):
    name = State()
    age = State()
    city = State()
    bio = State()
    photo = State()

# --- Клавиатуры ---
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Смотреть анкеты")],
            [KeyboardButton(text="✏️ Заполнить анкету заново")]
        ],
        resize_keyboard=True
    )

def action_keyboard(target_user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍", callback_data=f"like_{target_user_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"dislike_{target_user_id}")
        ]
    ])

# --- Регистрация ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Добро пожаловать в бот знакомств! 👋\nНачнем с заполнения вашей анкеты.\n\nКак тебя зовут?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.name)

@dp.message(Registration.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет? (Доступ строго с 18 лет)")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введи возраст числом.")
        return
    
    age = int(message.text)
    if age < 18:
        await message.answer("Извини, регистрация разрешена только с 18 лет.")
        await state.clear()
        return

    await state.update_data(age=age)
    await message.answer("Из какого ты города?")
    await state.set_state(Registration.city)

@dp.message(Registration.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Расскажи немного о себе (описание анкеты):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def process_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Отправь свое фото (именно картинку или фото):")
    await state.set_state(Registration.photo)

# Прием фото или документа
@dp.message(Registration.photo, F.photo | F.document)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        photo_id = message.document.file_id

    if not photo_id:
        await message.answer("Не удалось распознать фото. Пожалуйста, отправь изображение.")
        return

    data = await state.get_data()
    
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, name, age, city, bio, photo_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (message.from_user.id, data["name"], data["age"], data["city"], data["bio"], photo_id))
    conn.commit()
    conn.close()

    await state.clear()
    caption = f"Анкета сохранена! 🎉\n\n<b>{data['name']}</b>, {data['age']}, {data['city']}\n{data['bio']}"
    
    if message.photo:
        await message.answer_photo(photo_id, caption=caption, parse_mode="HTML", reply_markup=main_menu_keyboard())
    else:
        await message.answer_document(photo_id, caption=caption, parse_mode="HTML", reply_markup=main_menu_keyboard())

@dp.message(Registration.photo)
async def process_photo_invalid(message: types.Message):
    await message.answer("Жду фотографию! Пожалуйста, отправь картинку.")

# --- Просмотр анкет ---
@dp.message(F.text == "🚀 Смотреть анкеты")
async def show_next_profile(message: types.Message):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, name, age, city, bio, photo_id FROM users 
        WHERE user_id != ? ORDER BY RANDOM() LIMIT 1
    """, (message.from_user.id,))
    target = cursor.fetchone()
    conn.close()

    if not target:
        await message.answer("Пока нет других доступных анкет в базе. Зарегистрируйте еще одного пользователя для проверки!")
        return

    u_id, name, age, city, bio, photo_id = target
    caption = f"<b>{name}</b>, {age}, {city}\n\n{bio}"
    try:
        await message.answer_photo(photo_id, caption=caption, parse_mode="HTML", reply_markup=action_keyboard(u_id))
    except Exception:
        await message.answer_document(photo_id, caption=caption, parse_mode="HTML", reply_markup=action_keyboard(u_id))

@dp.message(F.text == "✏️ Заполнить анкету заново")
async def restart_registration(message: types.Message, state: FSMContext):
    await start_cmd(message, state)

# --- Лайки / Дизлайки ---
@dp.callback_query(F.data.startswith("like_"))
async def handle_like(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    from_id = callback.from_user.id

    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, age, city, bio, photo_id FROM users WHERE user_id = ?", (from_id,))
    sender = cursor.fetchone()
    conn.close()

    if sender:
        s_name, s_age, s_city, s_bio, s_photo = sender
        username_str = f"@{callback.from_user.username}" if callback.from_user.username else "без юзернейма"
        caption = f"Ты кому-то понравился(лась)! ❤️\n\n<b>{s_name}</b>, {s_age}, {s_city}\n{s_bio}\n\nНаписать: {username_str}"
        try:
            await bot.send_photo(target_id, photo=s_photo, caption=caption, parse_mode="HTML")
        except Exception:
            pass

    await callback.answer("Лайк отправлен! 👍")
    await callback.message.delete()
    await show_next_profile(callback.message)

@dp.callback_query(F.data.startswith("dislike_"))
async def handle_dislike(callback: types.CallbackQuery):
    await callback.answer("Пропущено 👎")
    await callback.message.delete()
    await show_next_profile(callback.message)

# --- Веб-сервер для Render ---
async def handle_ping(request):
    return web.Response(text="Dating Bot Active")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
