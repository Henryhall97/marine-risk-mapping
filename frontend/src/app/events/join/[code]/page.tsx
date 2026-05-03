"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import { SonarPing } from "@/components/animations";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  IconUsers,
  IconWhale,
  IconCamera,
  IconPin,
  IconCheck,
  IconWarning,
} from "@/components/icons/MarineIcons";

/* ── Types ──────────────────────────────────────────────── */

interface EventPreview {
  id: string;
  title: string;
  description: string | null;
  event_type: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  location_name: string | null;
  creator_name: string;
  member_count: number;
  sighting_count: number;
}

const TYPE_LABELS: Record<string, string> = {
  whale_watching: "Whale Watching",
  research_expedition: "Research Expedition",
  citizen_science: "Citizen Science",
  cleanup: "Cleanup",
  educational: "Educational",
  other: "Other",
};

const STATUS_LABELS: Record<string, string> = {
  upcoming: "Upcoming",
  active: "Active",
  completed: "Completed",
  cancelled: "Cancelled",
};

/* ── Main Page ─────────────────────────────────────────── */

export default function JoinEventPage() {
  const params = useParams();
  const router = useRouter();
  const inviteCode = params.code as string;
  const { user, token, loading: authLoading } = useAuth();

  const [event, setEvent] = useState<EventPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [joined, setJoined] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPreview = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/events/invite/${inviteCode}`);
      if (!res.ok) throw new Error("Event not found");
      const data = await res.json();
      setEvent(data);
    } catch {
      setEvent(null);
      setError("This invite link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  }, [inviteCode]);

  useEffect(() => {
    fetchPreview();
  }, [fetchPreview]);

  const handleJoin = async () => {
    if (!token) return;
    setJoining(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/events/join/${inviteCode}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail || "Failed to join");
      }
      const data = await res.json();
      setJoined(true);
      // Navigate to event detail after a brief delay
      setTimeout(() => router.push(`/events/${data.id}`), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to join event");
    } finally {
      setJoining(false);
    }
  };

  const fmtDate = (d: string | null) =>
    d ? new Date(d).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) : null;

  if (loading || authLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-abyss-950 pt-20">
        <SonarPing size={56} ringCount={3} active />
      </main>
    );
  }

  if (!event) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-abyss-950 pt-20">
        <IconWarning className="h-12 w-12 text-red-400/50" />
        <p className="text-sm text-slate-400">{error || "Event not found."}</p>
        <Link href="/community?tab=events" className="text-sm text-ocean-400 underline">
          Browse events →
        </Link>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-abyss-950 px-4 pt-20">
      <div className="glass-panel-strong w-full max-w-md rounded-2xl border border-ocean-800/30 p-6 text-center">
        {/* Event icon */}
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-ocean-500/15">
          <IconWhale className="h-8 w-8 text-ocean-300" />
        </div>

        <h1 className="text-xl font-bold text-white">You&apos;re invited!</h1>
        <p className="mt-1 text-sm text-slate-400">
          {event.creator_name} invited you to join:
        </p>

        {/* Event card */}
        <div className="mt-4 rounded-xl border border-ocean-800/20 bg-abyss-900/50 p-4 text-left">
          <h2 className="text-lg font-bold text-white">{event.title}</h2>
          {event.description && (
            <p className="mt-1 text-xs text-slate-400 line-clamp-2">{event.description}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span>{TYPE_LABELS[event.event_type] ?? event.event_type}</span>
            <span>·</span>
            <span>{STATUS_LABELS[event.status] ?? event.status}</span>
            {event.location_name && (
              <>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <IconPin className="h-3 w-3" /> {event.location_name}
                </span>
              </>
            )}
          </div>
          {event.start_date && (
            <p className="mt-2 text-xs text-slate-500">
              📅 {fmtDate(event.start_date)}
              {event.end_date && ` – ${fmtDate(event.end_date)}`}
            </p>
          )}
          <div className="mt-3 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <IconUsers className="h-3.5 w-3.5 text-ocean-400" />
              {event.member_count} members
            </span>
            <span className="flex items-center gap-1">
              <IconCamera className="h-3.5 w-3.5 text-bioluminescent-400" />
              {event.sighting_count} sightings
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-6 space-y-3">
          {error && !loading && (
            <div className="rounded-lg bg-red-500/15 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          {joined ? (
            <div className="flex items-center justify-center gap-2 text-emerald-400">
              <IconCheck className="h-5 w-5" />
              <span className="font-medium">Joined! Redirecting…</span>
            </div>
          ) : user ? (
            <button
              onClick={handleJoin}
              disabled={joining || event.status === "cancelled"}
              className="w-full rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-5 py-3 text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400 disabled:opacity-50"
            >
              {joining ? "Joining…" : event.status === "cancelled" ? "Event Cancelled" : "Join Event"}
            </button>
          ) : (
            <div className="space-y-2">
              <Link
                href={`/auth?redirect=${encodeURIComponent(`/events/join/${inviteCode}`)}`}
                className="block w-full rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-5 py-3 text-center text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400"
              >
                Sign in to join
              </Link>
              <p className="text-xs text-slate-500">
                Don&apos;t have an account?{" "}
                <Link
                  href={`/auth?redirect=${encodeURIComponent(`/events/join/${inviteCode}`)}&tab=register`}
                  className="text-ocean-400 underline"
                >
                  Create one
                </Link>
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
