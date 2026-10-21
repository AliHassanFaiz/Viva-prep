import type { Mode } from "./types";

export const MODE_COPY: Record<Mode, { label: string; start: string; eyebrow: string; title: string; lead: string; drop: string; examiner: string; blurb: string }> = {
  viva: {
    label: "Viva", start: "Start viva", eyebrow: "Mock viva, powered by your own report",
    title: "Practise defending your work", lead: "Upload your thesis or project report. An AI examiner asks questions from it, listens to your answers, and gives you a readiness report.",
    drop: "Drop your report here, or click to browse", examiner: "examiner", blurb: "Thesis, dissertation or project report",
  },
  interview: {
    label: "Interview", start: "Start interview", eyebrow: "Mock interview, powered by your own documents",
    title: "Practise your interview", lead: "Upload your resume, a job description, or project notes. An AI interviewer asks questions from it, listens to your answers, and gives you a readiness report.",
    drop: "Drop your resume or job description here, or click to browse", examiner: "interviewer", blurb: "Resume, job description or project notes",
  },
};
