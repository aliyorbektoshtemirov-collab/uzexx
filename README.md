# UZEX AI Hackathon boti (uz/ru)

Telegram bot: UZEX, birja savdolari, bitimlar, ro‘yxatdan o‘tish, ERI, zakalat, davlat xaridlari.
Dataset **sun’iy (o‘ylab topilgan)** — bot har bir dataset javobida buni ogohlantiradi.

## O‘rnatish
    pip install -r requirements.txt
    cp .env.example .env     # TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, OPENROUTER_MODEL ni to‘ldiring
    python bot.py
Birinchi ishga tushishda `data/uzex_demo.sqlite.gz.part01…` (bo‘laklar) avtomatik ochiladi (~224 MB bo‘sh joy kerak).
OpenRouter kalitisiz ham ishlaydi: faqat tasdiqlangan faktlar ko‘rsatiladi.

## Boshqa AI servis
`OPENROUTER_BASE_URL` bo‘sh bo‘lsa OpenRouter ishlatiladi. Boshqa OpenAI-mos servis uchun URL, kalit va model nomini kiriting:
OpenAI: `https://api.openai.com/v1`; Groq: `https://api.groq.com/openai/v1`; Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`.

## Termux (Android)
    pkg update && pkg install python
    pip install python-telegram-bot
    cd uzex_bot && cp .env.example .env && nano .env
    python bot.py
**Bir vaqtda faqat bitta polling jarayoni** ishlashi mumkin (aks holda Telegram `Conflict` xatosi beradi): `pkill -f bot.py`.

## Testlar
    python -m unittest discover -s tests

## Tuzilma
`bot.py` (Telegram + OpenRouter), `knowledge.py` (bilimlar bazasi qidiruvi), `market_data.py` (dataset → SQLite, statistika),
`data/knowledge.json`, `data/uzex_demo.sqlite.gz.part01…` (bo‘laklar), `build_dataset.py` (bazani CSV’dan qayta yig‘ish).

## Hisoblash qoidalari
Aylanma: bekor qilingan («Аннулирован») bitimlar kirmaydi; USD bitimlar sana kursi bilan so‘mga o‘tkaziladi.
Hajm/o‘rtacha narx faqat bir xil o‘lchov birligi ichida. STIR va broker kodlari bazaga kiritilmagan.

## Ma’lum cheklovlar
- `knowledge.json` — qisqa boshlang‘ich baza: aniq summa/muddat/rekvizit yo‘q. **Topshirishdan oldin rasmiy manbalar bilan tekshirib, to‘ldiring** (ayniqsa BHKP zakalati).
- Telegram handlerlari (tugmalar, `/start`) ushbu muhitda internet/kutubxona yo‘qligi sababli jonli sinalmagan; mantiq `Engine` orqali testlangan.
- Mahsulot/hudud qidiruvi alias lug‘ati bo‘yicha; lug‘atda yo‘q so‘zlar filtrlanmaydi.
- Mavzu aniqlash kalit so‘zlarga asoslangan; AI faqat bilimlar bazasidagi parchalar bilan chaqiriladi.

## Railway
1. Loyihani GitHub’ga yuklang (`.env` yuklanmaydi — `.gitignore`da bor).
2. railway.app → New Project → Deploy from GitHub repo → shu repo. `Dockerfile` avtomatik ishlatiladi.
3. Service → Variables bo‘limida kiriting: `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY` (ixtiyoriy: `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`).
4. Deploy tugagach Logs’da xato yo‘qligini tekshiring. Bot polling bilan ishlaydi, port/domen kerak emas.
5. Bir vaqtda faqat bitta nusxa: kompyuter yoki Termux’dagi botni o‘chiring, aks holda `Conflict` xatosi chiqadi.
Baza har ishga tushganda siqilgan fayldan avtomatik ochiladi (doimiy disk kerak emas).
