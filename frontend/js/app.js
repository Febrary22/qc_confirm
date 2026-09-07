"use strict";

/* =========================================================================
 * 데이터 품질 검사(QC) 도구 - 프론트엔드
 * 서버(FastAPI, /api/...)와 통신하여 업로드된 nc/csv 파일의 QC 리포트를 렌더링한다.
 * ========================================================================= */

const CHECK_ORDER = ["missing_values", "time_continuity", "range_check", "outliers", "metadata", "duplicates"];
const STATUS_LABEL = { pass: "통과", warning: "경고", fail: "실패", skipped: "해당없음" };
const STATUS_ICON = { pass: "✅", warning: "⚠️", fail: "⛔", skipped: "➖" };
const VALID_EXT = [".nc", ".nc4", ".netcdf", ".cdf", ".csv", ".tsv", ".txt"];
const PRESET_STORAGE_KEY = "qc_tool_presets_v1";
const LAST_CONFIG_STORAGE_KEY = "qc_tool_last_config_v1";

let defaultConfig = null;
let currentConfig = null;
let selectedFiles = []; // { file: File, error: string|null }
let okResults = []; // 마지막 응답의 정상 결과들
let activeIndex = 0;
let activeCharts = []; // Chart.js 인스턴스 (재렌더시 destroy)

document.addEventListener("DOMContentLoaded", init);

async function init() {
  wireUploadUI();
  wireSettingsUI();

  try {
    const res = await fetch("/api/config/default");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    defaultConfig = await res.json();
  } catch (e) {
    console.error("기본 설정을 불러오지 못했습니다.", e);
    setRunStatus("서버에서 기본 설정을 불러오지 못했습니다. 백엔드가 실행 중인지 확인하세요.", true);
  }

  const saved = loadFromStorage(LAST_CONFIG_STORAGE_KEY);
  currentConfig = saved || deepClone(defaultConfig || emptyConfigShape());

  renderThresholdsForm();
  renderRangesTable();
  refreshJsonView();
  refreshPresetSelect();
}

function emptyConfigShape() {
  return {
    thresholds: {
      missing: { warning: 0.01, fail: 0.1 },
      time_gap: { tolerance_factor: 1.5, warning_gaps: 1, fail_gaps: 5, fail_ratio: 0.05 },
      outlier: { method: "zscore", zscore_threshold: 3.0, iqr_multiplier: 1.5, warning: 0.01, fail: 0.05 },
      range: { warning: 0.001, fail: 0.01 },
      duplicates: { warning: 0.0001, fail: 0.01 },
      metadata: { warning: 0.6, fail: 0.3 },
    },
    weights: { missing_values: 20, time_continuity: 15, range_check: 20, outliers: 15, metadata: 15, duplicates: 15 },
    variable_ranges: {},
    metadata_rules: { required_global_attrs: [], required_var_attrs: [], cf_convention_prefix: "CF-", expected_units: {} },
  };
}

/* =========================================================================
 * 유틸
 * ========================================================================= */

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtPct(ratio, digits = 2) {
  if (ratio === null || ratio === undefined) return "-";
  return `${(ratio * 100).toFixed(digits)}%`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const STATUS_CSS_VAR = { pass: "--pass", warning: "--warn", fail: "--fail", skipped: "--skip" };
function statusColor(status) {
  return cssVar(STATUS_CSS_VAR[status] || "--skip");
}

function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn("localStorage 저장 실패", e);
  }
}

function loadFromStorage(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

/* =========================================================================
 * 업로드 UI
 * ========================================================================= */

function wireUploadUI() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", (e) => {
    handleFiles(e.target.files);
    fileInput.value = "";
  });

  document.getElementById("btn-clear-files").addEventListener("click", () => {
    selectedFiles = [];
    renderFileChips();
  });

  document.getElementById("btn-run").addEventListener("click", runQC);
}

function hasValidExt(filename) {
  const lower = filename.toLowerCase();
  return VALID_EXT.some((ext) => lower.endsWith(ext));
}

function handleFiles(fileList) {
  for (const file of Array.from(fileList)) {
    const dup = selectedFiles.some((f) => f.file.name === file.name && f.file.size === file.size);
    if (dup) continue;
    if (!hasValidExt(file.name)) {
      selectedFiles.push({ file, error: "지원하지 않는 형식" });
      continue;
    }
    selectedFiles.push({ file, error: null });
  }
  renderFileChips();
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderFileChips();
}

function renderFileChips() {
  const list = document.getElementById("file-chip-list");
  const clearBtn = document.getElementById("btn-clear-files");
  const runBtn = document.getElementById("btn-run");

  list.innerHTML = "";
  if (selectedFiles.length === 0) {
    list.hidden = true;
    clearBtn.hidden = true;
    runBtn.disabled = true;
    return;
  }

  list.hidden = false;
  clearBtn.hidden = false;
  runBtn.disabled = !selectedFiles.some((f) => !f.error);

  selectedFiles.forEach((entry, idx) => {
    const chip = document.createElement("div");
    chip.className = "file-chip" + (entry.error ? " chip-error" : "");
    const sizeKb = (entry.file.size / 1024).toFixed(1);
    const label = document.createElement("span");
    label.textContent = entry.error ? `${entry.file.name} (${entry.error})` : `${entry.file.name} · ${sizeKb}KB`;
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "✕";
    removeBtn.title = "제거";
    removeBtn.addEventListener("click", () => removeFile(idx));
    chip.appendChild(label);
    chip.appendChild(removeBtn);
    list.appendChild(chip);
  });
}

function setRunStatus(msg, isError = false) {
  const el = document.getElementById("run-status");
  el.hidden = !msg;
  el.textContent = msg || "";
  el.classList.toggle("error", isError);
}

async function runQC() {
  const validFiles = selectedFiles.filter((f) => !f.error).map((f) => f.file);
  if (validFiles.length === 0) return;

  const runBtn = document.getElementById("btn-run");
  runBtn.disabled = true;
  setRunStatus(`분석 중입니다... (${validFiles.length}개 파일)`);

  const formData = new FormData();
  validFiles.forEach((f) => formData.append("files", f));
  formData.append("config", JSON.stringify(currentConfig));

  try {
    const res = await fetch("/api/qc/analyze", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    setRunStatus(`완료: ${data.count}개 파일 분석`);
    renderResults(data);
  } catch (e) {
    console.error(e);
    setRunStatus(`분석 중 오류가 발생했습니다: ${e.message}`, true);
  } finally {
    runBtn.disabled = !selectedFiles.some((f) => !f.error);
  }
}

/* =========================================================================
 * 결과 렌더링
 * ========================================================================= */

function renderResults(response) {
  const results = response.results || [];
  okResults = results.filter((r) => !r.error);
  const errResults = results.filter((r) => r.error);

  document.getElementById("empty-hint").hidden = true;

  if (errResults.length > 0) {
    const names = errResults.map((r) => `${r.filename}: ${r.error}`).join(" / ");
    setRunStatus(`일부 파일을 처리하지 못했습니다 → ${names}`, true);
  }

  const comparisonCard = document.getElementById("comparison-card");
  if (response.batch && response.comparison && response.comparison.length > 0) {
    comparisonCard.hidden = false;
    renderComparisonTable(response.comparison);
  } else {
    comparisonCard.hidden = true;
  }

  const detailSection = document.getElementById("detail-section");
  const fileSelect = document.getElementById("detail-file-select");
  if (okResults.length === 0) {
    detailSection.hidden = true;
    return;
  }

  detailSection.hidden = false;
  fileSelect.hidden = okResults.length <= 1;
  fileSelect.innerHTML = "";
  okResults.forEach((r, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = r.filename;
    fileSelect.appendChild(opt);
  });
  fileSelect.onchange = () => selectDetail(Number(fileSelect.value));

  selectDetail(0);
}

function renderComparisonTable(comparison) {
  const tbody = document.querySelector("#comparison-table tbody");
  tbody.innerHTML = "";
  comparison.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.filename)}</td>
      <td>${escapeHtml(row.file_type)}</td>
      <td><strong>${row.score}</strong></td>
      <td>${escapeHtml(row.grade)}</td>
      <td>${row.n_fail}</td>
      <td>${row.n_warning}</td>
    `;
    tr.addEventListener("click", () => {
      const idx = okResults.findIndex((r) => r.filename === row.filename);
      if (idx >= 0) {
        selectDetail(idx);
        document.getElementById("detail-file-select").value = String(idx);
        document.getElementById("detail-section").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    tbody.appendChild(tr);
  });
}

function selectDetail(idx) {
  activeIndex = idx;
  renderDetail(okResults[idx]);
}

function destroyCharts() {
  activeCharts.forEach((c) => c.destroy());
  activeCharts = [];
}

function renderDetail(report) {
  destroyCharts();
  renderScoreCard(report);

  const container = document.getElementById("checks-container");
  container.innerHTML = "";
  CHECK_ORDER.forEach((key) => {
    const data = report.checks[key];
    if (!data) return;
    container.appendChild(buildCheckCard(key, data));
  });
}

function renderScoreCard(report) {
  const score = report.score;
  const pct = Math.round(score.total);

  const ring = document.getElementById("score-ring");
  ring.style.setProperty("--pct", pct);
  let ringColor = cssVar("--fail");
  if (pct >= 90) ringColor = cssVar("--pass");
  else if (pct >= 75) ringColor = cssVar("--primary");
  else if (pct >= 50) ringColor = cssVar("--warn");
  ring.style.background = `conic-gradient(${ringColor} calc(var(--pct) * 1%), var(--border) 0)`;

  document.getElementById("score-number").textContent = pct;
  document.getElementById("score-filename").textContent = report.filename;

  const gradeEl = document.getElementById("score-grade");
  gradeEl.textContent = score.grade;
  gradeEl.style.background = ringColor + "22";
  gradeEl.style.color = ringColor;

  const info = report.dataset_info || {};
  const parts = [`형식: ${report.file_type.toUpperCase()}`, `변수 ${info.n_variables ?? "-"}개`];
  if (info.time_range) {
    parts.push(`기간: ${info.time_range.start} ~ ${info.time_range.end} (${info.time_range.count}개 시점)`);
  }
  if (info.dims) {
    const dimStr = Object.entries(info.dims).map(([k, v]) => `${k}=${v}`).join(", ");
    parts.push(`차원: ${dimStr}`);
  }
  document.getElementById("score-dataset-info").textContent = parts.join(" · ");

  const breakdown = document.getElementById("score-breakdown");
  breakdown.innerHTML = "";
  CHECK_ORDER.forEach((key) => {
    const w = score.weights[key] ?? 0;
    const s = score.per_check[key] ?? 0;
    const label = report.checks[key] ? report.checks[key].label : key;
    const item = document.createElement("div");
    item.className = "breakdown-item";
    item.innerHTML = `<div class="label">${escapeHtml(label)}</div><div class="value">${s.toFixed(1)} / ${w}</div>`;
    breakdown.appendChild(item);
  });
}

/* =========================================================================
 * 체크 카드 빌더
 * ========================================================================= */

function buildCheckCard(key, data) {
  const card = document.createElement("section");
  card.className = "card check-card";
  const collapsedByDefault = data.status === "pass" || data.status === "skipped";
  if (collapsedByDefault) card.classList.add("collapsed");

  const head = document.createElement("div");
  head.className = "check-head";
  head.innerHTML = `
    <span>${STATUS_ICON[data.status] || "❔"}</span>
    <h3>${escapeHtml(data.label || key)}</h3>
    <span class="status-badge status-${data.status}">${STATUS_LABEL[data.status] || data.status}</span>
    <span class="chevron">▾</span>
  `;
  head.addEventListener("click", () => card.classList.toggle("collapsed"));

  const body = document.createElement("div");
  body.className = "check-body";

  try {
    const builder = CHECK_BODY_BUILDERS[key];
    if (builder) builder(body, data);
    else body.textContent = JSON.stringify(data);
  } catch (e) {
    console.error(`체크 카드 렌더링 오류 (${key})`, e);
    body.textContent = "결과를 표시하는 중 오류가 발생했습니다.";
  }

  card.appendChild(head);
  card.appendChild(body);
  return card;
}

function nextCanvasId() {
  nextCanvasId._n = (nextCanvasId._n || 0) + 1;
  return `chart-${nextCanvasId._n}`;
}

function makeBarChart(container, labels, values, colors, yLabel, short = false) {
  const wrap = document.createElement("div");
  wrap.className = "chart-wrap" + (short ? " short" : "");
  const canvas = document.createElement("canvas");
  canvas.id = nextCanvasId();
  wrap.appendChild(canvas);
  container.appendChild(wrap);

  const chart = new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: { labels, datasets: [{ label: yLabel, data: values, backgroundColor: colors }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, title: { display: true, text: yLabel } } },
    },
  });
  activeCharts.push(chart);
}

function statusColorFor(status) {
  return statusColor(status);
}

/* ---- 1. 결측치 ---- */
function buildMissingBody(body, data) {
  if (!data.variables || data.variables.length === 0) {
    body.innerHTML = `<p class="check-note">${escapeHtml(data.message || "수치형 변수가 없습니다.")}</p>`;
    return;
  }
  const s = data.summary;
  const p = document.createElement("p");
  p.className = "check-note";
  p.textContent = `변수 ${s.total_variables}개 중 통과 ${s.pass} · 경고 ${s.warning} · 실패 ${s.fail} (평균 결측 비율 ${fmtPct(s.avg_ratio)})`;
  body.appendChild(p);

  const top = data.variables.slice(0, 15);
  makeBarChart(
    body,
    top.map((v) => v.variable),
    top.map((v) => Number((v.ratio * 100).toFixed(3))),
    top.map((v) => statusColorFor(v.status)),
    "결측 비율 (%)"
  );

  if (data.heatmap) {
    renderHeatmap(body, data.heatmap, "결측 비율");
  }
}

/* ---- 2. 시간 연속성 ---- */
function buildTimeContinuityBody(body, data) {
  if (data.status === "skipped") {
    body.innerHTML = `<p class="check-note">${escapeHtml(data.message || "검사를 건너뛰었습니다.")}</p>`;
    return;
  }
  const p = document.createElement("p");
  p.className = "check-note";
  p.textContent =
    `예상 간격: ${data.expected_interval_human} · 타임스탬프 ${data.n_timestamps}개 (예상 ${data.expected_points}개) · ` +
    `결측 추정 ${data.missing_points}개 (${fmtPct(data.ratio)}) · 결측 구간 ${data.n_gaps_total}개`;
  body.appendChild(p);

  if (data.gaps.length === 0) {
    const ok = document.createElement("p");
    ok.className = "check-note";
    ok.textContent = "빠진 시간 구간이 발견되지 않았습니다.";
    body.appendChild(ok);
    return;
  }

  const ul = document.createElement("ul");
  ul.className = "gap-list";
  data.gaps.slice(0, 30).forEach((g) => {
    const li = document.createElement("li");
    li.textContent = `${g.start} → ${g.end} (간격 ${g.actual_gap_human}, 약 ${g.missing_points}개 시점 누락)`;
    ul.appendChild(li);
  });
  body.appendChild(ul);
  if (data.n_gaps_total > 30) {
    const more = document.createElement("p");
    more.className = "check-note";
    more.textContent = `외 ${data.n_gaps_total - 30}개 구간 더 있음`;
    body.appendChild(more);
  }
}

/* ---- 3. 값의 범위 ---- */
function buildRangeBody(body, data) {
  if (data.status === "skipped") {
    body.innerHTML = `<p class="check-note">${escapeHtml(data.message || "적용 가능한 규칙이 없습니다.")}</p>`;
    if (data.unmatched_variables && data.unmatched_variables.length) {
      const note = document.createElement("p");
      note.className = "check-note";
      note.textContent = `규칙이 없는 변수: ${data.unmatched_variables.join(", ")}`;
      body.appendChild(note);
    }
    return;
  }

  const wrap = document.createElement("div");
  wrap.className = "table-scroll";
  const table = document.createElement("table");
  table.className = "table";
  table.innerHTML = `
    <thead><tr><th>변수</th><th>정상 범위</th><th>관측 범위</th><th>범위 초과</th><th>상태</th></tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  data.variables.forEach((v) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(v.variable)}</td>
      <td>${v.min} ~ ${v.max}${v.unit ? " " + escapeHtml(v.unit) : ""}</td>
      <td>${v.observed_min.toFixed(2)} ~ ${v.observed_max.toFixed(2)}</td>
      <td>${v.out_of_range} (${fmtPct(v.ratio)})</td>
      <td><span class="status-badge status-${v.status}">${STATUS_LABEL[v.status]}</span></td>
    `;
    tbody.appendChild(tr);
  });
  wrap.appendChild(table);
  body.appendChild(wrap);

  if (data.unmatched_variables && data.unmatched_variables.length) {
    const note = document.createElement("p");
    note.className = "check-note";
    note.textContent = `규칙이 없어 검사하지 않은 변수: ${data.unmatched_variables.join(", ")}`;
    body.appendChild(note);
  }
}

/* ---- 4. 이상치 ---- */
function buildOutliersBody(body, data) {
  if (!data.variables || data.variables.length === 0) {
    body.innerHTML = `<p class="check-note">${escapeHtml(data.message || "계산 가능한 변수가 없습니다.")}</p>`;
    return;
  }
  const p = document.createElement("p");
  p.className = "check-note";
  p.textContent = `탐지 방법: ${data.method === "iqr" ? "IQR" : "Z-Score"}`;
  body.appendChild(p);

  const top = [...data.variables].sort((a, b) => b.ratio - a.ratio).slice(0, 15);
  makeBarChart(
    body,
    top.map((v) => v.variable),
    top.map((v) => Number((v.ratio * 100).toFixed(3))),
    top.map((v) => statusColorFor(v.status)),
    "이상치 비율 (%)"
  );
}

/* ---- 5. 메타데이터 ---- */
function buildMetadataBody(body, data) {
  const p = document.createElement("p");
  p.className = "check-note";
  p.textContent = `준수율: ${data.passed_checks}/${data.total_checks} (${fmtPct(data.compliance_ratio, 1)})`;
  body.appendChild(p);
  if (data.note) {
    const note = document.createElement("p");
    note.className = "check-note";
    note.textContent = data.note;
    body.appendChild(note);
  }
  if (!data.checks || data.checks.length === 0) return;

  const wrap = document.createElement("div");
  wrap.className = "table-scroll";
  const table = document.createElement("table");
  table.className = "table";
  table.innerHTML = `<thead><tr><th>항목</th><th>결과</th></tr></thead><tbody></tbody>`;
  const tbody = table.querySelector("tbody");
  data.checks.forEach((c) => {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    td1.textContent = c.item;
    const td2 = document.createElement("td");
    td2.textContent = c.passed ? "✅" : "❌";
    tr.appendChild(td1);
    tr.appendChild(td2);
    tbody.appendChild(tr);
  });
  wrap.appendChild(table);
  body.appendChild(wrap);
}

/* ---- 6. 중복 ---- */
function buildDuplicatesBody(body, data) {
  if (data.status === "skipped") {
    body.innerHTML = `<p class="check-note">${escapeHtml(data.message || "검사를 건너뛰었습니다.")}</p>`;
    return;
  }
  const lines = [];
  if (data.type === "timestamp") {
    lines.push(`중복 타임스탬프: ${data.duplicates}개 / 전체 ${data.total}개 (${fmtPct(data.ratio)})`);
  } else {
    lines.push(`중복 행: ${data.duplicate_rows}개 / 전체 ${data.total}개 (${fmtPct(data.row_ratio)})`);
    if (data.duplicate_timestamps !== undefined) {
      lines.push(`중복 타임스탬프: ${data.duplicate_timestamps}개 (${fmtPct(data.timestamp_ratio)})`);
    }
  }
  lines.forEach((line) => {
    const p = document.createElement("p");
    p.className = "check-note";
    p.textContent = line;
    body.appendChild(p);
  });
}

const CHECK_BODY_BUILDERS = {
  missing_values: buildMissingBody,
  time_continuity: buildTimeContinuityBody,
  range_check: buildRangeBody,
  outliers: buildOutliersBody,
  metadata: buildMetadataBody,
  duplicates: buildDuplicatesBody,
};

/* =========================================================================
 * 히트맵 (결측치 시간대별 분포)
 * ========================================================================= */

function heatColor(v) {
  v = Math.max(0, Math.min(1, v));
  const stops = [
    [0.0, [31, 157, 85]],
    [0.5, [245, 215, 110]],
    [1.0, [214, 69, 69]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [p0, c0] = stops[i];
    const [p1, c1] = stops[i + 1];
    if (v >= p0 && v <= p1) {
      const t = (v - p0) / (p1 - p0 || 1);
      const c = c0.map((c0v, idx) => Math.round(c0v + (c1[idx] - c0v) * t));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return `rgb(${stops[stops.length - 1][1].join(",")})`;
}

function renderHeatmap(container, heatmap, title) {
  const wrapTitle = document.createElement("p");
  wrapTitle.className = "check-note";
  wrapTitle.textContent = `${title} 시간대별 분포 (변수별, 시간축을 ${heatmap.time_labels.length}개 구간으로 나눔)`;
  container.appendChild(wrapTitle);

  const scroll = document.createElement("div");
  scroll.className = "heatmap-scroll";
  const grid = document.createElement("div");
  grid.className = "heatmap";
  grid.style.gridTemplateColumns = `140px repeat(${heatmap.time_labels.length}, 16px)`;

  heatmap.variables.forEach((varName, ri) => {
    const label = document.createElement("div");
    label.className = "heatmap-row-label";
    label.textContent = varName;
    grid.appendChild(label);

    heatmap.matrix[ri].forEach((val, ci) => {
      const cell = document.createElement("div");
      cell.className = "heatmap-cell";
      cell.style.background = heatColor(val);
      cell.title = `${varName} · ${heatmap.time_labels[ci]} · ${(val * 100).toFixed(1)}%`;
      grid.appendChild(cell);
    });
  });

  scroll.appendChild(grid);
  container.appendChild(scroll);

  const axis = document.createElement("div");
  axis.className = "heatmap-axis";
  axis.innerHTML = `<span>${escapeHtml(heatmap.time_labels[0])}</span><span style="margin-left:auto">${escapeHtml(
    heatmap.time_labels[heatmap.time_labels.length - 1]
  )}</span>`;
  container.appendChild(axis);

  const legend = document.createElement("div");
  legend.className = "heatmap-legend";
  legend.innerHTML = `<span>낮음(0%)</span><div class="legend-bar"></div><span>높음(100%)</span>`;
  container.appendChild(legend);
}

/* =========================================================================
 * PDF 내보내기
 * ========================================================================= */

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-export-pdf").addEventListener("click", exportPdf);
});

async function exportPdf() {
  const btn = document.getElementById("btn-export-pdf");
  const target = document.getElementById("detail-view");
  const report = okResults[activeIndex];
  if (!target || !report) return;

  btn.disabled = true;
  btn.textContent = "PDF 생성 중...";
  try {
    const canvas = await html2canvas(target, { scale: 1.5, backgroundColor: getComputedStyle(document.body).backgroundColor });
    // JPEG로 인코딩해 PDF 용량을 대폭 줄인다 (리포트는 대부분 단색/텍스트라 화질 손실이 적음).
    const imgData = canvas.toDataURL("image/jpeg", 0.92);
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const imgWidth = pageWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;

    let heightLeft = imgHeight;
    let position = 0;
    pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
    heightLeft -= pageHeight;
    while (heightLeft > 0) {
      position = heightLeft - imgHeight;
      pdf.addPage();
      pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
    }
    const safeName = report.filename.replace(/[^\w.\-]/g, "_");
    pdf.save(`QC_리포트_${safeName}.pdf`);
  } catch (e) {
    console.error(e);
    alert("PDF 생성 중 오류가 발생했습니다: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "⬇️ PDF로 내보내기";
  }
}

/* =========================================================================
 * 설정 모달
 * ========================================================================= */

const THRESHOLD_GROUPS = [
  {
    key: "missing",
    title: "결측치",
    fields: [
      { path: "warning", label: "경고 기준 (비율)", step: "0.001" },
      { path: "fail", label: "실패 기준 (비율)", step: "0.001" },
    ],
  },
  {
    key: "time_gap",
    title: "시간 연속성",
    fields: [
      { path: "tolerance_factor", label: "허용 배수(예상 간격의 n배)", step: "0.1" },
      { path: "warning_gaps", label: "경고 기준 (구간 수)", step: "1" },
      { path: "fail_gaps", label: "실패 기준 (구간 수)", step: "1" },
      { path: "fail_ratio", label: "실패 기준 (누락 비율)", step: "0.001" },
    ],
  },
  {
    key: "range",
    title: "값의 범위",
    fields: [
      { path: "warning", label: "경고 기준 (비율)", step: "0.0001" },
      { path: "fail", label: "실패 기준 (비율)", step: "0.0001" },
    ],
  },
  {
    key: "outlier",
    title: "이상치",
    fields: [
      { path: "method", label: "탐지 방법", type: "select", options: ["zscore", "iqr"] },
      { path: "zscore_threshold", label: "Z-Score 임계값", step: "0.1" },
      { path: "iqr_multiplier", label: "IQR 배수", step: "0.1" },
      { path: "warning", label: "경고 기준 (비율)", step: "0.001" },
      { path: "fail", label: "실패 기준 (비율)", step: "0.001" },
    ],
  },
  {
    key: "metadata",
    title: "메타데이터",
    fields: [
      { path: "warning", label: "경고 기준 (준수율 미만)", step: "0.01" },
      { path: "fail", label: "실패 기준 (준수율 미만)", step: "0.01" },
    ],
  },
  {
    key: "duplicates",
    title: "중복/버전",
    fields: [
      { path: "warning", label: "경고 기준 (비율)", step: "0.0001" },
      { path: "fail", label: "실패 기준 (비율)", step: "0.0001" },
    ],
  },
];

const WEIGHT_LABELS = {
  missing_values: "결측치",
  time_continuity: "시간 연속성",
  range_check: "값의 범위",
  outliers: "이상치",
  metadata: "메타데이터",
  duplicates: "중복/버전",
};

function wireSettingsUI() {
  document.getElementById("btn-open-settings").addEventListener("click", () => {
    document.getElementById("settings-overlay").hidden = false;
  });
  document.getElementById("btn-close-settings").addEventListener("click", closeSettings);
  document.getElementById("btn-close-settings-2").addEventListener("click", closeSettings);
  document.getElementById("settings-overlay").addEventListener("click", (e) => {
    if (e.target.id === "settings-overlay") closeSettings();
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).classList.add("active");
    });
  });

  document.getElementById("btn-add-range").addEventListener("click", () => {
    currentConfig.variable_ranges[""] = { min: 0, max: 100, unit: "" };
    renderRangesTable();
  });

  document.getElementById("btn-apply-json").addEventListener("click", applyJsonConfig);
  document.getElementById("btn-save-preset").addEventListener("click", savePreset);
  document.getElementById("btn-delete-preset").addEventListener("click", deletePreset);
  document.getElementById("preset-select").addEventListener("change", loadPreset);
  document.getElementById("btn-export-config").addEventListener("click", exportConfigFile);
  document.getElementById("btn-reset-config").addEventListener("click", resetConfig);
  document.getElementById("import-config-file").addEventListener("change", importConfigFile);
}

function closeSettings() {
  document.getElementById("settings-overlay").hidden = true;
  persistConfig();
}

function persistConfig() {
  saveToStorage(LAST_CONFIG_STORAGE_KEY, currentConfig);
}

function getByPath(obj, path) {
  return path.split(".").reduce((o, k) => (o ? o[k] : undefined), obj);
}
function setByPath(obj, path, value) {
  const keys = path.split(".");
  const last = keys.pop();
  const target = keys.reduce((o, k) => (o[k] = o[k] || {}), obj);
  target[last] = value;
}

function renderThresholdsForm() {
  const form = document.getElementById("thresholds-form");
  form.innerHTML = "";

  THRESHOLD_GROUPS.forEach((group) => {
    const box = document.createElement("div");
    box.className = "threshold-group";
    const h4 = document.createElement("h4");
    h4.textContent = group.title;
    box.appendChild(h4);

    group.fields.forEach((f) => {
      const row = document.createElement("div");
      row.className = "field-row";
      const label = document.createElement("label");
      label.textContent = f.label;
      row.appendChild(label);

      const fullPath = `thresholds.${group.key}.${f.path}`;
      const value = getByPath(currentConfig, fullPath);

      let input;
      if (f.type === "select") {
        input = document.createElement("select");
        f.options.forEach((opt) => {
          const o = document.createElement("option");
          o.value = opt;
          o.textContent = opt;
          if (opt === value) o.selected = true;
          input.appendChild(o);
        });
      } else {
        input = document.createElement("input");
        input.type = "number";
        input.step = f.step || "any";
        input.value = value ?? "";
      }
      input.addEventListener("change", () => {
        const raw = input.value;
        const parsed = f.type === "select" ? raw : Number(raw);
        setByPath(currentConfig, fullPath, parsed);
        refreshJsonView();
      });
      row.appendChild(input);
      box.appendChild(row);
    });
    form.appendChild(box);
  });

  // 가중치
  const weightBox = document.createElement("div");
  weightBox.className = "threshold-group";
  const wh4 = document.createElement("h4");
  const sum = Object.values(currentConfig.weights).reduce((a, b) => a + Number(b), 0);
  wh4.textContent = `점수 가중치 (합계: ${sum})`;
  weightBox.appendChild(wh4);
  Object.keys(WEIGHT_LABELS).forEach((key) => {
    const row = document.createElement("div");
    row.className = "field-row";
    const label = document.createElement("label");
    label.textContent = WEIGHT_LABELS[key];
    row.appendChild(label);
    const input = document.createElement("input");
    input.type = "number";
    input.step = "1";
    input.value = currentConfig.weights[key] ?? 0;
    input.addEventListener("change", () => {
      currentConfig.weights[key] = Number(input.value);
      refreshJsonView();
      renderThresholdsForm();
    });
    row.appendChild(input);
    weightBox.appendChild(row);
  });
  form.appendChild(weightBox);
}

function renderRangesTable() {
  const tbody = document.querySelector("#ranges-table tbody");
  tbody.innerHTML = "";
  const entries = Object.entries(currentConfig.variable_ranges || {});

  entries.forEach(([name, rule], idx) => {
    const tr = document.createElement("tr");

    const tdName = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = name;
    nameInput.placeholder = "예: temperature";
    tdName.appendChild(nameInput);

    const tdMin = document.createElement("td");
    const minInput = document.createElement("input");
    minInput.type = "number";
    minInput.step = "any";
    minInput.value = rule.min;
    tdMin.appendChild(minInput);

    const tdMax = document.createElement("td");
    const maxInput = document.createElement("input");
    maxInput.type = "number";
    maxInput.step = "any";
    maxInput.value = rule.max;
    tdMax.appendChild(maxInput);

    const tdUnit = document.createElement("td");
    const unitInput = document.createElement("input");
    unitInput.type = "text";
    unitInput.value = rule.unit || "";
    tdUnit.appendChild(unitInput);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.className = "btn btn-ghost btn-icon";
    delBtn.textContent = "🗑️";
    delBtn.addEventListener("click", () => {
      delete currentConfig.variable_ranges[name];
      renderRangesTable();
      refreshJsonView();
    });
    tdDel.appendChild(delBtn);

    function commit() {
      const newName = nameInput.value.trim().toLowerCase();
      delete currentConfig.variable_ranges[name];
      if (newName) {
        currentConfig.variable_ranges[newName] = {
          min: Number(minInput.value),
          max: Number(maxInput.value),
          unit: unitInput.value,
        };
      }
      refreshJsonView();
    }
    [nameInput, minInput, maxInput, unitInput].forEach((inp) => inp.addEventListener("change", commit));

    tr.appendChild(tdName);
    tr.appendChild(tdMin);
    tr.appendChild(tdMax);
    tr.appendChild(tdUnit);
    tr.appendChild(tdDel);
    tbody.appendChild(tr);
  });
}

function refreshJsonView() {
  document.getElementById("advanced-json").value = JSON.stringify(currentConfig, null, 2);
  document.getElementById("json-error").textContent = "";
}

function applyJsonConfig() {
  const raw = document.getElementById("advanced-json").value;
  try {
    const parsed = JSON.parse(raw);
    currentConfig = parsed;
    document.getElementById("json-error").textContent = "";
    renderThresholdsForm();
    renderRangesTable();
  } catch (e) {
    document.getElementById("json-error").textContent = `JSON 오류: ${e.message}`;
  }
}

function resetConfig() {
  if (!defaultConfig) return;
  currentConfig = deepClone(defaultConfig);
  renderThresholdsForm();
  renderRangesTable();
  refreshJsonView();
}

/* ---- 프리셋 저장/불러오기 (브라우저 localStorage) ---- */

function getPresets() {
  return loadFromStorage(PRESET_STORAGE_KEY) || {};
}

function refreshPresetSelect() {
  const select = document.getElementById("preset-select");
  const presets = getPresets();
  select.innerHTML = '<option value="">저장된 프리셋…</option>';
  Object.keys(presets).forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
}

function savePreset() {
  const name = prompt("프리셋 이름을 입력하세요 (예: 우리팀 표준):");
  if (!name) return;
  const presets = getPresets();
  presets[name] = currentConfig;
  saveToStorage(PRESET_STORAGE_KEY, presets);
  refreshPresetSelect();
  document.getElementById("preset-select").value = name;
}

function loadPreset() {
  const name = document.getElementById("preset-select").value;
  if (!name) return;
  const presets = getPresets();
  if (!presets[name]) return;
  currentConfig = deepClone(presets[name]);
  renderThresholdsForm();
  renderRangesTable();
  refreshJsonView();
}

function deletePreset() {
  const name = document.getElementById("preset-select").value;
  if (!name) return;
  const presets = getPresets();
  delete presets[name];
  saveToStorage(PRESET_STORAGE_KEY, presets);
  refreshPresetSelect();
}

function exportConfigFile() {
  const blob = new Blob([JSON.stringify(currentConfig, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "qc_config.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function importConfigFile(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      currentConfig = JSON.parse(reader.result);
      renderThresholdsForm();
      renderRangesTable();
      refreshJsonView();
    } catch (err) {
      alert("설정 파일을 읽는 중 오류가 발생했습니다: " + err.message);
    }
  };
  reader.readAsText(file);
  e.target.value = "";
}
