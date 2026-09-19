<script lang="ts">
  import { app } from '$lib/stores.svelte';
  import IngredientPicker from './IngredientPicker.svelte';

  const veganIds = $derived(new Set(app.ingredients.filter((i) => i.is_vegan).map((i) => i.id)));
</script>

<section class="panel" aria-labelledby="pantry-title">
  <h2 id="pantry-title">La tua dispensa</h2>
  <IngredientPicker
    label="Cosa hai in casa?"
    selected={app.pantry}
    onadd={(id) => app.addIngredient(id)}
    onremove={(id) => app.removeIngredient(id)}
  />

  <details>
    <summary>Dispensa base ({app.basePantry.length})</summary>
    <p class="hint">
      Ingredienti sempre considerati disponibili.
      {#if app.mode === 'vegan'}
        In modalità vegana quelli non vegani sono ignorati.
      {/if}
    </p>
    <IngredientPicker
      label="Aggiungi alla dispensa base"
      selected={app.basePantry}
      onadd={(id) => app.toggleBaseIngredient(id)}
      onremove={(id) => app.toggleBaseIngredient(id)}
      isIgnored={(id) => app.mode === 'vegan' && !veganIds.has(id)}
    />
  </details>
</section>

<style>
  .panel {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
  }
  h2 {
    margin: 0 0 0.75rem;
    font-size: 1.05rem;
  }
  details {
    margin-top: 1rem;
  }
  summary {
    cursor: pointer;
    font-weight: 600;
  }
  .hint {
    color: var(--muted);
    font-size: 0.85rem;
  }
</style>
