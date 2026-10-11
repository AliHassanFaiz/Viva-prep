import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { IconHeadphones, IconPlay, IconRefresh } from "../components/Icons";
import QuestionCard from "../components/QuestionCard";
import Stepper from "../components/Stepper";
import { api } from "../lib/api";
import { preloadSession } from "../lib/audio";
import { settings } from "../lib/settings";
import type { DocumentInfo, Question } from "../lib/types";

export default function QuestionsPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [qs, setQs] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [regen, setRegen] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const load = useCallback(async () => {
    try {
      setDoc(await api.getDocument(id));
      let { questions } = await api.listQuestions(id);
      if (questions.length === 0) questions = (await api.generateQuestions(id, 3)).questions;
      setQs(questions);
    } catch (e: any) { setError(e.message); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  const accepted = (qs ?? []).filter((q) => q.accepted);
  const canStart = accepted.length >= settings.QUESTIONS_MIN && accepted.length <= settings.QUESTIONS_MAX && !starting;

  const toggle = async (q: Question) => {
    setBusy(true);
    try { const u = await api.patchQuestion(q.id, { accepted: !q.accepted }); setQs((p) => p!.map((x) => (x.id === q.id ? u : x))); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  const save = async (q: Question, text: string) => {
    try { const u = await api.patchQuestion(q.id, { text }); setQs((p) => p!.map((x) => (x.id === q.id ? u : x))); }
    catch (e: any) { setError(e.message); throw e; }
  };
  const remove = async (q: Question) => {
    setBusy(true);
    try { await api.deleteQuestion(q.id); setQs((p) => p!.filter((x) => x.id !== q.id)); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  const regenerate = async () => {
    setRegen(true); setError(null);
    try { setQs((await api.generateQuestions(id, Math.min(4, Math.max(2, qs?.length || 3)))).questions); }
    catch (e: any) { setError(e.message); } finally { setRegen(false); }
  };

  const startPractice = async () => {
    setError(null); setProgress(0);
    try {
      setStarting("Preparing your examiner's voice...");
      const created = await api.createSession(id, accepted.map((q) => q.id));
      setStarting("Loading audio...");
      const { missingQuestions } = await preloadSession(created, (d, t) => setProgress(d / t));
      if (missingQuestions > 0) sessionStorage.setItem(`viva.voiceNote.${created.session_id}`, "1");
      nav(`/session/${created.session_id}/call`);
    } catch (e: any) { setError(e.message); setStarting(null); }
  };

  if (error && !qs) return <div className="page"><div className="alert error">{error}</div><Link to="/" className="btn btn-ghost">Back to upload</Link></div>;
  if (!qs) return <div className="page"><Stepper current={1} /><div className="card center"><span className="spinner lg" /><p className="muted">Loading your questions...</p></div></div>;

  return (
    <div className="page">
      <Stepper current={1} />
      <div className="page-head">
        <div>
          <h1>Review your questions</h1>
          <p className="lead">{doc ? <>From <b>{doc.filename}</b>. </> : null}Keep the ones you want, edit the wording, or remove any. Pick {settings.QUESTIONS_MIN} to {settings.QUESTIONS_MAX}.</p>
        </div>
        <button className="btn btn-ghost" onClick={regenerate} disabled={regen || !!starting}>
          <IconRefresh width={16} height={16} className={regen ? "spin" : ""} /> {regen ? "Writing..." : "Regenerate"}
        </button>
      </div>

      {error && <div className="alert error" role="alert">{error}</div>}
      <div className="qlist">
        {qs.map((q, i) => <QuestionCard key={q.id} q={q} index={i} busy={busy || regen} onToggle={toggle} onSave={save} onRemove={remove} />)}
        {qs.length === 0 && <div className="card center muted">No questions left. Press Regenerate to get a new set.</div>}
      </div>

      <div className="sticky-bar">
        <div className="sticky-inner">
          <div className="tip"><IconHeadphones width={18} height={18} /> Use headphones so the examiner doesn't hear itself.</div>
          <div className="row gap-m">
            <span className={`count ${canStart ? "ok" : "bad"}`}>{accepted.length} selected</span>
            <button className="btn btn-primary btn-lg" disabled={!canStart || regen} onClick={startPractice}>
              {starting ? <><span className="spinner light" /> {starting}</> : <><IconPlay width={18} height={18} /> Start practice</>}
            </button>
          </div>
        </div>
        {starting && <div className="bar slim"><div className="bar-fill" style={{ width: `${Math.max(8, progress * 100)}%`, animation: "none" }} /></div>}
      </div>
    </div>
  );
}
