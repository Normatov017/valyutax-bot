# ValyutaX Bot

O'zbekiston Markaziy banki (CBU) rasmiy kurslari va xalqaro kurslar
asosida ishlaydigan valyuta Telegram boti.

## Imkoniyatlar

- **Joriy kurs** — CBU'ning rasmiy kurslari (USD, EUR, RUB, GBP va h.k.), o'zgarish (▲/▼) bilan
- **Konvertatsiya** — erkin matn orqali: `100 USD` (so'mga) yoki `100 USD EUR` (ikki valyuta orasida)
- **Kurs tarixi/grafik** — bot ishlagan har bir kun uchun kurs nuqtasi saqlanadi va grafik chizib beriladi
- **Kunlik bildirishnoma** — kurs o'zgargan kunlari obunachilarga avtomatik xabar (`/obuna`, `/bekor`)

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
| `TRACKED_CURRENCIES` | Kuzatiladigan valyutalar (vergul bilan) | `USD,EUR,RUB,GBP` |
| `NOTIFY_HOUR` | Kunlik bildirishnoma soati (Asia/Tashkent) | `9` |
| `DB_PATH` | SQLite fayl yo'li | `valyutax.db` |

## Buyruqlar

- `/start` — asosiy menyu
- `/kurs` — joriy kursni ko'rsatish
- `/obuna` — kunlik bildirishnomaga obuna bo'lish
- `/bekor` — obunani bekor qilish

## Ma'lumot manbalari

- [cbu.uz](https://cbu.uz) — rasmiy CBU JSON API (so'mga asoslangan kurslar)
- [open.er-api.com](https://open.er-api.com) — xalqaro valyutalar (API kalitsiz, bepul)
