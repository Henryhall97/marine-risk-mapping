"use client";

import { Suspense } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

type Tab = "login" | "register";

function AuthPageInner() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/profile";
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Redirect if already logged in
  useEffect(() => {
    if (!loading && user) router.push(next);
  }, [loading, user, router, next]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (tab === "register" && password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setSubmitting(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        await register(email, displayName || email.split("@")[0], password);
      }
      router.push(next);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-abyss-950 pt-14">
        <div className="animate-pulse text-slate-400">Loading…</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-abyss-950 px-4 pt-14">
      <div className="w-full max-w-md rounded-2xl border border-ocean-800 bg-abyss-900/80 p-8 shadow-xl">
        {/* Tabs */}
        <div className="mb-6 flex rounded-lg bg-abyss-800/60 p-1">
          {(["login", "register"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTab(t);
                setError(null);
              }}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                tab === t
                  ? "bg-ocean-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {t === "login" ? "Sign In" : "Create Account"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-slate-400">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-white placeholder-gray-500 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
              placeholder="you@example.com"
            />
          </div>

          {tab === "register" && (
            <div>
              <label className="mb-1 block text-sm text-slate-400">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-white placeholder-gray-500 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
                placeholder="Your name"
              />
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm text-slate-400">
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-white placeholder-gray-500 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
              placeholder="Min 8 characters"
            />
          </div>

          {tab === "register" && (
            <div>
              <label className="mb-1 block text-sm text-slate-400">
                Confirm Password
              </label>
              <input
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-white placeholder-gray-500 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
                placeholder="Re-enter password"
              />
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/30 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-ocean-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ocean-500 disabled:opacity-50"
          >
            {submitting
              ? "Please wait…"
              : tab === "login"
                ? "Sign In"
                : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense>
      <AuthPageInner />
    </Suspense>
  );
}
