/** Marca propia de CacaoResiliente (no usa la insignia de la NASA ni el logo de Space Apps). */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" aria-hidden>
      <circle cx="18" cy="18" r="17" fill="#0042A6" />
      <ellipse cx="18" cy="18" rx="15" ry="6" fill="none" stroke="#EAFE07" strokeWidth="1.6" transform="rotate(-24 18 18)" />
      <ellipse cx="18" cy="18" rx="5" ry="8" fill="#E8997B" transform="rotate(24 18 18)" />
      <path d="M18 11 L18 25" stroke="#8E1100" strokeWidth="1.2" transform="rotate(24 18 18)" />
    </svg>
  );
}
