/**
 * The dose table of the Zine theme, like a size chart: one row per ingredient, one column
 * per number of people, from 1 to the servings of the post (at least 3).
 */
import type { IngredientView } from "@/lib/api/server";
import { scale } from "./dose";

export type DoseRow = {
  index: number;
  name: string;
  cells: string[]; // "?" when the post does not say
  missing: boolean;
  estimated: boolean;
};

export type DoseTable = { columns: number[]; rows: DoseRow[] };

const MAX_COLUMNS = 8;

export function doseTable(ingredients: IngredientView[], servings: number | null): DoseTable {
  const last = Math.min(MAX_COLUMNS, Math.max(3, servings ?? 3));
  const columns = Array.from({ length: last }, (_, i) => i + 1);
  const rows = ingredients.map((item) => ({
    index: item.index,
    name: item.name,
    cells: columns.map((n) => scale(item, n, servings).value ?? "?"),
    missing: item.status === "missing",
    estimated: item.status === "estimated",
  }));
  // Unknown quantities together at the bottom, so one marker loop can circle them.
  return { columns, rows: [...rows.filter((r) => !r.missing), ...rows.filter((r) => r.missing)] };
}
