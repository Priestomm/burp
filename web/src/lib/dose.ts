/**
 * Portion scaling: every quantity times n / servings in the post, written the way a person
 * would say it in a kitchen. Pure functions, no React.
 *
 * - grams and ml: above 100 rounded to 5, below to the unit;
 * - spoons are counted in teaspoons (1 cucchiaio = 3 cucchiaini): a multiple of 3 is shown in
 *   cucchiai, from two spoons up half spoons too, the rest in cucchiaini with ½ ⅓ ⅔, and under ⅕
 *   of a teaspoon "un pizzico";
 * - liquids under 35 ml also get spoons (15 ml = 1 cucchiaio);
 * - q.b. stays q.b., and unknown quantities stay unknown until the user fills them in.
 */
import type { IngredientView } from "@/lib/api/server";

export type DoseLine = {
  /** What to show on the right: "135 g", "1 cucchiaio", "q.b.", or null when unknown. */
  value: string | null;
  /** Small print under it: "nel reel: 400 g", "circa 1 cucchiaio". */
  note: string | null;
  status: IngredientView["status"];
};

const FRACTIONS: [number, string][] = [
  [0, ""],
  [1 / 3, "⅓"],
  [1 / 2, "½"],
  [2 / 3, "⅔"],
  [1, ""],
];

/** 0.5 -> "½", 1.34 -> "1 ⅓", 2 -> "2": the nearest of whole, ⅓, ½, ⅔. */
export function readable(x: number): string {
  let whole = Math.floor(x);
  const rest = x - whole;
  let best = FRACTIONS[0];
  for (const candidate of FRACTIONS) {
    if (Math.abs(rest - candidate[0]) < Math.abs(rest - best[0])) best = candidate;
  }
  if (best[0] === 1) whole += 1;
  if (!best[1]) return String(whole);
  return whole ? `${whole} ${best[1]}` : best[1];
}

function plural(x: number, one: string, many: string): string {
  return x <= 1 ? one : many;
}

/** Teaspoons, as a person would say them. */
export function spoons(tsp: number): string {
  if (tsp < 1 / 5) return "un pizzico";
  const tbsp = tsp / 3;
  if (tsp >= 3 && Math.abs(tbsp - Math.round(tbsp)) < 0.05) {
    const k = Math.round(tbsp);
    return `${k} ${plural(k, "cucchiaio", "cucchiai")}`;
  }
  // From two spoons up, half spoons too: "4 ½ cucchiai", not "13 ½ cucchiaini".
  if (tbsp >= 2 && Math.abs(tbsp * 2 - Math.round(tbsp * 2)) < 0.1) {
    return `${readable(Math.round(tbsp * 2) / 2)} cucchiai`;
  }
  const shown = readable(tsp);
  if (tsp < 1) return shown === "½" ? "½ cucchiaino" : `${shown} di cucchiaino`;
  return `${shown} ${plural(tsp, "cucchiaino", "cucchiaini")}`;
}

/** Grams or millilitres: above 100 to the nearest 5, below to the unit (never 0). */
export function metric(x: number): number {
  return x >= 100 ? Math.round(x / 5) * 5 : Math.max(1, Math.round(x));
}

function asWritten(item: IngredientView): string {
  const q = item.quantity === null ? "" : readable(item.quantity);
  return [q, unitFor(item.quantity ?? 0, item.unit)].filter(Boolean).join(" ");
}

const PLURALS: Record<string, string> = {
  cucchiaio: "cucchiai",
  cucchiaino: "cucchiaini",
  tazza: "tazze",
  spicchio: "spicchi",
  fetta: "fette",
  foglia: "foglie",
  pezzo: "pezzi",
  lattina: "lattine",
};

/** The unit agreeing with the number: "3 cucchiai", "2 spicchi", "1 lattina da 15 oz". */
function unitFor(n: number, unit: string | null): string | null {
  if (!unit) return unit;
  const [head, ...rest] = unit.split(" ");
  return n > 1 && PLURALS[head] ? [PLURALS[head], ...rest].join(" ") : unit;
}

function pieces(n: number, unit: string | null): string {
  // Whole pieces and halves: "½ cipolla", "2 spicchi".
  const rounded = Math.max(0.5, Math.round(n * 2) / 2);
  return [readable(rounded), unitFor(rounded, unit)].filter(Boolean).join(" ");
}

export function scale(item: IngredientView, people: number, servings: number | null): DoseLine {
  const { status } = item;
  if (status === "to_taste") return { value: "q.b.", note: null, status };
  if (status === "missing") return { value: null, note: null, status };
  if (status === "by_eye") return { value: "a occhio", note: null, status };

  const factor = servings ? people / servings : 1;
  const scaled = factor !== 1;
  const estimated = status === "estimated";
  const fromPost = estimated
    ? `stima: ${item.estimate_reason ?? "dell'AI"}`
    : item.edited
      ? "scritto da te"
      : `nel reel: ${asWritten(item)}`;
  const note = scaled || item.edited || estimated ? fromPost : null;

  if (item.base_unit === null || item.base_quantity === null) {
    // Not scalable as a measure ("lattina da 15 oz"): scale the count, keep the unit.
    const value = scaled ? pieces((item.quantity ?? 0) * factor, item.unit) : asWritten(item);
    return { value, note, status };
  }

  const amount = item.base_quantity * factor;
  switch (item.base_unit) {
    case "g":
      return { value: `${metric(amount)} g`, note, status };
    case "ml": {
      const value = `${metric(amount)} ml`;
      if (amount < 35) {
        const tbsp = Math.round((amount / 15) * 2) / 2;
        const spoon = tbsp < 0.5 ? "meno di mezzo cucchiaio" : `circa ${readable(tbsp)} ${plural(tbsp, "cucchiaio", "cucchiai")}`;
        return { value, note: scaled ? `${spoon} · ${fromPost}` : spoon, status };
      }
      return { value, note, status };
    }
    case "tsp":
      return { value: spoons(amount), note, status };
    case "piece":
      return { value: pieces(amount, item.unit), note, status };
  }
}
