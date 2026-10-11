import type { CallState } from "../lib/types";
import { IconMic } from "./Icons";

const LABEL: Record<CallState, string> = {
  idle: "Getting ready", speaking: "Examiner speaking", listening: "Listening", thinking: "Thinking", ended: "Call ended",
};
const HINT: Record<CallState, string> = {
  idle: "Connecting to your examiner...", speaking: "Start talking any time to interrupt", listening: "Answer out loud. Take your time.",
  thinking: "Reading your answer...", ended: "Preparing your report",
};

export default function CallStatus({ state, userSpeaking }: { state: CallState; userSpeaking: boolean }) {
  const cls = userSpeaking && state === "listening" ? "you" : state;
  return (
    <div className="status" role="status" aria-live="polite">
      <div className={`orb orb-${cls}`}>
        <span className="orb-ring r1" /><span className="orb-ring r2" /><span className="orb-ring r3" />
        <div className="orb-core">{state === "listening" || state === "idle" ? <IconMic width={34} height={34} /> :
          state === "thinking" ? <span className="dots"><i /><i /><i /></span> :
            <span className="bars"><i /><i /><i /><i /><i /></span>}</div>
      </div>
      <h2>{userSpeaking && state === "listening" ? "I'm hearing you" : LABEL[state]}</h2>
      <p>{HINT[state]}</p>
    </div>
  );
}
