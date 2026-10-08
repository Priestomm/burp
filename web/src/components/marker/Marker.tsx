import type { CSSProperties } from "react";
import styles from "./marker.module.css";

type Drawing = { viewBox: string; paths: string[] };

/**
 * Blue marker strokes. Decorative: what they say must also be in the text.
 * `width` is the stroke in CSS pixels, the same at any size. `draw` makes the strokes write
 * themselves one after the other (not under reduced motion).
 */
export function Marker({
  drawing,
  width = 4,
  draw = false,
  stretch = false,
  className,
  style,
}: {
  drawing: Drawing;
  width?: number;
  draw?: boolean;
  stretch?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      viewBox={drawing.viewBox}
      preserveAspectRatio={stretch ? "none" : undefined}
      className={[styles.marker, draw ? styles.draw : "", className].filter(Boolean).join(" ")}
      style={{ ...style, "--w": `${width}px` } as CSSProperties}
      aria-hidden="true"
    >
      {drawing.paths.map((d, i) => (
        <path key={i} d={d} pathLength={1} style={{ "--i": i } as CSSProperties} />
      ))}
    </svg>
  );
}

/** "8.10" written with the marker digits: a viewBox wide enough for every character. */
export function digitsDrawing(text: string, digits: Record<string, string>): Drawing {
  const chars = [...text].filter((c) => c in digits);
  const paths = chars.map((c, i) => shift(digits[c], i * 34));
  return { viewBox: `0 0 ${Math.max(1, chars.length) * 34 + 6} 62`, paths };
}

/** Moves every x of a path by `dx` (the path uses absolute M and C commands). */
function shift(d: string, dx: number): string {
  let index = 0;
  return d.replace(/-?\d+(?:\.\d+)?/g, (n) => {
    const value = Number(n);
    return String(index++ % 2 === 0 ? value + dx : value);
  });
}
