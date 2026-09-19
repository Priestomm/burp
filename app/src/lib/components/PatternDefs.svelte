<script lang="ts">
  // Each level has a color AND a texture, so the map stays readable without color vision.
  // The prefix keeps ids unique when the same defs are used by the map and by the legend.
  let { prefix }: { prefix: string } = $props();
</script>

<pattern id="{prefix}-ready" width="8" height="8" patternUnits="userSpaceOnUse">
  <rect width="8" height="8" style="fill: var(--c-ready)" />
</pattern>
<pattern id="{prefix}-close" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <rect width="8" height="8" style="fill: var(--c-close)" />
  <rect width="3" height="8" fill="rgba(255, 255, 255, 0.6)" />
</pattern>
<pattern id="{prefix}-far" width="8" height="8" patternUnits="userSpaceOnUse">
  <rect width="8" height="8" style="fill: var(--c-far)" />
  <circle cx="4" cy="4" r="1.5" fill="rgba(255, 255, 255, 0.7)" />
</pattern>
