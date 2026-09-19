<script lang="ts">
  import { geoNaturalEarth1, geoPath } from 'd3-geo';
  import { feature } from 'topojson-client';
  import type { GeometryCollection, Topology } from 'topojson-specification';
  import topology from 'world-atlas/countries-110m.json';
  import { LEVEL_LABELS } from '$lib/labels';
  import { app } from '$lib/stores.svelte';
  import PatternDefs from './PatternDefs.svelte';

  const WIDTH = 960;
  const HEIGHT = 500;
  const ANTARCTICA = '010';

  const world = topology as unknown as Topology<{ countries: GeometryCollection }>;
  const features = feature(world, world.objects.countries).features.filter(
    (f) => String(f.id) !== ANTARCTICA,
  );
  const projection = geoNaturalEarth1().fitExtent(
    [
      [4, 4],
      [WIDTH - 4, HEIGHT - 4],
    ],
    { type: 'FeatureCollection', features },
  );
  const toPath = geoPath(projection);

  // world-atlas ids are ISO 3166-1 numeric codes; a few disputed territories have none.
  const shapes = features.map((f, index) => ({
    key: f.id === undefined ? `no-id-${index}` : String(f.id),
    code: f.id === undefined ? null : String(f.id).padStart(3, '0'),
    name: String((f.properties as { name?: string } | null)?.name ?? ''),
    d: toPath(f) ?? '',
  }));

  function onKeydown(event: KeyboardEvent, code: string) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      app.select(code);
    }
  }
</script>

<svg viewBox="0 0 {WIDTH} {HEIGHT}" role="group" aria-label="Mappa del mondo">
  <defs><PatternDefs prefix="map" /></defs>
  {#each shapes as shape (shape.key)}
    {@const score = shape.code ? app.scores.get(shape.code) : undefined}
    {#if shape.code && score}
      <path
        d={shape.d}
        class="country interactive"
        class:selected={app.selectedCountry === shape.code}
        fill="url(#map-{score.level})"
        role="button"
        tabindex="0"
        aria-label="{shape.name}: {LEVEL_LABELS[score.level]}"
        aria-pressed={app.selectedCountry === shape.code}
        onclick={() => app.select(shape.code)}
        onkeydown={(event) => onKeydown(event, shape.code as string)}
      >
        <title>{shape.name}: {LEVEL_LABELS[score.level]}</title>
      </path>
    {:else}
      <path d={shape.d} class="country" fill="var(--c-none)" />
    {/if}
  {/each}
</svg>

<style>
  svg {
    display: block;
    width: 100%;
    height: auto;
  }
  .country {
    stroke: var(--bg);
    stroke-width: 0.6;
  }
  .interactive {
    cursor: pointer;
  }
  .interactive:hover,
  .interactive:focus-visible {
    stroke: var(--text);
    stroke-width: 1.5;
    outline: none;
  }
  .selected {
    stroke: var(--text);
    stroke-width: 2;
  }
</style>
