import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { IconRefresh } from "../components/Icons";
import { MiniBar, ScoreBadge, ScoreRing } from "../components/ScoreBadge";
import Stepper from "../components/Stepper";
import { api } from "../lib/api";
import type { Report, ReportQuestion } from "../lib/types";

const BAND_COPY = {
  needs_work: "You have a clear path to improve. Focus on the gaps below, then practise again.",
  developing: "A solid base. Tighten the weaker answers and you'll be in good shape.",
  ready: "You defended your work well. Keep it fresh with one more practice round.",
} as const;

export default function ReportPage() {
  const { id = "" } = useParams();
  const [r, setR] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true, timer: number | undefined;
    const tick = async () => {
      try {
        const rep = await api.getReport(id);
        if (!alive) return;
        setR(rep);
        if (rep.status === "pending" || rep.status === "running") timer = window.setTimeout(tick, 2000);
      } catch (e: any) {
        if (!alive) return;
        setError(e.message);
      }
    };
    void tick();
    return () => { alive = false; window.clearTimeout(timer); };
  }, [id]);

  if (error) return <div className="page"><div className="alert error">{error}</div><Link to="/history" className="btn btn-ghost">Back to history</Link></div>;
  if (!r) return <div className="page"><Stepper current={3} /><div className="card center"><span className="spinner lg" /></div></div>;

  if (r.status === "pending" || r.status === "running") {
    const { done, total } = r.progress;
    return (
      <div className="page narrow">
        <Stepper current={3} />
        <div className="card center generating" role="status" aria-live="polite">
          <span className="spinner lg" />
          <h2>Generating your report</h2>
          <p className="muted">{total ? `Scoring answer ${Math.min(done + 1, total)} of ${total}...` : "Starting..."} This takes under a minute.</p>
          <div className="bar"><div className="bar-fill" style={{ width: `${total ? Math.max(8, (done / total) * 100) : 8}%`, animation: "none" }} /></div>
        </div>
      </div>
    );
  }
  if (r.status === "failed") {
    return (
      <div className="page narrow"><Stepper current={3} />
        <div className="card center"><h2>We couldn't build the report</h2><p className="muted">{r.error ?? "Something went wrong on our side."}</p>
          <Link to="/" className="btn btn-primary">Start a new practice</Link></div></div>
    );
  }

  const score = r.overall_score ?? 0;
  return (
    <div className="page">
      <Stepper current={3} />
      <section className="card report-hero">
        <ScoreRing score={score} />
        <div className="report-hero-text">
          <div className="row gap-s"><ScoreBadge band={r.band} /><span className="muted small">Readiness</span></div>
          <h1>Your readiness report</h1>
          <p className="lead">{r.summary?.overall_comment || (r.band ? BAND_COPY[r.band] : "")}</p>
          <div className="stats">
            <div><b>{r.questions.length}</b><span>questions</span></div>
            {r.avg_wpm != null && <div><b>{r.avg_wpm}</b><span>words / min</span></div>}
            <div><b>{r.questions.filter((q) => q.transcript.followup).length}</b><span>follow-ups</span></div>
          </div>
        </div>
      </section>

      {r.summary && (
        <section className="summary-grid">
          <SummaryCard title="Strengths" tone="good" items={r.summary.strengths} />
          <SummaryCard title="Gaps to close" tone="warn" items={r.summary.gaps} />
          <SummaryCard title="Practise next" tone="info" items={r.summary.practice_next} />
        </section>
      )}

      <h2 className="section-title">Question by question</h2>
      <div className="qreports">{r.questions.map((q) => <QuestionReport key={q.session_question_id} q={q} />)}</div>

      <div className="row gap-m center-row">
        <Link to="/" className="btn btn-primary btn-lg"><IconRefresh width={18} height={18} /> Practise again</Link>
        <Link to="/history" className="btn btn-ghost btn-lg">View history</Link>
      </div>
    </div>
  );
}

function SummaryCard({ title, tone, items }: { title: string; tone: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className={`card sum sum-${tone}`}>
      <h3>{title}</h3>
      <ul>{items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    </div>
  );
}

function QuestionReport({ q }: { q: ReportQuestion }) {
  const [open, setOpen] = useState(false);
  const failed = q.status === "failed";
  const score = q.question_score;
  return (
    <article className="card qreport">
      <header>
        <span className="qnum">Q{q.position + 1}</span>
        <h3>{q.question}</h3>
        {failed ? <span className="badge badge-muted">Not scored</span> : <ScoreBadge band={score == null ? null : score < 50 ? "needs_work" : score < 75 ? "developing" : "ready"} score={score} />}
      </header>
      {failed ? <p className="muted">Could not score this question.</p> : (
        <>
          {q.scores && (
            <div className="minibars">
              <MiniBar label="Accuracy" value={q.scores.accuracy} /><MiniBar label="Completeness" value={q.scores.completeness} />
              <MiniBar label="Clarity" value={q.scores.clarity} /><MiniBar label="Justification" value={q.scores.justification} />
            </div>
          )}
          {q.feedback && <p className="feedback">{q.feedback}</p>}
          <div className="points-grid">
            {q.covered_points.length > 0 && <div><h4 className="good">You covered</h4><ul>{q.covered_points.map((p, i) => <li key={i}>{p}</li>)}</ul></div>}
            {q.missed_points.length > 0 && <div><h4 className="warn">You missed</h4><ul>{q.missed_points.map((p, i) => <li key={i}>{p}</li>)}</ul></div>}
            {q.incorrect_claims.length > 0 && <div><h4 className="bad">Check these claims</h4><ul>{q.incorrect_claims.map((p, i) => <li key={i}>{p}</li>)}</ul></div>}
          </div>
          {q.model_answer && <div className="model"><h4>A strong answer</h4><p>{q.model_answer}</p></div>}
        </>
      )}
      <button className="link-btn" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "Hide transcript" : "Show transcript"}</button>
      {open && (
        <div className="transcript">
          <p><b>You:</b> {q.transcript.answer || <i className="muted">No answer recorded.</i>}</p>
          {q.transcript.followup && <p><b>Examiner follow-up:</b> {q.transcript.followup}</p>}
          {q.transcript.followup_answer && <p><b>You:</b> {q.transcript.followup_answer}</p>}
        </div>
      )}
    </article>
  );
}
