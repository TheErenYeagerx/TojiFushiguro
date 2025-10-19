import os
import time
import threading
import subprocess
import logging
import yt_dlp
import asyncio
from collections import defaultdict, deque
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config

# OWNER_ID and LOGGER_ID must be defined in config.py
OWNER_ID = getattr(config, "OWNER_ID", None)   # Your Telegram user ID (int)
LOGGER_ID = getattr(config, "LOGGER_ID", None) # Log channel/group/user ID (int)

# Logging setup (stdout + actions.log file)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RTMPStreamerLogger")
file_handler = logging.FileHandler("actions.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

bot = Client(
    "EnhancedRTMPStreamer",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

rtmp_keys = {}
ffmpeg_processes = {}
queues = defaultdict(deque)

ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": "%(title)s.%(ext)s",
    "quiet": True,
    "noplaylist": True,
    "default_search": "ytsearch1",
    "cookiefile": "cookies.txt"
}

def format_duration(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}:{mins:02}:{secs:02}" if hours else f"{mins}:{secs:02}"

def get_rtmp_url(chat_id):
    key = rtmp_keys.get(chat_id)
    return f"{config.DEFAULT_RTMP_URL.rstrip('/')}/{key}" if key else None

def stop_ffmpeg(chat_id):
    process = ffmpeg_processes.get(chat_id)
    if process:
        try:
            process.terminate()
            process.wait(timeout=10)
        except Exception:
            process.kill()
        ffmpeg_processes[chat_id] = None

def run_ffmpeg(chat_id, command, input_file=None, on_finish=None):
    try:
        logging.info(f"Starting FFmpeg for chat {chat_id}...")
        ffmpeg_processes[chat_id] = subprocess.Popen(command)
        ffmpeg_processes[chat_id].wait()
    except Exception as e:
        logging.error(f"FFmpeg error: {e}")
    finally:
        ffmpeg_processes[chat_id] = None
        if input_file and os.path.exists(input_file):
            try:
                os.remove(input_file)
                logging.info(f"Deleted file {input_file}")
            except Exception as e:
                logging.warning(f"Failed to delete {input_file}: {e}")
        if on_finish:
            asyncio.run(on_finish(chat_id))

def download_media(query, video=True):
    opts = ydl_opts.copy()
    opts["format"] = "bestvideo+bestaudio/best" if video else "bestaudio/best"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info and info["entries"]:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info)
        return filename, info

def build_ffmpeg_video(input_file, url):
    return [
        "ffmpeg", "-re", "-i", input_file,
        "-c:v", "libx264", "-preset", "superfast", "-tune", "zerolatency",
        "-pix_fmt", "yuv420p", "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k",
        "-g", "50", "-keyint_min", "50",
        "-vf", "scale=1280:720,fps=30",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
        "-f", "flv", url
    ]

def build_ffmpeg_audio(input_file, url):
    return [
        "ffmpeg", "-re", "-i", input_file,
        "-vn", "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
        "-f", "flv", url
    ]

async def send_log(text):
    for log_id in set(filter(None, [OWNER_ID, LOGGER_ID])):
        try:
            await bot.send_message(log_id, text)
        except Exception as e:
            logger.error(f"Failed to send log to {log_id}: {e}")

async def start_next_in_queue(chat_id):
    if not queues[chat_id]:
        return
    item = queues[chat_id].popleft()
    url = get_rtmp_url(chat_id)
    if not url:
        return
    msg = item["msg"]
    caption = item["caption"]
    thumb_url = item.get("thumbnail")
    try:
        if thumb_url:
            await msg.reply_photo(thumb_url, caption=caption)
        else:
            await msg.edit(caption)
    except Exception:
        await msg.edit(caption)
    stop_ffmpeg(chat_id)
    command = item["ffmpeg_cmd"]
    title = item.get("title", "Unknown")
    duration = item.get("duration", "Unknown")
    requester = item.get("requester", "Unknown")
    log_text = (
        f"🔴 [STREAM START]\n"
        f"👤 User: {requester}\n"
        f"🎶 Song: {title}\n"
        f"⏱️ Duration: {duration}\n"
        f"💬 Chat: {chat_id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    threading.Thread(target=run_ffmpeg, args=(chat_id, command, item.get("input_file"), lambda cid=chat_id: start_next_in_queue(cid))).start()

def enqueue(chat_id, item):
    queues[chat_id].append(item)

@bot.on_message(filters.command("start"))
async def hello(_, m):
    start_buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧾 Help & Commands", callback_data="commands")],
            [
                InlineKeyboardButton("🏨 Support", url="https://t.me/RadhaSprt"),
                InlineKeyboardButton("🧑‍💻 Updates", url="https://t.me/TheRadhaUpdate")
            ]
        ]
    )
    caption_text = f"""ʜᴇʏ @{m.from_user.username}

ɪ'ᴍ ᴛᴏᴊɪ ғᴜsʜɪɢᴜʀᴏ ғʀᴏᴍ ᴊᴜᴊᴜᴛsᴜ ᴋᴀɪsᴇɴ.  
ɪ'ᴍ ᴀ ʀᴛᴍᴘ ᴛᴇʟᴇɢʀᴀᴍ sᴛʀᴇᴀᴍɪɴɢ ʙᴏᴛ.  

ʙᴏᴛ ᴡᴀs ᴍᴀᴅᴇ ʙʏ @TheErenYeager"""

    log_text = (
        f"✅ [BOT STARTED]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)

    await m.reply_photo(
        photo="https://i.ibb.co/bM64YvKD/tmpe0qt1em.jpg",
        caption=caption_text,
        reply_markup=start_buttons
    )

@bot.on_callback_query(filters.regex("commands"))
def show_commands(_, query):
    commands_text = """**Available Commands:**

• /setkey   - Bind your RTMP stream key
• /play     - Reply with audio/video to stream (video+audio) [Queue Supported]
• /playaudio - Reply with audio/video to stream (audio only) [Queue Supported]
• /uplay    - Stream direct media file/link [Queue Supported]
• /ytplay   - Stream YouTube (video+audio) [Queue Supported]
• /ytaudio  - Stream YouTube (audio only) [Queue Supported]
• /stop     - Kill active stream
• /skip     - Skip current stream (if queue)
• /queue    - Show queue
• /ping     - Check bot latency
"""
    back_button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("« Back", callback_data="back")]]
    )
    query.message.edit_text(commands_text, reply_markup=back_button)

@bot.on_callback_query(filters.regex("back"))
def back_to_start(_, query):
    start_buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧾 Help & Commands", callback_data="commands")],
            [
                InlineKeyboardButton("🏨 Support", url="https://t.me/RadhaSprt"),
                InlineKeyboardButton("🧑‍💻 Updates", url="https://t.me/TheRadhaUpdate")
            ]
        ]
    )
    caption_text = f"""ʜᴇʏ @{query.from_user.username}

ɪ'ᴍ ᴛᴏᴊɪ ғᴜsʜɪɢᴜʀᴏ ғʀᴏᴍ ᴊᴜᴊᴜᴛsᴜ ᴋᴀɪsᴇɴ.  
ɪ'ᴍ ᴀ ʀᴛᴍᴘ ᴛᴇʟᴇɢʀᴀᴍ sᴛʀᴇᴀᴍɪɴɢ ʙᴏᴛ.  

ʙᴏᴛ ᴡᴀs ᴍᴀᴅᴇ ʙʏ @TheErenYeager"""
    query.message.edit_caption(
        caption=caption_text,
        reply_markup=start_buttons
    )
    query.message.edit_reply_markup(reply_markup=start_buttons)

@bot.on_message(filters.command("setkey"))
async def setkey(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /setkey <RTMP_KEY>")
    rtmp_keys[m.chat.id] = m.command[1]
    await m.reply("✅ RTMP key set.")

@bot.on_message(filters.command("ping"))
async def ping(_, m):
    start = time.perf_counter()
    reply = await m.reply("🏓 Pinging...")
    end = time.perf_counter()
    latency = (end - start) * 1000
    await reply.edit_text(f"🏓 Pong! `{int(latency)}ms`")

@bot.on_message(filters.command("stop"))
async def stop(_, m):
    stop_ffmpeg(m.chat.id)
    queues[m.chat.id].clear()
    await m.reply("🛑 Stream stopped and queue cleared.")
    log_text = (
        f"🛑 [STREAM STOPPED]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)

@bot.on_message(filters.command("skip"))
async def skip(_, m):
    stop_ffmpeg(m.chat.id)
    await m.reply("⏭️ Skipped current stream.")
    log_text = (
        f"⏭️ [STREAM SKIPPED]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("queue"))
async def show_queue(_, m):
    q = queues[m.chat.id]
    if not q:
        return await m.reply("Queue is empty.")
    text = "**Current Queue:**\n"
    for idx, item in enumerate(q, 1):
        text += f"{idx}. {item['title']} ({item['duration']})\n"
    await m.reply(text)

@bot.on_message(filters.command("play"))
async def play(_, m):
    if not m.reply_to_message or not (m.reply_to_message.audio or m.reply_to_message.voice or m.reply_to_message.video):
        return await m.reply("Reply with an audio, voice, or video file.")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗ Set an RTMP key first using /setkey.")
    msg = await m.reply("Downloading...")
    media = await m.reply_to_message.download()
    title = getattr(m.reply_to_message, "file_name", "Telegram Media")
    duration = format_duration(getattr(m.reply_to_message, "duration", 0))
    thumb_url = None
    if getattr(m.reply_to_message, "video", None) and m.reply_to_message.video.thumbs:
        thumb_file = await m.reply_to_message.video.thumbs[0].get_file()
        thumb_url = thumb_file.file_id
    caption = f"🎬 Queued: {title}\n⏱️ Duration: {duration}\n👤 Requested by: {m.from_user.mention}"
    item = {
        "title": title,
        "duration": duration,
        "caption": caption,
        "thumbnail": thumb_url,
        "msg": msg,
        "input_file": media,
        "ffmpeg_cmd": build_ffmpeg_video(media, url),
        "requester": f"@{m.from_user.username} (ID: {m.from_user.id})"
    }
    enqueue(m.chat.id, item)
    await msg.edit(f"✅ Added to queue: {title}")
    log_text = (
        f"🟢 [QUEUED]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"🎶 Song: {title}\n"
        f"⏱️ Duration: {duration}\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    if not ffmpeg_processes.get(m.chat.id):
        await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("playaudio"))
async def playaudio(_, m):
    if not m.reply_to_message or not (m.reply_to_message.audio or m.reply_to_message.voice or m.reply_to_message.video):
        return await m.reply("Reply with an audio, voice, or video file.")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗ Set an RTMP key first using /setkey.")
    msg = await m.reply("Downloading...")
    media = await m.reply_to_message.download()
    title = getattr(m.reply_to_message, "file_name", "Telegram Media")
    duration = format_duration(getattr(m.reply_to_message, "duration", 0))
    thumb_url = None
    if getattr(m.reply_to_message, "video", None) and m.reply_to_message.video.thumbs:
        thumb_file = await m.reply_to_message.video.thumbs[0].get_file()
        thumb_url = thumb_file.file_id
    caption = f"🎵 Queued (Audio): {title}\n⏱️ Duration: {duration}\n👤 Requested by: {m.from_user.mention}"
    item = {
        "title": title,
        "duration": duration,
        "caption": caption,
        "thumbnail": thumb_url,
        "msg": msg,
        "input_file": media,
        "ffmpeg_cmd": build_ffmpeg_audio(media, url),
        "requester": f"@{m.from_user.username} (ID: {m.from_user.id})"
    }
    enqueue(m.chat.id, item)
    await msg.edit(f"✅ Added to queue: {title}")
    log_text = (
        f"🟢 [QUEUED AUDIO]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"🎶 Song: {title}\n"
        f"⏱️ Duration: {duration}\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    if not ffmpeg_processes.get(m.chat.id):
        await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("uplay"))
async def uplay(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /uplay <direct_media_url>")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗ Set an RTMP key first using /setkey.")
    media_url = m.text.split(maxsplit=1)[1]
    title = "Direct URL"
    duration = "Unknown"
    caption = f"🎬 Queued from URL\n👤 Requested by: {m.from_user.mention}"
    msg = await m.reply("✅ Added to queue: Direct URL")
    item = {
        "title": title,
        "duration": duration,
        "caption": caption,
        "thumbnail": None,
        "msg": msg,
        "ffmpeg_cmd": build_ffmpeg_video(media_url, url),
        "requester": f"@{m.from_user.username} (ID: {m.from_user.id})"
    }
    enqueue(m.chat.id, item)
    log_text = (
        f"🟢 [QUEUED URL]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    if not ffmpeg_processes.get(m.chat.id):
        await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("ytplay"))
async def ytplay(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /ytplay <song or YouTube URL>")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗ Set an RTMP key first using /setkey.")
    query = m.text.split(maxsplit=1)[1]
    msg = await m.reply("🔍 Searching YouTube...")
    try:
        loop = asyncio.get_event_loop()
        filepath, info = await loop.run_in_executor(None, lambda: download_media(query, video=True))
        title = info.get("title", "Unknown")
        duration = format_duration(info.get("duration", 0))
        thumb_url = info.get("thumbnail")
    except Exception as e:
        return await msg.edit(f"❌ Failed: {e}")
    caption = f"🎬 Queued: {title}\n⏱️ Duration: {duration}\n👤 Requested by: {m.from_user.mention}"
    item = {
        "title": title,
        "duration": duration,
        "caption": caption,
        "thumbnail": thumb_url,
        "msg": msg,
        "input_file": filepath,
        "ffmpeg_cmd": build_ffmpeg_video(filepath, url),
        "requester": f"@{m.from_user.username} (ID: {m.from_user.id})"
    }
    enqueue(m.chat.id, item)
    await msg.edit(f"✅ Added to queue: {title}")
    log_text = (
        f"🟢 [QUEUED YOUTUBE]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"🎶 Song: {title}\n"
        f"⏱️ Duration: {duration}\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    if not ffmpeg_processes.get(m.chat.id):
        await start_next_in_queue(m.chat.id)

@bot.on_message(filters.command("ytaudio"))
async def ytaudio(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /ytaudio <song or YouTube URL>")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗ Set an RTMP key first using /setkey.")
    query = m.text.split(maxsplit=1)[1]
    msg = await m.reply("🔍 Searching YouTube...")
    try:
        loop = asyncio.get_event_loop()
        filepath, info = await loop.run_in_executor(None, lambda: download_media(query, video=False))
        title = info.get("title", "Unknown")
        duration = format_duration(info.get("duration", 0))
        thumb_url = info.get("thumbnail")
    except Exception as e:
        return await msg.edit(f"❌ Failed: {e}")
    caption = f"🎵 Queued (Audio): {title}\n⏱️ Duration: {duration}\n👤 Requested by: {m.from_user.mention}"
    item = {
        "title": title,
        "duration": duration,
        "caption": caption,
        "thumbnail": thumb_url,
        "msg": msg,
        "input_file": filepath,
        "ffmpeg_cmd": build_ffmpeg_audio(filepath, url),
        "requester": f"@{m.from_user.username} (ID: {m.from_user.id})"
    }
    enqueue(m.chat.id, item)
    await msg.edit(f"✅ Added to queue: {title}")
    log_text = (
        f"🟢 [QUEUED YOUTUBE AUDIO]\n"
        f"👤 User: @{m.from_user.username} (ID: {m.from_user.id})\n"
        f"🎶 Song: {title}\n"
        f"⏱️ Duration: {duration}\n"
        f"💬 Chat: {m.chat.id}\n"
        f"🕜 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    logger.info(log_text.replace('\n', ' | '))
    await send_log(log_text)
    if not ffmpeg_processes.get(m.chat.id):
        await start_next_in_queue(m.chat.id)

bot.run()
