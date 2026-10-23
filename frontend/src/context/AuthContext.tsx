import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { clearToken, getToken, onUnauthorized, setToken } from "../lib/auth";
import type { AuthUser } from "../lib/types";

interface AuthValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}
const Ctx = createContext<AuthValue>(null as unknown as AuthValue);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(() => !!getToken());

  const logout = useCallback(() => { clearToken(); setUser(null); }, []);
  useEffect(() => { onUnauthorized(() => setUser(null)); }, []);

  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    let alive = true;
    api.me().then((u) => alive && setUser(u)).catch(() => { /* 401 already logged us out */ }).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  const value = useMemo<AuthValue>(() => ({
    user, loading, logout,
    login: async (email, password) => { const r = await api.login(email, password); setToken(r.access_token); setUser(r.user); },
    signup: async (email, password) => { const r = await api.signup(email, password); setToken(r.access_token); setUser(r.user); },
  }), [user, loading, logout]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
