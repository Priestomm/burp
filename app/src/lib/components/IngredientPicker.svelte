<script lang="ts">
  import { searchIngredients } from '$lib/search';
  import { app } from '$lib/stores.svelte';

  let {
    label,
    selected,
    onadd,
    onremove,
    isIgnored = () => false,
  }: {
    label: string;
    selected: string[];
    onadd: (id: string) => void;
    onremove: (id: string) => void;
    /** Marks selected items that currently have no effect (shown dimmed). */
    isIgnored?: (id: string) => boolean;
  } = $props();

  const inputId = $props.id();
  let query = $state('');
  let active = $state(0);

  const suggestions = $derived(searchIngredients(app.ingredients, query, new Set(selected)));

  function pick(id: string) {
    onadd(id);
    query = '';
    active = 0;
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'ArrowDown' && suggestions.length) {
      event.preventDefault();
      active = (active + 1) % suggestions.length;
    } else if (event.key === 'ArrowUp' && suggestions.length) {
      event.preventDefault();
      active = (active - 1 + suggestions.length) % suggestions.length;
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const choice = suggestions[active] ?? suggestions[0];
      if (choice) pick(choice.id);
    } else if (event.key === 'Escape') {
      query = '';
    }
  }
</script>

<div class="picker">
  <label for={inputId}>{label}</label>
  <input
    id={inputId}
    type="text"
    role="combobox"
    aria-expanded={suggestions.length > 0}
    aria-controls="{inputId}-list"
    aria-autocomplete="list"
    autocomplete="off"
    autocapitalize="off"
    placeholder="Cerca un ingrediente…"
    bind:value={query}
    oninput={() => (active = 0)}
    onkeydown={onKeydown}
  />
  {#if suggestions.length}
    <ul id="{inputId}-list" class="suggestions" role="listbox">
      {#each suggestions as ingredient, index (ingredient.id)}
        <li role="option" aria-selected={index === active}>
          <button type="button" class:active={index === active} onclick={() => pick(ingredient.id)}>
            {ingredient.name_it}
            <span class="en">{ingredient.name_en}</span>
          </button>
        </li>
      {/each}
    </ul>
  {:else if query.trim()}
    <p class="hint">Nessun ingrediente trovato.</p>
  {/if}

  {#if selected.length}
    <ul class="tags">
      {#each selected as id (id)}
        <li>
          <button
            type="button"
            class="tag"
            class:ignored={isIgnored(id)}
            aria-label="Rimuovi {app.ingredientsById.get(id)?.name_it ?? id}"
            onclick={() => onremove(id)}
          >
            {app.ingredientsById.get(id)?.name_it ?? id}
            <span aria-hidden="true">×</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .picker {
    position: relative;
  }
  label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 600;
  }
  input {
    width: 100%;
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--surface);
    color: var(--text);
  }
  .suggestions {
    margin: 0.25rem 0 0;
    padding: 0.25rem;
    list-style: none;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--surface);
  }
  .suggestions button {
    display: flex;
    justify-content: space-between;
    width: 100%;
    padding: 0.55rem 0.6rem;
    border: 0;
    border-radius: 0.35rem;
    background: transparent;
    color: var(--text);
    text-align: left;
    cursor: pointer;
  }
  .suggestions button:hover,
  .suggestions button.active {
    background: color-mix(in srgb, var(--accent) 15%, transparent);
  }
  .en,
  .hint {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.6rem 0 0;
    padding: 0;
    list-style: none;
  }
  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2.25rem;
    padding: 0.25rem 0.75rem;
    border: 1px solid var(--accent);
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 12%, var(--surface));
    color: var(--text);
    cursor: pointer;
  }
  .tag.ignored {
    border-style: dashed;
    border-color: var(--muted);
    background: transparent;
    color: var(--muted);
    text-decoration: line-through;
  }
</style>
