import { Sticker } from "./Sticker";
import { SHAPES, type ShapeName, bubble, scalloped, shapePath, star } from "./shapes";
import styles from "./stickers.module.css";

/** Tomato starburst with the diet in big letters, and course and cuisine under it. */
export function DietStar({ diet, lines }: { diet: string; lines: string[] }) {
  return (
    <Sticker
      d={star(192, 192)}
      width={192}
      height={192}
      fill="var(--tomato)"
      rotate={-11}
      label={[diet, ...lines].join(", ")}
    >
      {/* About 0.45 em per condensed capital: keep the word inside the star's 148 units. */}
      <text x={96} y={100} className={styles.cond} fontSize={Math.min(44, 148 / (diet.length * 0.45))} fill="var(--cream)">
        {diet}
      </text>
      {lines.map((line, i) => (
        <text key={line} x={96} y={124 + i * 18} className={styles.body} fontSize={15} fill="var(--cream)">
          {line}
        </text>
      ))}
    </Sticker>
  );
}

/** Sky circle "PER N PERSONA/E", following the portion selector. */
export function ServingsBadge({ n }: { n: number }) {
  const word = n === 1 ? "PERSONA" : "PERSONE";
  return (
    <Sticker d={shapePath("circle", 104, 104)} width={104} height={104} fill="var(--sky)" rotate={9} label={`Per ${n} ${word.toLowerCase()}`}>
      <text x={52} y={30} className={styles.cond} fontSize={19} fill="var(--ink)">
        PER
      </text>
      <text x={52} y={76} className={styles.cond} fontSize={56} fill="var(--ink)">
        {n}
      </text>
      <text x={52} y={94} className={styles.cond} fontSize={12.5} fill="var(--ink)">
        {word}
      </text>
    </Sticker>
  );
}

/** Yolk scalloped button face "L'HO CUCINATA" with how many times so far. */
export function CookedFace({ count }: { count: number }) {
  const times = count === 0 ? "mai, finora" : count === 1 ? "cucinata 1 volta" : `cucinata ${count} volte`;
  return (
    <Sticker d={scalloped(124, 124)} width={124} height={124} fill="var(--yolk)" rotate={5}>
      <text x={62} y={54} className={styles.cond} fontSize={25} fill="var(--ink)">
        L&apos;HO
      </text>
      <text x={62} y={80} className={styles.cond} fontSize={25} fill="var(--ink)">
        CUCINATA
      </text>
      <text x={62} y={98} className={styles.body} fontSize={11} fill="var(--ink)">
        {times}
      </text>
    </Sticker>
  );
}

/** Tomato speech bubble "BURP!" with the day, slapped on the photo when cooked. */
export function BurpStamp({ date, className }: { date: string; className?: string }) {
  return (
    <Sticker d={bubble(184, 124)} width={184} height={124} fill="var(--tomato)" rotate={-8} label={`Burp! Cucinata ${date}`} className={className}>
      <text x={94} y={66} className={styles.cond} fontSize={58} fill="var(--cream)">
        BURP!
      </text>
      <text x={94} y={88} className={styles.body} fontSize={14} fill="var(--cream)">
        {date}
      </text>
    </Sticker>
  );
}

const SHEET_FILLS = ["var(--cream)", "var(--yolk)", "var(--sky)", "var(--tomato)", "var(--ink)"];
const DARK_FILLS = new Set(["var(--tomato)", "var(--ink)"]);

/**
 * Stable look for a recipe on the sticker sheet: same id, same shape and colour, always.
 * Steps coprime with 5 make neighbouring ids (recipes saved one after another) all differ.
 */
export function stickerLook(id: number): { shape: ShapeName; fill: string; ink: string } {
  const fill = SHEET_FILLS[(id * 2 + 1) % SHEET_FILLS.length];
  return {
    shape: SHAPES[(id * 3) % SHAPES.length],
    fill,
    ink: DARK_FILLS.has(fill) ? "var(--cream)" : "var(--ink)",
  };
}

const SHEET_SIZE: Record<ShapeName, [number, number]> = {
  circle: [96, 96],
  pill: [148, 76],
  rounded: [138, 84],
  oval: [140, 86],
  scalloped: [100, 100],
};

/** A recipe on the library sheet: short name and "N da chiarire". */
export function RecipeSticker({
  id,
  line1,
  line2,
  toClarify,
  cooked,
  lifted = false,
}: {
  id: number;
  line1: string;
  line2: string | null;
  toClarify: number;
  cooked: boolean;
  lifted?: boolean;
}) {
  const { shape, fill, ink } = stickerLook(id);
  const [w, h] = SHEET_SIZE[shape];
  const room = shape === "circle" || shape === "scalloped" ? 11 : 16;
  // The first line is the dish itself and stays whole; only the second one is cut.
  const lines = line2 ? [line1, shorten(line2, Math.max(room, line1.length))] : [line1];
  const size = Math.min(19, ((w - 18) / Math.max(...lines.map((l) => l.length))) * 1.9);
  const top = h / 2 - (lines.length - 1) * size * 0.5 - 2;
  return (
    <Sticker d={shapePath(shape, w, h)} width={w} height={h} fill={fill} lifted={lifted}>
      {lines.map((line, i) => (
        <text key={i} x={w / 2} y={top + i * size} className={styles.cond} fontSize={size} fill={ink}>
          {line}
        </text>
      ))}
      <text x={w / 2} y={top + lines.length * size - 1} className={styles.body} fontSize={9.5} fill={ink}>
        {toClarify === 0 ? "tutto chiaro" : `${toClarify} da chiarire`}
      </text>
      {cooked && (
        <g transform={`translate(${w - 14} 2) rotate(12)`}>
          <rect x={-22} y={-9} width={44} height={18} rx={9} fill="var(--tomato)" stroke="var(--ink)" strokeWidth={1.6} />
          <text x={0} y={4.5} className={styles.cond} fontSize={12} fill="var(--cream)">
            BURP!
          </text>
        </g>
      )}
    </Sticker>
  );
}

/** Word-safe cut for a sticker line: "di cardoncelli con crema…" -> "di cardoncelli". */
export function shorten(text: string, max: number): string {
  if (text.length <= max) return text;
  const words = text.split(" ");
  let out = "";
  for (const word of words) {
    const next = out ? `${out} ${word}` : word;
    // Never stop on a bare "di" or "alla": take the next word, the font size will adapt.
    const onlyLinkWords = out.split(" ").every((w) => w.length <= 4);
    if (next.length > max && !(out && onlyLinkWords)) break;
    out = next;
    if (next.length > max) break;
  }
  return out || `${text.slice(0, max - 1)}…`;
}
