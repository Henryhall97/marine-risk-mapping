"use client";

import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
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

interface PublicProfile {
  id: number;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
  submission_count: number;
  verified_count: number;
  reputation_score: number;
  reputation_tier: string;
  credentials: Credential[];
  species_breakdown: SpeciesCount[];
}

interface Credential {
  id: number;
  credential_type: string;
  description: string;
  is_verified: boolean;
  verified_at: string | null;
}

interface SpeciesCount {
  species: string;
  count: number;
}

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
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
}

const TIER_STYLE: Record<string, { color: string; bg: string; icon: string }> = {
  newcomer: { color: "text-slate-400", bg: "bg-abyss-800 border-ocean-800", icon: "🌱" },
  observer: { color: "text-ocean-400", bg: "bg-ocean-900/30 border-ocean-800", icon: "👁️" },
  contributor: { color: "text-green-400", bg: "bg-green-900/30 border-green-800", icon: "⭐" },
  expert: { color: "text-purple-400", bg: "bg-purple-900/30 border-purple-800", icon: "🔬" },
  authority: { color: "text-yellow-400", bg: "bg-yellow-900/30 border-yellow-800", icon: "👑" },
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

// Bar chart colours for species breakdown
const BAR_COLORS = [
  "bg-ocean-500",
  "bg-teal-500",
  "bg-purple-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-green-500",
  "bg-cyan-500",
  "bg-orange-500",
  "bg-pink-500",
  "bg-indigo-500",
];

/* ── Page ───────────────────────────────────────────────── */

export default function UserProfilePage() {
  const params = useParams();
  const userId = params.id as string;
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [subTotal, setSubTotal] = useState(0);
  const [subPage, setSubPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);
  const PAGE_SIZE = 15;

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/users/${userId}`);
        if (!res.ok) {
          setError(res.status === 404 ? "User not found" : "Failed to load");
          return;
        }
        setProfile(await res.json());
      } catch {
        setError("Network error");
      } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  const fetchSubs = useCallback(async () => {
    const res = await fetch(
      `${API_BASE}/api/v1/submissions/user/${userId}?limit=${PAGE_SIZE}&offset=${subPage * PAGE_SIZE}`,
    );
    if (res.ok) {
      const data = await res.json();
      setSubmissions(data.submissions);
      setSubTotal(data.total);
    }
  }, [userId, subPage]);

  useEffect(() => {
    fetchSubs();
  }, [fetchSubs]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-abyss-950 pt-14">
        <div className="animate-pulse text-slate-400">Loading…</div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-abyss-950 pt-14">
        <p className="text-slate-400">{error ?? "Not found"}</p>
        <Link href="/community" className="text-sm text-ocean-400 hover:underline">
          ← Back to community
        </Link>
      </div>
    );
  }

  const tier = TIER_STYLE[profile.reputation_tier] ?? TIER_STYLE.newcomer;
  const nextTier = TIER_THRESHOLDS.find((t) => t.min > profile.reputation_score);
  const currentTierMin =
    [...TIER_THRESHOLDS].reverse().find((t) => t.min <= profile.reputation_score)
      ?.min ?? 0;
  const progressMax = nextTier ? nextTier.min - currentTierMin : 1;
  const progressVal = nextTier ? profile.reputation_score - currentTierMin : 1;
  const progressPct = Math.min(100, (progressVal / progressMax) * 100);
  const totalSubPages = Math.ceil(subTotal / PAGE_SIZE);
  const maxSpeciesCount = Math.max(1, ...profile.species_breakdown.map((s) => s.count));

  const toMapSubmissions = (list: SubmissionSummary[]): MapSubmission[] =>
    list
      .filter((s) => s.lat != null && s.lon != null)
      .map((s) => ({
        id: s.id,
        lat: s.lat!,
        lon: s.lon!,
        species: s.model_species ?? s.species_guess ?? "unknown",
        interaction_type: s.interaction_type,
        verification_status: s.verification_status,
        submitter_name: s.submitter_name,
        created_at: s.created_at,
      }));

  const verificationRate =
    profile.submission_count > 0
      ? ((profile.verified_count / profile.submission_count) * 100).toFixed(0)
      : "—";

  return (
    <div className="min-h-screen bg-abyss-950 px-4 pt-20 pb-12">
      <div className="mx-auto max-w-5xl">
        <Link
          href="/community"
          className="mb-4 inline-block text-sm text-slate-400 hover:text-white"
        >
          ← Community sightings
        </Link>

        {/* Profile header */}
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          {/* Identity + credentials */}
          <div className="rounded-2xl border border-ocean-800 bg-abyss-900/80 p-6 sm:col-span-2">
            <div className="flex items-center gap-4">
              {/* Avatar */}
              <UserAvatar
                avatarUrl={profile.avatar_url}
                displayName={profile.display_name}
                size={56}
              />
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold text-white">
                    {profile.display_name}
                  </h1>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${tier.bg} ${tier.color}`}
                  >
                    {profile.reputation_tier}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  Member since{" "}
                  {new Date(profile.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            {/* Credentials */}
            {profile.credentials.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {profile.credentials.map((c) => (
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

          {/* Reputation score card */}
          <div className="rounded-2xl border border-ocean-800 bg-abyss-900/80 p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Reputation
            </h3>
            <div className={`mt-2 text-3xl font-bold ${tier.color}`}>
              {profile.reputation_score}
            </div>
            {nextTier && (
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-xs text-slate-500">
                  <span>{profile.reputation_tier}</span>
                  <span>{nextTier.name}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-abyss-800">
                  <div
                    className="h-full rounded-full bg-ocean-500 transition-all"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Sightings" value={String(profile.submission_count)} />
          <StatCard
            label="Verified"
            value={String(profile.verified_count)}
            accent="text-green-400"
          />
          <StatCard label="Verification Rate" value={`${verificationRate}%`} />
          <StatCard
            label="Species Observed"
            value={String(profile.species_breakdown.length)}
            accent="text-ocean-400"
          />
        </div>

        {/* Species breakdown */}
        {profile.species_breakdown.length > 0 && (
          <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/60 p-5">
            <h3 className="mb-3 text-sm font-semibold text-white">
              Species Breakdown
            </h3>
            <div className="space-y-2">
              {profile.species_breakdown.map((s, i) => (
                <div key={s.species} className="flex items-center gap-3">
                  <span className="w-32 truncate text-xs capitalize text-slate-300">
                    {s.species.replace(/_/g, " ")}
                  </span>
                  <div className="h-4 flex-1 overflow-hidden rounded-full bg-abyss-800">
                    <div
                      className={`h-full rounded-full ${BAR_COLORS[i % BAR_COLORS.length]} transition-all`}
                      style={{
                        width: `${(s.count / maxSpeciesCount) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs text-slate-500">
                    {s.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Submissions header + map toggle */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            Public Sightings
          </h2>
          <div className="flex gap-1 rounded-lg border border-ocean-800 bg-abyss-900 p-1">
            <button
              onClick={() => setShowMap(false)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                !showMap ? "bg-ocean-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              ☰ List
            </button>
            <button
              onClick={() => setShowMap(true)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                showMap ? "bg-ocean-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              🗺 Map
            </button>
          </div>
        </div>

        {/* Map view */}
        {showMap && (
          <div className="mb-6 h-[420px] overflow-hidden rounded-xl border border-ocean-800">
            <SubmissionMap
              data={toMapSubmissions(submissions)}
              onClickSubmission={(id) => window.open(`/submissions/${id}`, "_blank")}
            />
          </div>
        )}

        {/* List view */}
        {!showMap && (
          <>
            {submissions.length === 0 ? (
              <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 py-12 text-center">
                <p className="text-slate-400">
                  No public submissions yet.
                </p>
              </div>
            ) : (
              <>
                <div className="space-y-3">
                  {submissions.map((s) => (
                    <Link
                      key={s.id}
                      href={`/submissions/${s.id}`}
                      className="flex items-center justify-between rounded-xl border border-ocean-800 bg-abyss-900/70 px-5 py-4 transition-colors hover:border-ocean-700"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2.5">
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
                          {s.interaction_type && (
                            <span className="rounded-full border border-ocean-800 px-2 py-0.5 text-xs text-slate-500">
                              {s.interaction_type.replace(/_/g, " ")}
                            </span>
                          )}
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
                          {s.model_confidence != null && (
                            <span>
                              {(s.model_confidence * 100).toFixed(0)}% conf
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="text-sm text-slate-600">→</span>
                    </Link>
                  ))}
                </div>

                {totalSubPages > 1 && (
                  <div className="mt-6 flex items-center justify-center gap-4">
                    <button
                      disabled={subPage === 0}
                      onClick={() => setSubPage((p) => p - 1)}
                      className="rounded-lg border border-ocean-800 px-3 py-1.5 text-sm text-slate-400 disabled:opacity-30"
                    >
                      ← Prev
                    </button>
                    <span className="text-sm text-slate-500">
                      Page {subPage + 1} of {totalSubPages}
                    </span>
                    <button
                      disabled={subPage >= totalSubPages - 1}
                      onClick={() => setSubPage((p) => p + 1)}
                      className="rounded-lg border border-ocean-800 px-3 py-1.5 text-sm text-slate-400 disabled:opacity-30"
                    >
                      Next →
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Helpers ────────────────────────────────────────────── */

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-4 text-center">
      <div className={`text-2xl font-bold ${accent ?? "text-white"}`}>
        {value}
      </div>
      <div className="mt-1 text-xs text-slate-500">{label}</div>
    </div>
  );
}
