<script lang="ts">
  import { onMount } from 'svelte';
  import CountryPanel from '$lib/components/CountryPanel.svelte';
  import DietToggle from '$lib/components/DietToggle.svelte';
  import Legend from '$lib/components/Legend.svelte';
  import PantryPanel from '$lib/components/PantryPanel.svelte';
  import WorldMap from '$lib/components/WorldMap.svelte';
  import { app } from '$lib/stores.svelte';

  onMount(() => app.init());
</script>

<svelte:head><title>mappetito</title></svelte:head>

<main>
  <header>
    <h1>mappetito</h1>
    <DietToggle />
  </header>

  {#if app.error}
    <p role="alert">Impossibile caricare i dati: {app.error}</p>
  {:else if !app.loaded}
    <p>Caricamento…</p>
  {:else}
    <div class="layout">
      <div class="pantry"><PantryPanel /></div>
      <div class="map">
        <WorldMap />
        <Legend />
      </div>
      <div class="country"><CountryPanel /></div>
    </div>
  {/if}
</main>

<style>
  header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }
  .layout {
    display: grid;
    gap: 1rem;
    grid-template-areas:
      'pantry'
      'map'
      'country';
  }
  .pantry {
    grid-area: pantry;
  }
  .map {
    grid-area: map;
    display: grid;
    gap: 0.75rem;
  }
  .country {
    grid-area: country;
  }
  @media (min-width: 60rem) {
    .layout {
      grid-template-columns: minmax(0, 1fr) 24rem;
      grid-template-areas:
        'map pantry'
        'map country';
      align-items: start;
    }
  }
</style>
