// Independent analytics section. Its only data source is a public aggregate snapshot.
const root = document.querySelector("[data-ugc-analytics]");
const DAY = 86400000;
const COLORS = ["#92a7ff", "#73d8ba", "#efb77b", "#d89cd8", "#77c5e5", "#626e89"];
const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const format = value => value == null || !Number.isFinite(value) ? "—" : integer.format(value);
const mean = value => value == null || !Number.isFinite(value) ? "—" : decimal.format(value);
const dayKey = milliseconds => new Date(milliseconds).toISOString().slice(0, 10);
const dayTime = key => Date.parse(`${key}T00:00:00Z`);
const shortDay = key => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(dayTime(key));
const dateTime = value => new Intl.DateTimeFormat("en-US", {
  month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
}).format(new Date(value));
const stamp = seconds => seconds ? dateTime(seconds * 1000) : "not available";
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const svgEl = (tag, attrs = {}, text) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text != null) node.textContent = text;
  return node;
};

// Pure aggregation is also exercised by the Node checks, without a browser or private data.
export function selectPeriod(data, range) {
  const last = dayKey(Date.parse(data.generatedAt));
  const first = data.coverage.firstRecordedDay || last;
  const start = range === "all" ? first : dayKey(dayTime(last) - (Number(range) - 1) * DAY);
  const lookup = new Map(data.items.map(item => [item.key, item]));
  const days = new Map();
  for (let time = dayTime(start); time <= dayTime(last); time += DAY) {
    const date = dayKey(time);
    days.set(date, { date, sales: 0, earnedRobux: data.includes.revenue ? 0 : null, entries: new Map() });
  }
  const items = new Map();
  const location = { inGame: 0, website: 0, other: 0 };
  let sales = 0, earnedRobux = data.includes.revenue ? 0 : null;
  for (const bucket of data.daily) {
    const day = days.get(bucket.date);
    if (!day) continue;
    for (const entry of bucket.items) {
      const definition = lookup.get(entry.key);
      if (!definition) continue;
      if (!items.has(entry.key)) items.set(entry.key, { ...definition, sales: 0, earnedRobux: data.includes.revenue ? 0 : null });
      const item = items.get(entry.key);
      item.sales += entry.sales;
      day.sales += entry.sales;
      sales += entry.sales;
      if (data.includes.revenue) {
        for (const target of [item, day]) {
          target.earnedRobux = target.earnedRobux == null || entry.earnedRobux == null ? null : target.earnedRobux + entry.earnedRobux;
        }
        earnedRobux = earnedRobux == null || entry.earnedRobux == null ? null : earnedRobux + entry.earnedRobux;
      }
      day.entries.set(entry.key, entry);
      for (const key of Object.keys(location)) location[key] += entry[key] || 0;
    }
  }
  return { start, last, days: [...days.values()], items: [...items.values()], sales, earnedRobux, location };
}

function validate(data) {
  if (data.schemaVersion !== 1 || !Number.isFinite(Date.parse(data.generatedAt)) ||
      !Number.isSafeInteger(data.group?.id) || !Array.isArray(data.daily) || !Array.isArray(data.items) ||
      !data.coverage || typeof data.includes?.revenue !== "boolean") throw new Error("Unsupported snapshot");
  const first = data.coverage.firstRecordedDay;
  if (first && (!/^\d{4}-\d{2}-\d{2}$/.test(first) || !Number.isFinite(dayTime(first)) ||
      dayTime(first) > Date.parse(data.generatedAt) || Date.parse(data.generatedAt) - dayTime(first) > DAY * 36500)) {
    throw new Error("Invalid history range");
  }
  const keys = new Set();
  for (const item of data.items) {
    if (typeof item.key !== "string" || typeof item.name !== "string" || keys.has(item.key) ||
        (item.assetId != null && (!Number.isSafeInteger(item.assetId) || item.assetId <= 0))) throw new Error("Invalid item");
    keys.add(item.key);
  }
  for (const bucket of data.daily) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(bucket.date) || !Number.isFinite(dayTime(bucket.date)) || !Array.isArray(bucket.items)) throw new Error("Invalid date");
    for (const entry of bucket.items) {
      if (!keys.has(entry.key) || !Number.isSafeInteger(entry.sales) || entry.sales < 0 ||
          (data.includes.revenue && entry.earnedRobux != null && !Number.isFinite(entry.earnedRobux))) throw new Error("Invalid totals");
    }
  }
  return data;
}

function setup(data) {
  const $ = name => root.querySelector(`[data-${name}]`);
  let range = "30", metric = "sales", expanded = false;
  const narrow = window.matchMedia("(max-width: 750px)");
  const groupLink = $("group-link");
  groupLink.textContent = data.group.name;
  groupLink.href = `https://www.roblox.com/communities/${data.group.id}`;
  groupLink.target = "_blank";
  groupLink.rel = "noopener noreferrer";
  $("status").textContent = `Snapshot · ${dateTime(data.generatedAt)}`;
  $("dashboard").hidden = false;
  $("revenue-control").hidden = !data.includes.revenue;
  for (const name of ["daily-revenue", "item-revenue", "item-average"]) $(name).hidden = !data.includes.revenue;
  const account = document.querySelector("[data-account-balance]");
  if (account && data.includes.balance && data.accountBalance?.robux != null) {
    account.hidden = false;
    account.querySelector("[data-balance-value]").textContent = format(data.accountBalance.robux);
    account.querySelector("[data-balance-date]").textContent = `Recorded ${stamp(data.accountBalance.asOf)}`;
  }
  $("coverage").textContent = `Exported ${dateTime(data.generatedAt)}. ` +
    (data.coverage.firstRecordedDay ? `First recorded sale: ${data.coverage.firstRecordedDay}. ` : "") +
    (data.coverage.syncedThrough ? `Collector synced through ${dateTime(data.coverage.syncedThrough)}.` : "Collector sync time unavailable.");

  function statistic(label, value, note) {
    const card = el("div", null, "ugc-stat");
    card.append(el("span", label, "ugc-stat-label"), el("strong", value, "ugc-stat-value"));
    if (note) card.append(el("span", note, "ugc-stat-note"));
    return card;
  }

  function render() {
    const period = selectPeriod(data, range);
    const sorted = [...period.items].sort((a, b) => (b[metric] ?? -Infinity) - (a[metric] ?? -Infinity) || b.sales - a.sales || a.name.localeCompare(b.name));
    for (const button of root.querySelectorAll("[data-range]")) button.setAttribute("aria-pressed", String(button.dataset.range === range));
    for (const button of root.querySelectorAll("[data-metric]")) button.setAttribute("aria-pressed", String(button.dataset.metric === metric));
    $("date-range").textContent = `${shortDay(period.start)} – ${shortDay(period.last)}, ${period.last.slice(0, 4)} · UTC`;
    const summary = [statistic("Sales", format(period.sales), "recorded transactions")];
    if (data.includes.revenue) summary.push(statistic("Robux earned", format(period.earnedRobux), "creator revenue after fees"));
    summary.push(statistic("Sales / day", mean(period.sales / period.days.length), `${period.days.length} calendar days, including today`));
    if (data.includes.revenue) {
      summary.push(statistic("Robux / day", mean(period.earnedRobux == null ? null : period.earnedRobux / period.days.length), "calendar-day average"));
      summary.push(statistic("Robux / sale", mean(period.sales ? period.earnedRobux == null ? null : period.earnedRobux / period.sales : null), "average recorded revenue"));
    }
    const best = [...period.days].filter(day => day[metric] != null).sort((a, b) => b[metric] - a[metric])[0];
    summary.push(statistic(metric === "sales" ? "Best day / sales" : "Best day / Robux", format(best?.[metric]), best?.[metric] ? shortDay(best.date) : "no activity in this range"));
    $("summary").replaceChildren(...summary);
    renderChart(period, sorted);
    renderStore(period);
    renderLocations(period);
    renderItems(period, sorted);
    const dailyRows = [...period.days].reverse().map(day => {
      const row = el("tr");
      row.append(el("td", `${day.date}${day.date === period.last ? " (partial day)" : ""}`), el("td", format(day.sales)));
      if (data.includes.revenue) row.append(el("td", format(day.earnedRobux)));
      return row;
    });
    $("daily-table").replaceChildren(...dailyRows);
  }

  function renderChart(period, sorted) {
    const chartWidth = narrow.matches ? 600 : 1000;
    const svg = svgEl("svg", { viewBox: `0 0 ${chartWidth} 300`, role: "img", "aria-labelledby": "ugc-chart-title ugc-chart-description" });
    svg.append(svgEl("title", { id: "ugc-chart-title" }, `${metric === "sales" ? "Sales" : "Robux earned"} by UTC day`),
      svgEl("desc", { id: "ugc-chart-description" }, `${period.days.length} days from ${period.start} to ${period.last}. Stacked by top items. The daily numbers table provides the same totals.`));
    const chart = { left: narrow.matches ? 58 : 65, top: 16, width: chartWidth - (narrow.matches ? 74 : 80), height: 235 };
    const max = Math.max(1, ...period.days.map(day => day[metric] ?? 0));
    const ceiling = max * 1.12;
    for (let tick = 0; tick <= 4; tick++) {
      const y = chart.top + chart.height - tick / 4 * chart.height;
      svg.append(svgEl("line", { x1: chart.left, y1: y, x2: chart.left + chart.width, y2: y, stroke: "#303545", "stroke-width": 1 }),
        svgEl("text", { x: chart.left - 12, y: y + 4, "text-anchor": "end" }, narrow.matches ?
          new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(ceiling * tick / 4) : format(ceiling * tick / 4)));
    }
    const leaders = sorted.slice(0, 5);
    const leaderKeys = new Set(leaders.map(item => item.key));
    const series = [...leaders.map(item => ({ key: item.key, name: item.name })), ...(sorted.length > 5 ? [{ key: null, name: "Other items" }] : [])];
    const slot = chart.width / period.days.length;
    const width = Math.max(.6, slot * .72);
    const labelIndexes = new Set([0, Math.floor((period.days.length - 1) / 4), Math.floor((period.days.length - 1) / 2), Math.floor((period.days.length - 1) * .75), period.days.length - 1]);
    if (narrow.matches) { labelIndexes.clear(); labelIndexes.add(0); labelIndexes.add(Math.floor((period.days.length - 1) / 2)); labelIndexes.add(period.days.length - 1); }
    period.days.forEach((day, index) => {
      const x = chart.left + index * slot + (slot - width) / 2;
      let stacked = 0;
      series.forEach((item, seriesIndex) => {
        const entries = item.key ? [day.entries.get(item.key)].filter(Boolean) : [...day.entries.values()].filter(entry => !leaderKeys.has(entry.key));
        const amount = entries.reduce((sum, entry) => sum + (entry[metric] ?? 0), 0);
        if (amount <= 0) return;
        const height = amount / ceiling * chart.height;
        const rect = svgEl("rect", { x, y: chart.top + chart.height - (stacked / ceiling * chart.height) - height, width, height,
          fill: COLORS[seriesIndex], class: "ugc-bar" });
        rect.append(svgEl("title", {}, `${day.date} · ${item.name}: ${format(amount)} ${metric === "sales" ? "sales" : "Robux"}`));
        svg.append(rect);
        stacked += amount;
      });
      if (day[metric] == null) svg.append(svgEl("text", { x: x + width / 2, y: chart.top + chart.height - 5, "text-anchor": "middle" }, "?"));
      if (labelIndexes.has(index)) svg.append(svgEl("text", { x: x + width / 2, y: 281, "text-anchor": "middle" }, shortDay(day.date)));
    });
    $("chart").replaceChildren(svg);
    $("legend").replaceChildren(...series.map((item, index) => {
      const entry = el("span");
      const swatch = el("i"); swatch.style.backgroundColor = COLORS[index];
      entry.append(swatch, document.createTextNode(item.name));
      return entry;
    }));
    $("chart-note").textContent = (period.sales ? "Hover a bar for its item and total. " : "No recorded sales in this range. ") +
      "Today is partial. Empty days mean no sales recorded in this snapshot; ? means revenue is unknown.";
  }

  function renderStore(period) {
    const stats = [];
    const stat = (label, value, title) => {
      const entry = el("div");
      const term = el("dt", label);
      if (title) term.title = title;
      entry.append(term, el("dd", value)); stats.push(entry);
    };
    if (data.includes.financials) {
      stat("Pending Robux", format(data.financials?.pending));
      stat("Group funds", format(data.financials?.funds));
    }
    stat("Items on sale", format(data.itemsOnSale?.count));
    if (data.includes.financials) {
      const average = period.sales && period.earnedRobux != null ? period.earnedRobux / period.sales : null;
      const count = data.itemsOnSale?.count;
      const pending = data.financials?.pending;
      const ratio = count > 0 && average > 0 && pending != null ? pending / count / average : null;
      stat("Golden ratio", mean(ratio), "(Pending Robux ÷ items on sale) ÷ average Robux per sale in the selected range");
      stat("Roblox month summary / Robux", format(data.financials?.sales_month), "Latest item-sale Robux reported by Roblox’s Month revenue summary; independent of the selected chart range");
    }
    $("store-stats").replaceChildren(...stats);
    $("store-date").textContent = `Catalog: ${stamp(data.itemsOnSale?.asOf)}.` +
      (data.includes.financials ? ` Funds snapshot: ${stamp(data.financials?.updated)}. Cached figures can have different ages; golden ratio uses this date range’s average.` : "");
  }

  function renderLocations(period) {
    const definitions = [["inGame", "In-game", COLORS[0]], ["website", "Website", COLORS[1]], ["other", "Other / unknown", COLORS[5]]];
    const bars = [], labels = [];
    for (const [key, label, color] of definitions) {
      const count = period.location[key];
      const percent = period.sales ? count / period.sales * 100 : 0;
      if (count) { const bar = el("span"); bar.style.width = `${percent}%`; bar.style.backgroundColor = color; bars.push(bar); }
      const row = el("div"), term = el("dt"), swatch = el("i");
      swatch.style.backgroundColor = color;
      term.append(swatch, document.createTextNode(label));
      row.append(term, el("dd", `${format(count)} · ${mean(percent)}%`)); labels.push(row);
    }
    $("location-bar").replaceChildren(...bars);
    $("locations").replaceChildren(...labels);
  }

  function renderItems(period, sorted) {
    const total = period[metric];
    const visible = expanded ? sorted : sorted.slice(0, 10);
    const rows = visible.map((item, index) => {
      const row = el("tr"), name = el("td");
      name.append(el("span", String(index + 1).padStart(2, "0"), "ugc-rank"));
      const label = el(item.assetId ? "a" : "span", item.name);
      if (item.assetId) { label.href = `https://www.roblox.com/catalog/${item.assetId}`; label.target = "_blank"; label.rel = "noopener noreferrer"; }
      name.append(label); row.append(name, el("td", format(item.sales)));
      if (data.includes.revenue) row.append(el("td", format(item.earnedRobux)), el("td", mean(item.earnedRobux == null ? null : item.earnedRobux / item.sales)));
      row.append(el("td", total && item[metric] != null ? `${mean(item[metric] / total * 100)}%` : "—"));
      return row;
    });
    if (!rows.length) { const row = el("tr"), cell = el("td", "No recorded sales in this range."); cell.colSpan = data.includes.revenue ? 5 : 3; row.append(cell); rows.push(row); }
    $("items-table").replaceChildren(...rows);
    $("item-count").textContent = `${format(sorted.length)} items`;
    $("items-expand").hidden = sorted.length <= 10;
    $("items-expand").textContent = expanded ? "Show the top 10" : `Show all ${format(sorted.length)} items`;
    $("items-expand").setAttribute("aria-expanded", String(expanded));
  }

  $("items-expand").addEventListener("click", () => { expanded = !expanded; render(); });
  narrow.addEventListener("change", render);
  for (const button of root.querySelectorAll("[data-range]")) button.addEventListener("click", () => { range = button.dataset.range; expanded = false; render(); });
  for (const button of root.querySelectorAll("[data-metric]")) button.addEventListener("click", () => { metric = button.dataset.metric; render(); });
  render();
}

if (root) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const url = new URL("../data/ugc-stats.json", import.meta.url);
    const response = await fetch(url, { cache: "no-cache", credentials: "omit", signal: controller.signal });
    if (!response.ok) throw new Error("Snapshot unavailable");
    setup(validate(await response.json()));
  } catch {
    root.querySelector("[data-dashboard]").hidden = true;
    root.querySelector("[data-status]").textContent = "Analytics unavailable";
    const message = root.querySelector("[data-message]");
    message.hidden = false;
    message.textContent = "The numbers are taking a break. Check back soon.";
  } finally {
    clearTimeout(timeout);
    root.setAttribute("aria-busy", "false");
  }
}
