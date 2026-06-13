"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import Image from "next/image";
import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { MapSubmission } from "@/components/SubmissionMap";
import {
  rarityOf,
  speciesLabel,
  silhouetteFor,
  timeAgo,
  basinOf,
  tierMeta,
} from "@/app/community/_field";
import {
  IconCheck,
  IconMap,
  IconRefresh,
  IconShield,
  IconThumbDown,
  IconThumbUp,
} from "@/components/icons/MarineIcons";

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
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
  submission_count: number;
  verified_count: number;
  reputation_score: number;
  reputation_tier: string;
  is_moderator: boolean;
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
  community_agree: number;
  community_disagree: number;
  moderator_status: string | null;
}

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

const STATUS_STYLE: Record<string, { bg: string; dot: string; text: string }> = {
  unverified: { bg: "bg-slate-500/10", dot: "bg-slate-400", text: "text-slate-300" },
  verified: { bg: "bg-emerald-500/15", dot: "bg-emerald-400", text: "text-emerald-300" },
  community_verified: { bg: "bg-green-500/15", dot: "bg-green-400", text: "text-green-300" },
  under_review: { bg: "bg-blue-500/15", dot: "bg-blue-400", text: "text-blue-300" },
  rejected: { bg: "bg-red-500/15", dot: "bg-red-400", text: "text-red-300" },
  disputed: { bg: "bg-yellow-500/15", dot: "bg-yellow-400", text: "text-yellow-300" },
};

const STATUS_LABELS: Record<string, string> = {
  unverified: "Unverified",
  verified: "Mod Verified",
  community_verified: "Community Verified",
  under_review: "Under Review",
  rejected: "Rejected",
  disputed: "Disputed",
};

const RISK_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

/* ── Page ───────────────────────────────────────────────── */

export default function UserProfilePage() {
  const params = useParams();
  const router = useRouter();
  const { user: authUser } = useAuth();
  const userId = params.id as string;
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [subTotal, setSubTotal] = useState(0);
  const [subPage, setSubPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);
  const PAGE_SIZE = 15;

  // Redirect to /profile if viewing own profile
  useEffect(() => {
    if (authUser && String(authUser.id) === userId) {
      router.replace("/profile");
    }
  }, [authUser, userId, router]);

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

  const tm = tierMeta(profile.reputation_tier);
  const nextTier = TIER_THRESHOLDS.find((t) => t.min > profile.reputation_score);
  const currentTierMin =
    [...TIER_THRESHOLDS].reverse().find((t) => t.min <= profile.reputation_score)
      ?.min ?? 0;
  const progressMax = nextTier ? nextTier.min - currentTierMin : 1;
  const progressVal = nextTier ? profile.reputation_score - currentTierMin : 1;
  const progressPct = Math.min(100, (progressVal / progressMax) * 100);
  const totalSubPages = Math.ceil(subTotal / PAGE_SIZE);

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
    <div className="relative min-h-screen overflow-hidden bg-abyss-950 px-4 pt-20 pb-16">
      {/* Ambient depth gradient */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[420px] opacity-70"
        style={{
          background: `radial-gradient(120% 90% at 18% 0%, ${tm.pennant}22 0%, transparent 55%), radial-gradient(90% 80% at 85% 10%, rgba(8,145,178,0.18) 0%, transparent 60%)`,
        }}
      />

      <div className="relative mx-auto max-w-5xl">
        <Link
          href="/community"
          className="mb-6 inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.2em] text-slate-500 transition-colors hover:text-white"
        >
          ← The Field Station
        </Link>

        {/* ── MASTHEAD ─────────────────────────────────── */}
        <header className="relative">
          <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.3em] text-slate-600">
            <span>Observer Dossier</span>
            <span>No. {String(profile.id).padStart(4, "0")}</span>
          </div>
          <div className="mt-3 h-px w-full bg-gradient-to-r from-white/15 via-white/5 to-transparent" />

          <div className="mt-6 flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
            {/* Identity */}
            <div className="flex items-start gap-5">
              {/* Field portrait with tier ring + pennant */}
              <div className="relative shrink-0">
                <div
                  className="rounded-2xl p-[2px]"
                  style={{
                    background: `linear-gradient(145deg, ${tm.pennant}, transparent 70%)`,
                  }}
                >
                  <div className="rounded-2xl bg-abyss-950 p-1">
                    <UserAvatar
                      avatarUrl={profile.avatar_url}
                      displayName={profile.display_name}
                      size={76}
                    />
                  </div>
                </div>
                {/* Pennant flag */}
                <span
                  className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full ring-2 ring-abyss-950"
                  style={{ background: tm.pennant }}
                  title={tm.label}
                >
                  <span className="text-abyss-950">{tm.icon}</span>
                </span>
              </div>

              <div className="min-w-0">
                <h1 className="font-display text-3xl font-extrabold leading-tight tracking-tight text-white sm:text-4xl">
                  {profile.display_name}
                </h1>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 text-sm font-semibold ${tm.text}`}
                  >
                    {tm.icon}
                    {tm.label}
                  </span>
                  {profile.is_moderator && (
                    <span
                      className="inline-flex items-center gap-1 rounded-full border border-amber-700/60 bg-amber-900/30 px-2.5 py-0.5 text-xs font-semibold text-amber-300"
                      title="Platform Moderator"
                    >
                      <IconShield className="h-3.5 w-3.5" /> Moderator
                    </span>
                  )}
                </div>
                <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.15em] text-slate-500">
                  Logging since{" "}
                  {new Date(profile.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    year: "numeric",
                  })}
                </p>
                {profile.bio && (
                  <p className="mt-3 max-w-md border-l-2 border-white/10 pl-3 text-sm italic leading-relaxed text-slate-300">
                    {profile.bio}
                  </p>
                )}

                {/* Credentials */}
                {profile.credentials.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
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
                        {c.is_verified ? (
                          <IconCheck className="inline h-3.5 w-3.5" />
                        ) : (
                          <IconRefresh className="inline h-3.5 w-3.5" />
                        )}
                        {CREDENTIAL_LABELS[c.credential_type] ??
                          c.credential_type}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Reputation — oversized numeral + rail */}
            <div className="shrink-0 sm:text-right">
              <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-slate-600">
                Reputation
              </div>
              <div
                className="font-display text-6xl font-black leading-none tabular-nums"
                style={{ color: tm.pennant }}
              >
                {profile.reputation_score}
              </div>
              {nextTier ? (
                <div className="mt-3 sm:ml-auto sm:w-48">
                  <div className="mb-1 flex justify-between font-mono text-[10px] uppercase tracking-wide text-slate-500">
                    <span>{tm.label}</span>
                    <span>{nextTier.name}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-abyss-800">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${progressPct}%`,
                        background: tm.pennant,
                      }}
                    />
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-slate-600">
                    {nextTier.min - profile.reputation_score} pts to{" "}
                    {nextTier.name}
                  </div>
                </div>
              ) : (
                <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.2em] text-amber-300">
                  Top rank reached
                </div>
              )}
            </div>
          </div>
        </header>

        {/* ── STAT RIBBON ──────────────────────────────── */}
        <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-6 border-y border-white/[0.07] py-6 sm:grid-cols-4">
          <DossierStat
            value={String(profile.submission_count)}
            label="Interactions logged"
          />
          <DossierStat
            value={String(profile.verified_count)}
            label="Verified"
            accent="text-emerald-400"
          />
          <DossierStat
            value={`${verificationRate}%`}
            label="Verification rate"
          />
          <DossierStat
            value={String(profile.species_breakdown.length)}
            label="Species observed"
            accent="text-ocean-300"
          />
        </div>

        {/* ── SPECIES LOG — collection grid ────────────── */}
        {profile.species_breakdown.length > 0 && (
          <section className="mt-10">
            <div className="mb-4 flex items-baseline justify-between">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.3em] text-slate-500">
                Field Collection
              </h2>
              <span className="font-mono text-[10px] text-slate-600">
                {profile.species_breakdown.length} taxa
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {[...profile.species_breakdown]
                .sort((a, b) => b.count - a.count)
                .map((s) => {
                  const r = rarityOf(s.species);
                  const sil = silhouetteFor(s.species);
                  return (
                    <div
                      key={s.species}
                      className="group relative overflow-hidden rounded-xl border border-white/[0.07] bg-abyss-900/50 p-3 transition-colors hover:border-white/20"
                    >
                      <div
                        className="pointer-events-none absolute -right-4 -top-4 h-16 w-16 rounded-full opacity-20 blur-xl transition-opacity group-hover:opacity-40"
                        style={{ background: r.hex }}
                      />
                      <div className="relative flex items-center gap-3">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center">
                          {sil ? (
                            <Image
                              src={sil}
                              alt={speciesLabel(s.species)}
                              width={44}
                              height={44}
                              className="h-11 w-11 object-contain"
                              style={{ filter: r.tint }}
                            />
                          ) : (
                            <span
                              className="h-3 w-3 rounded-full"
                              style={{ background: r.hex }}
                            />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-semibold text-white">
                            {speciesLabel(s.species)}
                          </div>
                          <div
                            className={`text-[10px] font-medium uppercase tracking-wide ${r.text}`}
                          >
                            {r.tier}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-display text-xl font-bold tabular-nums text-white">
                            {s.count}
                          </div>
                          <div className="font-mono text-[9px] uppercase text-slate-600">
                            {s.count === 1 ? "log" : "logs"}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </section>
        )}

        {/* ── FIELD LOG header + map toggle ────────────── */}
        <div className="mt-12 mb-5 flex items-end justify-between border-b border-white/[0.07] pb-3">
          <div>
            <h2 className="font-mono text-[10px] uppercase tracking-[0.3em] text-slate-500">
              The Logbook
            </h2>
            <p className="mt-1 font-display text-xl font-bold text-white">
              Public interactions
            </p>
          </div>
          <div className="flex gap-1 rounded-lg border border-white/[0.08] bg-abyss-900 p-1">
            <button
              onClick={() => setShowMap(false)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                !showMap
                  ? "bg-ocean-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              ☰ List
            </button>
            <button
              onClick={() => setShowMap(true)}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                showMap
                  ? "bg-ocean-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <IconMap className="h-3.5 w-3.5" /> Map
            </button>
          </div>
        </div>

        {/* Map view */}
        {showMap && (
          <div className="mb-6 h-[420px] overflow-hidden rounded-xl border border-white/[0.08]">
            <SubmissionMap
              data={toMapSubmissions(submissions)}
              onClickSubmission={(id) =>
                window.open(`/submissions/${id}`, "_blank")
              }
            />
          </div>
        )}

        {/* List view — logbook entries */}
        {!showMap && (
          <>
            {submissions.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/[0.1] py-16 text-center">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">
                  Logbook empty — no public entries yet
                </p>
              </div>
            ) : (
              <>
                <div className="divide-y divide-white/[0.06] overflow-hidden rounded-xl border border-white/[0.07] bg-abyss-900/40">
                  {submissions.map((s) => {
                    const sp = s.model_species ?? s.species_guess;
                    const r = rarityOf(sp);
                    const sil = silhouetteFor(sp);
                    const st =
                      STATUS_STYLE[s.verification_status] ??
                      STATUS_STYLE.unverified;
                    return (
                      <Link
                        key={s.id}
                        href={`/submissions/${s.id}`}
                        className="group relative flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-white/[0.025] sm:px-5"
                      >
                        {/* Rarity rule */}
                        <span
                          className="absolute inset-y-0 left-0 w-[3px]"
                          style={{ background: r.hex }}
                        />
                        {/* Silhouette */}
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center">
                          {sil ? (
                            <Image
                              src={sil}
                              alt={speciesLabel(sp)}
                              width={40}
                              height={40}
                              className="h-10 w-10 object-contain opacity-90"
                              style={{ filter: r.tint }}
                            />
                          ) : (
                            <span
                              className="h-2.5 w-2.5 rounded-full"
                              style={{ background: r.hex }}
                            />
                          )}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-white">
                              {speciesLabel(sp)}
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${st.bg} ${st.text}`}
                            >
                              <span
                                className={`h-1.5 w-1.5 rounded-full ${st.dot}`}
                              />
                              {s.moderator_status ? (
                                <IconShield className="inline h-3 w-3" />
                              ) : null}
                              {STATUS_LABELS[s.verification_status] ??
                                s.verification_status}
                            </span>
                            {(s.community_agree > 0 ||
                              s.community_disagree > 0) && (
                              <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
                                <span className="inline-flex items-center gap-0.5 text-green-400">
                                  <IconThumbUp className="h-3 w-3" />
                                  {s.community_agree}
                                </span>
                                <span className="inline-flex items-center gap-0.5 text-red-400">
                                  <IconThumbDown className="h-3 w-3" />
                                  {s.community_disagree}
                                </span>
                              </span>
                            )}
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[11px] text-slate-500">
                            <span>{timeAgo(s.created_at)}</span>
                            {s.lat != null && s.lon != null && (
                              <span className="text-slate-400">
                                {basinOf(s.lat, s.lon)}
                              </span>
                            )}
                            {s.interaction_type && (
                              <span className="capitalize">
                                {s.interaction_type.replace(/_/g, " ")}
                              </span>
                            )}
                            {s.model_confidence != null && (
                              <span>
                                {(s.model_confidence * 100).toFixed(0)}% conf
                              </span>
                            )}
                            {s.risk_category && (
                              <span
                                className={`font-semibold uppercase ${RISK_COLOR[s.risk_category] ?? "text-slate-400"}`}
                              >
                                {s.risk_category} risk
                              </span>
                            )}
                          </div>
                        </div>

                        <span className="text-slate-600 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-300">
                          →
                        </span>
                      </Link>
                    );
                  })}
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

function DossierStat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div>
      <div
        className={`font-display text-4xl font-black leading-none tabular-nums ${accent ?? "text-white"}`}
      >
        {value}
      </div>
      <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">
        {label}
      </div>
    </div>
  );
}
