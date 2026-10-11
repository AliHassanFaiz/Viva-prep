import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CallStatus from "../components/CallStatus";
import Captions from "../components/Captions";
import { IconHeadphones, IconKeyboard, IconMic, IconPhoneOff, IconPlay, IconShield, IconStop } from "../components/Icons";
import Stepper from "../components/Stepper";
import { useCall } from "../hooks/useCall";
import { api } from "../lib/api";
import { isSessionLoaded, preloadSession } from "../lib/audio";
import { getAllowInterruptions, setAllowInterruptions } from "../lib/settings";
import type { SessionDetail } from "../lib/types";

export default function CallPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allow, setAllow] = useState(getAllowInterruptions());
  const [text, setText] = useState("");
  const [confirmEnd, setConfirmEnd] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await api.getSession(id);
        if (!alive) return;
        if (["ended", "report_running", "report_ready", "report_failed"].includes(s.status)) { nav(`/session/${id}/report`, { replace: true }); return; }
        if (!isSessionLoaded(id)) await preloadSession({ ...s, session_id: id });
        if (alive) setSession(s);
      } catch (e: any) { if (alive) setError(e.message); }
    })();
    return () => { alive = false; };
  }, [id, nav]);

  const call = useCall({
    sessionId: id, questions: session?.questions ?? [], allowInterruptions: allow,
    onEnded: () => nav(`/session/${id}/report`),
  });

  const total = session?.questions.length ?? 0;
  const inputRef = useRef<HTMLInputElement>(null);

  if (error) return <div className="page"><div className="alert error">{error}</div></div>;
  if (!session) return <div className="page"><Stepper current={2} /><div className="card center"><span className="spinner lg" /><p className="muted">Preparing your session...</p></div></div>;

  // ---------- lobby ----------
  if (call.phase === "lobby" || call.phase === "connecting") {
    const connecting = call.phase === "connecting";
    return (
      <div className="page narrow">
        <Stepper current={2} />
        <section className="card lobby">
          <span className="drop-icon"><IconMic width={30} height={30} /></span>
          <h1>Ready when you are</h1>
          <p className="lead">{total} questions about <b>{session.document_name}</b>. It feels like a real viva: no scoring during the call, your report comes at the end.</p>
          <ul className="tips">
            <li><IconHeadphones width={18} height={18} /> Wear headphones, and find a quiet spot.</li>
            <li><IconMic width={18} height={18} /> Allow the microphone when your browser asks. Typing works too.</li>
            <li><IconShield width={18} height={18} /> Pause to think: the examiner waits for a natural gap before replying.</li>
          </ul>
          <label className="switch">
            <input type="checkbox" checked={allow} onChange={(e) => { setAllow(e.target.checked); setAllowInterruptions(e.target.checked); }} />
            <span className="slider" />
            <span><b>Allow interruptions</b><small className="muted">Speak over the examiner to cut them off. Best with headphones.</small></span>
          </label>
          {sessionStorage.getItem(`viva.voiceNote.${id}`) && <div className="alert info">Some audio isn't available, so your browser's built-in voice will read those questions.</div>}
          <button className="btn btn-primary btn-lg" onClick={() => void call.start()} disabled={connecting}>
            {connecting ? <><span className="spinner light" /> Connecting...</> : <><IconPlay width={18} height={18} /> Start the call</>}
          </button>
        </section>
      </div>
    );
  }

  // ---------- live call ----------
  const listening = call.state === "listening";
  return (
    <div className="page call">
      <Stepper current={2} />
      {call.wsStatus === "reconnecting" && <div className="alert warn" role="alert"><span className="spinner" /> Reconnecting... your progress is saved.</div>}
      {call.wsStatus === "closed" && call.phase === "live" && <div className="alert error" role="alert">Connection lost. Refresh this page to resume where you left off.</div>}
      {call.micError && <div className="alert info">{call.micError}</div>}
      {call.notice && <div className="toast" role="status">{call.notice}</div>}

      <div className="call-grid">
        <section className="card call-main">
          <div className="qprogress" aria-label={`Question ${call.qIndex + 1} of ${total}`}>
            <span>Question {Math.min(call.qIndex + 1, total)} of {total}</span>
            <div className="dots-row">{session.questions.map((q, i) => <i key={q.session_question_id} className={i < call.qIndex ? "done" : i === call.qIndex ? "cur" : ""} />)}</div>
          </div>
          <CallStatus state={call.state} userSpeaking={call.userSpeaking} />

          <div className="controls">
            {call.micOk && <button className="btn btn-primary" onClick={() => void call.finishSegment()} disabled={!listening}><IconStop width={16} height={16} /> I'm done answering</button>}
            {call.state === "speaking" && <button className="btn btn-ghost" onClick={call.stopExaminer}><IconStop width={16} height={16} /> Stop examiner</button>}
            <button className="btn btn-ghost" onClick={() => { call.setTextFallback(!call.textFallback); setTimeout(() => inputRef.current?.focus(), 50); }}><IconKeyboard width={16} height={16} /> Type instead</button>
            {!confirmEnd
              ? <button className="btn btn-danger-ghost" onClick={() => setConfirmEnd(true)}><IconPhoneOff width={16} height={16} /> End call</button>
              : <span className="confirm"><small>End and get your report?</small>
                <button className="btn btn-danger btn-sm" onClick={call.endCall}>Yes, end</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setConfirmEnd(false)}>Keep going</button></span>}
          </div>

          {call.textFallback && (
            <form className="typebox" onSubmit={(e) => { e.preventDefault(); call.sendText(text); setText(""); }}>
              <input ref={inputRef} className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your answer and press Enter" aria-label="Type your answer" />
              <button className="btn btn-primary" type="submit" disabled={!text.trim() || call.state === "thinking"}>Send</button>
            </form>
          )}
          <label className="inline-toggle"><input type="checkbox" checked={allow} onChange={(e) => { setAllow(e.target.checked); setAllowInterruptions(e.target.checked); }} /> Allow interruptions</label>
        </section>

        <aside className="card captions-card">
          <h3>Live captions</h3>
          <Captions items={call.captions} />
        </aside>
      </div>
    </div>
  );
}
