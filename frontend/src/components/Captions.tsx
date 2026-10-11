import { useEffect, useRef } from "react";
import type { Caption } from "../hooks/useCall";

export default function Captions({ items }: { items: Caption[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items.length]);
  return (
    <div className="captions" aria-live="polite" aria-label="Live captions">
      {items.length === 0 && <p className="captions-empty">Captions will appear here as you talk.</p>}
      {items.map((c) => (
        <div key={c.id} className={`bubble ${c.who}`}>
          <span className="who">{c.who === "examiner" ? (c.kind === "followup" ? "Examiner - follow-up" : "Examiner") : "You"}</span>
          <p>{c.text}</p>
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}
