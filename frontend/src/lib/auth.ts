// The login token lives in localStorage so a refresh keeps you signed in.
// If storage is blocked we fall back to memory (lost on refresh).
const KEY = "viva.token";
let mem: string | null = null;
let handler: (() => void) | null = null;

export function getToken(): string | null {
  try { return localStorage.getItem(KEY) ?? mem; } catch { return mem; }
}
export function setToken(t: string) {
  mem = t;
  try { localStorage.setItem(KEY, t); } catch { /* storage blocked */ }
}
export function clearToken() {
  mem = null;
  try { localStorage.removeItem(KEY); localStorage.removeItem("viva.userId"); } catch { /* ignore */ }
  try { Object.keys(sessionStorage).filter((k) => k.startsWith("viva.")).forEach((k) => sessionStorage.removeItem(k)); } catch { /* ignore */ }
}
/** AuthContext registers this so any API call that gets a 401 logs the user out. */
export function onUnauthorized(fn: () => void) { handler = fn; }
export function notifyUnauthorized() { clearToken(); handler?.(); }
