import asyncio
import json
import os
import socket
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiohttp import ClientSession
from dotenv import load_dotenv
from pytz import timezone

from utils.zoom import ZoomClient

# Загружаем переменные окружения
load_dotenv()

# Получаем учетные данные Zoom из переменных окружения
PROJECTS = [
    {
        "name": "Vanya",
        "json_file": "rec_history/messages_vanya.json",
        "zoom_account_id": os.getenv("VANYA_ZOOM_ACCOUNT_ID"),
        "zoom_client_id": os.getenv("VANYA_ZOOM_CLIENT_ID"),
        "zoom_client_secret": os.getenv("VANYA_ZOOM_CLIENT_SECRET"),
        "group_chat_id": os.getenv("KVL_GROUP_CHAT_ID"),
        "message_thread_id": os.getenv("MESSAGE_THREAD_ID"),
    },
    {
        "name": "Krauz",
        "json_file": "rec_history/messages_krauz.json",
        "zoom_account_id": os.getenv("KRAUZ_ZOOM_ACCOUNT_ID"),
        "zoom_client_id": os.getenv("KRAUZ_ZOOM_CLIENT_ID"),
        "zoom_client_secret": os.getenv("KRAUZ_ZOOM_CLIENT_SECRET"),
        "group_chat_id": os.getenv("KVL_GROUP_CHAT_ID"),  # Тот же чат, что и у Вани
        "message_thread_id": os.getenv("MESSAGE_THREAD_ID"),
    },
    {
        "name": "Lera",
        "json_file": "rec_history/messages_lera.json",
        "zoom_account_id": os.getenv("LERA_ZOOM_ACCOUNT_ID"),
        "zoom_client_id": os.getenv("LERA_ZOOM_CLIENT_ID"),
        "zoom_client_secret": os.getenv("LERA_ZOOM_CLIENT_SECRET"),
        "group_chat_id": os.getenv("KVL_GROUP_CHAT_ID"),  # Отдельный чат
        "message_thread_id": None,  # У Леры нет темы
    },
    {
        "name": "Misha",
        "json_file": "rec_history/messages_misha.json",
        "zoom_account_id": os.getenv("MISHA_ZOOM_ACCOUNT_ID"),
        "zoom_client_id": os.getenv("MISHA_ZOOM_CLIENT_ID"),
        "zoom_client_secret": os.getenv("MISHA_ZOOM_CLIENT_SECRET"),
        "group_chat_id": os.getenv("KVL_GROUP_CHAT_ID"),
        "message_thread_id": os.getenv("TEST_MESSAGE_THREAD_ID")
    }
]

moscow_tz = timezone('Europe/Moscow')


# Получаем локальный IP-адрес
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # Google DNS
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return local_ip


local_ip = get_local_ip()
http_port = 8081  # Укажите порт, на котором работает Docker-контейнер с telegram-bot-api
TOKEN = os.environ.get('TOKEN')

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()  # Инициализируем Dispatcher без передачи bot напрямую

# Состояние пользователей
user_states = {}


# Функция для отправки сообщений в Telegram
async def send_message(chat_id, text):
    url = f"http://{local_ip}:{http_port}/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    async with ClientSession() as session:
        await session.post(url, json=payload)


def get_message_ids_by_text(chat_id, meeting_topic):
    """Возвращает список message_id по заданному тексту"""
    user_data = user_states.get(chat_id, {})
    json_file = user_data.get("json_file")
    try:
        print(f"DEBUG: meeting_topic={meeting_topic}, user_data={user_data}, json_file={json_file}")
        with open(json_file, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get(meeting_topic, [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Функция для форматирования времени
def format_time(dt):
    return dt.strftime("%d:%m:%Y %H:%M:%S")


# Функция для загрузки и отправки записи
async def send_recording(chat_id, download_url_with_token, filename):
    if os.path.exists(filename):
        print(f"DEBUG: Файл {filename} уже существует, отправляем снова.")
        with open(filename, 'rb') as f:
            files = {'document': f}
            send_document_url = f"http://{local_ip}:{http_port}/bot{TOKEN}/sendDocument"
            async with ClientSession() as session:
                await session.post(send_document_url, data={"chat_id": chat_id}, files=files)
        await send_message(chat_id, f"Запись {filename} уже скачена. Отправляю снова.")
    else:
        async with ClientSession() as session:
            response = await session.get(download_url_with_token)
            print("DEBUG: Статус загрузки:", response.status)

            if response.status == 200:
                with open(filename, 'wb') as f:
                    total_size = 0
                    async for chunk in response.content.iter_any():
                        f.write(chunk)
                        total_size += len(chunk)
                    print(f"DEBUG: Размер загруженного файла {filename} - {total_size} байт.")

                with open(filename, 'rb') as f:
                    files = {'document': f}
                    send_document_url = f"http://{local_ip}:{http_port}/bot{TOKEN}/sendDocument"
                    async with ClientSession() as session:
                        await session.post(send_document_url, data={"chat_id": chat_id}, files=files)
                await send_message(chat_id, f"Запись {filename} успешно загружена и отправлена.")
            else:
                print(f"DEBUG: Не удалось загрузить запись для встречи.")
                await send_message(chat_id, "Не удалось загрузить запись.")


# Функция для обработки команды /start
@dp.message(Command("start"))
async def start(message: Message):
    await send_message(message.chat.id,
                       "Привет! Я ваш помощник для Zoom 👋\n\nЯ создан для того, чтобы сделать вашу жизнь проще и освободить вас от рутины и долгих ожиданий\n\nЯ автоматически проверяю появление новых конференций и отправляю их записи в ваши чаты 😎\nБольше не придется ждать скачивания созвонов!\n\nНажимайте /recs, чтобы увидеть список доступных конференций")


@dp.message(Command("help"))
async def start(message: Message):
    await send_message(message.chat.id,
                       "/start - Запускает бота, выводит приветственное сообщение с кратким описанием возможностей\n\n"
                       "/recs - Показывает список доступных конференций, нажав на которые можно получить их записи, если записи не скачаны - попытка их получить запустит скачивание записей этих конференций, подождите немного и попробуйте еще раз, либо же дождитесь появление запись в вашей группе\n\n"
                       "/help - Показывает это сообщение с описанием всех доступных на данный момент команд")


# Функция для обработки команды /recs
@dp.message(Command("recs"))
async def choose_conference(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ваня", callback_data="recs_vanya")],
        [InlineKeyboardButton(text="Крауз", callback_data="recs_krauz")],
        [InlineKeyboardButton(text="Лера", callback_data="recs_lera")],
        [InlineKeyboardButton(text="Миша", callback_data="recs_misha")]
    ])
    await message.answer("Чьи конференции хотите получить?", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("recs_"))
async def recs(callback: CallbackQuery):
    user = callback.data.split("_")[1].capitalize()
    project = next((p for p in PROJECTS if p["name"] == user), None)

    if not project:
        await callback.message.answer("Ошибка: неизвестный пользователь")
        return

    client = ZoomClient(
        account_id=project["zoom_account_id"],
        client_id=project["zoom_client_id"],
        client_secret=project["zoom_client_secret"]
    )

    client.access_token = client.get_access_token()  # Обновляем токен перед запросом
    recs = client.get_recordings(from_date='2023-01-01', to_date=datetime.utcnow().strftime('%Y-%m-%d'))
    print("DEBUG: Получены записи:", recs)

    if recs.get('meetings'):
        user_states[callback.message.chat.id] = {
            'meetings': recs['meetings'],
            'group_chat_id': project["group_chat_id"],
            'message_thread_id': project["message_thread_id"],
            'json_file': project["json_file"]
        }
        message_text = "Список всех доступных конференций:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Скачать", callback_data="download")]
        ])

        for index, meeting in enumerate(recs['meetings'], start=1):
            start_time_moscow = datetime.fromisoformat(
                meeting['start_time'].replace("Z", "+00:00")).astimezone(moscow_tz)
            message_text += f"{index}. {format_time(start_time_moscow)} - {meeting['topic']}\n"

        await callback.message.answer(message_text, reply_markup=keyboard)
    else:
        await callback.message.answer("Записи не найдены.\nСейчас все скачаю, подождите немного ⏳")


# Функция для обработки команды /download
@dp.callback_query(lambda c: c.data == "download")
async def choose_conference(callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    meetings = user_states.get(chat_id, {}).get('meetings', [])
    if not meetings:
        await send_message(chat_id, "Нет доступных конференций.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for index, meeting in enumerate(meetings, start=1):
        row.append(InlineKeyboardButton(text=str(index), callback_data=f"send_{index - 1}"))
        if len(row) == 4:
            keyboard.inline_keyboard.append(row)
            row = []
    if row:
        keyboard.inline_keyboard.append(row)

    await callback_query.message.answer("Записи какой конференции вы хотите получить?", reply_markup=keyboard)


# Функция для поиска и пересылки записей из группы
# Функция для поиска и пересылки записей из группы
async def forward_videos(chat_id, meeting_topic):
    """Находим сообщения с нужным текстом и пересылаем их видео"""
    user_data = user_states.get(chat_id, {})
    group_chat_id = user_data.get("group_chat_id")
    if not group_chat_id:
        await bot.send_message(chat_id, "Ошибка: не найден group_chat_id.")
        return

    message_ids = get_message_ids_by_text(chat_id, meeting_topic)

    if not message_ids:
        await bot.send_message(chat_id, "Не найдено записей с таким названием.\nСейчас скачаю 🫡")
        return

    found = False
    for message_id in message_ids:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=group_chat_id,
                message_id=message_id
            )
            found = True
        except Exception as e:
            print(f"Ошибка пересылки сообщения {message_id}: {e}")
    if found:
        await bot.send_message(chat_id, "Записи успешно отправлены!")


# Функция для обработки выбора конференции и пересылки записей
@dp.callback_query(lambda c: c.data.startswith("send_"))
async def send_records(callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    meetings = user_states.get(chat_id, {}).get('meetings', [])
    index = int(callback_query.data.split('_')[1])
    if index >= len(meetings):
        await send_message(chat_id, "Неверный выбор конференции.")
        return

    meeting = meetings[index]
    start_time_moscow = datetime.fromisoformat(meeting['start_time'].replace("Z", "+00:00")) + timedelta(hours=3)
    # Формируем тему конференции в формате "дата время - Zoom Meeting Тема"
    meeting_topic = f"{format_time(start_time_moscow)} - {meeting['topic']}"

    await forward_videos(chat_id, meeting_topic)


# Запуск бота с опросом
async def main():
    await dp.start_polling(bot)  # Передаем bot в start_polling


if __name__ == "__main__":
    asyncio.run(main())  # Запускаем асинхронный цикл
