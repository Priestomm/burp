<script lang="ts">
  import { onMount } from 'svelte';
  import Legend from '$lib/components/Legend.svelte';
  import WorldMap from '$lib/components/WorldMap.svelte';
  import { app } from '$lib/stores.svelte';

  onMount(() => app.init());
</script>

<svelte:head><title>mappetito</title></svelte:head>

<main>
  <header><h1>mappetito</h1></header>
  {#if app.error}
    <p role="alert">Impossibile caricare i dati: {app.error}</p>
  {:else if !app.loaded}
    <p>Caricamento…</p>
  {:else}
    <WorldMap />
    <Legend />
  {/if}
</main>
