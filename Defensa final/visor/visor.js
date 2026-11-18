"use strict";

const evidence = window.EVIDENCIA;
const elements = Object.fromEntries([...document.querySelectorAll("[id]")].map(node => [node.id, node]));
const names = {
  unica: "Vertida única",
  continua: "Sucesiva sin espera",
  espera_3h: "Sucesiva · espera 3 h",
  espera_6h: "Sucesiva · espera 6 h",
  unica_manta: "Vertida única · manta 50 mm",
  continua_manta: "Sucesiva sin espera · manta 50 mm",
  espera_3h_manta: "Espera 3 h · manta 50 mm",
  espera_6h_manta: "Espera 6 h · manta 50 mm",
  unica_poliestireno: "Vertida única · EPS 100 mm",
  continua_poliestireno: "Sucesiva · EPS 100 mm",
};
const campaigns = {original: "Original", extension: "Extensión final", pilotos: "Pilotos"};
const levels = {
  barrido: "Barrido",
  cribado: "Cribado",
  temporal: "Paso temporal",
  registro: "Frecuencia de registro",
  fino: "Malla fina",
  confirmacion: "Confirmación 0,20 m",
};
const format = (value, digits = 2) => Number(value).toLocaleString("es-CL", {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
});
const temperature = value => format(value) + " °C";
const climate = value => value === "pronostico" ? "Pronóstico" : value.replace("era5_", "ERA5 ");
const curve = value => value.replace("_", " ");
const levelName = value => levels[value] ?? value.replaceAll("_", " ");
function planName(id, campaign) {
  if (id in names) return names[id] + " · 18 °C";
  const match = /^eps(\d+)_T(\d+)(_sucesiva)?$/.exec(id);
  if (!match) return id;
  const [, thickness, initial, successive] = match;
  const suffix = successive ? " · sucesiva" : id === "eps200_T12" && campaign === "extension" ? " · elegido" : "";
  return `EPS ${thickness} mm · ${initial} °C${suffix}`;
}

const allRuns = Object.keys(campaigns).flatMap(campaign => evidence[campaign].runs.map((run, index) => ({
  ...run, campaign, id: `${campaign}-${index}`,
})));
const selected = allRuns.filter(run => run.campaign === "extension" && run.plan === "eps200_T12");
const critical = selected.reduce((worst, run) => run.delta_C > worst.delta_C ? run : worst);
const fine = selected.filter(run => run.nivel === "fino" && run.clima !== "pronostico");
const fineCritical = fine.reduce((worst, run) => run.delta_C > worst.delta_C ? run : worst);
let activePlan;
let plotBounds;

function option(value, label) {
  return new Option(label, value);
}
function badge(label, tone = "") {
  return `<span class="badge ${tone}">${label}</span>`;
}
function runStatus(run) {
  if (run.I_F) return badge("Excede", "fail");
  if (run.pico_tardio) return badge("Horizonte abierto");
  return badge("Dentro de límites", "pass");
}
function groupStatus(summary, rows) {
  if (summary?.cumple === "si") return badge("Cumple en la matriz", "pass");
  if (summary?.cumple === "no") return badge("Descartado", "fail");
  if (summary) return badge("Horizonte abierto");
  if (rows.some(run => run.I_F)) return badge("Se observó excedencia", "fail");
  return badge("Comprobación parcial");
}
function setCaseLevels() {
  const campaign = elements.campaign.value;
  const available = new Set(evidence[campaign].runs.map(run => run.nivel));
  const ordered = [...new Set([...Object.keys(levels), ...available])].filter(level => available.has(level));
  elements.level.replaceChildren(...ordered.map(level => option(level, levelName(level))));
  elements.level.value = campaign === "extension" ? "fino" : "barrido";
  activePlan = null;
  showCases();
}
function showCases({restoreFocus = false} = {}) {
  const campaign = elements.campaign.value;
  const level = elements.level.value;
  const rows = allRuns.filter(run => run.campaign === campaign && run.nivel === level);
  const groups = Map.groupBy(rows, run => run.plan);
  if (!groups.has(activePlan)) activePlan = groups.has("eps200_T12") ? "eps200_T12" : groups.keys().next().value;
  const summaries = evidence[campaign].comparison.filter(row => row.nivel === level && row.pesos === elements.weights.value);
  elements["case-note"].textContent = campaign === "pilotos"
    ? "Campaña exploratoria de EPS. El EPS de 100 mm a 12 °C se descartó al registrar 20,15 °C en malla fina."
    : campaign === "original"
      ? "Los diez planes originales excedieron el límite de diferencial en uno o más escenarios del barrido."
      : "El candidato se evaluó en seis escenarios de malla fina con activación conjunta. Las comprobaciones parciales se muestran sin riesgo agregado.";
  elements.cases.innerHTML = [...groups].map(([plan, runs]) => {
    const summary = summaries.find(row => row.plan === plan);
    const weighted = runs.filter(run => run.clima !== "pronostico");
    const peaks = weighted.length ? weighted : runs;
    const risk = summary ? format(Number(summary.P_F) * 100, 1) + " %" : "—";
    return `<tr class="${plan === activePlan ? "selected" : ""}">
      <td><button data-plan="${plan}" aria-pressed="${plan === activePlan}">${planName(plan, campaign)}</button></td>
      <td>${format(runs[0].D_h)} h</td><td>${temperature(Math.max(...peaks.map(run => run.T_max_C)))}</td>
      <td>${temperature(Math.max(...peaks.map(run => run.delta_C)))}</td><td>${risk}</td>
      <td>${groupStatus(summary, weighted.length ? weighted : runs)}</td></tr>`;
  }).join("");
  elements["scenario-caption"].textContent = "Escenarios · " + planName(activePlan, campaign);
  elements.scenarios.innerHTML = groups.get(activePlan).map(run => `<tr>
    <td>${curve(run.curva)}</td><td>${climate(run.clima)}</td><td>${temperature(run.T_max_C)}</td>
    <td>${temperature(run.delta_C)}</td><td>${format(run.horizonte_h, 0)} h</td>
    <td>${runStatus(run)}</td><td><button data-run="${run.id}" aria-label="Ver curvas de ${curve(run.curva)}, ${climate(run.clima)}">Ver curvas</button></td></tr>`).join("");
  if (restoreFocus) elements.cases.querySelector('[aria-pressed="true"]').focus();
}

function currentRun() {
  return allRuns.find(run => run.id === elements.run.value);
}
function referenceRun(run) {
  return allRuns.find(other => other.campaign === "original" && other.plan === "unica" &&
    other.nivel === "barrido" && other.curva === run.curva && other.clima === run.clima);
}
function closestIndex(times, target) {
  let start = 0;
  let end = times.length - 1;
  while (start < end) {
    const middle = Math.floor((start + end) / 2);
    if (times[middle] < target) start = middle + 1;
    else end = middle;
  }
  return start > 0 && target - times[start - 1] <= times[start] - target ? start - 1 : start;
}
function updateRun(id) {
  elements.run.value = id;
  const run = currentRun();
  elements.time.max = run.series.t_h.length - 1;
  elements.time.value = closestIndex(run.series.t_h, elements.metric.value === "delta" ? run.t_delta_h : run.t_T_h);
  elements["run-summary"].innerHTML = `<span><strong>T máx. ${temperature(run.T_max_C)}</strong> a las ${format(run.t_T_h)} h</span>
    <span><strong>Δ máx. ${temperature(run.delta_C)}</strong> a las ${format(run.t_delta_h)} h</span>
    <span>Horizonte <strong>${format(run.horizonte_h, 0)} h</strong></span>${runStatus(run)}`;
  draw();
}

function draw() {
  const run = currentRun();
  const base = referenceRun(run);
  const activeBase = elements.reference.checked && base && base.id !== run.id ? base : null;
  const temperatures = elements.metric.value === "temp";
  const series = temperatures
    ? [{run, key: "T_max_C", label: "Máxima del hormigón", color: "#086d61"},
       {run, key: "T_superficie_min_C", label: "Mínima cercana a la superficie", color: "#315f9c"}]
    : [{run, key: "delta_C", label: "Diferencial de la corrida", color: "#086d61"}];
  if (activeBase) series.push({run: activeBase, key: temperatures ? "T_max_C" : "delta_C", label: temperatures ? "Máxima del caso base" : "Diferencial del caso base", color: "#6c7780", dash: true});
  const threshold = temperatures ? 70 : 20;
  elements.legend.innerHTML = [...series, {label: `Límite ${threshold} °C`, color: "#a74b1a", dash: true}]
    .map(line => `<span class="${line.dash ? "dash" : ""}" style="--series:${line.color}">${line.label}</span>`).join("");
  elements["reference-note"].textContent = activeBase
    ? "Referencia: vertida única sin manta, a 18 °C y en malla de barrido, con la misma curva M1 y el mismo clima. Cada serie termina en su propio horizonte."
    : elements.reference.checked
      ? (base ? "La corrida seleccionada ya es el caso base." : "Esta combinación de clima y curva no tiene caso base guardado.")
      : "";
  const canvas = elements.chart;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext("2d");
  context.scale(scale, scale);
  const top = 18, left = 47, right = width - 17, bottom = height - 45;
  const xMax = Math.max(run.horizonte_h, activeBase?.horizonte_h ?? 0);
  const values = series.flatMap(line => line.run.series[line.key]).filter(value => value !== null);
  const yStep = temperatures ? 10 : 5;
  const yMin = Math.min(0, yStep * Math.floor(Math.min(...values) / yStep));
  const yMax = yStep * Math.ceil(Math.max(threshold + yStep, ...values) / yStep);
  const x = hour => left + hour / xMax * (right - left);
  const y = value => bottom - (value - yMin) / (yMax - yMin) * (bottom - top);
  plotBounds = {left, right, xMax};
  const index = Number(elements.time.value);
  const hour = run.series.t_h[index];
  context.font = "12px Segoe UI, sans-serif";
  context.fillStyle = "#49616b";
  context.textAlign = "right";
  for (let value = yMin; value <= yMax; value += yStep) {
    context.strokeStyle = "#dce7e7";
    context.beginPath();
    context.moveTo(left, y(value));
    context.lineTo(right, y(value));
    context.stroke();
    context.fillText(String(value), left - 7, y(value) + 4);
  }
  context.textAlign = "center";
  const tick = xMax > 450 ? (width > 530 ? 96 : 168) : (width > 530 ? 72 : 120);
  for (let time = 0; time <= xMax; time += tick) context.fillText(String(time), x(time), bottom + 17);
  context.fillText("Horas desde el inicio", (left + right) / 2, height - 6);
  context.textAlign = "left";
  context.fillText("°C", 8, 12);
  context.save();
  context.strokeStyle = "#a74b1a";
  context.setLineDash([5, 5]);
  context.beginPath();
  context.moveTo(left, y(threshold));
  context.lineTo(right, y(threshold));
  context.stroke();
  for (const line of series) {
    context.setLineDash(line.dash ? [6, 4] : []);
    context.strokeStyle = line.color;
    context.lineWidth = line.dash ? 1.6 : 2.2;
    context.beginPath();
    let started = false;
    line.run.series[line.key].forEach((value, i) => {
      if (value === null) {
        started = false;
        return;
      }
      const point = [x(line.run.series.t_h[i]), y(value)];
      if (started) context.lineTo(...point);
      else context.moveTo(...point);
      started = true;
    });
    context.stroke();
  }
  context.restore();
  context.strokeStyle = "#58777a";
  context.beginPath();
  context.moveTo(x(hour), top);
  context.lineTo(x(hour), bottom);
  context.stroke();
  const current = run.series;
  const read = key => current[key][index] === null ? "—" : temperature(current[key][index]);
  elements.reading.textContent = `${format(hour)} h · Máxima ${read("T_max_C")} · Mínima cercana a la superficie ${read("T_superficie_min_C")} · Δ ${read("delta_C")}`;
}

const runGroups = Object.entries(campaigns).map(([campaign, label]) => {
  const group = document.createElement("optgroup");
  group.label = label;
  group.append(...allRuns.filter(run => run.campaign === campaign).map(run => option(run.id,
    `${planName(run.plan, run.campaign)} / ${levelName(run.nivel)} / ${curve(run.curva)} / ${climate(run.clima)}`)));
  return group;
});
elements.run.replaceChildren(...runGroups);
elements.schedule.innerHTML = evidence.schedule.filter(row => row.plan === "unica").map(row =>
  `<div><strong>V${row.vertida}</strong><progress max="220" value="${row.volumen_m3}" aria-label="Volumen V${row.vertida}"></progress><span>${format(row.volumen_m3, 3)} m³</span></div>`).join("");

elements.campaign.addEventListener("change", setCaseLevels);
elements.level.addEventListener("change", () => showCases());
elements.weights.addEventListener("change", () => showCases());
elements.cases.addEventListener("click", event => {
  const button = event.target.closest("[data-plan]");
  if (!button) return;
  activePlan = button.dataset.plan;
  showCases({restoreFocus: true});
});
elements.scenarios.addEventListener("click", event => {
  const button = event.target.closest("[data-run]");
  if (!button) return;
  updateRun(button.dataset.run);
  elements.run.focus({preventScroll: true});
  elements.curvas.scrollIntoView();
});
elements["hero-run"].addEventListener("click", () => updateRun(critical.id));
elements.run.addEventListener("change", () => updateRun(elements.run.value));
elements.metric.addEventListener("change", () => updateRun(elements.run.value));
elements.reference.addEventListener("change", draw);
elements.time.addEventListener("input", draw);
elements.chart.addEventListener("pointermove", event => {
  if (!plotBounds || event.pointerType === "touch") return;
  const {left, right, xMax} = plotBounds;
  const x = event.clientX - elements.chart.getBoundingClientRect().left;
  const hour = Math.max(0, Math.min(xMax, (x - left) / (right - left) * xMax));
  elements.time.value = closestIndex(currentRun().series.t_h, hour);
  draw();
});
setCaseLevels();
updateRun(fineCritical.id);
new ResizeObserver(draw).observe(elements.chart.parentElement);
