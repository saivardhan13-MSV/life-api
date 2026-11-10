// Tiny SVG chart helpers for the Life API dashboard. No dependencies.
// Bars: thin, 2px gaps, 4px rounded data-ends on the baseline. Hover: per-day tooltip.

const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};

export const fmtDay = (iso, opts = { month: "short", day: "numeric" }) =>
  new Date(iso + "T12:00:00").toLocaleDateString(undefined, opts);

function niceMax(v) {
  if (!v || v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

// Rect with only the top corners rounded (data end), flat on the baseline.
function topRounded(x, y, w, h, r) {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

let tip;
function tooltip() {
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "tip";
    tip.setAttribute("role", "status");
    document.body.appendChild(tip);
  }
  return tip;
}
function showTip(evt, html) {
  const t = tooltip();
  t.innerHTML = html;
  t.style.display = "block";
  const pad = 14, r = t.getBoundingClientRect();
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
  if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
  t.style.left = `${x}px`;
  t.style.top = `${y}px`;
}
const hideTip = () => tip && (tip.style.display = "none");

function frame(container, height, margin) {
  container.innerHTML = "";
  const width = Math.max(container.clientWidth, 260);
  const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img" }, container);
  return { svg, width, iw: width - margin.l - margin.r, ih: height - margin.t - margin.b };
}

function axes(svg, { margin, iw, ih, max, fmtY, days }) {
  const g = el("g", { transform: `translate(${margin.l},${margin.t})` }, svg);
  for (const f of [0.5, 1]) {
    const y = ih - f * ih;
    el("line", { x1: 0, x2: iw, y1: y, y2: y, class: "grid" }, g);
    el("text", { x: -8, y: y + 4, class: "tick", "text-anchor": "end" }, g).textContent = fmtY(max * f);
  }
  el("line", { x1: 0, x2: iw, y1: ih, y2: ih, class: "base" }, g);
  const idx = [...new Set([0, Math.floor((days.length - 1) / 2), days.length - 1])];
  for (const i of idx) {
    const x = ((i + 0.5) / days.length) * iw;
    const anchor = i === 0 ? "start" : i === days.length - 1 ? "end" : "middle";
    el("text", { x: anchor === "start" ? 0 : anchor === "end" ? iw : x, y: ih + 18, class: "tick", "text-anchor": anchor }, g)
      .textContent = fmtDay(days[i].day);
  }
  return g;
}

/** Stacked (or single) bar chart, one bar per day. */
// `unit` rounds the axis in display units (e.g. 60 = whole hours for minute data).
export function barChart(container, { days, series, fmt = (v) => Math.round(v), fmtY = fmt, height = 220, empty = "No data yet", unit = 1 }) {
  const margin = { t: 10, r: 4, b: 26, l: 44 };
  const draw = () => {
    const { svg, iw, ih } = frame(container, height, margin);
    const total = (d) => series.reduce((s, k) => s + (d[k.key] ?? 0), 0);
    const hasData = days.some((d) => series.some((k) => d[k.key] != null && d[k.key] > 0));
    const max = niceMax(Math.max(...days.map(total)) / unit) * unit;
    const g = axes(svg, { margin, iw, ih, max, fmtY: hasData ? fmtY : () => "", days });
    svg.setAttribute("aria-label", `${series.map((s) => s.label).join(", ")} per day`);
    if (!hasData) {
      el("text", { x: iw / 2, y: ih / 2, class: "empty", "text-anchor": "middle" }, g).textContent = empty;
      return;
    }
    const slot = iw / days.length;
    const bw = Math.max(2, Math.min(28, slot * 0.66));
    days.forEach((d, i) => {
      const x = i * slot + (slot - bw) / 2;
      let y0 = ih;
      const segs = series.filter((s) => (d[s.key] ?? 0) > 0);
      segs.forEach((s, j) => {
        const h = (d[s.key] / max) * ih;
        const top = j === segs.length - 1;
        const gap = j > 0 ? 2 : 0; // 2px surface gap between stacked fills
        const y = y0 - h;
        if (top) el("path", { d: topRounded(x, y, bw, Math.max(h - gap, 1), 4), fill: s.color }, g);
        else el("rect", { x, y, width: bw, height: Math.max(h - gap, 1), fill: s.color }, g);
        y0 = y;
      });
      const hit = el("rect", { x: i * slot, y: 0, width: slot, height: ih, class: "hit" }, g);
      const rows = series
        .map((s) => `<div class="tr"><i style="background:${s.color}"></i>${s.label}<b>${d[s.key] == null ? "–" : fmt(d[s.key])}</b></div>`)
        .join("");
      const sum = series.length > 1 && total(d) > 0 ? `<div class="tr tot">Total<b>${fmt(total(d))}</b></div>` : "";
      const html = `<div class="th">${fmtDay(d.day, { weekday: "short", month: "short", day: "numeric" })}</div>${rows}${sum}`;
      hit.addEventListener("mousemove", (e) => { hit.classList.add("on"); showTip(e, html); });
      hit.addEventListener("mouseleave", () => { hit.classList.remove("on"); hideTip(); });
    });
  };
  draw();
  new ResizeObserver(() => draw()).observe(container);
}

/** Single-series line chart with crosshair. */
export function lineChart(container, { days, key, label, color, fmt = (v) => v, height = 220, empty = "No data yet" }) {
  const margin = { t: 10, r: 8, b: 26, l: 44 };
  const draw = () => {
    const { svg, iw, ih } = frame(container, height, margin);
    const vals = days.map((d) => d[key]).filter((v) => v != null);
    svg.setAttribute("aria-label", `${label} per day`);
    if (!vals.length) {
      const g = axes(svg, { margin, iw, ih, max: 1, fmtY: () => "", days });
      el("text", { x: iw / 2, y: ih / 2, class: "empty", "text-anchor": "middle" }, g).textContent = empty;
      return;
    }
    const lo = Math.floor(Math.min(...vals) - 3), hi = Math.ceil(Math.max(...vals) + 3);
    const g = el("g", { transform: `translate(${margin.l},${margin.t})` }, svg);
    for (const v of [lo, Math.round((lo + hi) / 2), hi]) {
      const y = ih - ((v - lo) / (hi - lo)) * ih;
      el("line", { x1: 0, x2: iw, y1: y, y2: y, class: v === lo ? "base" : "grid" }, g);
      el("text", { x: -8, y: y + 4, class: "tick", "text-anchor": "end" }, g).textContent = fmt(v);
    }
    const idx = [...new Set([0, Math.floor((days.length - 1) / 2), days.length - 1])];
    const X = (i) => ((i + 0.5) / days.length) * iw;
    const Y = (v) => ih - ((v - lo) / (hi - lo)) * ih;
    for (const i of idx) {
      const anchor = i === 0 ? "start" : i === days.length - 1 ? "end" : "middle";
      el("text", { x: anchor === "start" ? 0 : anchor === "end" ? iw : X(i), y: ih + 18, class: "tick", "text-anchor": anchor }, g)
        .textContent = fmtDay(days[i].day);
    }
    let dpath = "", pen = false;
    days.forEach((d, i) => {
      if (d[key] == null) { pen = false; return; }
      dpath += `${pen ? "L" : "M"}${X(i)},${Y(d[key])}`;
      pen = true;
    });
    el("path", { d: dpath, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, g);
    const cross = el("line", { y1: 0, y2: ih, class: "cross", style: "display:none" }, g);
    const dot = el("circle", { r: 4, fill: color, class: "ring", style: "display:none" }, g);
    const slot = iw / days.length;
    days.forEach((d, i) => {
      const hit = el("rect", { x: i * slot, y: 0, width: slot, height: ih, class: "hit hit-line" }, g);
      hit.addEventListener("mousemove", (e) => {
        cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.style.display = "";
        if (d[key] != null) { dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(d[key])); dot.style.display = ""; }
        else dot.style.display = "none";
        showTip(e, `<div class="th">${fmtDay(d.day, { weekday: "short", month: "short", day: "numeric" })}</div>
          <div class="tr"><i style="background:${color}"></i>${label}<b>${d[key] == null ? "–" : fmt(d[key])}</b></div>`);
      });
      hit.addEventListener("mouseleave", () => { cross.style.display = "none"; dot.style.display = "none"; hideTip(); });
    });
  };
  draw();
  new ResizeObserver(() => draw()).observe(container);
}

/** Horizontal bars for the application funnel. */
export function funnel(container, { rows, color }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  container.innerHTML = rows
    .map((r) => `<div class="fr" title="${r.label}: ${r.value}">
      <span class="fl">${r.label}</span>
      <span class="fb"><span style="width:${(r.value / max) * 100}%;background:${r.muted ? "var(--muted-fill)" : color}"></span></span>
      <span class="fv">${r.value}</span></div>`)
    .join("");
}
