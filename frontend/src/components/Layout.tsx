import { NavLink, Outlet, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { IconHistory, IconShield } from "./Icons";

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="ViVa Prep home">
      <span className="logo-mark">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round">
          <path d="M6 9v6M10 5v14M14 9v6M18 11v2" />
        </svg>
      </span>
      <span>ViVa <b>Prep</b></span>
    </Link>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <div className="container topbar-inner">
          <Logo />
          {user ? (
            <nav className="nav">
              <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>New practice</NavLink>
              <NavLink to="/history" className={({ isActive }) => (isActive ? "active" : "")}><IconHistory width={16} height={16} /> History</NavLink>
              <span className="nav-user" title={user.email}>{user.email}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>Log out</button>
            </nav>
          ) : (
            <nav className="nav">
              <NavLink to="/login" className={({ isActive }) => (isActive ? "active" : "")}>Log in</NavLink>
              <NavLink to="/signup" className={({ isActive }) => (isActive ? "active" : "")}>Sign up</NavLink>
            </nav>
          )}
        </div>
      </header>
      <main className="container main"><Outlet /></main>
      <footer className="footer">
        <div className="container footer-inner">
          <IconShield width={16} height={16} />
          <span>Your data is private to your account. The file itself is never stored, and you can delete your data any time from History.</span>
        </div>
      </footer>
    </div>
  );
}
