import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';
import topology from 'world-atlas/countries-110m.json';

const ANTARCTICA = '010';

const world = topology as unknown as Topology<{ countries: GeometryCollection }>;

export const countryFeatures = feature(world, world.objects.countries).features.filter(
  (f) => String(f.id) !== ANTARCTICA,
);

function featureName(f: (typeof countryFeatures)[number]): string {
  return String((f.properties as { name?: string } | null)?.name ?? '');
}

/** English country names by ISO 3166-1 numeric code (world-atlas feature ids). */
export const countryNames = new Map(
  countryFeatures
    .filter((f) => f.id !== undefined)
    .map((f) => [String(f.id).padStart(3, '0'), featureName(f)]),
);

export { featureName };
