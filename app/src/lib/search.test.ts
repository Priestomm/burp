import { describe, expect, it } from 'vitest';
import type { Ingredient } from './data';
import { searchIngredients } from './search';

const make = (
  id: string,
  name_it: string,
  name_en: string,
  synonyms_it: string[] = [],
): Ingredient => ({
  id,
  name_it,
  name_en,
  synonyms_it,
  is_vegetarian: true,
  is_vegan: true,
});

const INGREDIENTS = [
  make('chickpeas', 'ceci', 'chickpeas', ['garbanzo']),
  make('tomato', 'pomodoro', 'tomato'),
  make('tomato_passata', 'passata di pomodoro', 'tomato passata'),
];

describe('searchIngredients', () => {
  it('returns nothing for an empty query', () => {
    expect(searchIngredients(INGREDIENTS, '  ')).toEqual([]);
  });

  it('matches Italian names, English names and synonyms, ignoring case and accents', () => {
    expect(searchIngredients(INGREDIENTS, 'CE').map((i) => i.id)).toEqual(['chickpeas']);
    expect(searchIngredients(INGREDIENTS, 'chick').map((i) => i.id)).toEqual(['chickpeas']);
    expect(searchIngredients(INGREDIENTS, 'garb').map((i) => i.id)).toEqual(['chickpeas']);
  });

  it('ranks prefix matches before substring matches', () => {
    expect(searchIngredients(INGREDIENTS, 'pomodoro').map((i) => i.id)).toEqual([
      'tomato',
      'tomato_passata',
    ]);
  });

  it('ranks an exact match before other prefix matches', () => {
    const list = [make('miso', 'miso', 'miso', ['pasta di miso']), make('pasta', 'pasta', 'pasta')];
    expect(searchIngredients(list, 'pasta').map((i) => i.id)).toEqual(['pasta', 'miso']);
  });

  it('skips excluded ingredients', () => {
    expect(
      searchIngredients(INGREDIENTS, 'pomodoro', new Set(['tomato'])).map((i) => i.id),
    ).toEqual(['tomato_passata']);
  });
});
