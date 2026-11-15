"use client";
import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

/**
 * Movimiento de cada pantalla, en un solo lugar:
 * - Al cambiar de pantalla, el contenido aparece suave (.page-in).
 * - Cada sección de primer nivel entra una vez al llegar a la vista, en escalera (.reveal).
 * Si el sistema pide «reducir movimiento», no se anima nada. Lo que aún no se ve nunca queda oculto
 * más de 1,5 s (por si el navegador no avisa la intersección).
 */
export function MotionRoot({ children, scrollRoot }: { children: ReactNode; scrollRoot?: boolean }) {
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root || !scrollRoot || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const sections = Array.from(root.querySelectorAll<HTMLElement>(":scope > * > *")).filter((el) => !el.classList.contains("reveal"));
    sections.forEach((el, i) => {
      el.classList.add("reveal");
      el.style.setProperty("--d", `${Math.min(i, 5) * 70}ms`);
    });
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      }),
      { root: root.parentElement, rootMargin: "0px 0px -6% 0px", threshold: 0.06 },
    );
    sections.forEach((el) => io.observe(el));
    const safety = window.setTimeout(() => sections.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.top < window.innerHeight) el.classList.add("is-in");
    }), 1500);
    return () => {
      io.disconnect();
      window.clearTimeout(safety);
      sections.forEach((el) => el.classList.add("is-in"));
    };
  }, [pathname, scrollRoot]);

  return <div key={pathname} ref={ref} className="page-in h-full">{children}</div>;
}
