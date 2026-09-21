"""
ValyutaX Mini App uchun FastAPI backend.

bot.py bilan bir xil `rates.py`/`db.py` modullaridan foydalanadi — shuning
uchun Mini App'dagi kurs va tarix ma'lumotlari botdagi bilan izchil.

Ishga tushirish:
    uvicorn webapp.api:app --host 0.0.0.0 --port 8080
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import db  # noqa: E402
import rates  # noqa: E402

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

TRACKED_CURRENCIES = [
    code.strip().upper()
    for code in os.environ.get(
        "TRACKED_CURRENCIES", "USD,EUR,RUB,GBP,CNY,KZT,TRY,JPY,AED,CHF"
    ).split(",")
    if code.strip()
]

db.init_db()

app = FastAPI(title="ValyutaX API")


@app.get("/api/config")
def get_config() -> dict:
    return {"tracked_currencies": TRACKED_CURRENCIES}


@app.get("/api/rates")
def get_rates() -> dict:
    try:
        cbu = rates.fetch_cbu_rates()
    except rates.RateFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    currencies = []
    date_str = ""
    for code in TRACKED_CURRENCIES:
        info = cbu.get(code)
        if not info:
            continue
        currencies.append(
            {
                "code": code,
                "name": info["name"],
                "rate": info["rate"],
                "diff": info["diff"],
            }
        )
        date_str = info.get("date", date_str)

    return {"date": date_str, "currencies": currencies}


@app.get("/api/convert")
def convert(
    amount: float = Query(..., gt=0),
    from_code: str = Query(..., alias="from"),
    to_code: str = Query("UZS", alias="to"),
) -> dict:
    try:
        result, target = rates.convert(amount, from_code, to_code)
    except rates.RateFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.log_usage(from_code.upper())
    return {
        "amount": amount,
        "from": from_code.upper(),
        "to": target,
        "result": result,
    }


@app.get("/api/history")
def get_history(code: str, days: int = 30) -> dict:
    code = code.upper()
    db.log_usage(code)
    history = db.get_rate_history(code, days=days)
    return {
        "code": code,
        "history": [{"date": date_, "rate": rate_} for date_, rate_ in history],
    }


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
