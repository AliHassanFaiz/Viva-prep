import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { IconFile, IconHeadphones, IconMic, IconSpark, IconUpload } from "../components/Icons";
import Stepper from "../components/Stepper";
import { api, ApiError } from "../lib/api";

type Phase = "idle" | "uploading" | "processing" | "questions" | "error";
const MAX_MB = 15;

export default function UploadPage() {
  const nav = useNavigate();
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const cancelled = useRef(false);
  useEffect(() => { cancelled.current = false; return () => { cancelled.current = true; }; }, []);

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    if (!/\.(pdf|docx)$/i.test(f.name)) { setError("Please choose a PDF or Word (.docx) file."); setPhase("error"); return; }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`That file is larger than ${MAX_MB} MB.`); setPhase("error"); return; }
    setFile(f); setError(null); setPhase("idle");
  };

  const run = useCallback(async () => {
    if (!file) return;
    setError(null);
    try {
      setPhase("uploading");
      const { document_id } = await api.uploadDocument(file);
      setPhase("processing");
      for (;;) {
        await new Promise((r) => setTimeout(r, 1500));
        if (cancelled.current) return;
        const d = await api.getDocument(document_id);
        if (d.status === "failed") throw new ApiError(422, "failed", d.error ?? "We couldn't read this file.");
        if (d.status === "ready") break;
      }
      setPhase("questions");
      await api.generateQuestions(document_id, 3);
      if (!cancelled.current) nav(`/documents/${document_id}/questions`);
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong."); setPhase("error");
    }
  }, [file, nav]);

  const busy = phase === "uploading" || phase === "processing" || phase === "questions";
  const stepText = phase === "uploading" ? "Uploading your report..." : phase === "processing" ? "Reading and indexing your report..." : "Writing your examiner's questions...";

  return (
    <div className="page">
      <Stepper current={0} />
      <section className="hero">
        <span className="eyebrow"><IconSpark width={14} height={14} /> Mock viva, powered by your own report</span>
        <h1>Practise defending your work <span className="grad">out loud</span></h1>
        <p className="lead">Upload your thesis or project report. An AI examiner asks questions from it, listens to your answers, and gives you a readiness report.</p>
      </section>

      <section className="card upload-card">
        <div className={`drop ${drag ? "drag" : ""} ${file ? "has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (!busy) pick(e.dataTransfer.files?.[0]); }}
          onClick={() => !busy && input.current?.click()} role="button" tabIndex={0}
          onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !busy) input.current?.click(); }}
          aria-label="Choose a PDF or Word file">
          <input ref={input} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
          {file ? (
            <>
              <span className="drop-icon ok"><IconFile width={28} height={28} /></span>
              <b className="drop-name">{file.name}</b>
              <small className="muted">{(file.size / 1024 / 1024).toFixed(1)} MB{!busy && " - click to choose a different file"}</small>
            </>
          ) : (
            <>
              <span className="drop-icon"><IconUpload width={28} height={28} /></span>
              <b>Drop your report here, or click to browse</b>
              <small className="muted">PDF or Word (.docx), up to {MAX_MB} MB. Scanned PDFs are not supported.</small>
            </>
          )}
        </div>

        {busy && (
          <div className="progress-line" role="status" aria-live="polite">
            <span className="spinner" /> <span>{stepText}</span>
            <div className="bar"><div className={`bar-fill ${phase}`} /></div>
          </div>
        )}
        {error && <div className="alert error" role="alert">{error}</div>}

        <button className="btn btn-primary btn-lg" disabled={!file || busy} onClick={run}>
          {busy ? "Working..." : "Create my practice session"}
        </button>
      </section>

      <section className="features">
        <div className="feature"><span className="f-icon"><IconSpark /></span><h3>Questions from your report</h3><p>2 to 4 questions grounded in your own text. Edit or remove any before you start.</p></div>
        <div className="feature"><span className="f-icon"><IconMic /></span><h3>A real spoken viva</h3><p>Speak naturally. The examiner waits for your pauses and may ask one follow-up.</p></div>
        <div className="feature"><span className="f-icon"><IconHeadphones /></span><h3>Honest feedback</h3><p>Scores per answer, gaps to fix, and model answers drawn from your report.</p></div>
      </section>
      <p className="center muted small">Already practised? <Link to="/history">See your sessions</Link></p>
    </div>
  );
}
