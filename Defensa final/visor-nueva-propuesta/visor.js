"use strict";

const data = window.DATOS_PROPUESTA;
const select = id => document.getElementById(id);
const runSelect = select("corrida");
const metricSelect = select("metrica");
const weightSelect = select("pesos");
const reference = select("referencia");
const slider = select("hora");
const canvas = select("grafico");
const runs = [data.critica, ...data.matriz, data.referencia];
const baselineIndex = runs.length - 1;
const number = (value, digits = 2) => value.toLocaleString("es-CL", {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
});
const temperature = (value, digits = 2) => number(value, digits) + " °C";
const scenario = run => run.curva.replace("_", " ") + " / " + run.clima.replace("era5_", "ERA5 ");
const mode = index => index === 0 ? "Confirmación 20 cm" : index === baselineIndex ? "Contacto directo" : "Malla fina";
const weight = run => (run.curva === "M1_SS" ? Number(weightSelect.value) : 1 - Number(weightSelect.value)) / 3;
let plot = null;

runs.forEach((run, index) => runSelect.add(new Option(mode(index) + " · " + scenario(run), index)));

function updateMatrix() {
  const active = Number(runSelect.value);
  const table = select("matriz");
  table.replaceChildren();
  data.matriz.forEach((run, index) => {
    const row = table.insertRow();
    if (active === index + 1) row.dataset.active = "";
    const button = document.createElement("button");
    button.textContent = scenario(run);
    button.setAttribute("aria-pressed", String(active === index + 1));
    button.addEventListener("click", () => {
      runSelect.value = index + 1;
      updateRun();
      select("curvas").scrollIntoView();
      runSelect.focus({preventScroll: true});
    });
    row.insertCell().append(button);
    for (const value of [
      number(weight(run) * 100) + " %", temperature(run.maxima, 3),
      temperature(run.delta, 3), number(run.horizonte, 0) + " h",
    ]) row.insertCell().textContent = value;
    const status = document.createElement("span");
    status.className = "badge " + (run.excede ? "fail" : "pass");
    status.textContent = run.excede ? "Excede" : "Cumple";
    row.insertCell().append(status);
  });
  const probability = data.matriz.reduce((total, run) => total + weight(run) * run.excede, 0);
  const passes = data.matriz.filter(run => !run.excede).length;
  select("riesgo").textContent =
    passes + " de 6 escenarios cumplen. Probabilidad conjunta observada: " +
    number(probability * 100, 1) + " % frente al máximo permitido de 5 %.";
}

function updateRun() {
  const index = Number(runSelect.value);
  const run = runs[index];
  const peak = metricSelect.value === "temp" ? run.picoT : run.picoDelta;
  slider.max = run.series.length - 1;
  slider.value = run.series.findIndex(row => row[0] === peak);
  reference.disabled = index !== 0;
  select("resumen").textContent = "T máxima " + temperature(run.maxima, 3) +
    " a " + number(run.picoT) + " h  ·  Δ máximo " + temperature(run.delta, 3) +
    " a " + number(run.picoDelta) + " h  ·  Horizonte " + number(run.horizonte, 0) + " h";
  select("nota").textContent = index === 0
    ? "La referencia comparte escenario, malla y colocación, y termina a las 672 h. La serie se muestra cada hora y conserva las horas exactas de los máximos."
    : "La superposición está disponible en la comprobación de 20 cm para comparar el mismo escenario y la misma malla.";
  updateMatrix();
  draw();
}

function draw() {
  const index = Number(runSelect.value);
  const run = runs[index];
  const isTemp = metricSelect.value === "temp";
  const limit = isTemp ? 70 : 20;
  const curves = isTemp
    ? [[run, 1, "#086d61", "Máxima del hormigón"], [run, 2, "#315f9c", "Mínima cerca de la superficie"]]
    : [[run, 3, "#086d61", "Diferencial de la corrida"]];
  if (index === 0 && reference.checked)
    curves.push([data.referencia, isTemp ? 1 : 3, "#647582", "Contacto directo", true]);

  select("leyenda").replaceChildren(...[...curves, [null, null, "#a74b1a", "Límite " + limit + " °C", true]]
    .map(([, , color, label, dashed]) => {
      const item = document.createElement("span");
      item.style.setProperty("--series", color);
      item.textContent = label;
      if (dashed) item.className = "dash";
      return item;
    }));

  const row = run.series[Number(slider.value)];
  select("lectura").textContent = number(row[0]) + " h · Caliente " + temperature(row[1]) +
    " · Frío " + temperature(row[2]) + " · Diferencial " + temperature(row[3]);
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const left = 42, right = width - 17, top = 13, bottom = height - 36;
  const step = isTemp ? 10 : 5;
  const values = curves.flatMap(([source, col]) => source.series.map(point => point[col]));
  const maximum = Math.ceil(Math.max(limit + step, ...values) / step) * step;
  const x = t => left + t / run.horizonte * (right - left);
  const y = v => bottom - v / maximum * (bottom - top);
  plot = {left, right, horizon: run.horizonte};
  function line(x1, y1, x2, y2, color, dash = []) {
    ctx.strokeStyle = color;
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }
  ctx.font = "12px Segoe UI, sans-serif";
  ctx.fillStyle = "#49616b";
  ctx.textAlign = "right";
  for (let value = 0; value <= maximum; value += step) {
    line(left, y(value), right, y(value), "#dce7e7");
    ctx.fillText(String(value), left - 7, y(value) + 4);
  }
  ctx.textAlign = "center";
  const timeStep = width < 520 ? 240 : 120;
  for (let t = 0; t <= run.horizonte; t += timeStep) ctx.fillText(String(t), x(t), bottom + 15);
  ctx.fillText("Horas desde el inicio", (left + right) / 2, height - 4);
  ctx.textAlign = "left";
  ctx.fillText("°C", 7, 12);
  line(left, y(limit), right, y(limit), "#a74b1a", [5, 5]);
  for (const [source, col, color, , dashed] of curves) {
    ctx.strokeStyle = color;
    ctx.lineWidth = dashed ? 1.5 : 2.1;
    ctx.setLineDash(dashed ? [6, 4] : []);
    ctx.beginPath();
    source.series.forEach((point, i) => {
      if (i === 0) ctx.moveTo(x(point[0]), y(point[col]));
      else ctx.lineTo(x(point[0]), y(point[col]));
    });
    ctx.stroke();
  }
  ctx.lineWidth = 1;
  line(x(row[0]), top, x(row[0]), bottom, "#58777a");
}

runSelect.addEventListener("change", updateRun);
metricSelect.addEventListener("change", updateRun);
weightSelect.addEventListener("change", updateMatrix);
reference.addEventListener("change", draw);
slider.addEventListener("input", draw);
canvas.addEventListener("pointermove", event => {
  if (!plot || event.pointerType === "touch") return;
  const local = event.clientX - canvas.getBoundingClientRect().left;
  const time = (local - plot.left) / (plot.right - plot.left) * plot.horizon;
  const series = runs[Number(runSelect.value)].series;
  slider.value = series.reduce((closest, row, index) =>
    Math.abs(row[0] - time) < Math.abs(series[closest][0] - time) ? index : closest, 0);
  draw();
});
updateRun();
new ResizeObserver(draw).observe(canvas.parentElement);
