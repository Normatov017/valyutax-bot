"""
Valyuta kurslarini olib keluvchi funksiyalar.

- CBU (O'zbekiston Markaziy banki) rasmiy kurslari — so'mga asoslangan
  konvertatsiya uchun (masalan 100 USD -> so'm).
- open.er-api.com — xalqaro valyutalar orasidagi konvertatsiya uchun
  (masalan 100 EUR -> GBP), API kalitsiz, bepul.

Ikkala manba ham qisqa vaqt (TTL) xotirada keshlanadi, shu bilan har bir
foydalanuvchi xabari uchun tashqi API'ga alohida so'rov yubormaydi.
"""

import time

import requests

CBU_ALL_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
INTL_URL_TEMPLATE = "https://open.er-api.com/v6/latest/{base}"

_CACHE_TTL_SECONDS = 300

_cbu_cache: dict = {"rates": None, "fetched_at": 0.0}
_intl_cache: dict = {"rates": None, "fetched_at": 0.0}


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
        response = requests.get(CBU_ALL_URL, timeout=10)
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError) as exc:
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
    return rates


def fetch_international_rates(base: str = "USD", force: bool = False) -> dict[str, float]:
    now = time.monotonic()
    if not force and _intl_cache["rates"] and now - _intl_cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return _intl_cache["rates"]

    try:
        response = requests.get(INTL_URL_TEMPLATE.format(base=base), timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("result") != "success":
            raise RateFetchError(f"Xalqaro API muvaffaqiyatsiz: {data}")
        rates = data["rates"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        if _intl_cache["rates"]:
            return _intl_cache["rates"]
        raise RateFetchError(f"Xalqaro API xato: {exc}") from exc

    _intl_cache["rates"] = rates
    _intl_cache["fetched_at"] = now
    return rates


def convert_international(amount: float, from_code: str, to_code: str) -> float:
    rates = fetch_international_rates("USD")
    if from_code not in rates or to_code not in rates:
        raise RateFetchError(f"{from_code} yoki {to_code} xalqaro ro'yxatda topilmadi")
    usd_amount = amount / rates[from_code]
    return usd_amount * rates[to_code]


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
