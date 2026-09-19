<script lang="ts">
  import { countryNames } from '$lib/countries';
  import { DIET_LABELS, LEVEL_LABELS } from '$lib/labels';
  import { app } from '$lib/stores.svelte';

  let panel: HTMLElement | undefined = $state();
  let shownId = $state<string | null>(null);

  const country = $derived(app.selectedCountry ? app.scores.get(app.selectedCountry) : undefined);
  const countryName = $derived(
    app.selectedCountry ? (countryNames.get(app.selectedCountry) ?? app.selectedCountry) : '',
  );
  const all = $derived(country ? [country.best, ...country.others] : []);
  const shown = $derived(all.find((s) => s.recipe.id === shownId) ?? country?.best);

  // A new country always starts from its best dish, and the panel is brought into view
  // (on phones it sits below the map).
  $effect(() => {
    app.selectedCountry;
    shownId = null;
    panel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  const ingredientName = (id: string) => app.ingredientsById.get(id)?.name_it ?? id;

  function amount(quantity: number | null | undefined, unit: string | null | undefined): string {
    if (quantity == null) return 'q.b.';
    return unit ? `${quantity} ${unit}` : String(quantity);
  }
</script>

{#if app.selectedCountry}
  <section class="panel" bind:this={panel} aria-labelledby="country-title">
    <div class="head">
      <h2 id="country-title">{countryName}</h2>
      <button type="button" class="close" aria-label="Chiudi" onclick={() => app.select(null)}>×</button>
    </div>

    {#if !shown}
      <p class="hint">Nessun piatto {DIET_LABELS[app.mode].toLowerCase()} per questo paese.</p>
    {:else}
      {@const recipe = shown.recipe}
      <p class="level">
        <span class="badge {shown.level}">{LEVEL_LABELS[shown.level]}</span>
        <span class="badge diet">{DIET_LABELS[recipe.diet]}</span>
      </p>
      <h3>{recipe.name_it}</h3>
      <p class="en">{recipe.name}</p>

      {#if recipe.adaptation}
        <p class="adaptation" role="note">
          <strong>Versione {recipe.diet === 'vegan' ? 'vegana' : 'vegetariana'} di {recipe.adaptation.original_dish}.</strong>
          {recipe.adaptation.changes}
        </p>
      {/if}

      <p class="servings">Per {recipe.servings} {recipe.servings === 1 ? 'porzione' : 'porzioni'}</p>

      <h4>Ce l'hai ({shown.have.length})</h4>
      <ul class="items">
        {#each shown.have as item (item.ingredient_id)}
          <li>✓ {ingredientName(item.ingredient_id)} <span class="qty">{amount(item.quantity, item.unit)}</span></li>
        {:else}
          <li class="hint">Niente, per ora.</li>
        {/each}
      </ul>

      <h4>Ti manca ({shown.missing.length})</h4>
      <ul class="items">
        {#each shown.missing as item (item.ingredient_id)}
          <li>
            ✗ {ingredientName(item.ingredient_id)}
            <span class="qty">{amount(item.quantity, item.unit)}</span>
            {#if item.is_core}<span class="core">essenziale</span>{/if}
          </li>
        {:else}
          <li class="hint">Hai tutto!</li>
        {/each}
      </ul>

      <h4>Procedimento</h4>
      <ol class="steps">
        {#each recipe.steps as step}
          <li>{step}</li>
        {/each}
      </ol>

      <p class="source">Fonte: {recipe.source} · Licenza: {recipe.license}</p>

      {#if country && country.others.length}
        <h4>Altri piatti</h4>
        <ul class="others">
          {#each all.filter((s) => s.recipe.id !== recipe.id) as other (other.recipe.id)}
            <li>
              <button type="button" onclick={() => (shownId = other.recipe.id)}>
                {other.recipe.name_it}
                <span class="badge {other.level}">{LEVEL_LABELS[other.level]}</span>
                {#if other.recipe.adaptation}<span class="badge diet">Adattamento</span>{/if}
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .panel {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  h2,
  h3,
  h4 {
    margin: 0;
  }
  h2 {
    font-size: 1.05rem;
  }
  h3 {
    margin-top: 0.5rem;
    font-size: 1.25rem;
  }
  h4 {
    margin-top: 1rem;
    font-size: 0.95rem;
  }
  .close {
    min-width: 2.25rem;
    min-height: 2.25rem;
    border: 0;
    background: transparent;
    color: var(--text);
    font-size: 1.4rem;
    cursor: pointer;
  }
  .en,
  .hint,
  .qty,
  .servings,
  .source {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .en {
    margin: 0;
  }
  .level {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.5rem 0 0;
  }
  .badge {
    padding: 0.1rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 0.8rem;
    white-space: nowrap;
  }
  .badge.ready {
    border-color: var(--c-ready);
  }
  .badge.close {
    border-color: var(--c-close);
  }
  .badge.far {
    border-color: var(--c-far);
  }
  .adaptation {
    margin: 0.75rem 0;
    padding: 0.6rem 0.75rem;
    border-left: 4px solid var(--c-close);
    border-radius: 0.25rem;
    background: color-mix(in srgb, var(--c-close) 15%, transparent);
    font-size: 0.9rem;
  }
  .items,
  .others {
    margin: 0.25rem 0 0;
    padding: 0;
    list-style: none;
  }
  .items li {
    padding: 0.1rem 0;
  }
  .core {
    margin-left: 0.25rem;
    color: var(--c-far);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }
  .steps {
    margin: 0.25rem 0 0;
    padding-left: 1.25rem;
  }
  .others button {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    width: 100%;
    margin-top: 0.3rem;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: transparent;
    color: var(--text);
    text-align: left;
    cursor: pointer;
  }
</style>
