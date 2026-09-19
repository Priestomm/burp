<script lang="ts">
  import { LEVEL_LABELS } from '$lib/labels';
  import PatternDefs from './PatternDefs.svelte';

  const levels = ['ready', 'close', 'far', 'none'] as const;
</script>

<ul class="legend" aria-label="Legenda della mappa">
  {#each levels as level}
    <li>
      <svg width="28" height="18" aria-hidden="true">
        <defs><PatternDefs prefix="legend" /></defs>
        <rect
          width="28"
          height="18"
          rx="3"
          fill={level === 'none' ? 'var(--c-none)' : `url(#legend-${level})`}
        />
      </svg>
      {LEVEL_LABELS[level]}
    </li>
  {/each}
</ul>

<style>
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.25rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.9rem;
  }
  li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
</style>
