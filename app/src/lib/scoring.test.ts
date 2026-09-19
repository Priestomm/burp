import { describe, expect, it } from 'vitest';
import type { Ingredient, Recipe, RecipeIngredient } from './data';
import { ExactSynonymMatcher } from './matching';
import {
  buildAvailable,
  CORE_WEIGHT,
  OPTIONAL_WEIGHT,
  scoreCountries,
  scoreRecipe,
} from './scoring';

const ingredient = (id: string, is_vegan = true): Ingredient => ({
  id,
  name_en: id,
  name_it: id,
  is_vegetarian: true,
  is_vegan,
});

const INGREDIENTS = [
  ingredient('pasta'),
  ingredient('chickpeas'),
  ingredient('garlic'),
  ingredient('salt'),
  ingredient('egg', false),
  ingredient('butter', false),
];
const matcher = new ExactSynonymMatcher(INGREDIENTS);

const item = (ingredient_id: string, is_core: boolean): RecipeIngredient => ({
  ingredient_id,
  is_core,
});

function recipe(
  id: string,
  country: string,
  items: RecipeIngredient[],
  extra: Partial<Recipe> = {},
): Recipe {
  return {
    id,
    name: id,
    name_it: id,
    country_code: country,
    servings: 1,
    ingredients: items,
    steps: ['Cook.'],
    adaptation: null,
    source: 'test',
    license: 'test',
    diet: 'vegan',
    ...extra,
  };
}

// 2 core (pasta, chickpeas) + 2 optional (garlic, salt): total weight 12.
const pastaAndChickpeas = recipe('pasta-chickpeas', '380', [
  item('pasta', true),
  item('chickpeas', true),
  item('garlic', false),
  item('salt', false),
]);

const score = (available: string[]) => scoreRecipe(pastaAndChickpeas, new Set(available), matcher);

describe('scoreRecipe', () => {
  it('with an empty pantry everything is missing', () => {
    const result = score([]);
    expect(result.score).toBe(0);
    expect(result.have).toHaveLength(0);
    expect(result.missing).toHaveLength(4);
    expect(result.level).toBe('far');
  });

  it('with everything available the recipe is ready with a perfect score', () => {
    const result = score(['pasta', 'chickpeas', 'garlic', 'salt']);
    expect(result.score).toBe(1);
    expect(result.missing).toHaveLength(0);
    expect(result.level).toBe('ready');
  });

  it('missing only an optional ingredient is still ready, with a slightly lower score', () => {
    const result = score(['pasta', 'chickpeas', 'salt']);
    expect(result.level).toBe('ready');
    expect(result.missing.map((m) => m.ingredient_id)).toEqual(['garlic']);
    expect(result.score).toBeCloseTo(1 - OPTIONAL_WEIGHT / (2 * CORE_WEIGHT + 2 * OPTIONAL_WEIGHT));
  });

  it('missing a core ingredient prevents ready and weighs much more than an optional one', () => {
    const coreMissing = score(['pasta', 'garlic', 'salt']);
    const optionalMissing = score(['pasta', 'chickpeas', 'salt']);
    expect(coreMissing.level).not.toBe('ready');
    expect(coreMissing.missingCore.map((m) => m.ingredient_id)).toEqual(['chickpeas']);
    expect(coreMissing.score).toBeLessThan(optionalMissing.score);
    expect(optionalMissing.score - coreMissing.score).toBeCloseTo(
      (CORE_WEIGHT - OPTIONAL_WEIGHT) / 12,
    );
  });

  it('is close when little is missing, far when a lot is', () => {
    // 3 core + 5 optional: total weight 20. Missing one core keeps 75%, missing two keeps 50%.
    const big = recipe('big', '380', [
      ...['a', 'b', 'c'].map((id) => item(id, true)),
      ...['d', 'e', 'f', 'g', 'h'].map((id) => item(id, false)),
    ]);
    const levelWith = (ids: string[]) => scoreRecipe(big, new Set(ids), matcher).level;
    expect(levelWith(['a', 'b', 'd', 'e', 'f', 'g', 'h'])).toBe('close');
    expect(levelWith(['a', 'd', 'e', 'f', 'g', 'h'])).toBe('far');
  });

  it('counts base pantry ingredients as available', () => {
    const available = buildAvailable(
      ['pasta', 'chickpeas'],
      ['garlic', 'salt'],
      INGREDIENTS,
      'vegetarian',
    );
    expect(scoreRecipe(pastaAndChickpeas, available, matcher).level).toBe('ready');
  });
});

describe('buildAvailable', () => {
  it('drops non-vegan base pantry items in vegan mode only', () => {
    const base = ['salt', 'butter'];
    expect(buildAvailable([], base, INGREDIENTS, 'vegetarian')).toEqual(new Set(base));
    expect(buildAvailable([], base, INGREDIENTS, 'vegan')).toEqual(new Set(['salt']));
  });
});

describe('scoreCountries', () => {
  const omelette = recipe('omelette', '250', [item('egg', true), item('butter', false)], {
    diet: 'vegetarian',
  });
  const soup = recipe('soup', '250', [item('chickpeas', true)]);
  const eggOnly = recipe('egg-dish', '392', [item('egg', true)], { diet: 'vegetarian' });
  const recipes = [pastaAndChickpeas, omelette, soup, eggOnly];
  const available = new Set(['egg', 'butter']);

  it('in vegetarian mode every country with a dish appears and takes its best dish', () => {
    const result = scoreCountries(recipes, { available, mode: 'vegetarian', matcher });
    expect([...result.keys()].sort()).toEqual(['250', '380', '392']);
    expect(result.get('250')?.best.recipe.id).toBe('omelette');
    expect(result.get('250')?.others.map((o) => o.recipe.id)).toEqual(['soup']);
    expect(result.get('250')?.level).toBe('ready');
  });

  it('in vegan mode vegetarian-only recipes are excluded from map and scores', () => {
    const result = scoreCountries(recipes, { available, mode: 'vegan', matcher });
    expect(result.has('392')).toBe(false);
    expect(result.get('250')?.best.recipe.id).toBe('soup');
    expect(result.get('250')?.best.score).toBe(0);
  });

  it('prefers traditional dishes over adaptations when scores tie', () => {
    const adapted = recipe('adapted', '392', [item('egg', true)], {
      diet: 'vegetarian',
      adaptation: { original_dish: 'Something with meat', changes: 'No meat.' },
    });
    const traditional = recipe('traditional', '392', [item('egg', true)], { diet: 'vegetarian' });
    const result = scoreCountries([adapted, traditional], {
      available,
      mode: 'vegetarian',
      matcher,
    });
    expect(result.get('392')?.best.recipe.id).toBe('traditional');
  });
});

describe('ExactSynonymMatcher', () => {
  const synonymMatcher = new ExactSynonymMatcher([
    { ...ingredient('chickpeas'), name_it: 'ceci', synonyms_en: ['garbanzo beans'] },
  ]);

  it('resolves names and synonyms, ignoring case and accents', () => {
    expect(synonymMatcher.resolve('Garbanzo Beans')).toBe('chickpeas');
    expect(synonymMatcher.resolve('CECI')).toBe('chickpeas');
    expect(synonymMatcher.resolve('unknown')).toBeNull();
  });
});
