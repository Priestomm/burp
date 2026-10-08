import type { ReactNode, SVGProps } from "react";
import styles from "./stickers.module.css";

export const INK = "#171311";

type Props = {
  /** Path data in a box from (0, 0) to (width, height). */
  d: string;
  width: number;
  height: number;
  fill: string;
  /** Degrees; every sticker sits slightly askew. */
  rotate?: number;
  /** Accessible name; leave empty for a decorative sticker. */
  label?: string;
  className?: string;
  children?: ReactNode;
} & Omit<SVGProps<SVGSVGElement>, "fill" | "width" | "height" | "children">;

/** Kiss-cut sticker: the shape filled, an ink edge, a white backing margin around it. */
export function Sticker({
  d,
  width,
  height,
  fill,
  rotate = 0,
  label,
  className,
  children,
  ...rest
}: Props) {
  const pad = 8; // room for the 5 px white margin and the edge, at 1:1 scale
  return (
    <svg
      viewBox={`${-pad} ${-pad} ${width + pad * 2} ${height + pad * 2}`}
      className={[styles.sticker, className].filter(Boolean).join(" ")}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      {...rest}
    >
      <g transform={rotate ? `rotate(${rotate} ${width / 2} ${height / 2})` : undefined}>
        <path d={d} className={styles.kiss} />
        <path d={d} fill={fill} className={styles.edge} />
        {children}
      </g>
    </svg>
  );
}
