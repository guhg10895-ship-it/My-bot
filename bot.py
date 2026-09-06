#!/usr/bin/env python3
# 🔓 GHOST Unlock Bot — AES-256 WinZip Support

import os
import sys
import time
import subprocess
import shutil
import tempfile
import re
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================
# ⚙️ CONFIG
# ============================================
BOT_TOKEN = "8940684766:AAFij8rh9ihggCOakDhofjTikQj8x8AeS3Q"
WORDLIST_PATH = "rockyou.txt"
MAX_FILE_SIZE = 45 * 1024 * 1024
TIMEOUT_CRACK = 300  # 5 minutes for AES

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# 📁 Helper Functions
# ============================================

def download_wordlist():
    if os.path.exists(WORDLIST_PATH):
        return True
    try:
        import requests
        url = "https://raw.githubusercontent.com/brannondorsey/naive-hashcat/master/rockyou.txt"
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(WORDLIST_PATH, 'wb') as f:
                f.write(r.content)
            return True
    except:
        pass
    # Fallback
    with open(WORDLIST_PATH, 'w') as f:
        words = ["password", "123456", "qwerty", "admin", "letmein", "welcome", "monkey", "dragon"]
        for w in words:
            f.write(w + "\n")
    return True

def is_password_protected(file_path):
    """Check if ZIP is AES-256 protected using 7z"""
    try:
        result = subprocess.run(
            ["7z", "t", file_path],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout + result.stderr
        if "Can not open encrypted archive" in output:
            return True
        if "Enter password" in output:
            return True
        if "AES-256" in output:
            return True
        return False
    except:
        return True  # Assume protected if can't read

def crack_password_zip_aes(file_path, wordlist):
    """
    Crack AES-256 WinZip using hashcat or john
    Falls back to 7z brute force
    """
    # Method 1: Try using john (most compatible)
    try:
        # Extract hash
        subprocess.run(
            f"zip2john '{file_path}' > hash.txt 2>/dev/null",
            shell=True, timeout=10
        )
        
        if os.path.exists("hash.txt") and os.path.getsize("hash.txt") > 100:
            # Crack with john
            result = subprocess.run(
                f"john --wordlist={wordlist} --format=zip hash.txt",
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_CRACK
            )
            
            # Get password
            show = subprocess.run(
                "john --show hash.txt | grep -o ':[^:]*$' | sed 's/://'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            password = show.stdout.strip()
            os.remove("hash.txt") if os.path.exists("hash.txt") else None
            if password:
                return password
    except Exception as e:
        print(f"[DEBUG] john error: {e}")
    
    # Method 2: Try hashcat (if installed)
    try:
        subprocess.run(
            f"zip2john '{file_path}' > hash.txt 2>/dev/null",
            shell=True, timeout=10
        )
        if os.path.exists("hash.txt") and os.path.getsize("hash.txt") > 100:
            # hashcat mode 13600 = WinZip AES-256
            result = subprocess.run(
                f"hashcat -m 13600 -a 0 hash.txt {wordlist} --force --potfile-disable 2>/dev/null",
                shell=True,
                timeout=TIMEOUT_CRACK
            )
            # Get password
            show = subprocess.run(
                "hashcat -m 13600 hash.txt --show --force 2>/dev/null | grep -o ':[^:]*$' | sed 's/://'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            password = show.stdout.strip()
            os.remove("hash.txt") if os.path.exists("hash.txt") else None
            if password:
                return password
    except Exception as e:
        print(f"[DEBUG] hashcat error: {e}")
    
    # Method 3: Brute force with 7z (slow but works)
    try:
        with open(wordlist, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                pwd = line.strip()
                if not pwd:
                    continue
                result = subprocess.run(
                    ["7z", "t", f"-p{pwd}", file_path],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    return pwd
    except:
        pass
    
    return None

def extract_file(file_path, password, file_type):
    """Extract using 7z (handles AES-256)"""
    extract_dir = tempfile.mkdtemp()
    try:
        if file_type == 'zip':
            cmd = ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if "Everything is Ok" in result.stdout.decode() or result.returncode == 0:
                return extract_dir
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None
    except:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None

def get_file_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.zip':
        return 'zip'
    elif ext == '.rar':
        return 'rar'
    elif ext == '.7z':
        return '7z'
    return None

# ============================================
# 📋 Telegram Commands
# ============================================

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📖 Help", callback_data="help"))
    bot.reply_to(
        msg,
        "🔓 **GHOST Unlock Bot v3.0 — AES-256 Support**\n\n"
        "Send me a password-protected **ZIP** file.\n"
        "✅ Supports **WinZip AES-256 (Method 99)**\n"
        "⚠️ For **educational purposes** only!\n\n"
        "⏱️ Cracking may take 5+ minutes for AES.",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(content_types=['document'])
def handle_file(msg):
    chat_id = msg.chat.id
    file_name = msg.document.file_name
    file_size = msg.document.file_size

    if file_size > MAX_FILE_SIZE:
        bot.reply_to(msg, f"❌ File too large! Max: {MAX_FILE_SIZE//1024//1024} MB")
        return

    if not file_name.lower().endswith('.zip'):
        bot.reply_to(msg, "❌ Please send a **ZIP** file only.")
        return

    bot.reply_to(msg, f"📥 Downloading `{file_name}`...", parse_mode='Markdown')

    # Download
    file_info = bot.get_file(msg.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(downloaded)

    # Check protection
    bot.reply_to(msg, "🔍 Checking file (AES-256 detection)...")
    if not is_password_protected(file_path):
        bot.reply_to(msg, "ℹ️ This file is **NOT** password protected!", parse_mode='Markdown')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, "🔐 File is AES-256 encrypted! Cracking with dictionary attack...\n⏱️ This may take 5+ minutes.")

    # Crack
    password = crack_password_zip_aes(file_path, WORDLIST_PATH)

    if not password:
        bot.reply_to(
            msg,
            "❌ Password **NOT FOUND** in wordlist.\n\n"
            "💡 **Suggestions:**\n"
            "- Use a stronger wordlist (rockyou.txt is limited).\n"
            "- Try brute-force (very slow for AES-256).\n"
            "- Consider using hashcat with GPU.",
            parse_mode='Markdown'
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, f"✅ Password found: `{password}`\n🔓 Extracting files...", parse_mode='Markdown')

    # Extract
    extract_dir = extract_file(file_path, password, 'zip')
    if not extract_dir:
        bot.reply_to(msg, "❌ Failed to extract files!")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    # Create output zip
    output_zip = os.path.join(temp_dir, "unlocked_files.zip")
    shutil.make_archive(output_zip.replace('.zip', ''), 'zip', extract_dir)

    # Send back
    with open(output_zip, 'rb') as f:
        bot.send_document(
            chat_id,
            f,
            caption=f"✅ **Unlocked!**\n\n"
                    f"🔑 Password: `{password}`\n"
                    f"📁 Original: `{file_name}`\n"
                    f"🔐 WinZip AES-256 cracked successfully!",
            parse_mode='Markdown'
        )

    shutil.rmtree(temp_dir, ignore_errors=True)
    bot.send_message(chat_id, "🧹 Cleanup done!")

# ============================================
# 🎛️ Callback Handler
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "help":
        bot.answer_callback_query(call.id, "📖 Help sent!")
        bot.edit_message_text(
            "📖 **AES-256 Crack Guide**\n\n"
            "1️⃣ Send a WinZip AES-256 encrypted ZIP file.\n"
            "2️⃣ Wait 5+ minutes for cracking.\n"
            "3️⃣ If password is in wordlist, you'll get your files.\n\n"
            "⚡ **Supported:**\n"
            "- WinZip AES-256 (Method 99)\n"
            "- ZipCrypto (legacy)\n\n"
            "📦 Max file size: 45 MB",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# ============================================
# 🚀 Start
# ============================================
if __name__ == "__main__":
    print("🔥 GHOST Unlock Bot v3.0 (AES-256) Starting...")
    download_wordlist()
    print("✅ Bot is ready!")
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(10)
