import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { user, login, signup } = useAuth();
  const nav = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  if (user) return <Navigate to={from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (isSignup && password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (isSignup && password !== confirm) { setError("The two passwords do not match."); return; }
    setBusy(true);
    try {
      await (isSignup ? signup : login)(email.trim(), password);
      nav(from, { replace: true });
    } catch (err: any) {
      setError(err?.message ?? "Something went wrong. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <section className="card auth-card">
        <h1>{isSignup ? "Create your account" : "Welcome back"}</h1>
        <p className="muted">{isSignup ? "Your documents, sessions and reports stay private to your account." : "Log in to see your practice history."}</p>
        <form onSubmit={submit} className="auth-form">
          <label className="field">Email
            <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">Password
            <input type="password" autoComplete={isSignup ? "new-password" : "current-password"} required minLength={isSignup ? 8 : undefined}
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {isSignup && (
            <label className="field">Confirm password
              <input type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </label>
          )}
          {error && <div className="alert error" role="alert">{error}</div>}
          <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
            {busy ? "Please wait..." : isSignup ? "Sign up" : "Log in"}
          </button>
        </form>
        <p className="muted small center">
          {isSignup ? <>Already have an account? <Link to="/login" state={{ from }}>Log in</Link></>
            : <>New here? <Link to="/signup" state={{ from }}>Create an account</Link></>}
        </p>
      </section>
    </div>
  );
}
