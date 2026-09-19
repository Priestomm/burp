import type { Ingredient, Recipe, RecipeIngredient } from './data';
import type { DietMode } from './db';
import type { IngredientMatcher } from './matching';

/** A missing core ingredient weighs much more than a missing optional one. */
export const CORE_WEIGHT = 5;
export const OPTIONAL_WEIGHT = 1;
/** Minimum score for a recipe that misses core ingredients to count as "almost there". */
export const CLOSE_THRESHOLD = 0.6;

/** ready: cookable now; close: missing little; far: missing a lot; none: no dish for the country. */
export type Level = 'ready' | 'close' | 'far' | 'none';

export interface RecipeScore {
  recipe: Recipe;
  have: RecipeIngredient[];
  missing: RecipeIngredient[];
  missingCore: RecipeIngredient[];
  /** Share of the ingredient weight that is available, from 0 to 1. */
  score: number;
  level: Exclude<Level, 'none'>;
}

export interface CountryScore {
  countryCode: string;
  best: RecipeScore;
  /** The other compatible dishes of the country, best first. */
  others: RecipeScore[];
  level: Exclude<Level, 'none'>;
}

export interface ScoringContext {
  available: ReadonlySet<string>;
  mode: DietMode;
  matcher: IngredientMatcher;
}

/**
 * Ingredients considered available: the pantry plus the base pantry. In vegan mode, base
 * pantry items that are not vegan are dropped.
 */
export function buildAvailable(
  pantry: readonly string[],
  basePantry: readonly string[],
  ingredients: readonly Ingredient[],
  mode: DietMode,
): Set<string> {
  const veganIds = new Set(ingredients.filter((i) => i.is_vegan).map((i) => i.id));
  const base = mode === 'vegan' ? basePantry.filter((id) => veganIds.has(id)) : basePantry;
  return new Set([...pantry, ...base]);
}

export function isCompatible(recipe: Recipe, mode: DietMode): boolean {
  return mode === 'vegetarian' || recipe.diet === 'vegan';
}

export function scoreRecipe(
  recipe: Recipe,
  available: ReadonlySet<string>,
  matcher: IngredientMatcher,
): RecipeScore {
  const have: RecipeIngredient[] = [];
  const missing: RecipeIngredient[] = [];
  let haveWeight = 0;
  let totalWeight = 0;

  for (const item of recipe.ingredients) {
    const weight = item.is_core ? CORE_WEIGHT : OPTIONAL_WEIGHT;
    totalWeight += weight;
    if (matcher.isAvailable(item.ingredient_id, available)) {
      have.push(item);
      haveWeight += weight;
    } else {
      missing.push(item);
    }
  }

  const missingCore = missing.filter((item) => item.is_core);
  const score = totalWeight === 0 ? 0 : haveWeight / totalWeight;
  const level = missingCore.length === 0 ? 'ready' : score >= CLOSE_THRESHOLD ? 'close' : 'far';
  return { recipe, have, missing, missingCore, score, level };
}

/** Best first: higher score, then traditional dishes before adaptations, then id. */
function compareScores(a: RecipeScore, b: RecipeScore): number {
  if (b.score !== a.score) return b.score - a.score;
  const aAdapted = a.recipe.adaptation ? 1 : 0;
  const bAdapted = b.recipe.adaptation ? 1 : 0;
  if (aAdapted !== bAdapted) return aAdapted - bAdapted;
  return a.recipe.id.localeCompare(b.recipe.id);
}

/**
 * Scores every country that has at least one dish compatible with the diet mode; each
 * country takes the score of its best dish. Countries without compatible dishes are absent.
 */
export function scoreCountries(
  recipes: readonly Recipe[],
  context: ScoringContext,
): Map<string, CountryScore> {
  const byCountry = new Map<string, RecipeScore[]>();
  for (const recipe of recipes) {
    if (!isCompatible(recipe, context.mode)) continue;
    const scored = scoreRecipe(recipe, context.available, context.matcher);
    const list = byCountry.get(recipe.country_code);
    if (list) list.push(scored);
    else byCountry.set(recipe.country_code, [scored]);
  }

  const result = new Map<string, CountryScore>();
  for (const [countryCode, scores] of byCountry) {
    scores.sort(compareScores);
    const [best, ...others] = scores;
    result.set(countryCode, { countryCode, best, others, level: best.level });
  }
  return result;
}
