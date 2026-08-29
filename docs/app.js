import { drawChart } from "./chart.js";

const stamp = (iso) => Date.parse(`${iso}Z`);

function seriesOf(block) {
    return {
        recent: (block.recent || []).map((p) => ({ t: stamp(p.timestamp), v: p.actual_mw })),
        forecast: (block.forecast || []).map((p) => ({ t: stamp(p.timestamp), v: p.predicted_mw })),
    };
}

function stat(value, label) {
    const node = document.createElement("div");
    node.className = "stat";
    node.innerHTML = `<div class="value">${value}</div><div class="label">${label}</div>`;
    return node;
}

function renderHeadline(payload) {
    const metrics = payload.metrics || {};
    const improvement = metrics.improvement ? `${(metrics.improvement.mae * 100).toFixed(1)}%` : "n/a";
    const mae = metrics.model ? `${Math.round(metrics.model.mae).toLocaleString("en-GB")} MW` : "n/a";
    const mape = metrics.model ? `${metrics.model.mape.toFixed(2)}%` : "n/a";
    document.getElementById("headline").append(
        stat(improvement, "lower MAE than a seasonal-naive baseline"),
        stat(mae, "mean absolute error, held-out weeks"),
        stat(mape, "mean absolute percentage error"),
        stat(Object.keys(payload.countries).length, "grids forecast weekly")
    );
}

function renderLegend() {
    document.getElementById("legend").innerHTML =
        '<span><i class="swatch actual"></i>actual</span><span><i class="swatch forecast"></i>forecast</span>';
}

function renderMultiples(payload, issued) {
    const host = document.getElementById("multiples");
    for (const [code, block] of Object.entries(payload.countries)) {
        const cell = document.createElement("div");
        cell.className = "multiple";
        cell.innerHTML = `<div class="name">${code}</div>`;
        const plot = document.createElement("div");
        cell.appendChild(plot);
        host.appendChild(cell);
        drawChart(plot, { ...seriesOf(block), issued, compact: true });
    }
}

function renderHero(payload, issued, codes) {
    const tabs = document.getElementById("tabs");
    const hero = document.getElementById("hero");
    let current = codes[0];

    const paint = () => {
        for (const button of tabs.children) {
            button.setAttribute("aria-selected", String(button.dataset.code === current));
        }
        drawChart(hero, { ...seriesOf(payload.countries[current]), issued });
    };

    for (const code of codes) {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "tab");
        button.dataset.code = code;
        button.textContent = code;
        button.addEventListener("click", () => {
            current = code;
            paint();
        });
        tabs.appendChild(button);
    }

    paint();
    addEventListener("resize", paint);
}

async function main() {
    const response = await fetch(`data/latest.json?v=${Date.now()}`);
    const payload = await response.json();
    const issued = stamp(payload.issued);
    const codes = Object.keys(payload.countries).sort();

    document.getElementById("issued").textContent =
        `Data through ${new Date(issued).toISOString().slice(0, 16).replace("T", " ")} UTC. Republished every Monday at 07:00 UTC.`;

    renderHeadline(payload);
    renderLegend();
    renderHero(payload, issued, codes);
    renderMultiples(payload, issued);
}

main();