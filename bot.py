#!/usr/bin/env python3
# 🔓 GHOST Unlock Bot v5.0 — hashcat + john + 7z

import os
import sys
import time
import subprocess
import shutil
import tempfile
import re
import zipfile
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================
# ⚙️ CONFIG
# ============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8940684766:AAFij8rh9ihggCOakDhofjTikQj8x8AeS3Q")
WORDLIST_PATH = "rockyou.txt"
MAX_FILE_SIZE = 45 * 1024 * 1024
TIMEOUT_CRACK = 300  # 5 minutes

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# 📁 Helper Functions
# ============================================

def download_wordlist():
    """Download rockyou.txt"""
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
    return False

def is_password_protected(file_path):
    """Check if file is password protected using 7z"""
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
        if "Everything is Ok" in output and "Password" not in output:
            return False
    except:
        pass
    return True

def crack_password_zip(file_path, wordlist):
    """
    Multi-method ZIP cracker:
    1. hashcat (best for AES-256)
    2. john (fallback)
    3. 7z brute force (last resort)
    """
    
    # ===== METHOD 1: hashcat =====
    print("[DEBUG] Method 1: hashcat")
    try:
        # Extract hash using zip2john (if available)
        hash_file = "hash.txt"
        subprocess.run(
            f"zip2john '{file_path}' > {hash_file} 2>/dev/null",
            shell=True, timeout=10
        )
        
        if os.path.exists(hash_file) and os.path.getsize(hash_file) > 50:
            # hashcat mode 13600 = WinZip AES-256
            # mode 17200 = PKZIP (legacy)
            cmd = f"hashcat -m 13600 -a 0 {hash_file} {wordlist} --force --potfile-disable 2>/dev/null"
            result = subprocess.run(
                cmd,
                shell=True,
                timeout=TIMEOUT_CRACK
            )
            print(f"[DEBUG] hashcat returncode: {result.returncode}")
            
            # Get password
            show = subprocess.run(
                f"hashcat -m 13600 {hash_file} --show --force 2>/dev/null | grep -o ':[^:]*$' | sed 's/://'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            password = show.stdout.strip()
            os.remove(hash_file) if os.path.exists(hash_file) else None
            if password:
                print(f"[DEBUG] hashcat found: {password}")
                return password
        os.remove(hash_file) if os.path.exists(hash_file) else None
    except subprocess.TimeoutExpired:
        print("[DEBUG] hashcat: TIMEOUT")
    except Exception as e:
        print(f"[DEBUG] hashcat error: {e}")

    # ===== METHOD 2: john =====
    print("[DEBUG] Method 2: john")
    try:
        # john with --format=zip
        cmd = f"john --wordlist={wordlist} --format=zip {file_path}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_CRACK
        )
        print(f"[DEBUG] john returncode: {result.returncode}")
        
        # Get password
        show = subprocess.run(
            f"john --show {file_path} | grep -o ':[^:]*$' | sed 's/://'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        password = show.stdout.strip()
        if password:
            print(f"[DEBUG] john found: {password}")
            return password
    except subprocess.TimeoutExpired:
        print("[DEBUG] john: TIMEOUT")
    except Exception as e:
        print(f"[DEBUG] john error: {e}")

    # ===== METHOD 3: 7z brute force (slow) =====
    print("[DEBUG] Method 3: 7z brute force")
    try:
        with open(wordlist, 'r', encoding='utf-8', errors='ignore') as f:
            count = 0
            for line in f:
                pwd = line.strip()
                if not pwd:
                    continue
                count += 1
                if count % 50 == 0:
                    print(f"[DEBUG] 7z tried: {count}")
                result = subprocess.run(
                    ["7z", "t", f"-p{pwd}", file_path],
                    capture_output=True,
                    timeout=3
                )
                if result.returncode == 0:
                    print(f"[DEBUG] 7z found: {pwd}")
                    return pwd
    except Exception as e:
        print(f"[DEBUG] 7z brute error: {e}")

    return None  # No password found

def extract_file(file_path, password):
    """Extract ZIP using 7z"""
    extract_dir = tempfile.mkdtemp()
    try:
        cmd = ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if "Everything is Ok" in result.stdout or result.returncode == 0:
            return extract_dir
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None
    except:
        shutil.rmtree(extract_dir, ignore_errors=True)
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
        "🔓 **GHOST Unlock Bot v5.0**\n\n"
        "Send me a password-protected **ZIP** file.\n"
        "✅ Supports **WinZip AES-256**\n"
        "⚡ Multi-method: hashcat → john → 7z\n"
        "⚠️ For **educational purposes** only!\n\n"
        "⏱️ Cracking may take 5+ minutes.",
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
    bot.reply_to(msg, "🔍 Checking file...")
    if not is_password_protected(file_path):
        bot.reply_to(msg, "ℹ️ File is **NOT** password protected!", parse_mode='Markdown')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, "🔐 Cracking with multi-method attack...\n⏱️ May take 5+ minutes.", parse_mode='Markdown')

    # Crack
    password = crack_password_zip(file_path, WORDLIST_PATH)

    if not password:
        bot.reply_to(
            msg,
            "❌ Password **NOT FOUND** using any method.\n\n"
            "💡 **Suggestions:**\n"
            "1. Use a **stronger wordlist** (e.g., `rockyou.txt` full version)\n"
            "2. Try **brute-force** with hashcat (requires GPU)\n"
            "3. If this is your file, try to **remember** the password.\n"
            "4. The password might be **too complex** (long, special chars).",
            parse_mode='Markdown'
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, f"✅ Password found: `{password}`\n🔓 Extracting...", parse_mode='Markdown')

    # Extract
    extract_dir = extract_file(file_path, password)
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
                    f"📦 Files extracted successfully.\n\n"
                    f"⚡ Method: hashcat / john / 7z",
            parse_mode='Markdown'
        )

    shutil.rmtree(temp_dir, ignore_errors=True)
    bot.send_message(chat_id, "🧹 Cleanup done! Send another file to crack more.")

# ============================================
# 🎛️ Callback Handler
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "help":
        bot.answer_callback_query(call.id, "📖 Help sent!")
        bot.edit_message_text(
            "📖 **How to use:**\n\n"
            "1️⃣ Send a password-protected ZIP file.\n"
            "2️⃣ Bot will try hashcat → john → 7z.\n"
            "3️⃣ If password found, you'll get your files.\n\n"
            "⚡ Supports **WinZip AES-256**.\n"
            "📦 Max file size: 45 MB\n"
            "⏱️ Timeout: 5 minutes",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# ============================================
# 🚀 Start
# ============================================
if __name__ == "__main__":
    print("🔥 GHOST Unlock Bot v5.0 Starting...")
    download_wordlist()
    print("✅ Bot is ready!")
    print("📩 Waiting for files...")
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except KeyboardInterrupt:
            print("\n⏹️ Bot stopped by user.")
            break
        except Exception as e:
            print(f"❌ Polling error: {e}")
            time.sleep(10)
