import type { DietMode } from './db';
import type { Level } from './scoring';

// UI copy lives here so the interface language is easy to change.
export const LEVEL_LABELS: Record<Level, string> = {
  ready: 'Posso cucinare',
  close: 'Manca poco',
  far: 'Lontano',
  none: 'Nessun piatto',
};

export const DIET_LABELS: Record<DietMode, string> = {
  vegetarian: 'Vegetariano',
  vegan: 'Vegano',
};
