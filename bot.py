import os
import sys
import asyncio
import base64
import time
import traceback
import uuid
from io import BytesIO
from typing import Dict, Optional, Tuple
from asyncio import Lock
from functools import lru_cache

import requests
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest, NetworkError, TimedOut
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()

# --------------------- تنظیمات از متغیرهای محیطی ---------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment")

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    raise ValueError("REPLICATE_API_TOKEN is not set")

PROXY_URL = os.getenv("PROXY_URL")
FALLBACK_VERSION = os.getenv("FALLBACK_VERSION", "5c7d5e6b8c7c9e6a5b4c3d2e1f0a9b8c7d6e5f4a")

DOWNLOAD_FOLDER = "downloads"
REQUEST_TIMEOUT = 120

MODEL_NAME = "tencentarc/real-esrgan-v2"

QUALITY_OPTIONS = [
    ("HD (2x)", 2, 2),
    ("Full HD (3x)", 3, 3),
    ("4K (4x)", 4, 4),
    ("8K (8x)", 4, 8),
]

# --------------------- لیست زبان‌ها ---------------------
LANGUAGES = [
    ("af", "Afrikaans", "ZA"), ("sq", "Albanian", "AL"), ("am", "Amharic", "ET"),
    ("ar", "Arabic", "SA"), ("hy", "Armenian", "AM"), ("az", "Azerbaijani", "AZ"),
    ("eu", "Basque", "ES"), ("be", "Belarusian", "BY"), ("bn", "Bengali", "BD"),
    ("bs", "Bosnian", "BA"), ("bg", "Bulgarian", "BG"), ("ca", "Catalan", "ES"),
    ("ceb", "Cebuano", "PH"), ("ny", "Chichewa", "MW"), ("zh", "Chinese (Simplified)", "CN"),
    ("zh-TW", "Chinese (Traditional)", "TW"), ("co", "Corsican", "FR"), ("hr", "Croatian", "HR"),
    ("cs", "Czech", "CZ"), ("da", "Danish", "DK"), ("nl", "Dutch", "NL"),
    ("en", "English", "GB"), ("eo", "Esperanto", "UN"), ("et", "Estonian", "EE"),
    ("tl", "Filipino", "PH"), ("fi", "Finnish", "FI"), ("fr", "French", "FR"),
    ("fy", "Frisian", "NL"), ("gl", "Galician", "ES"), ("ka", "Georgian", "GE"),
    ("de", "German", "DE"), ("el", "Greek", "GR"), ("gu", "Gujarati", "IN"),
    ("ht", "Haitian Creole", "HT"), ("ha", "Hausa", "NG"), ("haw", "Hawaiian", "US"),
    ("iw", "Hebrew", "IL"), ("hi", "Hindi", "IN"), ("hmn", "Hmong", "CN"),
    ("hu", "Hungarian", "HU"), ("is", "Icelandic", "IS"), ("ig", "Igbo", "NG"),
    ("id", "Indonesian", "ID"), ("ga", "Irish", "IE"), ("it", "Italian", "IT"),
    ("ja", "Japanese", "JP"), ("jw", "Javanese", "ID"), ("kn", "Kannada", "IN"),
    ("kk", "Kazakh", "KZ"), ("km", "Khmer", "KH"), ("rw", "Kinyarwanda", "RW"),
    ("ko", "Korean", "KR"), ("ku", "Kurdish", "IQ"), ("ky", "Kyrgyz", "KG"),
    ("lo", "Lao", "LA"), ("la", "Latin", "VA"), ("lv", "Latvian", "LV"),
    ("lt", "Lithuanian", "LT"), ("lb", "Luxembourgish", "LU"), ("mk", "Macedonian", "MK"),
    ("mg", "Malagasy", "MG"), ("ms", "Malay", "MY"), ("ml", "Malayalam", "IN"),
    ("mt", "Maltese", "MT"), ("mi", "Maori", "NZ"), ("mr", "Marathi", "IN"),
    ("mn", "Mongolian", "MN"), ("my", "Myanmar (Burmese)", "MM"), ("ne", "Nepali", "NP"),
    ("no", "Norwegian", "NO"), ("or", "Odia", "IN"), ("ps", "Pashto", "AF"),
    ("fa", "Persian", "IR"), ("pl", "Polish", "PL"), ("pt", "Portuguese", "PT"),
    ("pa", "Punjabi", "IN"), ("ro", "Romanian", "RO"), ("ru", "Russian", "RU"),
    ("sm", "Samoan", "WS"), ("gd", "Scots Gaelic", "GB"), ("sr", "Serbian", "RS"),
    ("st", "Sesotho", "LS"), ("sn", "Shona", "ZW"), ("sd", "Sindhi", "PK"),
    ("si", "Sinhala", "LK"), ("sk", "Slovak", "SK"), ("sl", "Slovenian", "SI"),
    ("so", "Somali", "SO"), ("es", "Spanish", "ES"), ("su", "Sundanese", "ID"),
    ("sw", "Swahili", "KE"), ("sv", "Swedish", "SE"), ("tg", "Tajik", "TJ"),
    ("ta", "Tamil", "IN"), ("tt", "Tatar", "RU"), ("te", "Telugu", "IN"),
    ("th", "Thai", "TH"), ("tr", "Turkish", "TR"), ("tk", "Turkmen", "TM"),
    ("uk", "Ukrainian", "UA"), ("ur", "Urdu", "PK"), ("ug", "Uyghur", "CN"),
    ("uz", "Uzbek", "UZ"), ("vi", "Vietnamese", "VN"), ("cy", "Welsh", "GB"),
    ("xh", "Xhosa", "ZA"), ("yi", "Yiddish", "IL"), ("yo", "Yoruba", "NG"),
    ("zu", "Zulu", "ZA")
]
LANGUAGES.sort(key=lambda x: x[1])

# --------------------- کش و قفل‌ها ---------------------
_translation_cache: Dict[Tuple[str, str], str] = {}
_translation_lock = Lock()

# --------------------- توابع کمکی ---------------------
def flag(country_code: str) -> str:
    if not country_code or len(country_code) != 2:
        return ""
    return chr(ord(country_code[0]) + 127397) + chr(ord(country_code[1]) + 127397)

def language_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    per_page = 8
    total_pages = (len(LANGUAGES) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    buttons = []
    for code, name, country in LANGUAGES[start:end]:
        buttons.append([InlineKeyboardButton(f"{flag(country)} {name}", callback_data=f"lang_{code}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"langpage_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"langpage_{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)

async def translate_text(text: str, dest_lang: str) -> str:
    if dest_lang == 'en':
        return text
    key = (text, dest_lang)
    async with _translation_lock:
        if key in _translation_cache:
            return _translation_cache[key]
    try:
        loop = asyncio.get_running_loop()
        translated = await loop.run_in_executor(
            None,
            lambda: GoogleTranslator(source='auto', target=dest_lang).translate(text)
        )
        async with _translation_lock:
            _translation_cache[key] = translated
        return translated
    except Exception:
        return text

# --------------------- عملیات AI با پشتیبانی از پروکسی ---------------------
def get_proxies() -> Optional[Dict[str, str]]:
    if PROXY_URL:
        return {"http": PROXY_URL, "https": PROXY_URL}
    return None

@lru_cache(maxsize=1)
def get_model_version() -> str:
    headers = {"Authorization": f"Token {REPLICATE_API_TOKEN}"}
    url = f"https://api.replicate.com/v1/models/{MODEL_NAME}"
    proxies = get_proxies()
    try:
        resp = requests.get(url, headers=headers, timeout=30, proxies=proxies)
        if resp.status_code == 200:
            version = resp.json()["latest_version"]["id"]
            return version
    except Exception as e:
        print(f"⚠️ Could not fetch model version: {e}")
    print(f"⚠️ Using fallback version {FALLBACK_VERSION}")
    return FALLBACK_VERSION

def upscale_with_ai(input_path: str, scale: int) -> bytes:
    version = get_model_version()
    with open(input_path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('utf-8')
    data_uri = f"data:image/jpeg;base64,{encoded}"

    headers = {
        "Authorization": f"Token {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "version": version,
        "input": {
            "image": data_uri,
            "scale": min(scale, 4),
            "face_enhance": True
        }
    }
    proxies = get_proxies()

    resp = requests.post(
        "https://api.replicate.com/v1/predictions",
        json=payload,
        headers=headers,
        timeout=60,
        proxies=proxies
    )
    if resp.status_code != 201:
        raise Exception(f"Replicate create error {resp.status_code}: {resp.text}")

    prediction = resp.json()
    start_time = time.time()
    while prediction['status'] not in ('succeeded', 'failed', 'canceled'):
        if time.time() - start_time > 180:
            raise Exception("Prediction timed out")
        time.sleep(2)
        resp = requests.get(prediction['urls']['get'], headers=headers, timeout=30, proxies=proxies)
        prediction = resp.json()

    if prediction['status'] != 'succeeded':
        raise Exception(f"Prediction failed: {prediction.get('error', 'unknown')}")

    output_url = prediction['output']
    if isinstance(output_url, list):
        output_url = output_url[0]

    img_resp = requests.get(output_url, timeout=60, proxies=proxies)
    if img_resp.status_code != 200:
        raise Exception("Failed to download output image")
    return img_resp.content

def local_upscale_to_size(input_path: str, target_width: int, target_height: int) -> bytes:
    img = Image.open(input_path)
    img = img.resize((target_width, target_height), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

# --------------------- ابزارهای ربات ---------------------
async def safe_edit_message(message, text=None, reply_markup=None, **kwargs):
    try:
        if text is not None:
            return await message.edit_text(text, reply_markup=reply_markup, **kwargs)
        else:
            return await message.edit_reply_markup(reply_markup=reply_markup, **kwargs)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise
        return message

async def safe_reply(update, text, **kwargs):
    try:
        return await update.message.reply_text(text, **kwargs)
    except Exception:
        return None

def clean_download_folder():
    if os.path.exists(DOWNLOAD_FOLDER):
        for f in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, f)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception:
                pass

# --------------------- هندلرهای ربات ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_download_folder()
    if 'lang' not in context.user_data:
        await update.message.reply_text(
            "Please select your language / لطفاً زبان خود را انتخاب کنید:",
            reply_markup=language_keyboard()
        )
        return
    lang = context.user_data['lang']
    welcome = await translate_text("Welcome! Please send a photo to upscale.", lang)
    await update.message.reply_text(welcome)

async def language_page_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[1])
    await safe_edit_message(query.message, reply_markup=language_keyboard(page))

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_", 1)[1]
    context.user_data['lang'] = lang_code
    confirm = await translate_text("Language set. Now send a photo.", lang_code)
    await safe_edit_message(query.message, confirm)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'en')
    try:
        photo_file = await update.message.photo[-1].get_file()
    except (NetworkError, TimedOut, BadRequest) as e:
        await safe_reply(update, await translate_text(f"Error downloading photo: {str(e)[:100]}", lang))
        return

    if photo_file.file_size > 20 * 1024 * 1024:
        await safe_reply(update, await translate_text("Image too large (max 20MB).", lang))
        return

    input_path = os.path.join(DOWNLOAD_FOLDER, f"{update.effective_user.id}_{uuid.uuid4().hex}.jpg")
    try:
        await photo_file.download_to_drive(input_path)
    except Exception as e:
        await safe_reply(update, await translate_text(f"Could not save photo: {str(e)[:100]}", lang))
        return

    context.user_data['input_path'] = input_path
    try:
        with Image.open(input_path) as img:
            context.user_data['orig_width'] = img.width
            context.user_data['orig_height'] = img.height
    except Exception:
        context.user_data['orig_width'] = None

    kb_buttons = []
    for label, ai_scale, local_scale in QUALITY_OPTIONS:
        translated_label = await translate_text(label, lang)
        kb_buttons.append([InlineKeyboardButton(translated_label, callback_data=f"q_{ai_scale}_{local_scale}")])
    kb_buttons.append([InlineKeyboardButton(await translate_text("Cancel", lang), callback_data="cancel")])

    prompt = await translate_text("Choose quality:", lang)
    await update.message.reply_text(prompt, reply_markup=InlineKeyboardMarkup(kb_buttons))

async def quality_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = context.user_data.get('lang', 'en')
    input_path = context.user_data.get('input_path')
    orig_width = context.user_data.get('orig_width')
    orig_height = context.user_data.get('orig_height')

    if data == "cancel":
        await safe_edit_message(query.message, await translate_text("Cancelled.", lang))
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.pop('input_path', None)
        context.user_data.pop('orig_width', None)
        context.user_data.pop('orig_height', None)
        return

    try:
        parts = data.split("_")
        if len(parts) != 3 or parts[0] != 'q':
            raise ValueError
        ai_scale = int(parts[1])
        local_scale = int(parts[2])
    except:
        await safe_edit_message(query.message, "Invalid option.")
        return

    if not input_path or not os.path.exists(input_path):
        await safe_edit_message(query.message, await translate_text("No image found. Send a new photo.", lang))
        return

    final_scale = local_scale

    # پیام وضعیت
    status_msg = await safe_edit_message(query.message, await translate_text("⏳ Starting upscale...", lang))

    try:
        img_data = None
        ai_done = False
        if ai_scale > 1:
            await safe_edit_message(status_msg, await translate_text("⏳ Upscaling with AI (this may take a while)...", lang))
            try:
                effective_ai = min(ai_scale, 4)
                img_data = await asyncio.get_running_loop().run_in_executor(
                    None, upscale_with_ai, input_path, effective_ai
                )
                ai_done = True
            except Exception as e:
                print(f"AI failed: {e}")
                ai_done = False

        if ai_done and final_scale > ai_scale:
            await safe_edit_message(status_msg, await translate_text("⏳ Applying additional local scaling...", lang))
            if orig_width and orig_height:
                target_w = orig_width * final_scale
                target_h = orig_height * final_scale
            else:
                temp_img = Image.open(BytesIO(img_data))
                target_w = temp_img.width * (final_scale // ai_scale)
                target_h = temp_img.height * (final_scale // ai_scale)
                temp_img.close()
            temp_path = input_path + ".ai.tmp"
            with open(temp_path, 'wb') as f:
                f.write(img_data)
            img_data = await asyncio.get_running_loop().run_in_executor(
                None, local_upscale_to_size, temp_path, target_w, target_h
            )
            os.remove(temp_path)

        if not ai_done:
            await safe_edit_message(status_msg, await translate_text("⏳ Using local upscaling (no AI)...", lang))
            if orig_width and orig_height:
                target_w = orig_width * final_scale
                target_h = orig_height * final_scale
            else:
                with Image.open(input_path) as img:
                    target_w = img.width * final_scale
                    target_h = img.height * final_scale
            img_data = await asyncio.get_running_loop().run_in_executor(
                None, local_upscale_to_size, input_path, target_w, target_h
            )

        await safe_edit_message(status_msg, await translate_text("✅ Sending result...", lang))
        bio = BytesIO(img_data)
        bio.seek(0)
        caption = await translate_text("✅ Here is your upscaled image.", lang)
        await query.message.reply_document(
            document=bio,
            filename="upscaled.jpg",
            caption=caption,
            read_timeout=REQUEST_TIMEOUT,
            write_timeout=REQUEST_TIMEOUT,
            connect_timeout=REQUEST_TIMEOUT,
        )
        try:
            await query.message.delete()
        except:
            pass

    except Exception as e:
        error_text = f"❌ Error: {str(e)[:200]}"
        try:
            error_text = await translate_text(error_text, lang)
        except:
            pass
        await safe_edit_message(status_msg, error_text)
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Error from user {update.effective_user.id}:\n{str(e)[:500]}"
            )
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.pop('input_path', None)
        context.user_data.pop('orig_width', None)
        context.user_data.pop('orig_height', None)

# --------------------- خطاگیر ---------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, NetworkError):
        return
    print(f"Update {update} caused error: {context.error}", file=sys.stderr)
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ Error:\n{str(context.error)[:500]}"
            )
        except:
            pass

# --------------------- اجرای اصلی ---------------------
async def main():
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    clean_download_folder()

    app_builder = Application.builder().token(TOKEN)
    if PROXY_URL:
        app_builder = app_builder.proxy(PROXY_URL)
    app = (
        app_builder
        .connect_timeout(REQUEST_TIMEOUT)
        .read_timeout(REQUEST_TIMEOUT)
        .write_timeout(REQUEST_TIMEOUT)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(language_page_handler, pattern="^langpage_"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(quality_handler, pattern="^q_"))
    app.add_handler(CallbackQueryHandler(quality_handler, pattern="^cancel$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(error_handler)

    print("✅ Bot started (Tencent Real-ESRGAN v2) - Improved version")
    await app.run_polling()

if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
