import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { IconChevron, IconTrash } from "../components/Icons";
import { ScoreBadge } from "../components/ScoreBadge";
import { api } from "../lib/api";
import type { HistoryItem } from "../lib/types";

const STATUS: Record<string, string> = {
  ready: "Not started", in_progress: "In progress", ended: "Finishing", report_running: "Scoring...", report_failed: "Report failed",
};

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

  return (
    <div className="page narrow">
      <div className="page-head"><div><h1>Your practice history</h1><p className="lead">Reopen a report, compare rounds, or delete what you don't need.</p></div>
        <Link to="/" className="btn btn-primary">New practice</Link></div>
      {error && <div className="alert error">{error}</div>}
      {!items && !error && <div className="card center"><span className="spinner lg" /></div>}
      {items && items.length === 0 && (
        <div className="card center empty"><h3>No sessions yet</h3><p className="muted">Upload a document and run your first practice session.</p><Link to="/" className="btn btn-primary">Get started</Link></div>
      )}
      <div className="hlist">
        {items?.map((s) => (
          <div key={s.id} className="card hitem">
            <button className="hmain" onClick={() => open(s)}>
              <div>
                <b>{s.document_name}</b>
                <small className="muted">{new Date(s.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</small>
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
            ) : <button className="icon-btn danger" onClick={() => setConfirm(s.id)} aria-label="Delete session" title="Delete"><IconTrash width={18} height={18} /></button>}
          </div>
        ))}
      </div>
    </div>
  );
}
