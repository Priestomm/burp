/* Generated from pipeline/schema/*.json by scripts/generate-types.mjs. Do not edit. */

export interface Dataset {
  ingredients: Ingredient[];
  recipes: Recipe[];
}
/**
 * A canonical ingredient with names and synonyms in Italian and English.
 */
export interface Ingredient {
  /**
   * Canonical snake_case id
   */
  id: string;
  name_en: string;
  name_it: string;
  synonyms_en?: string[];
  synonyms_it?: string[];
  is_vegetarian: boolean;
  is_vegan: boolean;
  shelf_life_days?: number | null;
  /**
   * Explains hidden animal origin or other caveats
   */
  notes?: string | null;
}
/**
 * A recipe as published to the app, with `diet` computed from its ingredients.
 */
export interface Recipe {
  id: string;
  name: string;
  name_it: string;
  /**
   * ISO 3166-1 numeric, zero-padded; matches world-atlas feature ids
   */
  country_code: string;
  servings?: number;
  ingredients: RecipeIngredient[];
  steps: string[];
  /**
   * None for traditionally vegetarian/vegan dishes
   */
  adaptation?: Adaptation | null;
  source: string;
  license: string;
  diet: "vegan" | "vegetarian";
}
export interface RecipeIngredient {
  ingredient_id: string;
  /**
   * None means 'to taste'
   */
  quantity?: number | null;
  unit?: string | null;
  /**
   * True if the dish is not the same without it
   */
  is_core: boolean;
}
/**
 * Set when a vegetarian dish is a variant of a traditionally meat or fish dish.
 */
export interface Adaptation {
  original_dish: string;
  changes: string;
}
