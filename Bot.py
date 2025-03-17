import json
import logging
import asyncio
import uuid  # Import the uuid module

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

# Instead of from aiogram import Dispatcher
from aiogram import Router

TOKEN = "Your Bot Token" # Replace with your actual bot token
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)  # Added parse_mode
dp = Dispatcher()  # Use Dispatcher for aiogram 3.x

DATA_FILE = "music_data.json"

# Configure logging
logging.basicConfig(level=logging.INFO)

# Define states for FSM
class Form(StatesGroup):
    playlist_name = State()
    audio = State()
    delete_index = State()  # Add state for deleting music

# Dictionary to store user states (selected playlist)
user_states = {}


# Function to load and save data
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logging.error("JSONDecodeError: Could not decode JSON. The file might be corrupted.")
        return {}


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving data to {DATA_FILE}: {e}")


# Load data
users_music = load_data()

# Instead of dp.message_handler, use Router
router = Router()


# Helper function to create reply keyboard
def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Create Playlist"),
                KeyboardButton(text="🎵 Add Music"),
            ],
            [
                KeyboardButton(text="🎶 My Playlists"),
                KeyboardButton(text="❓ Help"),
            ],
        ],
        resize_keyboard=True,
    )
    return keyboard


@router.message(Command("start"))
async def start(message: Message):
    user_id = str(message.from_user.id)
    if user_id not in users_music:
        users_music[user_id] = {}
        save_data(users_music)

    # Check if the start command has a payload (deep linking)
    if message.text and len(message.text.split()) > 1:
        payload = message.text.split()[1]
        if payload.startswith("playlist_"):
            unique_id = payload.split("_")[1]
            shared_playlists = load_data()
            if "shared_playlists" in shared_playlists and unique_id in shared_playlists["shared_playlists"]:
                playlist_data = shared_playlists["shared_playlists"][unique_id]
                user_id = playlist_data["user_id"]
                playlist_name = playlist_data["playlist_name"]

                if user_id not in users_music or playlist_name not in users_music[user_id]:
                    await message.answer("Playlist not found or is no longer available.")
                    return

                songs = users_music[user_id][playlist_name]

                if not songs:
                    await message.answer(f"Playlist <b>{playlist_name}</b> is empty.", parse_mode=ParseMode.HTML)
                    return

                await message.answer(f"Playlist <b>{playlist_name}</b>:", parse_mode=ParseMode.HTML)
                for index, song in enumerate(songs, start=1):
                    try:
                        await message.answer(f"{index}. <b>{song['file_name']}</b>", parse_mode=ParseMode.HTML)
                        await bot.send_audio(message.chat.id, song["file_id"])
                    except TelegramAPIError as e:
                        logging.error(f"Telegram API Error sending audio: {e}")
                        await message.answer("❌ Could not send this song due to an error.")
                    except Exception as e:
                        logging.error(f"General error sending audio: {e}")
                        await message.answer("❌ An unexpected error occurred while sending this song.")
                return  # Exit to prevent showing the default menu

    await message.answer(
        "🎵 Welcome!\nChoose an action:",
        reply_markup=create_main_keyboard()
    )


@router.message(F.text == "➕ Create Playlist")
async def create_playlist_handler(message: Message, state: FSMContext):
    await message.answer("Please enter the name of the new playlist:")
    await state.set_state(Form.playlist_name)


@router.message(Form.playlist_name)
async def playlist_name_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    playlist_name = message.text.strip()

    if playlist_name in users_music[user_id]:
        await message.reply("Playlist name already exists. Please choose another name.")
        await state.clear()
        return

    users_music[user_id][playlist_name] = []
    save_data(users_music)
    await message.answer(f"Playlist <b>{playlist_name}</b> created!")
    await state.clear()


@router.message(F.text == "🎵 Add Music")
async def add_music_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not users_music[user_id]:
        await message.answer("You don't have any playlists. Create one first.")
        return

    buttons = []
    for playlist_name in users_music[user_id].keys():
        buttons.append([InlineKeyboardButton(text=playlist_name, callback_data=f"select_playlist:{playlist_name}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Select a playlist to add music to:", reply_markup=keyboard)


@router.callback_query(lambda query: query.data.startswith("select_playlist:"))
async def select_playlist_callback(query: CallbackQuery, state: FSMContext):
    user_id = str(query.from_user.id)
    playlist_name = query.data.split(":")[1]

    await state.update_data(playlist_name=playlist_name)
    await state.set_state(Form.audio)

    await query.message.answer(f"Send me the audio file to add to <b>{playlist_name}</b>.")
    await query.answer()


@router.message(Form.audio, F.audio)
async def audio_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    playlist_name = data.get("playlist_name")

    if not playlist_name:
        await message.reply("Please select a playlist first.")
        await state.clear()
        return

    try:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "Unknown.mp3"

        users_music[user_id][playlist_name].append({"file_id": file_id, "file_name": file_name})
        save_data(users_music)

        await message.answer(f"✅ Song <b>{file_name}</b> added to <b>{playlist_name}</b>!")

    except Exception as e:
        logging.error(f"Error saving music: {e}")
        await message.reply("❌ Sorry, there was an error saving the song.")

    await state.clear()


@router.message(F.text == "🎶 My Playlists")
async def my_playlists_handler(message: Message):
    user_id = str(message.from_user.id)
    if not users_music[user_id]:
        await message.answer("You don't have any playlists.")
        return

    buttons = []
    for playlist_name in users_music[user_id].keys():
        buttons.append([
            InlineKeyboardButton(text=playlist_name, callback_data=f"view_playlist:{playlist_name}"),
            InlineKeyboardButton(text="🔗 Share", callback_data=f"share_playlist:{playlist_name}"),  # Add share button
            InlineKeyboardButton(text="❌ Delete Playlist", callback_data=f"confirm_delete:{playlist_name}")
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Your playlists:", reply_markup=keyboard)


@router.callback_query(lambda query: query.data.startswith("view_playlist:"))
async def view_playlist_callback(query: CallbackQuery, state: FSMContext):
    playlist_name = query.data.split(":")[1]
    user_id = str(query.from_user.id)
    if not users_music[user_id][playlist_name]:
        await query.message.answer(f"Playlist <b>{playlist_name}</b> is empty.")
        return

    songs = users_music[user_id][playlist_name]
    buttons = [[InlineKeyboardButton(text="🎧 Send All Music", callback_data=f"send_all_music:{playlist_name}")]]  # Add "Send All Music" button
    for index, song in enumerate(songs, start=1):
        buttons.append([
            InlineKeyboardButton(text=f"🎵 {index}. {song['file_name']}", callback_data=f"play_song:{playlist_name}:{index}"),
            InlineKeyboardButton(text="❌", callback_data=f"confirm_delete_song:{playlist_name}:{index}")
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await query.message.answer(f"Songs in <b>{playlist_name}</b>:", reply_markup=keyboard)
    await state.update_data(playlist_name=playlist_name)


@router.callback_query(lambda query: query.data.startswith("send_all_music:"))
async def send_all_music_callback(query: CallbackQuery):
    playlist_name = query.data.split(":")[1]
    user_id = str(query.from_user.id)

    if user_id not in users_music or playlist_name not in users_music[user_id]:
        await query.answer("Playlist not found.")
        return

    songs = users_music[user_id][playlist_name]
    if not songs:
        await query.answer("Playlist is empty.")
        return

    for song in songs:
        try:
            await bot.send_audio(query.message.chat.id, song["file_id"], caption=song["file_name"])
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error sending audio: {e}")
            await query.answer("Could not send this song due to an error.")
            return  # Stop sending if one song fails
        except Exception as e:
            logging.error(f"General error sending audio: {e}")
            await query.answer("An unexpected error occurred while sending this song.")
            return  # Stop sending if one song fails

    await query.answer("All songs sent!")


@router.callback_query(lambda query: query.data.startswith("play_song:"))
async def play_song_callback(query: CallbackQuery):
    user_id = str(query.from_user.id)
    _, playlist_name, index_str = query.data.split(":")
    index = int(index_str) - 1

    if user_id not in users_music or playlist_name not in users_music[user_id]:
        await query.answer("Playlist not found.")
        return

    songs = users_music[user_id][playlist_name]
    if 0 <= index < len(songs):
        song = songs[index]
        try:
            await bot.send_audio(query.message.chat.id, song["file_id"], caption=song["file_name"])
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error sending audio: {e}")
            await query.answer("Could not send this song due to an error.")
        except Exception as e:
            logging.error(f"General error sending audio: {e}")
            await query.answer("An unexpected error occurred while sending this song.")
    else:
        await query.answer("Invalid song number.")

    await query.answer()


@router.callback_query(lambda query: query.data.startswith("confirm_delete_song:"))
async def confirm_delete_song_callback(query: CallbackQuery):
    _, playlist_name, index_str = query.data.split(":")
    index = int(index_str)
    user_id = str(query.from_user.id)

    buttons = [[
        InlineKeyboardButton(text="✅ Yes", callback_data=f"delete_song:{playlist_name}:{index}"),
        InlineKeyboardButton(text="❌ No", callback_data=f"view_playlist:{playlist_name}")
    ]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await query.message.answer(
        f"Are you sure you want to delete song number <b>{index}</b> from <b>{playlist_name}</b>?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await query.answer()


@router.callback_query(lambda query: query.data.startswith("delete_song:"))
async def delete_song_callback(query: CallbackQuery, state: FSMContext):
    user_id = str(query.from_user.id)
    _, playlist_name, index_str = query.data.split(":")
    index = int(index_str)

    data = await state.get_data()
    playlist_name = data.get("playlist_name")

    if not playlist_name:
        await query.message.answer("Something went wrong. Please try again.")
        return

    try:
        index = int(index_str) - 1
        if 0 <= index < len(users_music[user_id][playlist_name]):
            deleted_song = users_music[user_id][playlist_name].pop(index)
            save_data(users_music)
            await query.message.answer(f"✅ Song <b>{deleted_song['file_name']}</b> deleted from <b>{playlist_name}</b>!")
        else:
            await query.message.answer("Invalid song number.")
    except ValueError:
        await query.message.answer("Invalid song number.")
    except Exception as e:
        logging.error(f"Error deleting music: {e}")
        await query.message.answer("❌ Sorry, there was an error deleting the song.")


@router.callback_query(lambda query: query.data.startswith("confirm_delete:"))
async def confirm_delete_callback(query: CallbackQuery):
    playlist_name = query.data.split(":")[1]
    user_id = str(query.from_user.id)

    # Create confirmation keyboard
    buttons = [[
        InlineKeyboardButton(text="✅ Yes", callback_data=f"delete_playlist:{playlist_name}"),
        InlineKeyboardButton(text="❌ No", callback_data="cancel_delete")
    ]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await query.message.answer(
        f"Are you sure you want to delete playlist <b>{playlist_name}</b>?",
        reply_markup=keyboard
    )
    await query.answer()


@router.callback_query(lambda query: query.data.startswith("delete_playlist:"))
async def delete_playlist_callback(query: CallbackQuery):
    playlist_name = query.data.split(":")[1]
    user_id = str(query.from_user.id)
    if playlist_name in users_music[user_id]:
        del users_music[user_id][playlist_name]
        save_data(users_music)
        await query.message.answer(f"Playlist <b>{playlist_name}</b> deleted.")
    else:
        await query.message.answer("Playlist not found.")
    await query.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete_callback(query: CallbackQuery):
    await query.message.answer("Deletion cancelled.")
    await query.answer()


@router.message(Command("list_playlists"))
async def list_playlists_command(message: Message):
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.reply("Please provide a user ID. Example: `/list_playlists 123456789`")
        return

    target_user_id = command_parts[1]
    if target_user_id not in users_music:
        await message.reply("User not found.")
        return

    playlists = users_music[target_user_id].keys()
    if not playlists:
        await message.reply("This user has no playlists.")
        return

    playlist_list = "\n".join(playlists)
    await message.answer(f"Playlists for user <b>{target_user_id}</b>:\n{playlist_list}")


@router.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "Here are the available commands:\n"
        "- /start: Start the bot and show the main menu.\n"
        "- ➕ Create Playlist: Create a new playlist.\n"
        "- 🎵 Add Music: Add music to a playlist.\n"
        "- 🎶 My Playlists: View your playlists.\n"
        "- ❓ Help: Show this help message."
    )
    await message.answer(help_text)


@router.message(F.audio, Form.audio)
async def save_music(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    playlist_name = data.get("playlist_name")

    if not playlist_name:
        await message.reply("Please select a playlist first.")
        await state.clear()
        return

    file_id = message.audio.file_id
    file_name = message.audio.file_name or "Unknown.mp3"

    users_music[user_id][playlist_name].append({"file_id": file_id, "file_name": file_name})
    save_data(users_music)

    await message.answer(f"✅ Song <b>{file_name}</b> added to <b>{playlist_name}</b>!")
    await state.clear()


@router.message(Command("mylist"))
async def my_list(message: Message):
    user_id = str(message.from_user.id)
    if user_id not in users_music or not users_music[user_id]["music"]:
        await message.reply("⛔ شما هیچ آهنگی ذخیره نکرده‌اید!")
        return

    await message.answer("🎵 لیست آهنگ‌های شما:")
    for index, song in enumerate(users_music[user_id]["music"], start=1):
        await message.answer(f"{index}. <b>{song['file_name']}</b>")
        try:
            await bot.send_audio(message.chat.id, song["file_id"])
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error sending audio: {e}")
            await message.answer("❌ Could not send this song due to an error.")
        except Exception as e:
            logging.error(f"General error sending audio: {e}")
            await message.answer("❌ An unexpected error occurred while sending this song.")


@router.message(Command("getlist"))
async def get_list(message: Message):
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.reply("⛔ لطفاً شناسه را وارد کنید. مثال: `/getlist abc12345`")
        return

    unique_id = command_parts[1]
    user_id = next(
        (uid for uid, data in users_music.items() if data["unique_id"] == unique_id), None
    )

    if not user_id or not users_music[user_id]["music"]:
        await message.reply("⛔ این کاربر هیچ آهنگی ذخیره نکرده است یا شناسه اشتباه است!")
        return

    await message.answer("🎵 لیست آهنگ‌های این کاربر:")
    for song in users_music[user_id]["music"]:
        try:
            await bot.send_audio(message.chat.id, song["file_id"], caption=song["file_name"])
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error sending audio: {e}")
            await message.answer("❌ Could not send this song due to an error.")
        except Exception as e:
            logging.error(f"General error sending audio: {e}")
            await message.answer("❌ An unexpected error occurred while sending this song.")


@router.message(Command("delete"))
async def delete_music(message: Message, state: FSMContext):
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.reply("⛔ لطفاً شماره آهنگ را وارد کنید. مثال: `/delete 2`")
        return

    user_id = str(message.from_user.id)
    if user_id not in users_music or not users_music[user_id]["music"]:
        await message.reply("⛔ لیست شما خالی است!")
        return

    try:
        index = int(command_parts[1]) - 1
        if 0 <= index < len(users_music[user_id]["music"]):
            deleted_song = users_music[user_id]["music"].pop(index)
            save_data(users_music)
            await message.answer(f"✅ آهنگ <b>{deleted_song['file_name']}</b> حذف شد!")
        else:
            await message.reply("⛔ شماره نامعتبر است!")
    except ValueError:
        await message.reply("⛔ لطفاً یک عدد معتبر وارد کنید!")
    except Exception as e:
        logging.error(f"Error deleting music: {e}")
        await message.reply("❌ متاسفم، مشکلی در حذف آهنگ پیش آمد.")
    await state.clear()


@router.callback_query(lambda query: query.data.startswith("share_playlist:"))
async def share_playlist_callback(query: CallbackQuery):
    playlist_name = query.data.split(":")[1]
    user_id = str(query.from_user.id)

    # Generate a unique ID for the playlist
    unique_id = str(uuid.uuid4())

    # Store the playlist data with the unique ID
    shared_playlists = load_data()  # Load existing data
    if "shared_playlists" not in shared_playlists:
        shared_playlists["shared_playlists"] = {}
    shared_playlists["shared_playlists"][unique_id] = {
        "user_id": user_id,
        "playlist_name": playlist_name
    }
    save_data(shared_playlists)  # Save updated data

    # Fetch bot's username
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logging.error(f"Error fetching bot username: {e}")
        await query.answer("❌ Could not generate shareable link.")
        return

    # Create the shareable link
    shareable_link = f"t.me/{bot_username}?start=playlist_{unique_id}"

    await query.message.answer(
        f"Share this link to share your playlist <b>{playlist_name}</b>:\n"
        f"<code>{shareable_link}</code>",
        parse_mode=ParseMode.HTML  # Ensure HTML parsing for <code> tag
    )
    await query.answer()


@router.message(lambda message: message.text.startswith("playlist_"))
async def handle_shared_playlist(message: Message):
    unique_id = message.text.split("_")[1]

    shared_playlists = load_data()
    if "shared_playlists" not in shared_playlists or unique_id not in shared_playlists["shared_playlists"]:
        await message.answer("Playlist not found.")
        return

    playlist_data = shared_playlists["shared_playlists"][unique_id]
    user_id = playlist_data["user_id"]
    playlist_name = playlist_data["playlist_name"]

    if user_id not in users_music or playlist_name not in users_music[user_id]:
        await message.answer("Playlist not found or is no longer available.")
        return

    songs = users_music[user_id][playlist_name]

    if not songs:
        await message.answer(f"Playlist <b>{playlist_name}</b> is empty.", parse_mode=ParseMode.HTML)
        return

    await message.answer(f"Playlist <b>{playlist_name}</b>:", parse_mode=ParseMode.HTML)
    for index, song in enumerate(songs, start=1):
        try:
            await message.answer(f"{index}. <b>{song['file_name']}</b>", parse_mode=ParseMode.HTML)
            await bot.send_audio(message.chat.id, song["file_id"])
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error sending audio: {e}")
            await message.answer("❌ Could not send this song due to an error.")
        except Exception as e:
            logging.error(f"General error sending audio: {e}")
            await message.answer("❌ An unexpected error occurred while sending this song.")


@router.message(F.text == "❓ Help")
async def help_command(message: Message):
    help_text = (
        "Here are the available commands:\n"
        "- /start: Start the bot and show the main menu.\n"
        "- ➕ Create Playlist: Create a new playlist.\n"
        "- 🎵 Add Music: Add music to a playlist.\n"
        "- 🎶 My Playlists: View your playlists.\n"
        "- /list_playlists [user_id]: List playlists of a specific user.\n"
        "- ❓ Help: Show this help message."
    )
    await message.answer(help_text)


async def main():
    # Register the router with the dispatcher
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
