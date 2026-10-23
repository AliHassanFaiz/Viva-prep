import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { IconCheck, IconEye, IconEyeOff, IconHeadphones, IconLock, IconMail, IconShield, IconSpark } from "../components/Icons";
import { useAuth } from "../context/AuthContext";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

/** Advisory only: the server only requires 8+ characters. */
function strength(pw: string): { score: number; label: string } {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  return { score: pw ? Math.max(1, s) : 0, label: ["", "Weak", "Okay", "Good", "Strong"][pw ? Math.max(1, s) : 0] };
}

const POINTS = [
  { icon: IconSpark, title: "Questions from your own document", text: "Hidden until the call, so it feels like the real thing." },
  { icon: IconHeadphones, title: "A real spoken session", text: "Answer out loud and get one follow-up when you are vague." },
  { icon: IconShield, title: "Private to your account", text: "Your documents, answers and reports are never shared." },
];

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { user, login, signup } = useAuth();
  const nav = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const isSignup = mode === "signup";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean; confirm?: boolean }>({});
  const [caps, setCaps] = useState(false);
  const [error, setError] = useState<{ code?: string; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const pw = useMemo(() => strength(password), [password]);
  const emailOk = EMAIL_RE.test(email.trim());
  const pwOk = password.length >= 8;
  const matchOk = password === confirm;

  if (user) return <Navigate to={from} replace />;

  const touch = (k: "email" | "password" | "confirm") => setTouched((t) => ({ ...t, [k]: true }));
  const onKey = (e: KeyboardEvent) => setCaps(e.getModifierState?.("CapsLock") ?? false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setTouched({ email: true, password: true, confirm: true });
    if (!emailOk || (isSignup && (!pwOk || !matchOk)) || (!isSignup && !password)) return;
    setBusy(true);
    try {
      await (isSignup ? signup : login)(email.trim(), password);
      nav(from, { replace: true });
    } catch (err: any) {
      setError({ code: err?.code, message: err?.message ?? "Something went wrong. Please try again." });
      setBusy(false);
    }
  };

  const emailErr = touched.email && !emailOk ? "Enter a valid email address." : null;
  const pwErr = touched.password && (isSignup ? !pwOk : !password) ? (isSignup ? "Use at least 8 characters." : "Enter your password.") : null;
  const confirmErr = touched.confirm && isSignup && !matchOk ? "The passwords do not match." : null;

  return (
    <div className="auth-shell">
      <aside className="auth-aside">
        <div className="auth-aside-inner">
          <span className="auth-kicker">ViVa Prep</span>
          <h2>Practise out loud, <br />before it counts.</h2>
          <p>Upload a report or resume, answer an AI examiner in a real spoken session, and see exactly what to fix.</p>
          <ul className="auth-points">
            {POINTS.map(({ icon: Icon, title, text }) => (
              <li key={title}><span className="auth-point-icon"><Icon width={18} height={18} /></span><div><b>{title}</b><small>{text}</small></div></li>
            ))}
          </ul>
        </div>
      </aside>

      <section className="auth-main">
        <div className="auth-tabs" role="tablist" aria-label="Account">
          <Link to="/login" state={{ from }} role="tab" aria-selected={!isSignup} className={!isSignup ? "on" : ""}>Log in</Link>
          <Link to="/signup" state={{ from }} role="tab" aria-selected={isSignup} className={isSignup ? "on" : ""}>Sign up</Link>
        </div>

        <h1 className="auth-title">{isSignup ? "Create your account" : "Welcome back"}</h1>
        <p className="muted auth-sub">{isSignup ? "It takes a few seconds. No email verification needed." : "Log in to continue your practice and see your history."}</p>

        <form onSubmit={submit} className="auth-form" noValidate>
          <div className="field">
            <label htmlFor="email">Email</label>
            <div className={`input-wrap ${emailErr ? "invalid" : ""}`}>
              <IconMail width={18} height={18} />
              <input id="email" type="email" inputMode="email" autoComplete="email" autoFocus placeholder="you@example.com"
                value={email} onChange={(e) => setEmail(e.target.value)} onBlur={() => touch("email")}
                aria-invalid={!!emailErr} aria-describedby={emailErr ? "email-err" : undefined} />
            </div>
            {emailErr && <small id="email-err" className="field-err" role="alert">{emailErr}</small>}
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <div className={`input-wrap ${pwErr ? "invalid" : ""}`}>
              <IconLock width={18} height={18} />
              <input id="password" type={show ? "text" : "password"} autoComplete={isSignup ? "new-password" : "current-password"}
                placeholder={isSignup ? "At least 8 characters" : "Your password"} value={password}
                onChange={(e) => setPassword(e.target.value)} onBlur={() => touch("password")} onKeyUp={onKey} onKeyDown={onKey}
                aria-invalid={!!pwErr} aria-describedby={pwErr ? "pw-err" : undefined} />
              <button type="button" className="eye" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} aria-pressed={show}>
                {show ? <IconEyeOff width={18} height={18} /> : <IconEye width={18} height={18} />}
              </button>
            </div>
            {caps && <small className="field-hint warn">Caps Lock is on.</small>}
            {pwErr && <small id="pw-err" className="field-err" role="alert">{pwErr}</small>}
            {isSignup && password && (
              <div className="strength" aria-live="polite">
                <div className={`strength-bars s${pw.score}`}><i /><i /><i /><i /></div>
                <small>{pw.label}{pw.score < 3 && pwOk ? ": try a longer password" : ""}</small>
              </div>
            )}
          </div>

          {isSignup && (
            <div className="field">
              <label htmlFor="confirm">Confirm password</label>
              <div className={`input-wrap ${confirmErr ? "invalid" : ""}`}>
                <IconLock width={18} height={18} />
                <input id="confirm" type={show ? "text" : "password"} autoComplete="new-password" placeholder="Type it again" value={confirm}
                  onChange={(e) => setConfirm(e.target.value)} onBlur={() => touch("confirm")}
                  aria-invalid={!!confirmErr} aria-describedby={confirmErr ? "confirm-err" : undefined} />
                {confirm && matchOk && <span className="ok-mark" aria-label="Passwords match"><IconCheck width={18} height={18} /></span>}
              </div>
              {confirmErr && <small id="confirm-err" className="field-err" role="alert">{confirmErr}</small>}
            </div>
          )}

          {error && (
            <div className="alert error" role="alert">
              <span>{error.message}{error.code === "email_taken" && <> <Link to="/login" state={{ from }}>Log in instead</Link></>}</span>
            </div>
          )}

          <button className="btn btn-primary btn-lg auth-submit" type="submit" disabled={busy}>
            {busy ? <><span className="spinner light" /> {isSignup ? "Creating account..." : "Logging in..."}</> : isSignup ? "Create account" : "Log in"}
          </button>
        </form>

        <p className="muted small center auth-switch">
          {isSignup ? <>Already have an account? <Link to="/login" state={{ from }}>Log in</Link></>
            : <>New to ViVa Prep? <Link to="/signup" state={{ from }}>Create an account</Link></>}
        </p>
      </section>
    </div>
  );
}
