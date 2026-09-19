import Dexie, { type EntityTable } from 'dexie';

export type DietMode = 'vegetarian' | 'vegan';

/** Ingredients that are always considered available, until the user changes the list. */
export const DEFAULT_BASE_PANTRY = [
  'salt',
  'olive_oil',
  'black_pepper',
  'water',
  'sugar',
  'flour',
  'garlic',
];

interface PantryRow {
  ingredientId: string;
  addedAt: number;
}

interface BasePantryRow {
  ingredientId: string;
}

interface SettingRow {
  key: string;
  value: unknown;
}

class MappetitoDb extends Dexie {
  pantry!: EntityTable<PantryRow, 'ingredientId'>;
  basePantry!: EntityTable<BasePantryRow, 'ingredientId'>;
  settings!: EntityTable<SettingRow, 'key'>;

  constructor() {
    super('mappetito');
    this.version(1).stores({
      pantry: 'ingredientId, addedAt',
      basePantry: 'ingredientId',
      settings: 'key',
    });
  }
}

export interface PersistedState {
  pantry: string[];
  basePantry: string[];
  mode: DietMode;
}

const db = new MappetitoDb();

/** Reads the saved state; on first run seeds the base pantry with the defaults. */
export async function loadState(): Promise<PersistedState> {
  const seeded = await db.settings.get('baseSeeded');
  if (!seeded) {
    await db.transaction('rw', db.basePantry, db.settings, async () => {
      await db.basePantry.bulkPut(DEFAULT_BASE_PANTRY.map((ingredientId) => ({ ingredientId })));
      await db.settings.put({ key: 'baseSeeded', value: true });
    });
  }
  const [pantry, basePantry, mode] = await Promise.all([
    db.pantry.orderBy('addedAt').primaryKeys(),
    db.basePantry.toCollection().primaryKeys(),
    db.settings.get('mode'),
  ]);
  return {
    pantry,
    basePantry,
    mode: mode?.value === 'vegan' ? 'vegan' : 'vegetarian',
  };
}

export async function savePantryAdd(ingredientId: string): Promise<void> {
  await db.pantry.put({ ingredientId, addedAt: Date.now() });
}

export async function savePantryRemove(ingredientId: string): Promise<void> {
  await db.pantry.delete(ingredientId);
}

export async function saveBasePantry(ingredientIds: string[]): Promise<void> {
  await db.transaction('rw', db.basePantry, async () => {
    await db.basePantry.clear();
    await db.basePantry.bulkPut(ingredientIds.map((ingredientId) => ({ ingredientId })));
  });
}

export async function saveMode(mode: DietMode): Promise<void> {
  await db.settings.put({ key: 'mode', value: mode });
}
