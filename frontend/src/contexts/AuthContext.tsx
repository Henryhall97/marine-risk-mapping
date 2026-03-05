"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { API_BASE } from "@/lib/config";

/* ── Types ─────────────────────────────────────────────── */

export interface Credential {
  id: number;
  credential_type: string;
  description: string;
  is_verified: boolean;
  verified_at: string | null;
}

export interface UserProfile {
  id: number;
  email: string;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
  submission_count: number;
  reputation_score: number;
  reputation_tier: string;
  credentials: Credential[];
}

interface AuthState {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    displayName: string,
    password: string,
  ) => Promise<void>;
  logout: () => void;
  /** Re-fetch /auth/me to refresh user profile (e.g. after avatar upload) */
  refreshUser: () => Promise<void>;
  /** Convenience: Authorization header value, or undefined */
  authHeader: string | undefined;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "marine_risk_token";

/* ── Provider ──────────────────────────────────────────── */

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    loading: true,
  });

  /* Hydrate from localStorage on mount */
  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (!saved) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }
    // Validate the token by calling /auth/me
    fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${saved}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("expired");
        return r.json();
      })
      .then((user: UserProfile) => {
        setState({ user, token: saved, loading: false });
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setState({ user: null, token: null, loading: false });
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? "Login failed");
    }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setState({ user: data.user, token: data.access_token, loading: false });
  }, []);

  const register = useCallback(
    async (email: string, displayName: string, password: string) => {
      const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          display_name: displayName,
          password,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Registration failed");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setState({ user: data.user, token: data.access_token, loading: false });
    },
    [],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setState({ user: null, token: null, loading: false });
  }, []);

  const refreshUser = useCallback(async () => {
    const t = state.token;
    if (!t) return;
    try {
      const r = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (r.ok) {
        const u: UserProfile = await r.json();
        setState((s) => ({ ...s, user: u }));
      }
    } catch {
      /* silently ignore refresh failures */
    }
  }, [state.token]);

  const authHeader = state.token ? `Bearer ${state.token}` : undefined;

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, register, logout, refreshUser, authHeader }),
    [state, login, register, logout, refreshUser, authHeader],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/* ── Hook ──────────────────────────────────────────────── */

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
