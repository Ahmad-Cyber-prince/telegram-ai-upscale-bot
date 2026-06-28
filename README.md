# 🤖 Telegram AI Image Upscale Bot

A Telegram bot that enhances and upscales images using the **Real-ESRGAN v2** model via the [Replicate](https://replicate.com) API, with a local Pillow fallback for additional scaling.

## ✨ Features

- Upscale images up to **8x** (Combination of AI + Local processing).
- Supports **100+ languages** with automatic message translation.
- Choose output quality: **HD (2x)**, **Full HD (3x)**, **4K (4x)**, or **8K (8x)**.
- Real-time processing status updates.
- Cancel operation at any time.
- Optional Proxy support.
- Sends error logs to the Admin.

## 📸 Sample Output

| Input (Low Quality) | Output (Upscaled) |
|:---:|:---:|
| ![Low 1](sample_images/low_1.jpg) | ![High 1](sample_images/high_1.jpg) |
| ![Low 2](sample_images/low_2.jpg) | ![High 2](sample_images/high_2.jpg) |

## 🛠️ Prerequisites

- Python 3.8 or higher.
- A Telegram Bot Token (Get it from [@BotFather](https://t.me/botfather)).
- A Replicate API Token (Sign up at [Replicate](https://replicate.com) and add at least $1 credit to your account).

## 📦 Installation & Setup

Follow these steps to run the bot on your server:

```bash
# 1. Clone the repository
git clone https://github.com/your-username/telegram-ai-upscale-bot.git
cd telegram-ai-upscale-bot

# 2. Create a virtual environment (Recommended)
python -m venv venv
source venv/bin/activate   # On Windows use: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Open the .env file with a text editor and paste your real tokens.
