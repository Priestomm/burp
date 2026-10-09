import { describe, expect, it } from "vitest";
import { MAX_PATH, livePath, middle, placement, thin, toPath } from "./drawing";

// The pattern the API accepts (burp/models.py, STROKE_PATH).
const STROKE_PATH = /^M-?\d{1,5} -?\d{1,5}(L-?\d{1,5} -?\d{1,5})*$/;

describe("toPath", () => {
  it("writes points in thousandths of the element's width, on both axes", () => {
    const box = { left: 100, top: 50, width: 200 };
    const path = toPath([{ x: 100, y: 50 }, { x: 150, y: 70 }, { x: 300, y: 250 }], box);
    expect(path).toBe("M0 0L250 100L1000 1000");
    expect(path).toMatch(STROKE_PATH);
  });

  it("keeps strokes that leave the element, and turns a tap into a dot", () => {
    expect(toPath([{ x: 90, y: 40 }], { left: 100, top: 50, width: 200 })).toBe("M-50 -50L-50 -50");
  });

  it("thins a very long scribble until the API takes it", () => {
    const points = Array.from({ length: 6000 }, (_, i) => ({ x: i % 900, y: (i * 7) % 900 }));
    const path = toPath(points, { left: 0, top: 0, width: 1000 });
    expect(path.length).toBeLessThanOrEqual(MAX_PATH);
    expect(path).toMatch(STROKE_PATH);
    expect(path.endsWith("L" + points.at(-1)!.x + " " + points.at(-1)!.y)).toBe(true);
  });
});

describe("placement", () => {
  it("puts the element's stroke where the element is now, at its current size", () => {
    expect(placement({ left: 120, top: 400, width: 500 }, { left: 20, top: 100, width: 900 })).toBe(
      "translate(100 300) scale(0.5)",
    );
  });

  it("follows the element when the same stroke is drawn on a narrower screen", () => {
    const stroke = toPath([{ x: 300, y: 200 }], { left: 100, top: 100, width: 400 }); // M500 250
    expect(stroke).toBe("M500 250L500 250");
    // On the phone the element is 200 px wide: 500 thousandths of it is 100 px in.
    expect(placement({ left: 16, top: 900, width: 200 }, { left: 0, top: 0, width: 360 })).toBe(
      "translate(16 900) scale(0.2)",
    );
  });
});

describe("thin and livePath", () => {
  it("drops jitter but keeps where the pen lifted", () => {
    const points = [{ x: 0, y: 0 }, { x: 0.5, y: 0.5 }, { x: 5, y: 0 }, { x: 5.5, y: 0.2 }];
    expect(thin(points)).toEqual([{ x: 0, y: 0 }, { x: 5.5, y: 0.2 }]);
  });

  it("draws the stroke in progress in the sheet's coordinates", () => {
    expect(livePath([{ x: 30, y: 40 }, { x: 35, y: 41 }], { left: 10, top: 20, width: 500 })).toBe(
      "M20 20L25 21",
    );
  });
});

describe("middle", () => {
  it("is the centre of a ring, not where the ring started", () => {
    const ring = Array.from({ length: 12 }, (_, i) => ({
      x: 200 + 50 * Math.cos((i / 12) * 2 * Math.PI),
      y: 100 + 30 * Math.sin((i / 12) * 2 * Math.PI),
    }));
    const { x, y } = middle(ring);
    expect([Math.round(x), Math.round(y)]).toEqual([200, 100]);
  });
});
