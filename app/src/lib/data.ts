import { base } from '$app/paths';
import type { Dataset } from './types/generated';

export type { Adaptation, Ingredient, Recipe, RecipeIngredient } from './types/generated';

/** Loads the static dataset produced by the pipeline (app/static/data/*.json). */
export async function loadDataset(fetchFn: typeof fetch = fetch): Promise<Dataset> {
  const [ingredients, recipes] = await Promise.all([
    fetchFn(`${base}/data/ingredients.json`).then((r) => json<Dataset['ingredients']>(r)),
    fetchFn(`${base}/data/recipes.json`).then((r) => json<Dataset['recipes']>(r)),
  ]);
  return { ingredients, recipes };
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`Failed to load ${response.url}: ${response.status}`);
  return response.json();
}
