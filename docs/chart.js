const SVG_NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}) {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
}

function linear(domain, range) {
    const span = domain[1] - domain[0] || 1;
    return (value) => range[0] + ((value - domain[0]) / span) * (range[1] - range[0]);
}

function ticks(min, max, count) {
    const rough = (max - min) / count;
    const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) || magnitude * 10;
    const out = [];
    for (let value = Math.ceil(min / step) * step; value <= max; value += step) out.push(value);
    return out;
}

function pathFor(points, x, y) {
    return points
        .map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`)
        .join("");
}

const DAY = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", timeZone: "UTC" });
const FULL = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });

export function drawChart(host, { recent, forecast, issued, compact = false }) {
    host.textContent = "";
    const series = recent.concat(forecast);
    if (!series.length) return;

    const width = host.clientWidth || 720;
    const height = compact ? 120 : 300;
    const pad = compact
        ? { top: 8, right: 4, bottom: 18, left: 4 }
        : { top: 12, right: 12, bottom: 26, left: 54 };

    const values = series.map((p) => p.v);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const room = (hi - lo) * 0.12 || 1;

    const x = linear([series[0].t, series[series.length - 1].t], [pad.left, width - pad.right]);
    const y = linear([lo - room, hi + room], [height - pad.bottom, pad.top]);

    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width: "100%", height });

    if (!compact) {
        for (const value of ticks(lo - room, hi + room, 4)) {
            svg.appendChild(el("line", { class: "grid", x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value) }));
            const label = el("text", { class: "axis", x: pad.left - 8, y: y(value) + 4, "text-anchor": "end" });
            label.textContent = `${Math.round(value / 1000)} GW`;
            svg.appendChild(label);
        }
        for (const point of series.filter((p) => new Date(p.t).getUTCHours() === 0)) {
            const label = el("text", { class: "axis", x: x(point.t), y: height - 8, "text-anchor": "middle" });
            label.textContent = DAY.format(new Date(point.t));
            svg.appendChild(label);
        }
    }

    svg.appendChild(el("line", { class: "issued-rule", x1: x(issued), x2: x(issued), y1: pad.top, y2: height - pad.bottom }));
    svg.appendChild(el("path", { class: "series-actual", d: pathFor(recent, x, y) }));
    svg.appendChild(el("path", { class: "series-forecast", d: pathFor(forecast, x, y) }));

    host.appendChild(svg);
    if (compact) return;

    const rule = el("line", { class: "issued-rule", y1: pad.top, y2: height - pad.bottom, opacity: 0 });
    const marker = el("circle", { r: 4, fill: "var(--surface-1)", "stroke-width": 2, opacity: 0 });
    svg.appendChild(rule);
    svg.appendChild(marker);

    const tip = document.createElement("div");
    tip.className = "tooltip";
    tip.hidden = true;
    host.appendChild(tip);

    const hide = () => {
        tip.hidden = true;
        marker.setAttribute("opacity", 0);
        rule.setAttribute("opacity", 0);
    };
    svg.addEventListener("pointerleave", hide);

    svg.addEventListener("pointermove", (event) => {
        const box = svg.getBoundingClientRect();
        const at = ((event.clientX - box.left) / box.width) * width;
        let best = series[0];
        for (const point of series) {
            if (Math.abs(x(point.t) - at) < Math.abs(x(best.t) - at)) best = point;
        }
        const isForecast = best.t > issued;
        marker.setAttribute("cx", x(best.t));
        marker.setAttribute("cy", y(best.v));
        marker.setAttribute("stroke", isForecast ? "var(--series-forecast)" : "var(--series-actual)");
        marker.setAttribute("opacity", 1);
        rule.setAttribute("x1", x(best.t));
        rule.setAttribute("x2", x(best.t));
        rule.setAttribute("opacity", 1);
        tip.innerHTML =
            `<div class="k">${FULL.format(new Date(best.t))} UTC</div>` +
            `<div class="v">${Math.round(best.v).toLocaleString("en-GB")} MW &middot; ${isForecast ? "forecast" : "actual"}</div>`;
        tip.hidden = false;
        const left = Math.min(
            Math.max((x(best.t) / width) * box.width - tip.offsetWidth / 2, 0),
            box.width - tip.offsetWidth
        );
        tip.style.left = `${left}px`;
        tip.style.top = `${(y(best.v) / height) * box.height - tip.offsetHeight - 12}px`;
    });
}