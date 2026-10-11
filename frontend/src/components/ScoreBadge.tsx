const LABEL: Record<string, string> = { needs_work: "Needs work", developing: "Developing", ready: "Ready" };

export function bandOf(score: number | null | undefined): "needs_work" | "developing" | "ready" | null {
  if (score == null) return null;
  return score < 50 ? "needs_work" : score < 75 ? "developing" : "ready";
}

export function ScoreBadge({ band, score }: { band: string | null; score?: number | null }) {
  if (!band) return <span className="badge badge-muted">No score</span>;
  return <span className={`badge badge-${band}`}>{score != null && <b>{score}</b>}{LABEL[band] ?? band}</span>;
}

export function ScoreRing({ score, size = 148 }: { score: number; size?: number }) {
  const r = (size - 16) / 2, c = 2 * Math.PI * r, band = bandOf(score) ?? "developing";
  return (
    <div className={`ring ring-${band}`} style={{ width: size, height: size }} role="img" aria-label={`Overall score ${score} out of 100`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-bg" />
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-fg" strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.max(0, Math.min(100, score)) / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring-text"><b>{score}</b><span>/ 100</span></div>
    </div>
  );
}

export function MiniBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="minibar">
      <span>{label}</span>
      <div className="minibar-track"><div style={{ width: `${(value / 5) * 100}%` }} className={value >= 4 ? "hi" : value >= 3 ? "mid" : "lo"} /></div>
      <b>{value}/5</b>
    </div>
  );
}
