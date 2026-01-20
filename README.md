# 🛒 DroidRun Hackathon Solution -  Automatic Shopper

An AI-powered Android agent that autonomously finds the best deals across Amazon and Flipkart using computer vision and intelligent decision making.

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- Android device with USB debugging
- DroidRun framework license
- Android SDK Platform Tools (ADB)

### Installation
```bash
git clone https://github.com/rishavm1/Droidrun-hackthon-solution.git
cd Droidrun-hackthon-solution
python setup.py
```

### Configuration
1. Copy `.env.example` to `.env`
2. Add your API keys (see API Keys section below)
3. Connect Android device via USB

### Usage
```bash
python main.py
```

## 🔑 Required API Keys

### Essential
- **DroidRun License**: Contact DroidRun team for framework access

### Optional
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)

## 🤖 How It Works

1. **Search**: Opens Amazon & Flipkart apps, searches for your product
2. **Extract**: Reads prices, ratings, titles (ignores sponsored ads)
3. **Compare**: Uses weighted scoring (price vs rating) within budget
4. **Purchase**: Adds best option to cart automatically

## 🛡️ Security Features

- XSS protection with input sanitization
- Local processing (no external data sharing)
- Proper error handling and logging
- HTML escaping for all user inputs

## 📱 Supported Apps

- Amazon Shopping (com.amazon.mShop.android.shopping)
- Flipkart (com.flipkart.android)

## 🧪 Testing

Verify setup with:
```bash
python test_app.py
```

## 📄 License

MIT License - See LICENSE file for details.

## ⚠️ Disclaimer

For educational and personal use only. Respect platform terms of service.
