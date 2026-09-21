"""
Valyuta kurslarini olib keluvchi funksiyalar.

- CBU (O'zbekiston Markaziy banki) rasmiy kurslari — so'mga asoslangan
  konvertatsiya uchun (masalan 100 USD -> so'm).
- open.er-api.com — xalqaro valyutalar orasidagi konvertatsiya uchun
  (masalan 100 EUR -> GBP), API kalitsiz, bepul.

Ikkala manba ham qisqa vaqt (TTL) xotirada keshlanadi, shu bilan har bir
foydalanuvchi xabari uchun tashqi API'ga alohida so'rov yubormaydi.
"""

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

CBU_ALL_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
CBU_DATE_URL_TEMPLATE = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/all/{date}/"
INTL_URL_TEMPLATE = "https://open.er-api.com/v6/latest/{base}"

_CACHE_TTL_SECONDS = 300

_cbu_cache: dict = {"rates": None, "fetched_at": 0.0}
_intl_cache: dict = {"rates": None, "fetched_at": 0.0}

# So'nggi muvaffaqiyatli olingan kurs vaqti — /health va admin panelida ko'rsatiladi.
last_success: dict = {"cbu": None, "intl": None}

_session = requests.Session()
_retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))


class RateFetchError(RuntimeError):
    pass


def fetch_cbu_rates(force: bool = False) -> dict[str, dict]:
    """Barcha valyutalar uchun {code: {rate, diff, nominal, name, date}} qaytaradi.

    `rate`/`diff` allaqachon 1 birlikka nisbatan hisoblangan (Nominal'ga bo'lingan).
    """
    now = time.monotonic()
    if not force and _cbu_cache["rates"] and now - _cbu_cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return _cbu_cache["rates"]

    try:
        response = _session.get(CBU_ALL_URL, timeout=10)
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("CBU so'rovi muvaffaqiyatsiz: %s", exc)
        if _cbu_cache["rates"]:
            return _cbu_cache["rates"]
        raise RateFetchError(f"CBU API xato: {exc}") from exc

    rates: dict[str, dict] = {}
    for item in raw:
        try:
            nominal = float(item["Nominal"])
            rate = float(item["Rate"]) / nominal
            diff = float(item["Diff"]) / nominal
        except (KeyError, ValueError, ZeroDivisionError):
            continue
        rates[item["Ccy"]] = {
            "rate": rate,
            "diff": diff,
            "nominal": nominal,
            "name": item.get("CcyNm_UZ", item["Ccy"]),
            "date": item.get("Date", ""),
        }

    _cbu_cache["rates"] = rates
    _cbu_cache["fetched_at"] = now
    last_success["cbu"] = time.time()
    return rates


def fetch_international_rates(base: str = "USD", force: bool = False) -> dict[str, float]:
    now = time.monotonic()
    if not force and _intl_cache["rates"] and now - _intl_cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return _intl_cache["rates"]

    try:
        response = _session.get(INTL_URL_TEMPLATE.format(base=base), timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("result") != "success":
            raise RateFetchError(f"Xalqaro API muvaffaqiyatsiz: {data}")
        rates = data["rates"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Xalqaro API so'rovi muvaffaqiyatsiz: %s", exc)
        if _intl_cache["rates"]:
            return _intl_cache["rates"]
        raise RateFetchError(f"Xalqaro API xato: {exc}") from exc

    _intl_cache["rates"] = rates
    _intl_cache["fetched_at"] = now
    last_success["intl"] = time.time()
    return rates


def convert_international(amount: float, from_code: str, to_code: str) -> float:
    rates = fetch_international_rates("USD")
    if from_code not in rates or to_code not in rates:
        raise RateFetchError(f"{from_code} yoki {to_code} xalqaro ro'yxatda topilmadi")
    usd_amount = amount / rates[from_code]
    return usd_amount * rates[to_code]


def fetch_cbu_rates_for_date(iso_date: str) -> dict[str, dict]:
    """`iso_date` — 'YYYY-MM-DD' (CBU arxivi faqat shu formatni to'g'ri qabul qiladi,
    'DD.MM.YYYY' formatida har doim joriy kunni qaytaradi).

    Dam olish kunlari uchun CBU o'zining oxirgi ish kunidagi kursini, haqiqiy sanasi
    bilan qaytaradi — shuning uchun natijadagi `date` maydoni so'ralgan sanadan farq
    qilishi mumkin.
    """
    try:
        response = _session.get(CBU_DATE_URL_TEMPLATE.format(date=iso_date), timeout=10)
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RateFetchError(f"CBU tarixiy so'rovi xato ({iso_date}): {exc}") from exc

    result: dict[str, dict] = {}
    for item in raw:
        try:
            nominal = float(item["Nominal"])
            rate = float(item["Rate"]) / nominal
            day, month, year = item.get("Date", "").split(".")
        except (KeyError, ValueError, ZeroDivisionError):
            continue
        result[item["Ccy"]] = {"rate": rate, "date": f"{year}-{month}-{day}"}
    return result


def backfill_history(tracked_currencies: list[str], days: int = 7) -> int:
    """So'nggi `days` ish kuni uchun tarixni CBU arxividan to'ldiradi (allaqachon
    yetarli tarix bo'lsa, tashqi so'rov yubormaydi — tez va idempotent)."""
    import db as _db
    from datetime import date as _date, timedelta as _timedelta

    if not tracked_currencies:
        return 0

    existing = _db.get_rate_history(tracked_currencies[0], days=days)
    if len(existing) >= days:
        return 0

    filled = 0
    seen_dates: set[str] = {d for d, _ in existing}
    today = _date.today()

    for offset in range(1, days + 4):
        if len(seen_dates) >= days:
            break
        day_rates = None
        try:
            day_rates = fetch_cbu_rates_for_date((today - _timedelta(days=offset)).isoformat())
        except RateFetchError as exc:
            logger.warning("Tarixni to'ldirishda xato: %s", exc)
            continue

        sample = next(iter(day_rates.values()), None)
        actual_date = sample["date"] if sample else None
        if not actual_date or actual_date in seen_dates:
            continue
        seen_dates.add(actual_date)

        for code in tracked_currencies:
            info = day_rates.get(code)
            if info:
                _db.save_rate_snapshot(actual_date, code, info["rate"])
                filled += 1

    return filled


def convert(amount: float, from_code: str, to_code: str | None) -> tuple[float, str]:
    """`amount` miqdorini `from_code`dan `to_code`ga aylantiradi.

    `to_code` berilmasa, so'mga (UZS) aylantiriladi. Natija va haqiqiy
    ishlatilgan target kodini (tuple) qaytaradi.
    """
    from_code = from_code.upper()
    to_code = (to_code or "UZS").upper()

    if from_code == to_code:
        return amount, to_code

    cbu = fetch_cbu_rates()

    if to_code == "UZS" and from_code in cbu:
        return amount * cbu[from_code]["rate"], to_code

    if from_code == "UZS" and to_code in cbu:
        return amount / cbu[to_code]["rate"], to_code

    if from_code == "UZS" or to_code == "UZS":
        if "USD" not in cbu:
            raise RateFetchError("CBU'dan USD kursi olinmadi")
        usd_uzs = cbu["USD"]["rate"]
        if from_code == "UZS":
            usd_amount = amount / usd_uzs
            result = convert_international(usd_amount, "USD", to_code)
        else:
            usd_amount = convert_international(amount, from_code, "USD")
            result = usd_amount * usd_uzs
        return result, to_code

    return convert_international(amount, from_code, to_code), to_code
