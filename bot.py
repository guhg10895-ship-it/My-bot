#!/usr/bin/env python3
# 🔓 GHOST Unlock Bot — Telegram Bot untuk membuka file berpassword
# Dibuat oleh GHOST | Untuk tujuan edukasi dan file sendiri!

import os
import sys
import time
import subprocess
import shutil
import zipfile
import rarfile
import py7zr
import tempfile
import re
from pathlib import Path
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================
# ⚙️ CONFIG — Token langsung di sini
# ============================================
BOT_TOKEN = "8940684766:AAFij8rh9ihggCOakDhofjTikQj8x8AeS3Q"
WORDLIST_PATH = "rockyou.txt"  # Akan didownload otomatis
MAX_FILE_SIZE = 45 * 1024 * 1024  # 45 MB (Telegram limit 50 MB)
TIMEOUT_CRACK = 180  # 3 menit per file

# Inisialisasi Bot
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# 📁 Helper Functions
# ============================================

def download_wordlist():
    """Download rockyou.txt jika belum ada"""
    if os.path.exists(WORDLIST_PATH):
        return True
    print("📥 Downloading wordlist rockyou.txt...")
    try:
        # Dari GitHub (smaller version)
        import requests
        url = "https://raw.githubusercontent.com/brannondorsey/naive-hashcat/master/rockyou.txt"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            with open(WORDLIST_PATH, 'wb') as f:
                f.write(response.content)
            print("✅ Wordlist downloaded!")
            return True
    except:
        pass
    
    # Fallback: buat wordlist minimal
    print("⚠️ Creating minimal wordlist...")
    with open(WORDLIST_PATH, 'w') as f:
        words = [
            "password", "123456", "123456789", "qwerty", "abc123",
            "admin", "letmein", "welcome", "monkey", "dragon",
            "master", "sunshine", "iloveyou", "princess", "rockyou",
            "12345", "12345678", "abc123", "password1", "admin123"
        ]
        for w in words:
            f.write(w + "\n")
    return True

def get_file_type(file_path):
    """Deteksi jenis file berdasarkan ekstensi"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.zip':
        return 'zip'
    elif ext == '.rar':
        return 'rar'
    elif ext == '.7z':
        return '7z'
    else:
        return None

def is_password_protected(file_path):
    """Cek apakah file benar-benar diproteksi password"""
    file_type = get_file_type(file_path)
    if file_type == 'zip':
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Coba baca daftar file tanpa password
                zf.namelist()
                return False  # Tidak ada password
        except RuntimeError:
            return True  # Ada password
        except:
            return True
    elif file_type == 'rar':
        try:
            with rarfile.RarFile(file_path) as rf:
                rf.namelist()
                return False
        except:
            return True
    elif file_type == '7z':
        try:
            with py7zr.SevenZipFile(file_path, 'r') as sz:
                sz.getnames()
                return False
        except:
            return True
    return False

def crack_password_zip(file_path, wordlist):
    """Crack ZIP password dengan fcrackzip"""
    try:
        cmd = f"fcrackzip -u -D -p {wordlist} {file_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT_CRACK)
        output = result.stdout + result.stderr
        
        # Cari password
        match = re.search(r'PASSWORD FOUND:\s*(\S+)', output)
        if match:
            return match.group(1)
        
        # Format alternatif
        for line in output.split('\n'):
            if 'PASSWORD FOUND' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    return parts[-1].strip()
        return None
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception:
        return None

def crack_password_rar(file_path, wordlist):
    """Crack RAR password dengan rar2john + john"""
    try:
        # Extract hash
        cmd_hash = f"rar2john '{file_path}' > hash.txt 2>/dev/null"
        subprocess.run(cmd_hash, shell=True, timeout=10)
        
        if not os.path.exists("hash.txt"):
            return None
        
        # Crack with john
        cmd_crack = f"john --wordlist={wordlist} --format=rar hash.txt"
        result = subprocess.run(cmd_crack, shell=True, capture_output=True, text=True, timeout=TIMEOUT_CRACK)
        
        # Get password
        cmd_show = "john --show hash.txt | grep -o ':[^:]*$' | sed 's/://'"
        result2 = subprocess.run(cmd_show, shell=True, capture_output=True, text=True, timeout=5)
        password = result2.stdout.strip()
        
        os.remove("hash.txt") if os.path.exists("hash.txt") else None
        return password if password else None
    except:
        return None

def crack_password_7z(file_path, wordlist):
    """Crack 7z password dengan 7z2john + john"""
    try:
        # Extract hash
        cmd_hash = f"7z2john '{file_path}' > hash.txt 2>/dev/null"
        subprocess.run(cmd_hash, shell=True, timeout=10)
        
        if not os.path.exists("hash.txt"):
            return None
        
        # Crack with john
        cmd_crack = f"john --wordlist={wordlist} --format=7z hash.txt"
        subprocess.run(cmd_crack, shell=True, timeout=TIMEOUT_CRACK)
        
        # Get password
        cmd_show = "john --show hash.txt | grep -o ':[^:]*$' | sed 's/://'"
        result = subprocess.run(cmd_show, shell=True, capture_output=True, text=True, timeout=5)
        password = result.stdout.strip()
        
        os.remove("hash.txt") if os.path.exists("hash.txt") else None
        return password if password else None
    except:
        return None

def extract_file(file_path, password, file_type):
    """Ekstrak file dengan password"""
    extract_dir = tempfile.mkdtemp()
    
    try:
        if file_type == 'zip':
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.extractall(extract_dir, pwd=password.encode())
        elif file_type == 'rar':
            with rarfile.RarFile(file_path, 'r') as rf:
                rf.extractall(extract_dir, pwd=password)
        elif file_type == '7z':
            with py7zr.SevenZipFile(file_path, 'r', password=password) as sz:
                sz.extractall(extract_dir)
        return extract_dir
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None

def create_zip_from_dir(dir_path):
    """Buat ZIP dari direktori"""
    zip_path = tempfile.mktemp(suffix=".zip")
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', dir_path)
    return zip_path

def clean_filename(name):
    """Bersihkan nama file untuk aman"""
    return "".join(c for c in name if c.isalnum() or c in "._- ")

# ============================================
# 📋 Telegram Commands
# ============================================

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📖 Help", callback_data="help"))
    
    bot.reply_to(
        msg,
        "🔓 **GHOST Unlock Bot**\n\n"
        "Send me a password-protected **ZIP / RAR / 7z** file.\n"
        "I will try to crack the password using dictionary attack.\n\n"
        "⚠️ For **educational purposes** and your **own files** only!\n"
        "📦 Max file size: 45 MB\n"
        "⏱️ Processing time: ~3 minutes\n\n"
        "Use /help for more info.",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(
        msg,
        "📖 **How to use:**\n\n"
        "1️⃣ Send a **ZIP, RAR, or 7z** file that is password-protected.\n"
        "2️⃣ Wait while I try to crack the password using `rockyou.txt` wordlist.\n"
        "3️⃣ If found, I will extract and send you the unlocked files.\n\n"
        "⚠️ **Limitations:**\n"
        "- Only works with **weak/common passwords**.\n"
        "- Max file size: **45 MB**.\n"
        "- Processing time: **~3 minutes**.\n\n"
        "💡 For strong passwords, try a custom wordlist or brute-force.",
        parse_mode='Markdown'
    )

@bot.message_handler(content_types=['document'])
def handle_file(msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    file_name = msg.document.file_name
    file_size = msg.document.file_size

    # Check file size
    if file_size > MAX_FILE_SIZE:
        bot.reply_to(msg, f"❌ File too large! Max size: {MAX_FILE_SIZE//1024//1024} MB")
        return

    # Check extension
    if not any(file_name.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z']):
        bot.reply_to(msg, "❌ Please send **ZIP, RAR, or 7z** file only.")
        return

    bot.reply_to(msg, f"📥 Downloading `{file_name}`...", parse_mode='Markdown')

    # Download file
    file_info = bot.get_file(msg.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    # Save to temp
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(downloaded)

    # Check if really password protected
    bot.reply_to(msg, "🔍 Checking file type and protection...")
    file_type = get_file_type(file_path)
    
    if not file_type:
        bot.reply_to(msg, "❌ Unsupported file type!")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    if not is_password_protected(file_path):
        bot.reply_to(msg, "ℹ️ This file is **NOT** password protected!\nSend the unlocked file directly.", parse_mode='Markdown')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, f"🔐 File is password protected! Starting cracking with dictionary attack...\n⏱️ This may take up to 3 minutes.")

    # Crack password
    password = None
    if file_type == 'zip':
        password = crack_password_zip(file_path, WORDLIST_PATH)
    elif file_type == 'rar':
        password = crack_password_rar(file_path, WORDLIST_PATH)
    elif file_type == '7z':
        password = crack_password_7z(file_path, WORDLIST_PATH)

    if not password:
        bot.reply_to(
            msg,
            "❌ Password **NOT FOUND** in `rockyou.txt` wordlist.\n\n"
            "💡 Suggestions:\n"
            "- Use a stronger wordlist (e.g., `rockyou.txt` full version)\n"
            "- Try brute-force (but it's slow)\n"
            "- Check if the password is in the list below:\n"
            "  `password, 123456, qwerty, admin, letmein`",
            parse_mode='Markdown'
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    if password == "TIMEOUT":
        bot.reply_to(msg, "⏰ Cracking timed out after 3 minutes!\nPassword might be too strong.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, f"✅ Password found: `{password}`\n🔓 Extracting files...", parse_mode='Markdown')

    # Extract files
    extract_dir = extract_file(file_path, password, file_type)
    if not extract_dir:
        bot.reply_to(msg, "❌ Failed to extract files! The password might be incorrect.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    # Zip extracted files
    output_zip = os.path.join(temp_dir, "unlocked_files.zip")
    shutil.make_archive(output_zip.replace('.zip', ''), 'zip', extract_dir)

    # Send back
    with open(output_zip, 'rb') as f:
        bot.send_document(
            chat_id,
            f,
            caption=f"✅ **Unlocked!**\n\n"
                    f"🔑 Password: `{password}`\n"
                    f"📁 Original file: `{file_name}`\n"
                    f"📦 Files extracted and zipped for you.",
            parse_mode='Markdown'
        )

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    bot.send_message(chat_id, "🧹 Cleanup done! Send another file to crack more.")

# ============================================
# 🎛️ Callback Handlers
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "help":
        bot.answer_callback_query(call.id, "📖 Help sent!")
        bot.edit_message_text(
            "📖 **How to use:**\n\n"
            "1️⃣ Send a **ZIP, RAR, or 7z** file that is password-protected.\n"
            "2️⃣ Wait while I try to crack the password using `rockyou.txt` wordlist.\n"
            "3️⃣ If found, I will extract and send you the unlocked files.\n\n"
            "⚠️ **Limitations:**\n"
            "- Only works with **weak/common passwords**.\n"
            "- Max file size: **45 MB**.\n"
            "- Processing time: **~3 minutes**.\n\n"
            "💡 For strong passwords, try a custom wordlist or brute-force.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# ============================================
# 🚀 Start
# ============================================
if __name__ == "__main__":
    print("🔥 GHOST Unlock Bot Starting...")
    print(f"🤖 Token: {BOT_TOKEN[:10]}...")
    
    # Download wordlist
    if not download_wordlist():
        print("⚠️ Wordlist download failed, using minimal wordlist.")
    
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
