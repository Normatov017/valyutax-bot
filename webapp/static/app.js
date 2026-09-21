const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const FLAGS = {
  USD: "🇺🇸", EUR: "🇪🇺", RUB: "🇷🇺", GBP: "🇬🇧", CNY: "🇨🇳",
  KZT: "🇰🇿", TRY: "🇹🇷", JPY: "🇯🇵", AED: "🇦🇪", CHF: "🇨🇭",
  UZS: "🇺🇿",
};

function flagFor(code) {
  return FLAGS[code] || "💱";
}

// Trading-terminal look: dashed crosshair following the cursor/touch, plus a
// dashed "last price" line with a floating badge at the right edge — Chart.js
// has neither built in, so both are small custom plugins.
const crosshairPlugin = {
  id: "crosshair",
  afterDraw(chart) {
    const active = chart.getActiveElements();
    if (!active.length) return;
    const { ctx, chartArea } = chart;
    const { x, y } = active[0].element;

    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    ctx.strokeStyle = chart.$crosshairColor || "rgba(120,120,130,0.5)";
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.moveTo(chartArea.left, y);
    ctx.lineTo(chartArea.right, y);
    ctx.stroke();
    ctx.restore();
  },
};

const lastPricePlugin = {
  id: "lastPrice",
  afterDatasetsDraw(chart) {
    const meta = chart.getDatasetMeta(0);
    const point = meta.data[meta.data.length - 1];
    const values = chart.data.datasets[0].data;
    if (!point || !values.length) return;

    const { ctx, chartArea } = chart;
    const color = chart.$primaryColor || "#2f80ed";
    const label = fmt(values[values.length - 1], 0);

    ctx.save();
    ctx.setLineDash([2, 3]);
    ctx.lineWidth = 1;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(chartArea.left, point.y);
    ctx.lineTo(chartArea.right, point.y);
    ctx.stroke();

    ctx.setLineDash([]);
    ctx.font = "700 10px -apple-system, BlinkMacSystemFont, sans-serif";
    const textWidth = ctx.measureText(label).width;
    const paddingX = 6;
    const badgeW = textWidth + paddingX * 2;
    const badgeH = 16;
    const badgeX = chartArea.right - badgeW;
    const badgeY = Math.min(Math.max(point.y - badgeH / 2, chartArea.top), chartArea.bottom - badgeH);

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4);
    ctx.fill();

    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, badgeX + badgeW / 2, badgeY + badgeH / 2 + 0.5);
    ctx.restore();
  },
};

if (window.Chart) {
  Chart.register(crosshairPlugin, lastPricePlugin);
}

let trackedCurrencies = [];
let latestRates = {};
let historyChart = null;
let quickAmountSelected = 1000;

function fmt(n, digits = 2) {
  return Number(n).toLocaleString("uz-UZ", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

const UZ_MONTHS = [
  "yanvar", "fevral", "mart", "aprel", "may", "iyun",
  "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
];

function formatFullDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day}-${UZ_MONTHS[month - 1]}, ${year}`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
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
  const historyChips = document.getElementById("history-chips");

  fromSelect.innerHTML = trackedCurrencies
    .map((c) => `<option value="${c}">${flagFor(c)} ${c}</option>`)
    .join("");
  toSelect.innerHTML =
    `<option value="UZS">🇺🇿 UZS</option>` +
    trackedCurrencies.map((c) => `<option value="${c}">${flagFor(c)} ${c}</option>`).join("");

  historyChips.innerHTML = trackedCurrencies
    .map((c, i) => `<button class="ccy-chip${i === 0 ? " active" : ""}" data-code="${c}">${c}</button>`)
    .join("");
  historyChips.querySelectorAll(".ccy-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      historyChips.querySelectorAll(".ccy-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      loadHistory();
    });
  });

  const quickWrap = document.getElementById("quick-amounts");
  [100, 500, 1000, 5000].forEach((amount) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip" + (amount === quickAmountSelected ? " selected" : "");
    chip.textContent = fmt(amount, 0);
    chip.addEventListener("click", () => {
      quickAmountSelected = amount;
      document.getElementById("convert-amount").value = amount;
      quickWrap.querySelectorAll(".chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      runConversion();
    });
    quickWrap.appendChild(chip);
  });
}

function formatTime(dateStr) {
  if (!dateStr) return "—";
  return `bugun, ${new Date().toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" })}`;
}

async function loadRates() {
  const card = document.getElementById("rates-card");
  const errorBlock = document.getElementById("rates-error");
  errorBlock.hidden = true;
  card.hidden = false;

  try {
    const data = await fetchJSON("/api/rates");
    document.getElementById("updated-at").textContent = formatTime(data.date);
    latestRates = {};

    card.innerHTML = data.currencies
      .map((c) => {
        latestRates[c.code] = c.rate;
        const prevRate = c.rate - c.diff;
        const pct = prevRate ? (c.diff / prevRate) * 100 : 0;
        const cls = c.diff > 0 ? "up" : c.diff < 0 ? "down" : "flat";
        const arrow = c.diff > 0 ? "▲" : c.diff < 0 ? "▼" : "—";
        const pctLabel = c.diff === 0 ? "O'zgarishsiz" : `${pct >= 0 ? "+" : ""}${fmt(pct)}%`;
        return `
          <div class="rate-row">
            <div class="rate-left">
              <div class="flag-badge">${flagFor(c.code)}</div>
              <div class="rate-names">
                <div class="rate-code">${c.code}</div>
                <div class="rate-name">${c.name}</div>
              </div>
            </div>
            <div class="rate-right">
              <div class="rate-value">${fmt(c.rate)} <span class="unit">so'm</span></div>
              <div class="rate-change ${cls}">${arrow} ${pctLabel}</div>
            </div>
          </div>`;
      })
      .join("");
  } catch (err) {
    card.hidden = true;
    errorBlock.hidden = false;
  }
}

function setupRetry() {
  document.getElementById("rates-retry").addEventListener("click", loadRates);
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
    runConversion();
  });

  document.getElementById("convert-from").addEventListener("change", runConversion);
  document.getElementById("convert-to").addEventListener("change", runConversion);
  document.getElementById("convert-amount").addEventListener("input", () => {
    document.querySelectorAll("#quick-amounts .chip").forEach((c) => c.classList.remove("selected"));
  });
  document.getElementById("convert-submit").addEventListener("click", runConversion);
}

async function runConversion() {
  const amount = parseFloat(document.getElementById("convert-amount").value);
  const from = document.getElementById("convert-from").value;
  const to = document.getElementById("convert-to").value;
  const resultEl = document.getElementById("convert-result");
  const hintEl = document.getElementById("convert-rate-hint");
  const toast = document.getElementById("convert-toast");
  const errorEl = document.getElementById("convert-error");

  toast.hidden = true;
  errorEl.hidden = true;

  if (!amount || amount <= 0) {
    return;
  }

  try {
    const data = await fetchJSON(`/api/convert?amount=${amount}&from=${from}&to=${to}`);
    resultEl.textContent = fmt(data.result);
    const unitRate = data.amount ? data.result / data.amount : 0;
    hintEl.textContent = `1 ${data.from} = ${fmt(unitRate)} ${data.to}`;

    document.getElementById("convert-toast-sub").textContent = `1 ${data.from} = ${fmt(unitRate)} ${data.to}`;
    toast.hidden = false;
    tg?.HapticFeedback?.notificationOccurred("success");

    clearTimeout(runConversion._toastTimer);
    runConversion._toastTimer = setTimeout(() => {
      toast.hidden = true;
    }, 4000);
  } catch (err) {
    resultEl.textContent = "0";
    hintEl.textContent = "";
    errorEl.textContent = `⚠️ ${err.message}`;
    errorEl.hidden = false;
  }
}

async function loadHistory() {
  const activeChip = document.querySelector(".ccy-chip.active");
  const code = activeChip ? activeChip.dataset.code : trackedCurrencies[0];

  const statsRow = document.getElementById("history-stats");
  const chartCard = document.getElementById("chart-card");
  const minmaxRow = document.getElementById("minmax-row");
  const emptyBlock = document.getElementById("history-empty");

  try {
    const data = await fetchJSON(`/api/history?code=${code}&days=30`);

    if (data.history.length < 2) {
      statsRow.hidden = true;
      chartCard.hidden = true;
      minmaxRow.hidden = true;
      emptyBlock.hidden = false;
      return;
    }

    emptyBlock.hidden = true;
    statsRow.hidden = false;
    chartCard.hidden = false;
    minmaxRow.hidden = false;

    const fullDates = data.history.map((h) => h.date);
    const labels = data.history.map((h) => h.date.slice(5));
    const values = data.history.map((h) => h.rate);
    const current = values[values.length - 1];
    const first = values[0];
    const changePct = first ? ((current - first) / first) * 100 : 0;
    const max = Math.max(...values);
    const min = Math.min(...values);

    document.getElementById("stat-current").textContent = `${fmt(current)}`;
    const changeEl = document.getElementById("stat-change");
    changeEl.textContent = `${changePct >= 0 ? "+" : ""}${fmt(changePct)}%`;
    changeEl.className = "stat-value " + (changePct >= 0 ? "up" : "down");
    document.getElementById("stat-max").textContent = fmt(max);
    document.getElementById("stat-min").textContent = `${fmt(min)} UZS`;
    document.getElementById("chart-title").textContent = `${code} / UZS`;
    document.getElementById("chart-legend-label").textContent = `${code} kursi (so'mda)`;

    const canvas = document.getElementById("history-chart");
    if (historyChart) {
      historyChart.destroy();
    }
    const primaryColor = cssVar("--primary") || "#2f80ed";
    const surfaceColor = cssVar("--surface") || "#ffffff";
    const textColor = cssVar("--text") || "#0b0b0f";
    const mutedColor = cssVar("--text-muted") || "#8a8d93";
    const borderColor = cssVar("--border") || "rgba(0,0,0,0.08)";
    const upColor = cssVar("--up") || "#22c55e";
    const downColor = cssVar("--down") || "#ef4444";
    const crosshairColor = mutedColor;
    const lastSegmentUp = values[values.length - 1] >= values[values.length - 2];

    const barColor = (i) => (i > 0 && values[i] < values[i - 1] ? downColor : upColor);

    // Bars need a finite, nearby base — Chart.js's default base (pixel for
    // value 0) extrapolates wildly off-canvas when the axis floor sits far
    // above 0 (as currency rates do), which breaks hit-testing for hover.
    const dataMin = Math.min(...values);
    const dataMax = Math.max(...values);
    const span = dataMax - dataMin || dataMax * 0.01 || 1;
    const chartFloor = dataMin - span * 0.25;
    const chartCeil = dataMax + span * 0.25;

    historyChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            data: values,
            base: chartFloor,
            backgroundColor: (barCtx) => barColor(barCtx.dataIndex),
            hoverBackgroundColor: (barCtx) => barColor(barCtx.dataIndex),
            borderRadius: 2,
            barPercentage: 0.55,
            categoryPercentage: 0.85,
          },
        ],
      },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        layout: { padding: { right: 4 } },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: surfaceColor,
            titleColor: textColor,
            bodyColor: textColor,
            borderColor,
            borderWidth: 1,
            padding: 10,
            displayColors: false,
            titleFont: { size: 12, weight: "600" },
            bodyFont: { size: 14, weight: "700" },
            callbacks: {
              title: (items) => formatFullDate(fullDates[items[0].dataIndex]),
              label: (item) => `${fmt(item.parsed.y)} so'm`,
              labelTextColor: (item) => {
                const i = item.dataIndex;
                return i > 0 && values[i] < values[i - 1] ? downColor : upColor;
              },
            },
          },
        },
        scales: {
          y: {
            min: chartFloor,
            max: chartCeil,
            position: "right",
            ticks: { display: false },
            grid: { color: borderColor, drawTicks: false },
          },
          x: {
            ticks: { color: mutedColor, font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 6 },
            grid: { display: false },
          },
        },
      },
    });
    historyChart.$primaryColor = lastSegmentUp ? upColor : downColor;
    historyChart.$crosshairColor = crosshairColor;
  } catch (err) {
    statsRow.hidden = true;
    chartCard.hidden = true;
    minmaxRow.hidden = true;
    emptyBlock.hidden = false;
    emptyBlock.querySelector(".state-title").textContent = "Tarixni yuklab bo'lmadi";
    emptyBlock.querySelector(".state-desc").textContent = err.message;
  }
}

async function init() {
  setupTabs();
  setupRetry();
  setupConvert();
  await loadConfig();
  await loadRates();
  await runConversion();
}

init();
