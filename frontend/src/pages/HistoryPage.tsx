import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { IconBriefcase, IconCap, IconChevron, IconHistory, IconTrash } from "../components/Icons";
import { ScoreBadge } from "../components/ScoreBadge";
import { api } from "../lib/api";
import type { HistoryItem } from "../lib/types";

const STATUS: Record<string, string> = {
  ready: "Not started", in_progress: "In progress", ended: "Finishing", report_running: "Scoring...", report_failed: "Report failed",
};

function ago(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export default function HistoryPage() {
  const nav = useNavigate();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);

  useEffect(() => { api.listSessions().then(setItems).catch((e) => setError(e.message)); }, []);

  const remove = async (id: string) => {
    try { await api.deleteSession(id); setItems((p) => p!.filter((x) => x.id !== id)); setConfirm(null); }
    catch (e: any) { setError(e.message); }
  };
  const open = (s: HistoryItem) => nav(s.status === "ready" || s.status === "in_progress" ? `/session/${s.id}/call` : `/session/${s.id}/report`);

  const summary = useMemo(() => {
    if (!items?.length) return null;
    const scores = items.map((i) => i.overall_score).filter((x): x is number => x != null);
    return `${items.length} session${items.length === 1 ? "" : "s"}${scores.length ? ` · best score ${Math.max(...scores)}` : ""}`;
  }, [items]);

  return (
    <div className="page narrow">
      <div className="page-head">
        <div><h1>Your practice history</h1><p className="lead">{summary ?? "Reopen a report, compare rounds, or delete what you don't need."}</p></div>
        <Link to="/" className="btn btn-primary">New practice</Link>
      </div>
      {error && <div className="alert error" role="alert">{error}</div>}
      {!items && !error && (
        <div className="hlist" aria-busy="true" aria-label="Loading your sessions">
          {[0, 1, 2].map((i) => <div key={i} className="card hitem skeleton"><span /><span /></div>)}
        </div>
      )}
      {items && items.length === 0 && (
        <div className="card center empty">
          <span className="empty-icon"><IconHistory width={28} height={28} /></span>
          <h3>No sessions yet</h3>
          <p className="muted">Upload a report or resume, answer a few spoken questions, and your reports will show up here.</p>
          <Link to="/" className="btn btn-primary">Start your first practice</Link>
        </div>
      )}
      <div className="hlist">
        {items?.map((s) => (
          <div key={s.id} className="card hitem">
            <button className="hmain" onClick={() => open(s)}>
              <div className="hinfo">
                <b className="hname">{s.document_name}</b>
                <small className="muted hmeta">
                  {s.mode && <span className={`mode-tag ${s.mode}`}>{s.mode === "interview" ? <IconBriefcase width={12} height={12} /> : <IconCap width={12} height={12} />}{s.mode === "interview" ? "Interview" : "Viva"}</span>}
                  <span title={new Date(s.created_at).toLocaleString()}>{ago(s.created_at)}</span>
                </small>
              </div>
              <div className="row gap-s">
                {s.overall_score != null ? <ScoreBadge band={s.band} score={s.overall_score} /> : <span className="badge badge-muted">{STATUS[s.status] ?? s.status}</span>}
                <IconChevron width={18} height={18} />
              </div>
            </button>
            {confirm === s.id ? (
              <div className="confirm"><small>Delete this session?</small>
                <button className="btn btn-danger btn-sm" onClick={() => remove(s.id)}>Delete</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setConfirm(null)}>Cancel</button></div>
            ) : <button className="icon-btn danger" onClick={() => setConfirm(s.id)} aria-label={`Delete session ${s.document_name}`} title="Delete"><IconTrash width={18} height={18} /></button>}
          </div>
        ))}
      </div>
    </div>
  );
}
