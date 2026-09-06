#!/usr/bin/env python3
# 🔓 GHOST Unlock Bot — Force 7z Detection for AES-256

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
BOT_TOKEN = "8940684766:AAFij8rh9ihggCOakDhofjTikQj8x8AeS3Q"
WORDLIST_PATH = "rockyou.txt"
MAX_FILE_SIZE = 45 * 1024 * 1024
TIMEOUT_CRACK = 180

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# 📁 Helper Functions
# ============================================

def download_wordlist():
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
            return True
    except:
        pass
    # Fallback minimal
    with open(WORDLIST_PATH, 'w') as f:
        words = ["password", "123456", "qwerty", "admin", "letmein", "welcome", "monkey", "dragon"]
        for w in words:
            f.write(w + "\n")
    return True

def get_file_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.zip':
        return 'zip'
    elif ext == '.rar':
        return 'rar'
    elif ext == '.7z':
        return '7z'
    return None

def is_password_protected(file_path):
    """
    Check if file is password protected using MULTIPLE methods.
    Primarily uses 7z command because it handles AES-256 perfectly.
    """
    file_type = get_file_type(file_path)
    if not file_type:
        return False

    # ===== METHOD 1: 7z Command (MOST RELIABLE for AES) =====
    try:
        # Use 7z to test the archive
        result = subprocess.run(
            ["7z", "t", file_path],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout + result.stderr
        print(f"[DEBUG] 7z output: {output[:300]}")
        
        # 7z returns different messages for password protected files
        if "Can not open encrypted archive" in output:
            print("[DEBUG] 7z: Password protected (AES/ZipCrypto)")
            return True
        if "Enter password" in output:
            print("[DEBUG] 7z: Password protected")
            return True
        if "Password" in output and "ERROR" in output:
            print("[DEBUG] 7z: Password protected (error)")
            return True
        if "Cannot find archive" in output:
            # 7z couldn't read it, might be password protected
            pass
        else:
            # If 7z can list contents without error, it's NOT password protected
            # But sometimes 7z asks for password in stderr
            if "Everything is Ok" in output and "Password" not in output:
                print("[DEBUG] 7z: Not password protected")
                return False
    except Exception as e:
        print(f"[DEBUG] 7z test error: {e}")

    # ===== METHOD 2: pyzipper (AES support) =====
    if file_type == 'zip':
        try:
            import pyzipper
            with pyzipper.AESZipFile(file_path, 'r') as zf:
                # Try to read file list - this raises if password needed
                zf.namelist()
                print("[DEBUG] pyzipper: Not password protected")
                return False
        except pyzipper.BadPassword:
            print("[DEBUG] pyzipper: BadPassword exception")
            return True
        except pyzipper.WrongPassword:
            print("[DEBUG] pyzipper: WrongPassword exception")
            return True
        except RuntimeError as e:
            if "password required" in str(e).lower():
                print("[DEBUG] pyzipper: Password required")
                return True
        except Exception as e:
            print(f"[DEBUG] pyzipper error: {e}")

    # ===== METHOD 3: Standard zipfile (ZipCrypto only) =====
    if file_type == 'zip':
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.namelist()
                print("[DEBUG] zipfile: Not password protected")
                return False
        except RuntimeError as e:
            if "encrypted" in str(e).lower():
                print("[DEBUG] zipfile: Password protected")
                return True
        except Exception as e:
            print(f"[DEBUG] zipfile error: {e}")

    # ===== METHOD 4: Check file size / header (last resort) =====
    # Some AES files don't trigger any exception, so we check if extraction fails
    try:
        # Try to extract a single file with 7z in dry-run mode
        result = subprocess.run(
            ["7z", "l", file_path],
            capture_output=True, text=True, timeout=10
        )
        if "Enter password" in result.stderr or "Can not open encrypted archive" in result.stderr:
            print("[DEBUG] 7z list: Password protected")
            return True
        if "0 files" in result.stdout and result.returncode != 0:
            # Could be encrypted
            pass
    except:
        pass

    # If all methods fail, assume it's protected (better safe than sorry)
    print("[DEBUG] Fallback: Assuming password protected")
    return True

def crack_password_zip(file_path, wordlist):
    """Crack ZIP using fcrackzip"""
    try:
        cmd = f"fcrackzip -u -D -p {wordlist} {file_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT_CRACK)
        output = result.stdout + result.stderr
        
        match = re.search(r'PASSWORD FOUND:\s*(\S+)', output)
        if match:
            return match.group(1)
        for line in output.split('\n'):
            if 'PASSWORD FOUND' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    return parts[-1].strip()
        return None
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except:
        return None

def crack_password_rar(file_path, wordlist):
    try:
        subprocess.run(f"rar2john '{file_path}' > hash.txt 2>/dev/null", shell=True, timeout=10)
        if not os.path.exists("hash.txt") or os.path.getsize("hash.txt") < 10:
            return None
        subprocess.run(f"john --wordlist={wordlist} --format=rar hash.txt", shell=True, timeout=TIMEOUT_CRACK)
        result = subprocess.run("john --show hash.txt | grep -o ':[^:]*$' | sed 's/://'", 
                                shell=True, capture_output=True, text=True, timeout=5)
        password = result.stdout.strip()
        os.remove("hash.txt") if os.path.exists("hash.txt") else None
        return password if password else None
    except:
        return None

def crack_password_7z(file_path, wordlist):
    try:
        subprocess.run(f"7z2john '{file_path}' > hash.txt 2>/dev/null", shell=True, timeout=10)
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
    """Extract using 7z for best compatibility"""
    extract_dir = tempfile.mkdtemp()
    try:
        if file_type == 'zip':
            # Use 7z (handles AES-256)
            cmd = ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            print(f"[DEBUG] 7z extract stdout: {result.stdout[:200]}")
            print(f"[DEBUG] 7z extract stderr: {result.stderr[:200]}")
            if "Everything is Ok" in result.stdout or result.returncode == 0:
                return extract_dir
        elif file_type == 'rar':
            cmd = ["unrar", "x", f"-p{password}", file_path, extract_dir]
            subprocess.run(cmd, capture_output=True, timeout=60, check=True)
            return extract_dir
        elif file_type == '7z':
            cmd = ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"]
            subprocess.run(cmd, capture_output=True, timeout=60, check=True)
            return extract_dir
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None
    except Exception as e:
        print(f"[DEBUG] Extract error: {e}")
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
        "🔓 **GHOST Unlock Bot v2.0**\n\n"
        "Send me a password-protected **ZIP / RAR / 7z** file.\n"
        "✅ Supports **AES-256** encryption.\n"
        "⚠️ For **educational purposes** only!\n"
        "Use /help for more info.",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(
        msg,
        "📖 **How to use:**\n\n"
        "1️⃣ Send a password-protected ZIP/RAR/7z file.\n"
        "2️⃣ Wait for cracking (up to 3 minutes).\n"
        "3️⃣ If password found, I'll send you the unlocked files.\n\n"
        "⚡ **Supported Encryption:**\n"
        "- ZIP: ZipCrypto, AES-256\n"
        "- RAR: RAR 3.x, RAR 5.x\n"
        "- 7z: AES-256\n\n"
        "📦 Max file size: 45 MB\n"
        "⏱️ Timeout: 3 minutes",
        parse_mode='Markdown'
    )

@bot.message_handler(content_types=['document'])
def handle_file(msg):
    chat_id = msg.chat.id
    file_name = msg.document.file_name
    file_size = msg.document.file_size

    if file_size > MAX_FILE_SIZE:
        bot.reply_to(msg, f"❌ File too large! Max size: {MAX_FILE_SIZE//1024//1024} MB")
        return

    if not any(file_name.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z']):
        bot.reply_to(msg, "❌ Please send **ZIP, RAR, or 7z** file only.")
        return

    bot.reply_to(msg, f"📥 Downloading `{file_name}`...", parse_mode='Markdown')

    # Download file
    file_info = bot.get_file(msg.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(downloaded)

    file_type = get_file_type(file_path)
    if not file_type:
        bot.reply_to(msg, "❌ Unsupported file type!")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    # 🔥 Check if password protected (AES-256 ready)
    bot.reply_to(msg, "🔍 Checking file protection (AES-256 supported)...")
    protected = is_password_protected(file_path)
    print(f"[DEBUG] Protected: {protected}")

    if not protected:
        bot.reply_to(msg, "ℹ️ This file is **NOT** password protected!\nSend the unlocked file directly.", parse_mode='Markdown')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, f"🔐 File is password protected! Cracking with dictionary attack...\n⏱️ Up to 3 minutes.")

    # Crack
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
            "❌ Password **NOT FOUND** in wordlist.\n\n"
            "💡 **Suggestions:**\n"
            "- Use a stronger password wordlist.\n"
            "- Try brute-force (slow).\n"
            "- Check if password is common (e.g., `password`, `123456`).",
            parse_mode='Markdown'
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    if password == "TIMEOUT":
        bot.reply_to(msg, "⏰ Cracking timed out! Password might be too strong.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, f"✅ Password found: `{password}`\n🔓 Extracting files...", parse_mode='Markdown')

    # Extract
    extract_dir = extract_file(file_path, password, file_type)
    if not extract_dir:
        bot.reply_to(msg, "❌ Failed to extract files! Password may be incorrect or file is corrupted.")
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
                    f"🔐 AES-256 supported.",
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
            "1️⃣ Send a password-protected ZIP/RAR/7z file.\n"
            "2️⃣ Wait for cracking (up to 3 minutes).\n"
            "3️⃣ If password found, I'll send you the unlocked files.\n\n"
            "⚡ **Supported Encryption:**\n"
            "- ZIP: ZipCrypto, AES-256\n"
            "- RAR: RAR 3.x, RAR 5.x\n"
            "- 7z: AES-256\n\n"
            "📦 Max file size: 45 MB\n"
            "⏱️ Timeout: 3 minutes",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# ============================================
# 🚀 Start
# ============================================
if __name__ == "__main__":
    print("🔥 GHOST Unlock Bot v2.0 Starting...")
    download_wordlist()
    print("✅ Bot is ready!")
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except KeyboardInterrupt:
            print("\n⏹️ Stopped.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(10)
