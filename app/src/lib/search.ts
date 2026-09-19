import type { Ingredient } from './data';
import { normalizeName } from './matching';

/**
 * Autocomplete: ingredients whose name or synonym (Italian or English) matches the query.
 * Exact matches rank first, then names starting with the query, then names containing it.
 */
export function searchIngredients(
  ingredients: readonly Ingredient[],
  query: string,
  exclude: ReadonlySet<string> = new Set(),
  limit = 8,
): Ingredient[] {
  const needle = normalizeName(query);
  if (!needle) return [];

  const ranked: { ingredient: Ingredient; rank: number }[] = [];
  for (const ingredient of ingredients) {
    if (exclude.has(ingredient.id)) continue;
    const names = [
      ingredient.name_it,
      ingredient.name_en,
      ...(ingredient.synonyms_it ?? []),
      ...(ingredient.synonyms_en ?? []),
    ].map(normalizeName);
    if (names.some((n) => n === needle)) ranked.push({ ingredient, rank: 0 });
    else if (names.some((n) => n.startsWith(needle))) ranked.push({ ingredient, rank: 1 });
    else if (names.some((n) => n.includes(needle))) ranked.push({ ingredient, rank: 2 });
  }
  ranked.sort(
    (a, b) => a.rank - b.rank || a.ingredient.name_it.localeCompare(b.ingredient.name_it, 'it'),
  );
  return ranked.slice(0, limit).map((r) => r.ingredient);
}
