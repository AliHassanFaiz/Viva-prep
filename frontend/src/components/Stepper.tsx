import { IconCheck } from "./Icons";

const STEPS = ["Upload", "Ready", "Practice", "Report"];

export default function Stepper({ current }: { current: 0 | 1 | 2 | 3 }) {
  return (
    <ol className="stepper" aria-label="Progress">
      {STEPS.map((label, i) => (
        <li key={label} className={i < current ? "done" : i === current ? "current" : ""} aria-current={i === current ? "step" : undefined}>
          <span className="step-dot">{i < current ? <IconCheck width={14} height={14} strokeWidth={3} /> : i + 1}</span>
          <span className="step-label">{label}</span>
        </li>
      ))}
    </ol>
  );
}
