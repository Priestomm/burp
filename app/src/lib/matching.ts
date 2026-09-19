import type { Ingredient } from './data';

/**
 * Decides whether a recipe ingredient is covered by what the user has.
 *
 * The default implementation compares canonical ids only. This interface is the extension
 * point for fuzzier matching.
 * TODO: add an embedding-based matcher (Transformers.js) so that, e.g., "penne" can stand in
 * for "pasta" or "borlotti" for "pinto beans". Not implemented yet.
 */
export interface IngredientMatcher {
  /** Maps free text (a name or a synonym, in Italian or English) to a canonical id. */
  resolve(text: string): string | null;
  /** True if the required canonical ingredient is covered by the available ones. */
  isAvailable(requiredId: string, availableIds: ReadonlySet<string>): boolean;
}

export function normalizeName(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Matches on canonical ids; free text is resolved through names and synonyms. */
export class ExactSynonymMatcher implements IngredientMatcher {
  private readonly idByName = new Map<string, string>();

  constructor(ingredients: readonly Ingredient[]) {
    // Canonical names win over synonyms shared with other ingredients, so register them first.
    for (const ingredient of ingredients) {
      for (const name of [
        ingredient.id.replaceAll('_', ' '),
        ingredient.name_en,
        ingredient.name_it,
      ]) {
        this.idByName.set(normalizeName(name), ingredient.id);
      }
    }
    for (const ingredient of ingredients) {
      for (const name of [...(ingredient.synonyms_en ?? []), ...(ingredient.synonyms_it ?? [])]) {
        const key = normalizeName(name);
        if (!this.idByName.has(key)) this.idByName.set(key, ingredient.id);
      }
    }
  }

  resolve(text: string): string | null {
    return this.idByName.get(normalizeName(text)) ?? null;
  }

  isAvailable(requiredId: string, availableIds: ReadonlySet<string>): boolean {
    return availableIds.has(requiredId);
  }
}
