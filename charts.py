"""Kurs tarixi grafigini (PNG) yasab beruvchi funksiya."""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_history_chart(currency_code: str, history: list[tuple[str, float]]) -> io.BytesIO:
    dates = [date for date, _ in history]
    values = [rate for _, rate in history]

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    ax.plot(dates, values, marker="o", color="#2E86DE", linewidth=2)
    ax.set_title(f"{currency_code}/UZS kurs tarixi")
    ax.set_ylabel("so'm")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate(rotation=45)
    if len(dates) > 10:
        step = max(1, len(dates) // 10)
        ax.set_xticks(dates[::step])
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf
