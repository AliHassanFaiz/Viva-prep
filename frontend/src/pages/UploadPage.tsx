import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { IconFile, IconHeadphones, IconMic, IconPlay, IconSpark, IconUpload } from "../components/Icons";
import Stepper from "../components/Stepper";
import { api, ApiError } from "../lib/api";
import { preloadSession } from "../lib/audio";
import { MODE_COPY } from "../lib/modes";
import type { Mode } from "../lib/types";

type Phase = "idle" | "uploading" | "processing" | "questions" | "ready" | "starting" | "error";
const MAX_MB = 15;

export default function UploadPage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<Mode>("viva");
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState(0);
  // Generated questions stay here, never rendered. Only their ids are needed to start the session.
  const [prepared, setPrepared] = useState<{ documentId: string; questionIds: string[]; mode: Mode } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const cancelled = useRef(false);
  useEffect(() => { cancelled.current = false; return () => { cancelled.current = true; }; }, []);

  const copy = MODE_COPY[prepared?.mode ?? mode];

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    if (!/\.(pdf|docx)$/i.test(f.name)) { setError("Please choose a PDF or Word (.docx) file."); setPhase("error"); return; }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`That file is larger than ${MAX_MB} MB.`); setPhase("error"); return; }
    setFile(f); setError(null); setPhase("idle"); setPrepared(null);
  };

  const run = useCallback(async () => {
    if (!file) return;
    setError(null);
    try {
      setPhase("uploading");
      const { document_id } = await api.uploadDocument(file, mode);
      setPhase("processing");
      for (;;) {
        await new Promise((r) => setTimeout(r, 700));
        if (cancelled.current) return;
        const d = await api.getDocument(document_id);
        if (d.status === "failed") throw new ApiError(422, "failed", d.error ?? "We couldn't read this file.");
        if (d.status === "ready") break;
      }
      setPhase("questions");
      const { questions } = await api.generateQuestions(document_id, 3);
      if (cancelled.current) return;
      setPrepared({ documentId: document_id, questionIds: questions.map((q) => q.id), mode });
      setPhase("ready");
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong."); setPhase("error");
    }
  }, [file, mode]);

  const start = async () => {
    if (!prepared) return;
    setError(null); setProgress(0); setPhase("starting");
    try {
      const created = await api.createSession(prepared.documentId, prepared.questionIds);
      const { missingQuestions } = await preloadSession(created, (d, t) => setProgress(d / t));
      if (missingQuestions > 0) sessionStorage.setItem(`viva.voiceNote.${created.session_id}`, "1");
      nav(`/session/${created.session_id}/call`);
    } catch (e: any) {
      setError(e?.message ?? "Could not start the session."); setPhase("ready");
    }
  };

  const reset = () => { setFile(null); setPrepared(null); setError(null); setPhase("idle"); };

  const working = phase === "uploading" || phase === "processing" || phase === "questions";
  const showReady = (phase === "ready" || phase === "starting") && prepared;
  const stepText = phase === "uploading" ? "Uploading your document..." : phase === "processing" ? "Reading and indexing your document..." : "Preparing your questions...";

  return (
    <div className="page">
      <Stepper current={showReady ? 1 : 0} />
      <section className="hero">
        <span className="eyebrow"><IconSpark width={14} height={14} /> {copy.eyebrow}</span>
        <h1>{copy.title} <span className="grad">out loud</span></h1>
        <p className="lead">{copy.lead}</p>
      </section>

      {showReady ? (
        <section className="card upload-card center" role="status" aria-live="polite">
          <span className="drop-icon ok"><IconSpark width={28} height={28} /></span>
          <h2>Your questions are ready</h2>
          <p className="muted">{prepared.questionIds.length} questions prepared from <b>{file?.name}</b>. They stay hidden until the {MODE_COPY[prepared.mode].examiner} asks them.</p>
          {phase === "starting" && (
            <div className="progress-line"><span className="spinner" /> <span>Preparing the {MODE_COPY[prepared.mode].examiner}'s voice...</span>
              <div className="bar slim"><div className="bar-fill" style={{ width: `${Math.max(8, progress * 100)}%`, animation: "none" }} /></div></div>
          )}
          {error && <div className="alert error" role="alert">{error}</div>}
          <button className="btn btn-primary btn-lg" onClick={start} disabled={phase === "starting"}>
            <IconPlay width={18} height={18} /> {phase === "starting" ? "Starting..." : MODE_COPY[prepared.mode].start}
          </button>
          <button className="btn btn-ghost" onClick={reset} disabled={phase === "starting"}>Use a different file</button>
        </section>
      ) : (
        <section className="card upload-card">
          <div className="mode-toggle" role="radiogroup" aria-label="Practice mode">
            {(Object.keys(MODE_COPY) as Mode[]).map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? "on" : ""}
                disabled={working} onClick={() => setMode(m)}>
                <b>{MODE_COPY[m].label}</b><small>{MODE_COPY[m].blurb}</small>
              </button>
            ))}
          </div>

          <div className={`drop ${drag ? "drag" : ""} ${file ? "has-file" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); if (!working) pick(e.dataTransfer.files?.[0]); }}
            onClick={() => !working && input.current?.click()} role="button" tabIndex={0}
            onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !working) input.current?.click(); }}
            aria-label="Choose a PDF or Word file">
            <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
            {file ? (
              <>
                <span className="drop-icon ok"><IconFile width={28} height={28} /></span>
                <b className="drop-name">{file.name}</b>
                <small className="muted">{(file.size / 1024 / 1024).toFixed(1)} MB{!working && " - click to choose a different file"}</small>
              </>
            ) : (
              <>
                <span className="drop-icon"><IconUpload width={28} height={28} /></span>
                <b>{copy.drop}</b>
                <small className="muted">PDF or Word (.docx), up to {MAX_MB} MB. Scanned PDFs are not supported.</small>
              </>
            )}
          </div>

          {working && (
            <div className="progress-line" role="status" aria-live="polite">
              <span className="spinner" /> <span>{stepText}</span>
              <div className="bar"><div className={`bar-fill ${phase}`} /></div>
            </div>
          )}
          {error && <div className="alert error" role="alert">{error}</div>}

          <button className="btn btn-primary btn-lg" disabled={!file || working} onClick={run}>
            {working ? "Working..." : "Create my practice session"}
          </button>
        </section>
      )}

      <section className="features">
        <div className="feature"><span className="f-icon"><IconSpark /></span><h3>Questions from your document</h3><p>Grounded in your own text, kept hidden until the call so it feels real.</p></div>
        <div className="feature"><span className="f-icon"><IconMic /></span><h3>A real spoken session</h3><p>Speak naturally. The {copy.examiner} waits for your pauses and may ask one follow-up.</p></div>
        <div className="feature"><span className="f-icon"><IconHeadphones /></span><h3>Honest feedback</h3><p>Scores per answer, gaps to fix, and model answers drawn from your document.</p></div>
      </section>
      <p className="center muted small">Already practised? <Link to="/history">See your sessions</Link></p>
    </div>
  );
}
