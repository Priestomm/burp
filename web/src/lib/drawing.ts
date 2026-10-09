/**
 * The marker's geometry, no React. A stroke is stored against the element it was started on
 * (the photo, an ingredient, a step...), in thousandths of that element's width, on both axes:
 * when the page is narrower and the text wraps differently, the stroke follows its element and
 * keeps its shape.
 */

export type Point = { x: number; y: number };
/** An element's position on screen (`getBoundingClientRect()` has these). */
export type Box = { left: number; top: number; width: number };

export const UNITS = 1000;
/** The API refuses longer paths (see burp/models.py). */
export const MAX_PATH = 20_000;
export const MAX_STROKES = 500;

/** Drop points closer than `gap` pixels to the last one kept: a hand jitters, a path need not. */
export function thin(points: Point[], gap = 2): Point[] {
  const kept: Point[] = [];
  for (const point of points) {
    const last = kept[kept.length - 1];
    if (!last || Math.hypot(point.x - last.x, point.y - last.y) >= gap) kept.push(point);
  }
  const end = points[points.length - 1];
  if (end && kept[kept.length - 1] !== end && kept.length > 1) kept[kept.length - 1] = end;
  return kept;
}

/** The centre of the box around the points. */
export function middle(points: Point[]): Point {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  return { x: (Math.min(...xs) + Math.max(...xs)) / 2, y: (Math.min(...ys) + Math.max(...ys)) / 2 };
}

/** Screen points -> the stored SVG path, relative to `box`: "M12 340L15 338". */
export function toPath(points: Point[], box: Box): string {
  const scale = UNITS / box.width;
  const coords = points.map((p) => [
    clamp(Math.round((p.x - box.left) * scale)),
    clamp(Math.round((p.y - box.top) * scale)),
  ]);
  if (coords.length === 1) coords.push(coords[0]); // a dot: round caps draw it
  let path = write(coords);
  // Too long for the API (a very slow scribble): keep every other point until it fits.
  while (path.length > MAX_PATH && coords.length > 2) {
    const fewer = coords.filter((_, i) => i % 2 === 0 || i === coords.length - 1);
    coords.splice(0, coords.length, ...fewer);
    path = write(coords);
  }
  return path;
}

/** Where a stored stroke goes, drawn in the coordinates of `sheet`. */
export function placement(anchor: Box, sheet: Box): string {
  const x = round(anchor.left - sheet.left);
  const y = round(anchor.top - sheet.top);
  return `translate(${x} ${y}) scale(${round(anchor.width / UNITS, 5)})`;
}

/** Screen points as a path in the coordinates of `sheet`, while the stroke is being drawn. */
export function livePath(points: Point[], sheet: Box & { top: number }): string {
  return write(points.map((p) => [round(p.x - sheet.left), round(p.y - sheet.top)]));
}

function write(coords: number[][]): string {
  return coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x} ${y}`).join("");
}

function clamp(n: number): number {
  return Math.max(-99_999, Math.min(99_999, n));
}

function round(n: number, digits = 1): number {
  const f = 10 ** digits;
  return Math.round(n * f) / f;
}
