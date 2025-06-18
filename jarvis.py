# jarvis.py (Final Version - No audio error, deletable by anyone, human-like replies)

import os
import random
import threading
from flask import Flask
import httpx
import discord
from discord.ext import commands, tasks
from openai import OpenAI

# --- ENV VARS ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.getenv("PORT", 5000))

if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN not found.")
    exit(1)

# --- Fallback Replies ---
def load_lines(file):
    with open(file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

fallback_flirty = load_lines("fallback_flirty.txt")
fallback_funny = load_lines("fallback_funny.txt")
fallback_angry = load_lines("fallback_angry.txt")
fallback_roast = load_lines("fallback_roast.txt")
fallback_normal = load_lines("fallback_normal.txt")

all_fallbacks = fallback_flirty + fallback_funny + fallback_angry + fallback_roast + fallback_normal

# --- OpenAI ---
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# --- Flask App ---
app = Flask(__name__)

@app.route("/")
def home():
    return "JARVIS is alive ✅"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# --- Bot Setup ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

enabled_channels = set()

@bot.event
async def on_ready():
    print(f"✅ JARVIS is online as {bot.user}")
    auto_talk.start()

# --- Generate AI Reply ---
async def get_ai_reply(prompt):
    try:
        if openai_client:
            res = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a funny, flirty, human-like chatbot that talks like a best friend."},
                    {"role": "user", "content": prompt}
                ]
            )
            return res.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI failed:", e)

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "model": "openchat/openchat-7b",
            "messages": [
                {"role": "system", "content": "You are a funny, flirty, human-like chatbot that talks like a best friend."},
                {"role": "user", "content": prompt}
            ]
        }
        async with httpx.AsyncClient() as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("OpenRouter failed:", e)
        return random.choice(all_fallbacks)

# --- Auto Talk Every 1.5 Hours ---
@tasks.loop(seconds=5400)
async def auto_talk():
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages and channel.id in enabled_channels:
                members = [m for m in guild.members if not m.bot]
                if members:
                    name = random.choice(members).display_name
                    prompt = f"Say something fun or random to {name}, like a friend."
                    msg = await get_ai_reply(prompt)
                    await channel.send(f"Hey {name} 😜\n{msg}")
                break

# --- Message Event Handler ---
@bot.event
async def on_message(message):
    if message.author == bot.user or not message.guild:
        return

    content = message.content.lower()
    channel_id = message.channel.id
    mentioned = bot.user in message.mentions

    # --- On/Off toggle ---
    if content == "!jarvis on":
        enabled_channels.add(channel_id)
        await message.channel.send("🟢 JARVIS is now active in this channel!")
        return

    if content == "!jarvis off":
        enabled_channels.discard(channel_id)
        await message.channel.send("🔴 JARVIS is now inactive in this channel!")
        return

    if channel_id not in enabled_channels:
        return

    # --- Jarvis Delete by Anyone ---
    if content == "jarvis delete":
        try:
            deleted = await message.channel.purge(limit=100)
            await message.channel.send(f"🧹 {len(deleted)} messages cleaned by {message.author.mention}")
        except discord.Forbidden:
            await message.channel.send("❌ I need `Manage Messages` permission to delete messages.")

    # --- Natural chat if mentioned or casual words ---
    trigger_words = ["hi", "hello", "bored", "single", "miss me", "talk", "love", "lonely"]
    if mentioned or any(word in content for word in trigger_words):
        if mentioned or random.random() < 0.4:
            prompt = f"{message.author.display_name} said: {message.content}. Reply casually like a friend."
            reply = await get_ai_reply(prompt)
            await message.channel.send(reply)

    await bot.process_commands(message)

# --- Run Everything ---
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(TOKEN)
