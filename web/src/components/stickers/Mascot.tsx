/** The mascot: a mochi letting out a small burp. Decorative. */
export function Mascot({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden="true">
      <circle cx="50" cy="50" r="48" fill="var(--ink)" />
      <circle cx="50" cy="50" r="43.5" fill="none" stroke="var(--tomato)" strokeWidth="2.5" />
      <path
        d="M23 62 C19 43 32 30 50 30 C68 30 81 43 77 62 C74 74 63 79 50 79 C37 79 26 74 23 62 Z"
        fill="var(--cream)"
      />
      <path
        d="M35 53 Q39.5 46 44 53 M56 53 Q60.5 46 65 53"
        fill="none"
        stroke="var(--ink)"
        strokeWidth="2.8"
        strokeLinecap="round"
      />
      <ellipse cx="31.5" cy="61" rx="4.6" ry="3" fill="var(--tomato)" />
      <ellipse cx="68.5" cy="61" rx="4.6" ry="3" fill="var(--tomato)" />
      <ellipse cx="50" cy="64" rx="4.2" ry="5.2" fill="var(--ink)" />
      <circle cx="66" cy="27" r="4.6" fill="var(--sky)" stroke="var(--cream)" strokeWidth="1.6" />
      <circle cx="74" cy="18.5" r="3.2" fill="var(--sky)" stroke="var(--cream)" strokeWidth="1.4" />
      <circle cx="62" cy="14" r="2.2" fill="var(--sky)" stroke="var(--cream)" strokeWidth="1.2" />
    </svg>
  );
}
