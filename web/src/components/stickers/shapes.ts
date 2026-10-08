/**
 * SVG path data for sticker shapes, all drawn in a box from (0, 0) to (w, h).
 * Pure functions, so shapes are stable and testable.
 */

const f = (n: number) => Number(n.toFixed(1));

export function ellipse(w: number, h: number): string {
  const rx = w / 2;
  const ry = h / 2;
  return `M0 ${f(ry)} A${f(rx)} ${f(ry)} 0 1 0 ${f(w)} ${f(ry)} A${f(rx)} ${f(ry)} 0 1 0 0 ${f(ry)} Z`;
}

export function roundedRect(w: number, h: number, r: number): string {
  const k = Math.min(r, w / 2, h / 2);
  return [
    `M${f(k)} 0 H${f(w - k)} A${f(k)} ${f(k)} 0 0 1 ${f(w)} ${f(k)}`,
    `V${f(h - k)} A${f(k)} ${f(k)} 0 0 1 ${f(w - k)} ${f(h)}`,
    `H${f(k)} A${f(k)} ${f(k)} 0 0 1 0 ${f(h - k)}`,
    `V${f(k)} A${f(k)} ${f(k)} 0 0 1 ${f(k)} 0 Z`,
  ].join(" ");
}

/** A round shape with `bumps` soft scallops around the edge (bottle-cap sticker). */
export function scalloped(w: number, h: number, bumps = 16, depth = 0.12): string {
  const cx = w / 2;
  const cy = h / 2;
  const rx = (w / 2) * (1 - depth);
  const ry = (h / 2) * (1 - depth);
  const at = (a: number, k: number) => [cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k];
  const parts: string[] = [];
  for (let i = 0; i <= bumps; i++) {
    const a = (i / bumps) * 2 * Math.PI;
    const [x, y] = at(a, 1);
    if (i === 0) {
      parts.push(`M${f(x)} ${f(y)}`);
      continue;
    }
    const [qx, qy] = at(a - Math.PI / bumps, 1 + depth * 1.9);
    parts.push(`Q${f(qx)} ${f(qy)} ${f(x)} ${f(y)}`);
  }
  return `${parts.join(" ")} Z`;
}

/** A starburst with `spikes` points; `inner` is the valley radius as a share of the outer. */
export function star(w: number, h: number, spikes = 16, inner = 0.82): string {
  const cx = w / 2;
  const cy = h / 2;
  const points: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const a = (i / (spikes * 2)) * 2 * Math.PI;
    const k = i % 2 === 0 ? 1 : inner;
    points.push(`${f(cx + Math.cos(a) * (w / 2) * k)},${f(cy + Math.sin(a) * (h / 2) * k)}`);
  }
  return `M${points.join(" L")} Z`;
}

/** A comic speech bubble with its tail at the bottom left, in a 176 × 116 design box. */
export function bubble(w: number, h: number): string {
  const sx = w / 140;
  const sy = h / 94;
  const p = (x: number, y: number) => `${f((x - 18) * sx)} ${f((y - 12) * sy)}`;
  return [
    `M${p(20, 52)}`,
    `C${p(18, 26)} ${p(46, 12)} ${p(90, 12)}`,
    `C${p(136, 12)} ${p(160, 26)} ${p(158, 52)}`,
    `C${p(156, 78)} ${p(130, 90)} ${p(94, 90)}`,
    `L${p(62, 90)} L${p(36, 106)} L${p(44, 86)}`,
    `C${p(28, 82)} ${p(21, 68)} ${p(20, 52)} Z`,
  ].join(" ");
}

export type ShapeName = "circle" | "pill" | "rounded" | "oval" | "scalloped";

export const SHAPES: ShapeName[] = ["circle", "pill", "rounded", "oval", "scalloped"];

export function shapePath(shape: ShapeName, w: number, h: number): string {
  switch (shape) {
    case "circle": {
      const d = Math.min(w, h);
      return ellipse(d, d);
    }
    case "pill":
      return roundedRect(w, h, h / 2);
    case "rounded":
      return roundedRect(w, h, Math.min(w, h) * 0.24);
    case "oval":
      return ellipse(w, h);
    case "scalloped":
      return scalloped(w, h);
  }
}
