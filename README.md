# ValyutaX Bot

O'zbekiston Markaziy banki (CBU) rasmiy kurslari va xalqaro kurslar
asosida ishlaydigan valyuta Telegram boti.

## Imkoniyatlar

- **Joriy kurs** — CBU'ning rasmiy kurslari (10 ta valyuta: USD, EUR, RUB, GBP, CNY, KZT, TRY, JPY, AED, CHF), o'zgarish (▲/▼) bilan
- **Konvertatsiya** — erkin matn orqali (`100 USD`, `100 USD EUR`) yoki tayyor tugmalar (100/500/1000/5000)
- **Kurs tarixi/grafik** — bot ishlagan har bir kun uchun kurs nuqtasi saqlanadi va grafik chizib beriladi
- **Kunlik bildirishnoma** — kurs o'zgargan kunlari obunachilarga avtomatik xabar (`/obuna`, `/bekor`)
- **Doimiy pastki menyu** — asosiy bo'limlar har doim tugmalar panelida
- **Admin panel** (`/admin`) — obunachilar soni, eng ko'p so'ralgan valyutalar
- **Monitoring** (`/health`) — CBU/xalqaro API'dan so'nggi muvaffaqiyatli olingan vaqt
- **Xatolarga chidamlilik** — tarmoq so'rovlarida avtomatik qayta urinish, fayl loglari, global xato ishlovchi
- **Telegram Mini App** (`webapp/`) — bot ichida ochiladigan to'liq web interfeys (kurs, konvertatsiya, tarix grafigi)

## Ishga tushirish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env faylida BOT_TOKEN qiymatini @BotFather'dan olingan token bilan to'ldiring

export $(grep -v '^#' .env | xargs)   # yoki python-dotenv orqali yuklang
python bot.py
```

## Muhit o'zgaruvchilari

| O'zgaruvchi | Tavsif | Standart |
| --- | --- | --- |
| `BOT_TOKEN` | @BotFather'dan olingan token (**majburiy**) | — |
| `ADMIN_CHAT_ID` | `/admin` buyrug'iga ruxsat beriladigan chat id | — |
| `TRACKED_CURRENCIES` | Kuzatiladigan valyutalar (vergul bilan) | `USD,EUR,RUB,GBP,CNY,KZT,TRY,JPY,AED,CHF` |
| `NOTIFY_HOUR` | Kunlik bildirishnoma soati (Asia/Tashkent) | `9` |
| `DB_PATH` | SQLite fayl yo'li | `valyutax.db` |
| `WEBAPP_URL` | Mini App'ning ochiq HTTPS havolasi (berilsa, pastki menyuda "🌐 Web ilova" tugmasi chiqadi) | — |

## Buyruqlar

- `/start` — asosiy menyu
- `/kurs` — joriy kursni ko'rsatish
- `/obuna` — kunlik bildirishnomaga obuna bo'lish
- `/bekor` — obunani bekor qilish
- `/health` — bot va API'lar holati
- `/admin` — statistika (faqat `ADMIN_CHAT_ID`)

## Telegram Mini App

`webapp/` papkasida bot bilan bir xil `rates.py`/`db.py`dan foydalanadigan
FastAPI backend va statik frontend joylashgan.

```bash
uvicorn webapp.api:app --host 0.0.0.0 --port 8080
```

Mahalliy sinov uchun ochiq HTTPS havola kerak (Telegram Web App buni talab
qiladi), masalan:

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

Olingan havolani `.env` faylidagi `WEBAPP_URL`ga qo'ying — bot pastki
menyusida "🌐 Web ilova" tugmasi paydo bo'ladi. Doimiy ishlatish uchun
`webapp/`ni Vercel yoki boshqa hostingga joylashtirib, doimiy HTTPS
domendan foydalanish tavsiya etiladi.

## Ma'lumot manbalari

- [cbu.uz](https://cbu.uz) — rasmiy CBU JSON API (so'mga asoslangan kurslar)
- [open.er-api.com](https://open.er-api.com) — xalqaro valyutalar (API kalitsiz, bepul)
