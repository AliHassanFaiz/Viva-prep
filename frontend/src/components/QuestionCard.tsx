import { useState } from "react";
import type { Question } from "../lib/types";
import { IconCheck, IconEdit, IconTrash, IconX } from "./Icons";

interface Props {
  q: Question; index: number; busy?: boolean;
  onToggle: (q: Question) => void; onSave: (q: Question, text: string) => Promise<void>; onRemove: (q: Question) => void;
}

export default function QuestionCard({ q, index, busy, onToggle, onSave, onRemove }: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(q.text);
  const [saving, setSaving] = useState(false);
  const words = text.trim().split(/\s+/).filter(Boolean).length;

  const save = async () => {
    if (text.trim().length < 5) return;
    setSaving(true);
    try { await onSave(q, text.trim()); setEditing(false); } finally { setSaving(false); }
  };

  return (
    <article className={`qcard ${q.accepted ? "" : "off"}`}>
      <button className={`check ${q.accepted ? "on" : ""}`} onClick={() => onToggle(q)} disabled={busy}
        aria-pressed={q.accepted} aria-label={q.accepted ? "Included in practice. Click to exclude." : "Excluded. Click to include."}>
        {q.accepted && <IconCheck width={16} height={16} strokeWidth={3} />}
      </button>
      <div className="qbody">
        <div className="qmeta">
          <span className="qnum">Q{index + 1}</span>
          {q.topic && <span className="chip">{q.topic}</span>}
          {q.difficulty && <span className={`chip diff-${q.difficulty}`}>{q.difficulty}</span>}
        </div>
        {editing ? (
          <>
            <textarea className="input" value={text} rows={3} autoFocus onChange={(e) => setText(e.target.value)} aria-label="Edit question" />
            <div className="row-between">
              <small className={words > 30 ? "warn" : "muted"}>{words} words{words > 30 ? " - shorter questions sound more natural aloud" : ""}</small>
              <span className="row gap-s">
                <button className="btn btn-ghost btn-sm" onClick={() => { setText(q.text); setEditing(false); }}><IconX width={15} height={15} /> Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={save} disabled={saving || text.trim().length < 5}>{saving ? "Saving..." : "Save"}</button>
              </span>
            </div>
          </>
        ) : (
          <>
            <p className="qtext">{q.text}</p>
            {q.key_points.length > 0 && (
              <details className="points">
                <summary>What a strong answer covers</summary>
                <ul>{q.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul>
              </details>
            )}
          </>
        )}
      </div>
      {!editing && (
        <div className="qactions">
          <button className="icon-btn" onClick={() => { setText(q.text); setEditing(true); }} aria-label="Edit question" title="Edit"><IconEdit width={18} height={18} /></button>
          <button className="icon-btn danger" onClick={() => onRemove(q)} aria-label="Remove question" title="Remove" disabled={busy}><IconTrash width={18} height={18} /></button>
        </div>
      )}
    </article>
  );
}
