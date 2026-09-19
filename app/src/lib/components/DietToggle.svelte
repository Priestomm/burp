<script lang="ts">
  import { app } from '$lib/stores.svelte';
</script>

<label class="toggle">
  <input
    type="checkbox"
    role="switch"
    checked={app.mode === 'vegan'}
    onchange={(event) => app.setMode(event.currentTarget.checked ? 'vegan' : 'vegetarian')}
  />
  <span class="track" aria-hidden="true"><span class="thumb"></span></span>
  <span>
    Solo piatti vegani
    <small>{app.mode === 'vegan' ? 'Solo vegano' : 'Vegetariano (con anche i vegani)'}</small>
  </span>
</label>

<style>
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    cursor: pointer;
    user-select: none;
  }
  input {
    position: absolute;
    opacity: 0;
  }
  .track {
    position: relative;
    flex: none;
    width: 2.75rem;
    height: 1.5rem;
    border-radius: 999px;
    background: var(--border);
    transition: background 0.15s;
  }
  .thumb {
    position: absolute;
    top: 0.2rem;
    left: 0.2rem;
    width: 1.1rem;
    height: 1.1rem;
    border-radius: 50%;
    background: white;
    transition: transform 0.15s;
  }
  input:checked + .track {
    background: var(--accent);
  }
  input:checked + .track .thumb {
    transform: translateX(1.25rem);
  }
  input:focus-visible + .track {
    outline: 2px solid var(--text);
    outline-offset: 2px;
  }
  small {
    display: block;
    color: var(--muted);
    font-size: 0.8rem;
  }
</style>
