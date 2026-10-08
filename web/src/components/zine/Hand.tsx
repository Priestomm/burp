/** ☞ The pointing hand next to the current course, as in old catalogues. */
export function Hand() {
  return (
    <svg viewBox="0 0 64 34" width="2.4em" aria-hidden="true" style={{ flex: "none" }}>
      <rect x="1" y="7" width="11" height="21" rx="2" fill="var(--z-ink)" />
      <path
        fill="var(--z-ink)"
        d="M12 9 C16 6 22 5 28 6 L58 6 C62 6 63.5 8.5 63.5 10.5 C63.5 12.5 62 15 58 15 L36 15 C38 16 39 18.5 37.5 20.5 C39 22 39 25 36.5 26.5 C37.5 28.5 36 31 33 31 L20 31 C16 31 13 29 12 27 Z"
      />
      <path d="M26 15 L36 15 M27 21 L37 21 M27 26.5 L35 26.5" stroke="var(--z-sheet)" strokeWidth="1.6" fill="none" />
    </svg>
  );
}
