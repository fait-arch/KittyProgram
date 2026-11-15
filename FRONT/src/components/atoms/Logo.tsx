import { useId } from "react";

/**
 * Marca propia de CacaoResiliente: mazorca de cacao (dorado) con su hoja, sobre el mar del Pacífico
 * (la ola de El Niño), en una insignia color chocolate. No usa la insignia de la NASA ni de Space Apps.
 */
export function Logo({ size = 36, title }: { size?: number; title?: string }) {
  const clip = `cr-logo-${useId().replace(/:/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role={title ? "img" : undefined} aria-hidden={title ? undefined : true}>
      {title && <title>{title}</title>}
      <defs><clipPath id={clip}><rect x="2" y="2" width="60" height="60" rx="16" /></clipPath></defs>
      <g clipPath={`url(#${clip})`}>
        <rect x="2" y="2" width="60" height="60" fill="#4B3A2F" />
        <path d="M0 47c8-5 15-5 22 0s14 5 21 0 13-5 21 0v19H0z" fill="#3D5A43" />
        <path d="M0 47c8-5 15-5 22 0s14 5 21 0 13-5 21 0" fill="none" stroke="#96C9B2" strokeWidth="2.2" strokeLinecap="round" />
        <g transform="rotate(-16 31 31)">
          <path d="M31 13c7.5 0 11 8.5 11 17.5S38.5 50 31 50s-11-10.5-11-19.5S23.5 13 31 13z" fill="#C9BD7E" />
          <path d="M31 15c-2.4 4.6-3.1 10-3.1 15.5s.7 11.5 3.1 17.5M25 19.5c-1.1 3.6-1.5 7.2-1.5 11s.4 8 1.7 11.5M37 19.5c1.1 3.6 1.5 7.2 1.5 11s-.4 8-1.7 11.5"
            fill="none" stroke="#7D7340" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M31 13c0-2.6.9-4.6 2.6-6" fill="none" stroke="#96C9B2" strokeWidth="2.2" strokeLinecap="round" />
          <path d="M33.4 7.2c4.6-3.4 11-3 13.6.8-5 3.4-10.6 3.2-13.6-.8z" fill="#96C9B2" />
          <path d="M34.6 7.4c3.6-.6 7.4-.4 11 .6" fill="none" stroke="#3D5A43" strokeWidth="1" strokeLinecap="round" />
        </g>
      </g>
    </svg>
  );
}
