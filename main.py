import os
import sys
import config
import time
import threading
import subprocess
import logging
import yt_dlp
from queue import Queue
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot Initialization
bot = Client(
    "TojiFushiguro",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Globals
rtmp_keys = {}
ffmpeg_processes = {}
song_queue = Queue()
current_track = None

# YouTube DL options
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
    'outtmpl': '%(title)s.%(ext)s',
    'quiet': True,
    'noplaylist': True,
    'default_search': 'ytsearch1',
    'cookiefile': 'cookies.txt'
}

# Utilities
def format_duration(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}:{mins:02}:{secs:02}" if hours else f"{mins}:{secs:02}"

def get_rtmp_url(chat_id):
    key = rtmp_keys.get(chat_id)
    return config.DEFAULT_RTMP_URL + key if key else None

def stop_ffmpeg(chat_id):
    process = ffmpeg_processes.get(chat_id)
    if process:
        process.terminate()
        process.wait()
        ffmpeg_processes[chat_id] = None

def run_ffmpeg(chat_id, command):
    try:
        ffmpeg_processes[chat_id] = subprocess.Popen(command)
        ffmpeg_processes[chat_id].wait()
    except Exception as e:
        logging.error(f"FFmpeg error: {e}")
    finally:
        ffmpeg_processes[chat_id] = None

def download_video(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info:
            info = info['entries'][0]
        filename = ydl.prepare_filename(info)
        return os.path.splitext(filename)[0] + ".mp3", info

# Commands

@bot.on_message(filters.command("start"))
async def start(_, m):
    text = (
        "<b>Toji Fushiguro ✦ RTMP Streamer</b>\n\n"
        "Unleash raw power with seamless RTMP streaming, inspired by the <i>Sorcerer Killer</i> himself.\n\n"
        "<b>⚔️ Commands:</b>\n"
        "• /setkey <rtmp_key> - Bind your RTMP stream key\n"
        "• /play - Reply with audio/video to stream\n"
        "• /ytplay <query/link> - Stream directly from YouTube\n"
        "• /ping - Check active stream status\n"
    )

    await m.reply(text, disable_web_page_preview=True)

@bot.on_message(filters.command("ping"))
async def ping(_, m):
    start = time.perf_counter()
    reply = await m.reply("\ud83c\udfd3 Pinging...")
    end = time.perf_counter()
    latency = (end - start) * 1000
    await reply.edit_text(f"\ud83c\udfd3 Pong! `{int(latency)}ms`")

@bot.on_message(filters.command("setkey"))
async def setkey(_, m):
    if len(m.command) < 2:
        return await m.reply("Usage: /setkey <RTMP_KEY>")
    rtmp_keys[m.chat.id] = m.command[1]
    await m.reply("✅ RTMP key set.")

@bot.on_message(filters.command("play"))
async def play(_, m):
    if not m.reply_to_message or not (m.reply_to_message.audio or m.reply_to_message.voice or m.reply_to_message.video):
        return await m.reply("Reply to an audio, voice, or video file to stream.")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗️ Set an RTMP key first using /setkey.")
    msg = await m.reply("**Downloading...**")
    media = await m.reply_to_message.download()
    await msg.edit("**Starting stream...**")
    stop_ffmpeg(m.chat.id)
    command = ["ffmpeg", "-re", "-i", media, "-c:v", "libx264", "-preset", "fast",
               "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p",
               "-g", "25", "-keyint_min", "25", "-c:a", "aac", "-b:a", "96k",
               "-ac", "2", "-ar", "44100", "-f", "flv", url]
    threading.Thread(target=run_ffmpeg, args=(m.chat.id, command)).start()

@bot.on_message(filters.command("uplay"))
async def uplay(_, m):
    if len(m.command) < 2:
        return await m.reply("Send a direct media URL.")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗️ Set an RTMP key first using /setkey.")
    media_url = m.text.split(maxsplit=1)[1]
    await m.reply("Streaming from URL...")
    stop_ffmpeg(m.chat.id)
    command = ["ffmpeg", "-re", "-i", media_url, "-c:v", "libx264", "-preset", "fast",
               "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p",
               "-g", "25", "-keyint_min", "25", "-c:a", "aac", "-b:a", "96k",
               "-ac", "2", "-ar", "44100", "-f", "flv", url]
    threading.Thread(target=run_ffmpeg, args=(m.chat.id, command)).start()

@bot.on_message(filters.command("ytplay"))
async def ytplay(_, m):
    if len(m.command) < 2:
        return await m.reply("Send a YouTube song name or URL.")
    url = get_rtmp_url(m.chat.id)
    if not url:
        return await m.reply("❗️ Set an RTMP key first using /setkey.")
    query = m.text.split(maxsplit=1)[1]
    msg = await m.reply("🔍 Searching YouTube...")
    try:
        filepath, info = download_video(query)
        title = info.get("title", "Unknown")
        duration = info.get("duration")
        duration = format_duration(duration) if duration else "Unknown"
    except Exception as e:
        return await msg.edit(f"❌ Failed to download: {e}")
    caption = f"🎵 Now Playing: {title}\n⏱️ Duration: {duration}\n👤 Requested by: {m.from_user.mention}"
    await msg.edit(caption)
    stop_ffmpeg(m.chat.id)
    command = ["ffmpeg", "-re", "-i", filepath, "-c:v", "libx264", "-preset", "fast",
               "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p",
               "-g", "25", "-keyint_min", "25", "-c:a", "aac", "-b:a", "96k",
               "-ac", "2", "-ar", "44100", "-f", "flv", url]
    threading.Thread(target=run_ffmpeg, args=(m.chat.id, command)).start()

# Run bot
bot.run()
