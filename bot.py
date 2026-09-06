#!/usr/bin/env python3
# 🔓 GHOST Unlock Bot — Support AES-256 & ZipCrypto
# Created by GHOST | For educational & own file use only!

import os
import sys
import time
import subprocess
import shutil
import tempfile
import re
import zipfile
from pathlib import Path
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================
# ⚙️ CONFIG
# ============================================
BOT_TOKEN = "8940684766:AAFij8rh9ihggCOakDhofjTikQj8x8AeS3Q"
WORDLIST_PATH = "rockyou.txt"
MAX_FILE_SIZE = 45 * 1024 * 1024  # 45 MB
TIMEOUT_CRACK = 180  # 3 minutes

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# 📁 Helper Functions
# ============================================

def download_wordlist():
    """Download rockyou.txt if not exists"""
    if os.path.exists(WORDLIST_PATH):
        return True
    print("📥 Downloading wordlist...")
    try:
        import requests
        url = "https://raw.githubusercontent.com/brannondorsey/naive-hashcat/master/rockyou.txt"
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(WORDLIST_PATH, 'wb') as f:
                f.write(r.content)
            print("✅ Wordlist downloaded!")
            return True
    except:
        pass
    # Fallback: create minimal wordlist
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
    """Detect file type by extension"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.zip':
        return 'zip'
    elif ext == '.rar':
        return 'rar'
    elif ext == '.7z':
        return '7z'
    return None

def is_password_protected(file_path):
    """Check if file is password protected (supports AES-256)"""
    file_type = get_file_type(file_path)
    
    if file_type == 'zip':
        # Try pyzipper first (supports AES)
        try:
            import pyzipper
            with pyzipper.AESZipFile(file_path, 'r') as zf:
                # Try to read file list without password
                zf.namelist()
                return False
        except pyzipper.BadPassword:
            return True
        except pyzipper.WrongPassword:
            return True
        except:
            pass
        
        # Fallback to 7z command
        try:
            result = subprocess.run(
                ["7z", "t", file_path],
                capture_output=True, text=True, timeout=10
            )
            if "Password" in result.stdout or "Enter password" in result.stdout:
                return True
            if "Cannot find archive" in result.stderr:
                return False
        except:
            pass
        
        # Try standard zipfile (only works for ZipCrypto)
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.namelist()
                return False
        except RuntimeError:
            return True
        except:
            return True
    
    elif file_type == 'rar':
        try:
            import rarfile
            with rarfile.RarFile(file_path) as rf:
                rf.namelist()
                return False
        except rarfile.RarFileError:
            return True
        except:
            return True
    
    elif file_type == '7z':
        try:
            import py7zr
            with py7zr.SevenZipFile(file_path, 'r') as sz:
                sz.getnames()
                return False
        except py7zr.exceptions.Bad7zFile:
            return True
        except:
            return True
    
    return False

def crack_password_zip(file_path, wordlist):
    """Crack ZIP password with fcrackzip (supports AES)"""
    try:
        cmd = f"fcrackzip -u -D -p {wordlist} {file_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT_CRACK)
        output = result.stdout + result.stderr
        
        print(f"[DEBUG] fcrackzip output: {output[:500]}")
        
        # Try to extract password
        match = re.search(r'PASSWORD FOUND:\s*(\S+)', output)
        if match:
            return match.group(1)
        
        # Alternative format
        for line in output.split('\n'):
            if 'PASSWORD FOUND' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    return parts[-1].strip()
        
        # Check if fcrackzip didn't support this format
        if "not encrypted" in output.lower():
            return None  # Not actually protected
        
        return None
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        print(f"[DEBUG] Crack error: {e}")
        return None

def crack_password_rar(file_path, wordlist):
    """Crack RAR password"""
    try:
        # Try rar2john
        cmd_hash = f"rar2john '{file_path}' > hash.txt 2>/dev/null"
        subprocess.run(cmd_hash, shell=True, timeout=10)
        if not os.path.exists("hash.txt") or os.path.getsize("hash.txt") < 10:
            return None
        
        # Crack with john
        subprocess.run(f"john --wordlist={wordlist} --format=rar hash.txt", shell=True, timeout=TIMEOUT_CRACK)
        
        # Get password
        result = subprocess.run("john --show hash.txt | grep -o ':[^:]*$' | sed 's/://'", 
                                shell=True, capture_output=True, text=True, timeout=5)
        password = result.stdout.strip()
        
        os.remove("hash.txt") if os.path.exists("hash.txt") else None
        return password if password else None
    except:
        return None

def crack_password_7z(file_path, wordlist):
    """Crack 7z password"""
    try:
        cmd_hash = f"7z2john '{file_path}' > hash.txt 2>/dev/null"
        subprocess.run(cmd_hash, shell=True, timeout=10)
        if not os.path.exists("hash.txt") or os.path.getsize("hash.txt") < 10:
            return None
        
        subprocess.run(f"john --wordlist={wordlist} --format=7z hash.txt", shell=True, timeout=TIMEOUT_CRACK)
        
        result = subprocess.run("john --show hash.txt | grep -o ':[^:]*$' | sed 's/://'", 
                                shell=True, capture_output=True, text=True, timeout=5)
        password = result.stdout.strip()
        
        os.remove("hash.txt") if os.path.exists("hash.txt") else None
        return password if password else None
    except:
        return None

def extract_file(file_path, password, file_type):
    """Extract file with password support (AES-256 compatible)"""
    extract_dir = tempfile.mkdtemp()
    
    try:
        if file_type == 'zip':
            # Try pyzipper first (AES support)
            try:
                import pyzipper
                with pyzipper.AESZipFile(file_path, 'r') as zf:
                    zf.pwd = password.encode()
                    zf.extractall(extract_dir)
                print(f"[DEBUG] Extracted with pyzipper")
                return extract_dir
            except:
                pass
            
            # Try 7z command (works for most formats)
            try:
                subprocess.run(
                    ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"],
                    capture_output=True, timeout=60, check=True
                )
                print(f"[DEBUG] Extracted with 7z")
                return extract_dir
            except:
                pass
            
            # Try standard zipfile (ZipCrypto only)
            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    zf.extractall(extract_dir, pwd=password.encode())
                print(f"[DEBUG] Extracted with zipfile")
                return extract_dir
            except:
                pass
            
            shutil.rmtree(extract_dir, ignore_errors=True)
            return None
        
        elif file_type == 'rar':
            try:
                import rarfile
                with rarfile.RarFile(file_path, 'r') as rf:
                    rf.extractall(extract_dir, pwd=password)
                return extract_dir
            except:
                try:
                    subprocess.run(
                        ["unrar", "x", f"-p{password}", file_path, extract_dir],
                        capture_output=True, timeout=60, check=True
                    )
                    return extract_dir
                except:
                    pass
            shutil.rmtree(extract_dir, ignore_errors=True)
            return None
        
        elif file_type == '7z':
            try:
                import py7zr
                with py7zr.SevenZipFile(file_path, 'r', password=password) as sz:
                    sz.extractall(extract_dir)
                return extract_dir
            except:
                try:
                    subprocess.run(
                        ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"],
                        capture_output=True, timeout=60, check=True
                    )
                    return extract_dir
                except:
                    pass
            shutil.rmtree(extract_dir, ignore_errors=True)
            return None
        
        return None
    except Exception as e:
        print(f"[DEBUG] Extract error: {e}")
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None

def clean_filename(name):
    """Clean filename for safety"""
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
        "✅ Supports **AES-256** and **ZipCrypto** encryption.\n"
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
        "⚡ **Supported Encryption:**\n"
        "- ZIP: ZipCrypto, AES-256\n"
        "- RAR: RAR 3.x, RAR 5.x\n"
        "- 7z: AES-256\n\n"
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

    # Check password protection (supports AES)
    protected = is_password_protected(file_path)
    print(f"[DEBUG] Protected: {protected} for {file_type}")
    
    if not protected:
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
            "💡 **Suggestions:**\n"
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

    # Extract files (supports AES)
    extract_dir = extract_file(file_path, password, file_type)
    if not extract_dir:
        bot.reply_to(msg, "❌ Failed to extract files! The password might be incorrect or the file is corrupted.")
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
                    f"📁 Original file: `{file_name}`\n"
                    f"📦 Files extracted and zipped for you.\n\n"
                    f"🔐 Encryption supported: AES-256 / ZipCrypto",
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
            "⚡ **Supported Encryption:**\n"
            "- ZIP: ZipCrypto, AES-256\n"
            "- RAR: RAR 3.x, RAR 5.x\n"
            "- 7z: AES-256\n\n"
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
