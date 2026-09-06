#!/usr/bin/env python3
# 🔓 GHOST Unlock Bot v4.0 — AES-256 WinZip + Multi-Method Cracking
# Created by GHOST | For educational & own file use only!

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
MAX_FILE_SIZE = 45 * 1024 * 1024  # 45 MB
TIMEOUT_CRACK = 300  # 5 minutes per method

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# 📁 Helper Functions
# ============================================

def download_wordlist():
    """Download rockyou.txt or create minimal"""
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
    # Fallback minimal
    print("⚠️ Creating minimal wordlist...")
    with open(WORDLIST_PATH, 'w') as f:
        words = [
            "password", "123456", "123456789", "qwerty", "abc123",
            "admin", "letmein", "welcome", "monkey", "dragon",
            "master", "sunshine", "iloveyou", "princess", "rockyou",
            "12345", "12345678", "password1", "admin123", "1234567890"
        ]
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
    """Check if file is password protected (AES-256 detection)"""
    file_type = get_file_type(file_path)
    if not file_type:
        return False
    
    # Method 1: 7z test (most reliable)
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
        if "Password" in output and "ERROR" in output:
            return True
        if "Everything is Ok" in output and "Password" not in output:
            return False
    except:
        pass
    
    # Method 2: zipfile (only for ZipCrypto)
    if file_type == 'zip':
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.namelist()
                return False
        except RuntimeError:
            return True
        except:
            pass
    
    return True  # Assume protected if unsure

def crack_password_zip_multi(file_path, wordlist):
    """
    Multi-method ZIP cracker:
    1. john (best for AES-256)
    2. hashcat (if available)
    3. 7z brute force (slow)
    4. fcrackzip (legacy)
    """
    
    # ===== METHOD 1: john =====
    print("[DEBUG] Method 1: john")
    try:
        hash_file = "hash_john.txt"
        # Extract hash
        subprocess.run(
            f"zip2john '{file_path}' > {hash_file} 2>/dev/null",
            shell=True, timeout=15
        )
        
        if os.path.exists(hash_file) and os.path.getsize(hash_file) > 50:
            # Crack with john
            result = subprocess.run(
                f"john --wordlist={wordlist} --format=zip {hash_file}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_CRACK
            )
            print(f"[DEBUG] john stdout: {result.stdout[:200]}")
            print(f"[DEBUG] john stderr: {result.stderr[:200]}")
            
            # Get password
            show = subprocess.run(
                f"john --show {hash_file} | grep -o ':[^:]*$' | sed 's/://'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            password = show.stdout.strip()
            os.remove(hash_file) if os.path.exists(hash_file) else None
            
            if password:
                print(f"[DEBUG] Password found by john: {password}")
                return password
        os.remove(hash_file) if os.path.exists(hash_file) else None
    except subprocess.TimeoutExpired:
        print("[DEBUG] john: TIMEOUT")
    except Exception as e:
        print(f"[DEBUG] john error: {e}")

    # ===== METHOD 2: hashcat =====
    print("[DEBUG] Method 2: hashcat")
    try:
        hash_file = "hash_hashcat.txt"
        subprocess.run(
            f"zip2john '{file_path}' > {hash_file} 2>/dev/null",
            shell=True, timeout=15
        )
        
        if os.path.exists(hash_file) and os.path.getsize(hash_file) > 50:
            # hashcat mode 13600 = WinZip AES-256
            result = subprocess.run(
                f"hashcat -m 13600 -a 0 {hash_file} {wordlist} --force --potfile-disable 2>/dev/null",
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
                print(f"[DEBUG] Password found by hashcat: {password}")
                return password
        os.remove(hash_file) if os.path.exists(hash_file) else None
    except subprocess.TimeoutExpired:
        print("[DEBUG] hashcat: TIMEOUT")
    except Exception as e:
        print(f"[DEBUG] hashcat error: {e}")

    # ===== METHOD 3: 7z brute force =====
    print("[DEBUG] Method 3: 7z brute force")
    try:
        with open(wordlist, 'r', encoding='utf-8', errors='ignore') as f:
            count = 0
            for line in f:
                pwd = line.strip()
                if not pwd or len(pwd) > 30:
                    continue
                count += 1
                if count % 100 == 0:
                    print(f"[DEBUG] 7z tried: {count}")
                
                result = subprocess.run(
                    ["7z", "t", f"-p{pwd}", file_path],
                    capture_output=True,
                    timeout=3
                )
                if result.returncode == 0:
                    print(f"[DEBUG] Password found by 7z: {pwd}")
                    return pwd
    except Exception as e:
        print(f"[DEBUG] 7z brute error: {e}")

    # ===== METHOD 4: fcrackzip (legacy) =====
    print("[DEBUG] Method 4: fcrackzip")
    try:
        result = subprocess.run(
            f"fcrackzip -u -D -p {wordlist} {file_path}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_CRACK
        )
        output = result.stdout + result.stderr
        print(f"[DEBUG] fcrackzip output: {output[:200]}")
        
        match = re.search(r'PASSWORD FOUND:\s*(\S+)', output)
        if match:
            return match.group(1)
        for line in output.split('\n'):
            if 'PASSWORD FOUND' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    return parts[-1].strip()
    except subprocess.TimeoutExpired:
        print("[DEBUG] fcrackzip: TIMEOUT")
    except Exception as e:
        print(f"[DEBUG] fcrackzip error: {e}")

    return None  # No password found

def crack_password_rar(file_path, wordlist):
    """Crack RAR using john"""
    try:
        hash_file = "hash_rar.txt"
        # Try rar2john from john package
        john_rar = "/usr/share/john/rar2john.py"
        if os.path.exists(john_rar):
            cmd = f"python3 {john_rar} '{file_path}' > {hash_file} 2>/dev/null"
        else:
            cmd = f"rar2john '{file_path}' > {hash_file} 2>/dev/null"
        
        subprocess.run(cmd, shell=True, timeout=15)
        
        if os.path.exists(hash_file) and os.path.getsize(hash_file) > 50:
            result = subprocess.run(
                f"john --wordlist={wordlist} --format=rar {hash_file}",
                shell=True, capture_output=True, text=True, timeout=TIMEOUT_CRACK
            )
            show = subprocess.run(
                "john --show hash_rar.txt | grep -o ':[^:]*$' | sed 's/://'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            password = show.stdout.strip()
            os.remove(hash_file) if os.path.exists(hash_file) else None
            return password if password else None
        os.remove(hash_file) if os.path.exists(hash_file) else None
    except:
        pass
    return None

def crack_password_7z(file_path, wordlist):
    """Crack 7z using john"""
    try:
        hash_file = "hash_7z.txt"
        cmd = f"7z2john '{file_path}' > {hash_file} 2>/dev/null"
        subprocess.run(cmd, shell=True, timeout=15)
        
        if os.path.exists(hash_file) and os.path.getsize(hash_file) > 50:
            result = subprocess.run(
                f"john --wordlist={wordlist} --format=7z {hash_file}",
                shell=True, capture_output=True, text=True, timeout=TIMEOUT_CRACK
            )
            show = subprocess.run(
                "john --show hash_7z.txt | grep -o ':[^:]*$' | sed 's/://'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            password = show.stdout.strip()
            os.remove(hash_file) if os.path.exists(hash_file) else None
            return password if password else None
        os.remove(hash_file) if os.path.exists(hash_file) else None
    except:
        pass
    return None

def extract_file(file_path, password, file_type):
    """Extract using 7z (handles AES-256)"""
    extract_dir = tempfile.mkdtemp()
    try:
        if file_type == 'zip':
            # Try 7z first (handles AES)
            cmd = ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if "Everything is Ok" in result.stdout or result.returncode == 0:
                return extract_dir
            # Try zipfile as fallback
            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    zf.extractall(extract_dir, pwd=password.encode())
                return extract_dir
            except:
                pass
        elif file_type == 'rar':
            try:
                cmd = ["unrar", "x", f"-p{password}", file_path, extract_dir]
                subprocess.run(cmd, capture_output=True, timeout=60, check=True)
                return extract_dir
            except:
                pass
        elif file_type == '7z':
            try:
                cmd = ["7z", "x", f"-p{password}", file_path, f"-o{extract_dir}", "-y"]
                subprocess.run(cmd, capture_output=True, timeout=60, check=True)
                return extract_dir
            except:
                pass
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
        "🔓 **GHOST Unlock Bot v4.0**\n\n"
        "Send me a password-protected **ZIP / RAR / 7z** file.\n"
        "✅ Supports **WinZip AES-256 (Method 99)**\n"
        "⚡ Multi-method cracking: john → hashcat → 7z → fcrackzip\n"
        "⚠️ For **educational purposes** only!\n\n"
        "⏱️ Cracking may take 5+ minutes.",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(
        msg,
        "📖 **How to use:**\n\n"
        "1️⃣ Send a password-protected ZIP/RAR/7z file.\n"
        "2️⃣ Bot will try multiple cracking methods.\n"
        "3️⃣ If password found, you'll get your files.\n\n"
        "⚡ **Cracking Methods (in order):**\n"
        "1. `john` — best for AES-256 WinZip\n"
        "2. `hashcat` — GPU cracking (if available)\n"
        "3. `7z` — brute force (slow)\n"
        "4. `fcrackzip` — legacy ZIP\n\n"
        "📦 Max file size: 45 MB\n"
        "⏱️ Timeout: 5 minutes per method",
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

    if not any(file_name.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z']):
        bot.reply_to(msg, "❌ Please send **ZIP, RAR, or 7z** file only.")
        return

    bot.reply_to(msg, f"📥 Downloading `{file_name}`...", parse_mode='Markdown')

    # Download
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

    # Check protection
    bot.reply_to(msg, "🔍 Checking file (AES-256 detection)...")
    if not is_password_protected(file_path):
        bot.reply_to(msg, "ℹ️ This file is **NOT** password protected!", parse_mode='Markdown')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    bot.reply_to(msg, "🔐 File is encrypted! Starting multi-method cracking...\n⏱️ May take 5+ minutes.")

    # Crack
    password = None
    if file_type == 'zip':
        password = crack_password_zip_multi(file_path, WORDLIST_PATH)
    elif file_type == 'rar':
        password = crack_password_rar(file_path, WORDLIST_PATH)
    elif file_type == '7z':
        password = crack_password_7z(file_path, WORDLIST_PATH)

    if not password:
        bot.reply_to(
            msg,
            "❌ Password **NOT FOUND** using any method.\n\n"
            "💡 **Suggestions:**\n"
            "- Use a **stronger wordlist** (rockyou.txt is limited).\n"
            "- Try **brute-force** with hashcat (very slow for AES-256).\n"
            "- Consider using a **GPU** for faster cracking.\n"
            "- If this is your own file, try to remember the password.",
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
                    f"🔐 AES-256 WinZip supported.",
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
            "2️⃣ Bot will try multiple cracking methods.\n"
            "3️⃣ If password found, you'll get your files.\n\n"
            "⚡ **Cracking Methods (in order):**\n"
            "1. `john` — best for AES-256 WinZip\n"
            "2. `hashcat` — GPU cracking (if available)\n"
            "3. `7z` — brute force (slow)\n"
            "4. `fcrackzip` — legacy ZIP\n\n"
            "📦 Max file size: 45 MB\n"
            "⏱️ Timeout: 5 minutes per method",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# ============================================
# 🚀 Start
# ============================================
if __name__ == "__main__":
    print("🔥 GHOST Unlock Bot v4.0 (Multi-Method) Starting...")
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
