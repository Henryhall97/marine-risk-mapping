"use client";

import { useAuth, type Credential } from "@/contexts/AuthContext";
import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { MapSubmission } from "@/components/SubmissionMap";

const SubmissionMap = dynamic(() => import("@/components/SubmissionMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-abyss-900 text-slate-500">
      Loading map…
    </div>
  ),
});

/* ── Types ──────────────────────────────────────────────── */

interface SubmissionSummary {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  species_guess: string | null;
  model_species: string | null;
  model_confidence: number | null;
  model_source: string | null;
  interaction_type: string | null;
  risk_category: string | null;
  risk_score: number | null;
  is_public: boolean;
  verification_status: string;
  advisory_level: string | null;
}

interface RepEvent {
  id: number;
  event_type: string;
  points: number;
  submission_id: string | null;
  description: string | null;
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  unverified: "bg-abyss-700 text-slate-300",
  verified: "bg-green-900/60 text-green-300",
  rejected: "bg-red-900/60 text-red-300",
  disputed: "bg-yellow-900/60 text-yellow-300",
};

const RISK_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

const TIER_STYLE: Record<string, { color: string; icon: string }> = {
  newcomer: { color: "text-slate-400", icon: "🌱" },
  observer: { color: "text-ocean-400", icon: "👁️" },
  contributor: { color: "text-green-400", icon: "⭐" },
  expert: { color: "text-purple-400", icon: "🔬" },
  authority: { color: "text-yellow-400", icon: "👑" },
};

const TIER_THRESHOLDS = [
  { name: "Newcomer", min: 0 },
  { name: "Observer", min: 50 },
  { name: "Contributor", min: 200 },
  { name: "Expert", min: 500 },
  { name: "Authority", min: 1000 },
];

const CREDENTIAL_LABELS: Record<string, string> = {
  marine_biologist: "Marine Biologist",
  certified_observer: "Certified Observer",
  noaa_affiliate: "NOAA Affiliate",
  research_institution: "Research Institution",
  vessel_operator: "Vessel Operator",
  coast_guard: "Coast Guard",
  other: "Other",
};

/* ── Page ───────────────────────────────────────────────── */

export default function ProfilePage() {
  const { user, loading, logout, refreshUser, authHeader } = useAuth();
  const router = useRouter();
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [repHistory, setRepHistory] = useState<RepEvent[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showCredForm, setShowCredForm] = useState(false);
  const [credType, setCredType] = useState("marine_biologist");
  const [credDesc, setCredDesc] = useState("");
  const [credSubmitting, setCredSubmitting] = useState(false);
  const [showSubMap, setShowSubMap] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const PAGE_SIZE = 20;

  useEffect(() => {
    if (!loading && !user) router.push("/auth");
  }, [loading, user, router]);

  const fetchSubmissions = useCallback(async () => {
    if (!authHeader) return;
    setFetching(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/mine?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
        { headers: { Authorization: authHeader } },
      );
      if (res.ok) {
        const data = await res.json();
        setSubmissions(data.submissions);
        setTotal(data.total);
      }
    } finally {
      setFetching(false);
    }
  }, [authHeader, page]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  const fetchRepHistory = async () => {
    if (!authHeader) return;
    const res = await fetch(
      `${API_BASE}/api/v1/auth/reputation/history?limit=20`,
      { headers: { Authorization: authHeader } },
    );
    if (res.ok) {
      const data = await res.json();
      setRepHistory(data.events);
    }
  };

  const togglePublic = async (id: string, current: boolean) => {
    if (!authHeader) return;
    const res = await fetch(
      `${API_BASE}/api/v1/submissions/${id}/visibility?is_public=${!current}`,
      { method: "PATCH", headers: { Authorization: authHeader } },
    );
    if (res.ok) fetchSubmissions();
  };

  const addCredential = async () => {
    if (!authHeader || !credDesc.trim()) return;
    setCredSubmitting(true);
    try {
      const params = new URLSearchParams({
        credential_type: credType,
        description: credDesc,
      });
      const res = await fetch(
        `${API_BASE}/api/v1/auth/credentials?${params}`,
        { method: "POST", headers: { Authorization: authHeader } },
      );
      if (res.ok) {
        setCredDesc("");
        setShowCredForm(false);
        // Refresh profile to get updated credentials
        window.location.reload();
      }
    } finally {
      setCredSubmitting(false);
    }
  };

  const handleAvatarChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file || !authHeader) return;
    setAvatarUploading(true);
    try {
      const form = new FormData();
      form.append("image", file);
      const res = await fetch(`${API_BASE}/api/v1/auth/avatar`, {
        method: "POST",
        headers: { Authorization: authHeader },
        body: form,
      });
      if (res.ok) {
        await refreshUser();
      } else {
        const body = await res.json().catch(() => ({}));
        console.error("Avatar upload failed:", res.status, body);
        alert(body.detail ?? "Upload failed");
      }
    } finally {
      setAvatarUploading(false);
      // Reset so re-selecting the same file triggers onChange
      if (avatarInputRef.current) avatarInputRef.current.value = "";
    }
  };

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-abyss-950 pt-14">
        <div className="animate-pulse text-slate-400">Loading…</div>
      </div>
    );
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const tier = TIER_STYLE[user.reputation_tier] ?? TIER_STYLE.newcomer;
  const nextTier = TIER_THRESHOLDS.find((t) => t.min > user.reputation_score);
  const currentTierThreshold =
    [...TIER_THRESHOLDS].reverse().find((t) => t.min <= user.reputation_score)
      ?.min ?? 0;
  const progressMax = nextTier ? nextTier.min - currentTierThreshold : 1;
  const progressVal = nextTier
    ? user.reputation_score - currentTierThreshold
    : 1;
  const progressPct = Math.min(100, (progressVal / progressMax) * 100);

  return (
    <div className="min-h-screen bg-abyss-950 px-4 pt-20 pb-12">
      <div className="mx-auto max-w-5xl">
        {/* Profile header + reputation */}
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          {/* User info */}
          <div className="rounded-2xl border border-ocean-800 bg-abyss-900/80 p-6 sm:col-span-2">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                {/* Avatar with upload overlay */}
                <button
                  type="button"
                  onClick={() => avatarInputRef.current?.click()}
                  className="group relative shrink-0"
                  disabled={avatarUploading}
                  title="Change avatar"
                >
                  <UserAvatar
                    avatarUrl={user.avatar_url}
                    displayName={user.display_name}
                    size={64}
                  />
                  <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                    {avatarUploading ? (
                      <span className="text-xs text-white">…</span>
                    ) : (
                      <span className="text-sm text-white">📷</span>
                    )}
                  </div>
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={handleAvatarChange}
                  />
                </button>

                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-white">
                      {user.display_name}
                    </h1>
                    <span
                      className={`rounded-full border border-ocean-800 px-2.5 py-0.5 text-xs font-medium ${tier.color}`}
                    >
                      {tier.icon} {user.reputation_tier}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-400">{user.email}</p>
                  <p className="mt-2 text-sm text-slate-500">
                    Joined {new Date(user.created_at).toLocaleDateString()} ·{" "}
                    {total} submission{total !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  logout();
                  router.push("/");
                }}
                className="rounded-lg border border-ocean-800 px-4 py-2 text-sm text-slate-400 transition-colors hover:border-red-700 hover:text-red-400"
              >
                Sign Out
              </button>
            </div>

            {/* Credentials */}
            {user.credentials.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {user.credentials.map((c: Credential) => (
                  <span
                    key={c.id}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                      c.is_verified
                        ? "border border-green-800 bg-green-900/30 text-green-300"
                        : "border border-ocean-800 bg-abyss-800 text-slate-400"
                    }`}
                    title={c.description}
                  >
                    {c.is_verified ? "✓ " : "⏳ "}
                    {CREDENTIAL_LABELS[c.credential_type] ?? c.credential_type}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Reputation card */}
          <div className="rounded-2xl border border-ocean-800 bg-abyss-900/80 p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Reputation Score
            </h3>
            <div className={`mt-2 text-3xl font-bold ${tier.color}`}>
              {user.reputation_score}
            </div>

            {/* Progress bar to next tier */}
            {nextTier && (
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-xs text-slate-500">
                  <span>{user.reputation_tier}</span>
                  <span>{nextTier.name}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-abyss-800">
                  <div
                    className="h-full rounded-full bg-ocean-500 transition-all"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  {nextTier.min - user.reputation_score} points to{" "}
                  {nextTier.name}
                </p>
              </div>
            )}

            {/* Quick actions */}
            <div className="mt-4 flex flex-col gap-2">
              <button
                onClick={() => {
                  setShowHistory(!showHistory);
                  if (!showHistory) fetchRepHistory();
                }}
                className="text-left text-xs text-ocean-400 hover:underline"
              >
                {showHistory ? "Hide" : "View"} reputation history
              </button>
              <button
                onClick={() => setShowCredForm(!showCredForm)}
                className="text-left text-xs text-ocean-400 hover:underline"
              >
                {showCredForm ? "Cancel" : "+ Add credential"}
              </button>
            </div>
          </div>
        </div>

        {/* Reputation history (expandable) */}
        {showHistory && repHistory.length > 0 && (
          <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/60 p-4">
            <h3 className="mb-3 text-sm font-semibold text-white">
              Recent Reputation Events
            </h3>
            <div className="space-y-2">
              {repHistory.map((e) => (
                <div
                  key={e.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex-1">
                    <span className="text-slate-300">
                      {e.description ?? e.event_type.replace(/_/g, " ")}
                    </span>
                    <span className="ml-2 text-xs text-slate-600">
                      {new Date(e.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <span
                    className={`font-mono text-sm font-medium ${e.points > 0 ? "text-green-400" : "text-red-400"}`}
                  >
                    {e.points > 0 ? "+" : ""}
                    {e.points}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Add credential form (expandable) */}
        {showCredForm && (
          <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/60 p-4">
            <h3 className="mb-3 text-sm font-semibold text-white">
              Add a Credential
            </h3>
            <p className="mb-3 text-xs text-slate-500">
              Credentials are reviewed and verified. Verified credentials award
              +20 reputation points and increase trust in your submissions.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <select
                value={credType}
                onChange={(e) => setCredType(e.target.value)}
                className="rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white"
              >
                {Object.entries(CREDENTIAL_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={credDesc}
                onChange={(e) => setCredDesc(e.target.value)}
                placeholder="e.g. PhD Marine Biology, Woods Hole Oceanographic"
                className="flex-1 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
              <button
                onClick={addCredential}
                disabled={credSubmitting || !credDesc.trim()}
                className="rounded-lg bg-ocean-600 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-500 disabled:opacity-50"
              >
                Submit
              </button>
            </div>
          </div>
        )}

        {/* How scoring works */}
        <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/40 p-4">
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium text-slate-400 group-open:text-white">
              How is reputation calculated?
            </summary>
            <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
              <div>
                <span className="font-medium text-green-400">+10</span>{" "}
                Sighting verified by community
              </div>
              <div>
                <span className="font-medium text-green-400">+5</span>{" "}
                Species guess matches ML model
              </div>
              <div>
                <span className="font-medium text-green-400">+3</span>{" "}
                Your verification reaches consensus
              </div>
              <div>
                <span className="font-medium text-green-400">+2</span>{" "}
                Providing a verification vote
              </div>
              <div>
                <span className="font-medium text-green-400">+20</span>{" "}
                Credential verified
              </div>
              <div>
                <span className="font-medium text-red-400">−5</span>{" "}
                Sighting rejected by community
              </div>
              <div>
                <span className="font-medium text-red-400">−2</span>{" "}
                Sighting disputed
              </div>
            </div>
          </details>
        </div>

        {/* Quick stats row */}
        {submissions.length > 0 && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-white">{total}</div>
              <div className="text-xs text-slate-500">Total</div>
            </div>
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-green-400">
                {submissions.filter((s) => s.verification_status === "verified").length}
              </div>
              <div className="text-xs text-slate-500">Verified</div>
            </div>
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-ocean-400">
                {new Set(submissions.map((s) => s.model_species ?? s.species_guess).filter(Boolean)).size}
              </div>
              <div className="text-xs text-slate-500">Species</div>
            </div>
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-white">
                {submissions.filter((s) => s.is_public).length}
              </div>
              <div className="text-xs text-slate-500">Public</div>
            </div>
          </div>
        )}

        {/* Submissions list header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            Your Submissions
          </h2>
          {submissions.some((s) => s.lat != null) && (
            <div className="flex gap-1 rounded-lg border border-ocean-800 bg-abyss-900 p-1">
              <button
                onClick={() => setShowSubMap(false)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  !showSubMap ? "bg-ocean-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                ☰ List
              </button>
              <button
                onClick={() => setShowSubMap(true)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  showSubMap ? "bg-ocean-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                🗺 Map
              </button>
            </div>
          )}
        </div>

        {/* Submissions map */}
        {showSubMap && (
          <div className="mb-6 h-[380px] overflow-hidden rounded-xl border border-ocean-800">
            <SubmissionMap
              data={submissions
                .filter((s): s is typeof s & { lat: number; lon: number } =>
                  s.lat != null && s.lon != null,
                )
                .map((s) => ({
                  id: s.id,
                  lat: s.lat,
                  lon: s.lon,
                  species: s.model_species ?? s.species_guess ?? "unknown",
                  interaction_type: s.interaction_type,
                  verification_status: s.verification_status,
                  submitter_name: user.display_name,
                  created_at: s.created_at,
                }))}
              onClickSubmission={(id) => window.open(`/submissions/${id}`, "_blank")}
            />
          </div>
        )}

        {!showSubMap && (fetching && submissions.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            Loading submissions…
          </div>
        ) : !showSubMap && submissions.length === 0 ? (
          <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 py-16 text-center">
            <p className="text-slate-400">No submissions yet.</p>
            <Link
              href="/report"
              className="mt-3 inline-block text-sm text-ocean-400 hover:underline"
            >
              Report your first sighting →
            </Link>
          </div>
        ) : !showSubMap ? (
          <>
            <div className="space-y-3">
              {submissions.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-xl border border-ocean-800 bg-abyss-900/70 px-5 py-4 transition-colors hover:border-ocean-800"
                >
                  <Link href={`/submissions/${s.id}`} className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-white">
                        {s.model_species?.replace(/_/g, " ") ??
                          s.species_guess ??
                          "Unknown"}
                      </span>
                      {s.risk_category && (
                        <span
                          className={`text-xs font-medium ${RISK_COLOR[s.risk_category] ?? "text-slate-400"}`}
                        >
                          {s.risk_category}
                        </span>
                      )}
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[s.verification_status] ?? STATUS_BADGE.unverified}`}
                      >
                        {s.verification_status}
                      </span>
                    </div>
                    <div className="mt-1 flex gap-4 text-xs text-slate-500">
                      <span>
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                      {s.lat != null && s.lon != null && (
                        <span>
                          {s.lat.toFixed(2)}°, {s.lon.toFixed(2)}°
                        </span>
                      )}
                      {s.model_source && <span>via {s.model_source}</span>}
                      {s.model_confidence != null && (
                        <span>
                          {(s.model_confidence * 100).toFixed(0)}% conf
                        </span>
                      )}
                    </div>
                  </Link>

                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      togglePublic(s.id, s.is_public);
                    }}
                    className={`ml-4 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      s.is_public
                        ? "border border-green-800 text-green-400 hover:bg-green-900/30"
                        : "border border-ocean-800 text-slate-400 hover:bg-abyss-800"
                    }`}
                    title={
                      s.is_public
                        ? "Click to make private"
                        : "Click to make public for verification"
                    }
                  >
                    {s.is_public ? "Public ✓" : "Private"}
                  </button>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-4">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-lg border border-ocean-800 px-3 py-1.5 text-sm text-slate-400 disabled:opacity-30"
                >
                  ← Prev
                </button>
                <span className="text-sm text-slate-500">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-ocean-800 px-3 py-1.5 text-sm text-slate-400 disabled:opacity-30"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        ) : null)}
      </div>
    </div>
  );
}
