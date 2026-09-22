// Shared Lake Cumberland map renderer — vanilla JS, no build step.
// Reuses the real USGS-based shoreline/cove data from mapdata.json.

const NS = "http://www.w3.org/2000/svg";
function sv(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const k in (attrs || {})) el.setAttribute(k, attrs[k]);
  return el;
}

const PIN_COLOR = { business: "#C2410C", stay: "#0E7C86", custom: "#6D28D9" };
const PIN_LABEL = { business: "Business", stay: "Cabin / Stay", custom: "Custom" };

class LakeMap {
  constructor(svgEl, mapdata) {
    this.svg = svgEl;
    this.data = mapdata;
    this.W = mapdata.W;
    this.H = mapdata.H;
    svgEl.setAttribute("viewBox", `0 0 ${this.W} ${this.H}`);
    this.layers = {
      water: sv("g"),
      rings: sv("g", { opacity: "0.35" }),
      shore: sv("g"),
      roads: sv("g", { opacity: "0.55" }),
      coves: sv("g"),
      pins: sv("g"),
      draft: sv("g"),
    };
    Object.values(this.layers).forEach((g) => svgEl.appendChild(g));
    this._draw();
  }

  _draw() {
    const d = this.data;
    this.layers.water.appendChild(sv("rect", { x: 0, y: 0, width: this.W, height: this.H, fill: "var(--water)" }));
    for (const ring of d.rings || []) {
      if (!ring) continue;
      this.layers.rings.appendChild(sv("path", { d: ring, fill: "none", stroke: "var(--shore)", "stroke-width": 1 }));
    }
    if (d.deep2) this.layers.water.appendChild(sv("path", { d: d.deep2, fill: "var(--water-deep)", opacity: 0.5 }));
    if (d.deep) this.layers.water.appendChild(sv("path", { d: d.deep, fill: "var(--water-deep)", opacity: 0.5 }));
    if (d.shore) {
      this.layers.shore.appendChild(sv("path", { d: d.shore, fill: "var(--land)", stroke: "var(--shore)", "stroke-width": 1.4 }));
    }
    for (const r of d.sideRoads || []) {
      if (!r.pts || r.pts.length < 2) continue;
      const path = "M" + r.pts.map((p) => p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" L");
      this.layers.roads.appendChild(sv("path", { d: path, fill: "none", stroke: "var(--road)", "stroke-width": 1.1 }));
    }
    for (const c of d.coves || []) {
      if (c.t > 2) continue; // keep the base map uncluttered; only show the bigger names
      const t = sv("text", { x: c.x + 3, y: c.y, class: "cove-label" });
      t.textContent = c.n;
      this.layers.coves.appendChild(t);
    }
  }

  project(lat, lon) {
    const d = this.data;
    const x = ((lon - d.lon0) / (d.lon1 - d.lon0)) * this.W;
    const y = ((d.lat0 - lat) / (d.lat0 - d.lat1)) * this.H;
    return [x, y];
  }

  unproject(x, y) {
    const d = this.data;
    const lon = d.lon0 + (x / this.W) * (d.lon1 - d.lon0);
    const lat = d.lat0 - (y / this.H) * (d.lat0 - d.lat1);
    return [lat, lon];
  }

  clientToSvg(clientX, clientY) {
    const rect = this.svg.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * this.W;
    const y = ((clientY - rect.top) / rect.height) * this.H;
    return [x, y];
  }

  renderPins(pins, { onClick } = {}) {
    this.layers.pins.innerHTML = "";
    for (const p of pins) {
      const [x, y] = this.project(p.lat, p.lon);
      const g = sv("g", { transform: `translate(${x} ${y})`, class: "pin-marker", "data-id": p.id, tabindex: "0", role: "button" });
      g.appendChild(sv("circle", { r: 7, fill: PIN_COLOR[p.pin_type] || "#333", stroke: "#fff", "stroke-width": 1.6 }));
      g.appendChild(sv("circle", { r: 2.2, fill: "#fff" }));
      if (onClick) g.addEventListener("click", () => onClick(p));
      this.layers.pins.appendChild(g);
    }
  }

  // Lets the viewer click anywhere on the map to drop/move a single draft
  // marker; calls onPick(lat, lon) every time it moves.
  enablePlacement(onPick) {
    this.layers.draft.innerHTML = "";
    const marker = sv("g", { class: "draft-marker" });
    marker.appendChild(sv("circle", { r: 9, fill: "none", stroke: "#E5533D", "stroke-width": 2.4 }));
    marker.appendChild(sv("circle", { r: 3, fill: "#E5533D" }));
    marker.style.display = "none";
    this.layers.draft.appendChild(marker);

    this.svg.style.cursor = "crosshair";
    const handler = (evt) => {
      const [cx, cy] = "touches" in evt ? [evt.touches[0].clientX, evt.touches[0].clientY] : [evt.clientX, evt.clientY];
      const [x, y] = this.clientToSvg(cx, cy);
      marker.setAttribute("transform", `translate(${x} ${y})`);
      marker.style.display = "";
      const [lat, lon] = this.unproject(x, y);
      onPick(lat, lon);
    };
    this.svg.addEventListener("click", handler);
    this._placementHandler = handler;
  }

  disablePlacement() {
    if (this._placementHandler) this.svg.removeEventListener("click", this._placementHandler);
    this.svg.style.cursor = "";
  }
}

window.LakeMap = LakeMap;
window.PIN_LABEL = PIN_LABEL;
window.PIN_COLOR = PIN_COLOR;
