const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

let trackedCurrencies = [];
let historyChart = null;

function fmt(n, digits = 2) {
  return Number(n).toLocaleString("uz-UZ", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `So'rov xato: ${res.status}`);
  }
  return res.json();
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");

      if (tab.dataset.tab === "history") {
        loadHistory();
      }
    });
  });
}

async function loadConfig() {
  const config = await fetchJSON("/api/config");
  trackedCurrencies = config.tracked_currencies;

  const fromSelect = document.getElementById("convert-from");
  const toSelect = document.getElementById("convert-to");
  const historySelect = document.getElementById("history-currency");

  fromSelect.innerHTML = trackedCurrencies.map((c) => `<option value="${c}">${c}</option>`).join("");
  toSelect.innerHTML =
    `<option value="UZS">UZS (so'm)</option>` +
    trackedCurrencies.map((c) => `<option value="${c}">${c}</option>`).join("");
  historySelect.innerHTML = trackedCurrencies.map((c) => `<option value="${c}">${c}</option>`).join("");
}

async function loadRates() {
  const list = document.getElementById("rates-list");
  try {
    const data = await fetchJSON("/api/rates");
    document.getElementById("updated-at").textContent = data.date ? `Sana: ${data.date}` : "";

    list.innerHTML = data.currencies
      .map((c) => {
        const cls = c.diff > 0 ? "up" : c.diff < 0 ? "down" : "flat";
        const arrow = c.diff > 0 ? "▲" : c.diff < 0 ? "▼" : "•";
        return `
          <div class="rate-card">
            <div>
              <div class="code">${c.code}</div>
              <div class="name">${c.name}</div>
            </div>
            <div>
              <div class="rate-value">${fmt(c.rate)} so'm</div>
              <div class="diff ${cls}">${arrow} ${c.diff >= 0 ? "+" : ""}${fmt(c.diff)}</div>
            </div>
          </div>`;
      })
      .join("");
  } catch (err) {
    list.innerHTML = `<p class="muted">⚠️ ${err.message}</p>`;
  }
}

function setupConvert() {
  document.getElementById("convert-swap").addEventListener("click", () => {
    const fromSelect = document.getElementById("convert-from");
    const toSelect = document.getElementById("convert-to");
    const currentFrom = fromSelect.value;
    const currentTo = toSelect.value;

    if ([...fromSelect.options].some((o) => o.value === currentTo)) {
      fromSelect.value = currentTo;
    }
    if ([...toSelect.options].some((o) => o.value === currentFrom)) {
      toSelect.value = currentFrom;
    }
  });

  document.getElementById("convert-submit").addEventListener("click", async () => {
    const amount = parseFloat(document.getElementById("convert-amount").value);
    const from = document.getElementById("convert-from").value;
    const to = document.getElementById("convert-to").value;
    const resultEl = document.getElementById("convert-result");

    if (!amount || amount <= 0) {
      resultEl.textContent = "Miqdorni kiriting";
      return;
    }

    resultEl.textContent = "…";
    try {
      const data = await fetchJSON(
        `/api/convert?amount=${amount}&from=${from}&to=${to}`
      );
      resultEl.textContent = `${fmt(data.amount, 0)} ${data.from} = ${fmt(data.result)} ${data.to}`;
      tg?.HapticFeedback?.notificationOccurred("success");
    } catch (err) {
      resultEl.textContent = `⚠️ ${err.message}`;
    }
  });
}

async function loadHistory() {
  const code = document.getElementById("history-currency").value;
  const emptyMsg = document.getElementById("history-empty");
  const canvas = document.getElementById("history-chart");

  try {
    const data = await fetchJSON(`/api/history?code=${code}&days=30`);

    if (data.history.length < 2) {
      emptyMsg.hidden = false;
      canvas.hidden = true;
      return;
    }

    emptyMsg.hidden = true;
    canvas.hidden = false;

    const labels = data.history.map((h) => h.date);
    const values = data.history.map((h) => h.rate);

    if (historyChart) {
      historyChart.destroy();
    }
    historyChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: `${code}/UZS`,
            data: values,
            borderColor: "#2e86de",
            backgroundColor: "rgba(46,134,222,0.15)",
            tension: 0.3,
            fill: true,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: false } },
      },
    });
  } catch (err) {
    emptyMsg.hidden = false;
    emptyMsg.textContent = `⚠️ ${err.message}`;
    canvas.hidden = true;
  }
}

async function init() {
  setupTabs();
  setupConvert();
  await loadConfig();
  await loadRates();

  document.getElementById("history-currency").addEventListener("change", loadHistory);
}

init();
