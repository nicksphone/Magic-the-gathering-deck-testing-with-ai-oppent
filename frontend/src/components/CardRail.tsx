import { useRef, type ReactNode } from "react";

/** Native horizontal scrolling plus explicit navigation; no card virtualization or ID grouping. */
export function CardRail({ label, className, children }: { label: string; className: string; children: ReactNode }) {
  const rail = useRef<HTMLDivElement>(null);
  function scroll(direction: number) {
    const element = rail.current;
    if (element) element.scrollBy({ left: direction * element.clientWidth * 0.8, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }
  return <div className="card-rail">
    <div className="rail-heading"><span>{label}</span><div className="rail-navigation" aria-label={`${label} navigation`}>
      <button type="button" aria-label={`Previous ${label}`} onClick={() => scroll(-1)}>←</button>
      <button type="button" aria-label={`Next ${label}`} onClick={() => scroll(1)}>→</button>
    </div></div>
    <div ref={rail} className={className} aria-label={label}>{children}</div>
  </div>;
}
