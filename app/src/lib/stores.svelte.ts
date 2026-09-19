import { type Ingredient, loadDataset, type Recipe } from './data';
import {
  type DietMode,
  loadState,
  saveBasePantry,
  saveMode,
  savePantryAdd,
  savePantryRemove,
} from './db';
import { ExactSynonymMatcher } from './matching';
import { buildAvailable, scoreCountries } from './scoring';

/** Reactive app state: the static dataset, the persisted user settings and derived scores. */
class AppState {
  ingredients = $state.raw<Ingredient[]>([]);
  recipes = $state.raw<Recipe[]>([]);
  pantry = $state<string[]>([]);
  basePantry = $state<string[]>([]);
  mode = $state<DietMode>('vegetarian');
  selectedCountry = $state<string | null>(null);
  loaded = $state(false);
  error = $state<string | null>(null);

  matcher = $derived(new ExactSynonymMatcher(this.ingredients));
  ingredientsById = $derived(new Map(this.ingredients.map((i) => [i.id, i])));
  available = $derived(buildAvailable(this.pantry, this.basePantry, this.ingredients, this.mode));
  scores = $derived(
    scoreCountries(this.recipes, {
      available: this.available,
      mode: this.mode,
      matcher: this.matcher,
    }),
  );

  async init(): Promise<void> {
    try {
      const [dataset, saved] = await Promise.all([loadDataset(), loadState()]);
      this.ingredients = dataset.ingredients;
      this.recipes = dataset.recipes;
      this.pantry = saved.pantry;
      this.basePantry = saved.basePantry;
      this.mode = saved.mode;
      this.loaded = true;
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
    }
  }

  addIngredient(id: string): void {
    if (this.pantry.includes(id)) return;
    this.pantry.push(id);
    void savePantryAdd(id);
  }

  removeIngredient(id: string): void {
    this.pantry = this.pantry.filter((existing) => existing !== id);
    void savePantryRemove(id);
  }

  toggleBaseIngredient(id: string): void {
    this.basePantry = this.basePantry.includes(id)
      ? this.basePantry.filter((existing) => existing !== id)
      : [...this.basePantry, id];
    void saveBasePantry(this.basePantry);
  }

  setMode(mode: DietMode): void {
    this.mode = mode;
    void saveMode(mode);
  }

  select(countryCode: string | null): void {
    this.selectedCountry = countryCode;
  }
}

export const app = new AppState();
