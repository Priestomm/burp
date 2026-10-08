import { Sticker } from "./Sticker";
import { bubble } from "./shapes";
import styles from "./stickers.module.css";

/** "burp!" in Gloock cream, in a tomato speech bubble, tilted -6°. */
export function Logo({ className }: { className?: string }) {
  return (
    <Sticker d={bubble(140, 94)} width={140} height={94} fill="var(--tomato)" rotate={-6} label="burp!" className={className}>
      <text x={71} y={54} className={styles.serif} fontSize={46} fill="var(--cream)">
        burp!
      </text>
    </Sticker>
  );
}
