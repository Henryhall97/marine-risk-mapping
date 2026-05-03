"use client";

import { useAuth } from "@/contexts/AuthContext";
import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import {
  IconAlert,
  IconCamera,
  IconCheck,
  IconDownload,
  IconEye,
  IconInfo,
  IconMicrophone,
  IconMicroscope,
  IconPencil,
  IconPin,
  IconShield,
  IconStar,
  IconThumbDown,
  IconThumbUp,
  IconUser,
  IconUsers,
  IconWarning,
  IconWhale,
} from "@/components/icons/MarineIcons";

const AudioWaveform = dynamic(() => import("@/components/AudioWaveform"), {
  ssr: false,
});

/* ── Inline location map using OSM embed (reliable, no WebGL needed) ── */
function LocationMap({ lat, lon, label, height = 280 }: {
  lat: number; lon: number; label?: string; height?: number;
}) {
  const bbox = `${lon - 5},${lat - 3},${lon + 5},${lat + 3}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;
  return (
    <div className="relative overflow-hidden rounded-xl border border-ocean-800/30">
      <div
        style={{
          height,
          filter: "invert(0.92) hue-rotate(180deg) saturate(1.6) brightness(0.7) contrast(1.2)",
        }}
      >
        <iframe
          title="Sighting location"
          width="100%"
          height={height}
          style={{ border: 0, display: "block" }}
          loading="lazy"
          src={src}
        />
      </div>
      {/* Location overlay badge */}
      <div className="absolute bottom-2 left-2 flex items-center gap-2">
        <div className="rounded-md bg-black/70 px-2.5 py-1.5 backdrop-blur-sm">
          <p className="flex items-center gap-1 text-[11px] font-semibold text-white leading-tight">
            <IconPin className="h-3 w-3" /> {label ?? "Sighting Location"}
          </p>
          <p className="text-[10px] text-slate-400 leading-tight">
            {lat.toFixed(4)}°, {lon.toFixed(4)}°
          </p>
        </div>
      </div>
    </div>
  );
}

const CommentSection = dynamic(() => import("@/components/CommentSection"), {
  ssr: false,
});

const SpeciesPicker = dynamic(() => import("@/components/SpeciesPicker"), {
  ssr: false,
  loading: () => (
    <div className="h-10 animate-pulse rounded-lg bg-abyss-800/60" />
  ),
});

/* ── Types ──────────────────────────────────────────────── */

interface SubmissionDetail {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  h3_cell: string | null;
  gps_source: string | null;
  species_guess: string | null;
  description: string | null;
  interaction_type: string | null;
  group_size: number | null;
  photo_species: string | null;
  photo_confidence: number | null;
  audio_species: string | null;
  audio_confidence: number | null;
  model_species: string | null;
  model_confidence: number | null;
  model_source: string | null;
  risk_score: number | null;
  risk_category: string | null;
  advisory_level: string | null;
  advisory_message: string | null;
  is_public: boolean;
  verification_status: string;
  verification_notes: string | null;
  verified_at: string | null;
  moderator_status: string | null;
  moderator_id: number | null;
  moderator_at: string | null;
  moderator_notes: string | null;
  community_agree: number;
  community_disagree: number;
  verification_score: number | null;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
  submitter_is_moderator: boolean;
  photo_filename: string | null;
  audio_filename: string | null;
  /* Taxonomic rank fields */
  submitted_rank: string | null;
  submitted_scientific_name: string | null;
  /* Biological observation fields */
  behavior: string | null;
  life_stage: string | null;
  calf_present: boolean | null;
  sea_state_beaufort: number | null;
  observation_platform: string | null;
  scientific_name: string | null;
  sighting_datetime: string | null;
}

interface VoteInfo {
  id: number;
  user_id: number;
  vote: string;
  notes: string | null;
  species_suggestion: string | null;
  suggested_rank: string | null;
  created_at: string;
  display_name: string | null;
  reputation_tier: string | null;
  is_moderator: boolean;
  avatar_url: string | null;
}

interface RiskBreakdown {
  h3_cell: number;
  risk_score: number;
  risk_category: string;
  traffic: {
    traffic_score: number | null;
  } | null;
  cetacean_score: number | null;
  proximity_score: number | null;
  strike_score: number | null;
  habitat_score: number | null;
  protection_gap: number | null;
  reference_risk_score: number | null;
}

/* ── Constants ─────────────────────────────────────────── */

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

const RISK_STYLE: Record<string, { bar: string; text: string; bg: string }> = {
  critical: { bar: "bg-red-500", text: "text-red-400", bg: "bg-red-500/10" },
  high: { bar: "bg-orange-500", text: "text-orange-400", bg: "bg-orange-500/10" },
  medium: { bar: "bg-yellow-500", text: "text-yellow-400", bg: "bg-yellow-500/10" },
  low: { bar: "bg-green-500", text: "text-green-400", bg: "bg-green-500/10" },
};

const ADVISORY_STYLE: Record<string, string> = {
  critical: "border-red-700/60 bg-red-950/40 text-red-200",
  high: "border-orange-700/60 bg-orange-950/40 text-orange-200",
  moderate: "border-yellow-700/60 bg-yellow-950/40 text-yellow-200",
  low: "border-green-700/60 bg-green-950/40 text-green-200",
};

const TIER_STYLE: Record<string, { color: string; icon: ReactNode }> = {
  newcomer: { color: "text-slate-400", icon: <span className="inline-block h-3 w-3 rounded-full bg-slate-400" /> },
  observer: { color: "text-ocean-400", icon: <IconEye className="h-3.5 w-3.5" /> },
  contributor: { color: "text-green-400", icon: <IconStar className="h-3.5 w-3.5" /> },
  expert: { color: "text-purple-400", icon: <IconMicroscope className="h-3.5 w-3.5" /> },
  authority: { color: "text-yellow-400", icon: <IconStar className="h-3.5 w-3.5 text-yellow-400" /> },
};

/* ── Species link helper ────────────────────────────────── */

function SpeciesLink({
  species,
  className,
  children,
}: {
  species: string;
  className?: string;
  children?: React.ReactNode;
}) {
  const label = species.replace(/_/g, " ");
  return (
    <Link
      href={`/species?q=${encodeURIComponent(label)}`}
      className={`hover:underline ${className ?? ""}`}
      onClick={(e) => e.stopPropagation()}
    >
      {children ?? label}
    </Link>
  );
}

const BEHAVIOR_LABELS: Record<string, string> = {
  traveling: "Traveling",
  feeding: "Feeding",
  resting: "Resting",
  socializing: "Socializing",
  breaching: "Breaching",
  diving: "Diving",
  milling: "Milling",
  nursing: "Nursing",
  unknown: "Unknown",
};

const LIFE_STAGE_LABELS: Record<string, string> = {
  adult: "Adult",
  juvenile: "Juvenile",
  calf: "Calf",
  mother_calf_pair: "Mother-Calf Pair",
  unknown: "Unknown",
};

const PLATFORM_LABELS: Record<string, string> = {
  shore: "Shore",
  vessel_small: "Small Vessel",
  vessel_large: "Large Vessel",
  aircraft: "Aircraft",
  drone: "Drone",
  kayak_paddle: "Kayak/Paddle",
  research_vessel: "Research Vessel",
  whale_watch: "Whale Watch",
  unknown: "Unknown",
};

/* ── Page ───────────────────────────────────────────────── */

export default function SubmissionDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { user, authHeader } = useAuth();
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyNotes, setVerifyNotes] = useState("");
  const [speciesSuggestion, setSpeciesSuggestion] = useState("");
  const [suggestedRank, setSuggestedRank] = useState("");
  const [showRefinePicker, setShowRefinePicker] = useState(false);
  const [refinePickerOpen, setRefinePickerOpen] = useState(false);
  const [votes, setVotes] = useState<VoteInfo[]>([]);
  const [breakdown, setBreakdown] = useState<RiskBreakdown | null>(null);
  const [voteCast, setVoteCast] = useState(false);
  const [nextUnverifiedId, setNextUnverifiedId] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const headers: Record<string, string> = {};
      if (authHeader) headers["Authorization"] = authHeader;
      const res = await fetch(`${API_BASE}/api/v1/submissions/${id}`, {
        headers,
      });
      if (!res.ok) {
        setError(
          res.status === 404 ? "Submission not found" : "Failed to load",
        );
        return;
      }
      setDetail(await res.json());
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [id, authHeader]);

  const fetchVotes = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${id}/votes`,
      );
      if (res.ok) setVotes(await res.json());
    } catch { /* ignore */ }
  }, [id]);

  const fetchBreakdown = useCallback(async (h3Cell: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/risk/breakdown/${h3Cell}`,
      );
      if (res.ok) setBreakdown(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchDetail();
    fetchVotes();
  }, [fetchDetail, fetchVotes]);

  /* Fetch risk breakdown once we have the h3 cell */
  useEffect(() => {
    if (detail?.h3_cell != null) fetchBreakdown(detail.h3_cell);
  }, [detail?.h3_cell, fetchBreakdown]);

  /* Moderator verify/reject */
  const handleModerate = async (status: "verified" | "rejected") => {
    if (!authHeader) return;
    setVerifying(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${id}/moderate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: authHeader,
          },
          body: JSON.stringify({ status, notes: verifyNotes || null }),
        },
      );
      if (res.ok) {
        setDetail(await res.json());
        setVerifyNotes("");
        fetchVotes();
      }
    } finally {
      setVerifying(false);
    }
  };

  /* Community vote */
  const handleVote = async (vote: "agree" | "disagree" | "refine") => {
    if (!authHeader) return;
    setVerifying(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${id}/vote`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: authHeader,
          },
          body: JSON.stringify({
            vote,
            notes: verifyNotes || null,
            species_suggestion:
              (vote === "disagree" || vote === "refine") && speciesSuggestion
                ? speciesSuggestion
                : null,
            suggested_rank:
              vote === "refine" && suggestedRank ? suggestedRank : null,
          }),
        },
      );
      if (res.ok) {
        setDetail(await res.json());
        setVerifyNotes("");
        setSpeciesSuggestion("");
        setSuggestedRank("");
        setShowRefinePicker(false);
        setVoteCast(true);
        fetchVotes();
        // Try to find a next unverified submission
        try {
          const nextRes = await fetch(
            `${API_BASE}/api/v1/submissions/public?status=unverified&limit=1&offset=0`,
          );
          if (nextRes.ok) {
            const nextData = await nextRes.json();
            const next = nextData.submissions?.find(
              (s: { id: string }) => s.id !== id,
            );
            if (next) setNextUnverifiedId(next.id);
          }
        } catch {
          /* optional — ignore */
        }
      }
    } finally {
      setVerifying(false);
    }
  };

  /* ── Loading / error states ─────────────────────────────── */

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-abyss-950 pt-14">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-ocean-600 border-t-transparent" />
          <span className="text-sm text-slate-500">Loading report…</span>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-abyss-950 pt-14">
        <IconWhale className="h-10 w-10 text-ocean-400" />
        <p className="text-slate-400">{error ?? "Not found"}</p>
        <Link
          href="/community"
          className="text-sm text-ocean-400 hover:underline"
        >
          ← Back to community
        </Link>
      </div>
    );
  }

  const d = detail;
  const pct = (v: number | null) =>
    v != null ? `${(v * 100).toFixed(1)}%` : null;
  const speciesLabel =
    d.model_species?.replace(/_/g, " ") ??
    d.species_guess?.replace(/_/g, " ") ??
    "Unknown Species";
  const tier = TIER_STYLE[d.submitter_tier ?? ""] ?? TIER_STYLE.newcomer;
  const status =
    STATUS_STYLE[d.verification_status] ?? STATUS_STYLE.unverified;
  const risk = RISK_STYLE[d.risk_category ?? ""] ?? null;
  const hasLocation = d.lat != null && d.lon != null;
  const hasMedia = d.photo_filename || d.audio_filename;
  const totalVotes = d.community_agree + d.community_disagree;

  return (
    <div className="min-h-screen bg-abyss-950 pt-20 pb-12">
      <div className="mx-auto max-w-6xl px-4">
        {/* Breadcrumb */}
        <Link
          href="/community"
          className="mb-5 inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-white"
        >
          <span>←</span>
          <span>Community interactions</span>
        </Link>

        {/* ═══════════════════════════════════════════════════
            HERO: Photo / species header
            ═══════════════════════════════════════════════════ */}
        <div className="relative mb-8 overflow-hidden rounded-2xl border border-ocean-800/50">
          {/* Photo hero or gradient fallback */}
          {d.photo_filename ? (
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${API_BASE}/api/v1/media/${d.id}/photo`}
                alt={speciesLabel}
                className="max-h-[420px] w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-abyss-950 via-abyss-950/40 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-6 sm:p-8">
                <HeroContent
                  speciesLabel={speciesLabel}
                  d={d}
                  tier={tier}
                  status={status}
                />
              </div>
            </div>
          ) : (
            <div className="bg-gradient-to-br from-ocean-900/40 via-abyss-900 to-abyss-900 p-6 sm:p-8">
              <HeroContent
                speciesLabel={speciesLabel}
                d={d}
                tier={tier}
                status={status}
              />
            </div>
          )}
        </div>

        {/* ═══════════════════════════════════════════════════
            ADVISORY BANNER (if present, above everything)
            ═══════════════════════════════════════════════════ */}
        {d.advisory_message && (
          <div
            className={`mb-6 flex items-start gap-3 rounded-xl border p-4 ${ADVISORY_STYLE[d.advisory_level ?? "low"] ?? ADVISORY_STYLE.low}`}
          >
            <span className="mt-0.5">
              {d.advisory_level === "critical"
                ? <IconAlert className="h-5 w-5" />
                : d.advisory_level === "high"
                  ? <IconWarning className="h-5 w-5" />
                  : <IconInfo className="h-5 w-5" />}
            </span>
            <div>
              <span className="text-xs font-bold uppercase tracking-wider opacity-70">
                {d.advisory_level} advisory
              </span>
              <p className="mt-0.5 text-sm leading-relaxed">
                {d.advisory_message}
              </p>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════
            TWO-COLUMN BODY: left = details, right = media/map
            ═══════════════════════════════════════════════════ */}
        <div className="grid gap-6 lg:grid-cols-5">
          {/* ── Left column: details (3/5 width) ──────────── */}
          <div className="space-y-6 lg:col-span-3">
            {/* Description (if present) */}
            {d.description && (
              <p className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 px-5 py-4 text-sm leading-relaxed text-slate-300">
                &ldquo;{d.description}&rdquo;
              </p>
            )}

            {/* Group size (multi-whale encounter) */}
            {d.group_size != null && d.group_size > 0 && (
              <div className="flex items-center gap-3 rounded-xl border border-ocean-800/30 bg-abyss-900/40 px-5 py-3">
                <span className="text-ocean-400">
                  <IconUsers className="h-5 w-5" />
                </span>
                <div>
                  <span className="text-sm font-medium text-white">
                    {d.group_size} animal{d.group_size > 1 ? "s" : ""} observed
                  </span>
                  <p className="text-[11px] text-slate-500">Group encounter</p>
                </div>
              </div>
            )}

            {/* Biological observation details */}
            {(d.scientific_name || d.behavior || d.life_stage || d.calf_present || d.observation_platform || d.sea_state_beaufort != null || d.sighting_datetime) && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Observation Details
                </h3>
                <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
                  {d.scientific_name && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Species (scientific):</span>
                      <SpeciesLink
                        species={d.scientific_name}
                        className="text-sm italic text-ocean-300 hover:text-ocean-200"
                      />
                    </div>
                  )}
                  {d.sighting_datetime && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Sighting time:</span>
                      <span className="text-sm text-slate-300">
                        {new Date(d.sighting_datetime).toLocaleString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                  )}
                  {d.behavior && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Behavior:</span>
                      <span className="text-sm text-slate-300">
                        {BEHAVIOR_LABELS[d.behavior] ?? d.behavior.replace(/_/g, " ")}
                      </span>
                    </div>
                  )}
                  {d.life_stage && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Life stage:</span>
                      <span className="text-sm text-slate-300">
                        {LIFE_STAGE_LABELS[d.life_stage] ?? d.life_stage.replace(/_/g, " ")}
                      </span>
                    </div>
                  )}
                  {d.calf_present && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Calf present:</span>
                      <span className="inline-flex items-center gap-1 text-sm text-teal-300">
                        <IconCheck className="h-3.5 w-3.5" /> Yes
                      </span>
                    </div>
                  )}
                  {d.observation_platform && d.observation_platform !== "unknown" && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Platform:</span>
                      <span className="text-sm text-slate-300">
                        {PLATFORM_LABELS[d.observation_platform] ?? d.observation_platform.replace(/_/g, " ")}
                      </span>
                    </div>
                  )}
                  {d.sea_state_beaufort != null && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs text-slate-500">Sea state:</span>
                      <span className="text-sm text-slate-300">
                        Beaufort {d.sea_state_beaufort}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Risk + classification side-by-side */}
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Risk gauge */}
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Risk Assessment
                </h3>
                {risk && d.risk_score != null ? (
                  <div className="space-y-3">
                    {/* Large category label */}
                    <div className="flex items-baseline gap-2">
                      <span
                        className={`text-2xl font-bold capitalize ${risk.text}`}
                      >
                        {d.risk_category}
                      </span>
                      <span className="text-sm tabular-nums text-slate-500">
                        {d.risk_score.toFixed(4)}
                      </span>
                    </div>
                    {/* Score bar */}
                    <div className="h-2 overflow-hidden rounded-full bg-abyss-800">
                      <div
                        className={`h-full rounded-full ${risk.bar} transition-all`}
                        style={{
                          width: `${Math.min(d.risk_score * 100, 100)}%`,
                        }}
                      />
                    </div>
                    {d.interaction_type && (
                      <p className="text-xs text-slate-500">
                        Interaction:{" "}
                        <span className="text-slate-400">
                          {d.interaction_type.replace(/_/g, " ")}
                        </span>
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">
                    No risk data available
                  </p>
                )}
              </div>

              {/* Classification result */}
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Model Classification
                </h3>
                {d.model_species ? (
                  <div className="space-y-3">
                    <p className="text-lg font-bold capitalize text-white">
                      <SpeciesLink
                        species={d.model_species}
                        className="hover:text-ocean-300 transition-colors"
                      />
                    </p>
                    {d.model_confidence != null && (
                      <div className="flex items-center gap-2">
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-800">
                          <div
                            className="h-full rounded-full bg-ocean-500"
                            style={{
                              width: `${(d.model_confidence * 100).toFixed(0)}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm tabular-nums text-slate-400">
                          {(d.model_confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                    )}
                    <p className="text-xs text-slate-500">
                      Source:{" "}
                      <span className="text-slate-400">
                        {d.model_source ?? "—"}
                      </span>
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">
                    No classification available
                  </p>
                )}
              </div>
            </div>

            {/* Risk sub-score breakdown */}
            {breakdown && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Risk Breakdown by Category
                </h3>
                <div className="space-y-2.5">
                  <SubScoreBar
                    label="Shipping Traffic"
                    score={breakdown.traffic?.traffic_score ?? null}
                    weight={25}
                    color="bg-blue-500"
                  />
                  <SubScoreBar
                    label="Cetacean Presence"
                    score={breakdown.cetacean_score}
                    weight={25}
                    color="bg-cyan-500"
                  />
                  <SubScoreBar
                    label="Proximity"
                    score={breakdown.proximity_score}
                    weight={15}
                    color="bg-purple-500"
                  />
                  <SubScoreBar
                    label="Strike History"
                    score={breakdown.strike_score}
                    weight={10}
                    color="bg-red-500"
                  />
                  <SubScoreBar
                    label="Habitat Suitability"
                    score={breakdown.habitat_score}
                    weight={10}
                    color="bg-emerald-500"
                  />
                  <SubScoreBar
                    label="Protection Gap"
                    score={breakdown.protection_gap}
                    weight={10}
                    color="bg-yellow-500"
                  />
                  <SubScoreBar
                    label="Reference Risk"
                    score={breakdown.reference_risk_score}
                    weight={5}
                    color="bg-slate-400"
                  />
                </div>
              </div>
            )}

            {/* Classifier breakdown — horizontal comparison */}
            {(d.photo_species || d.audio_species || d.species_guess) && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Classifier Breakdown
                </h3>
                <div className="grid gap-3 sm:grid-cols-3">
                  <ClassifierResult
                    icon={<IconCamera className="h-3.5 w-3.5" />}
                    label="Photo"
                    species={d.photo_species}
                    confidence={d.photo_confidence}
                  />
                  <ClassifierResult
                    icon={<IconMicrophone className="h-3.5 w-3.5" />}
                    label="Audio"
                    species={d.audio_species}
                    confidence={d.audio_confidence}
                  />
                  <ClassifierResult
                    icon={<IconUser className="h-3.5 w-3.5" />}
                    label="User Guess"
                    species={d.species_guess}
                    confidence={null}
                  />
                </div>
                {/* Rank match info */}
                {d.submitted_rank && (
                  <div className="mt-3 border-t border-ocean-800/20 pt-3">
                    <p className="text-[11px] text-slate-500">
                      User identified at{" "}
                      <span className="font-medium text-slate-400">{d.submitted_rank}</span>
                      {" "}level
                      {d.submitted_scientific_name && (
                        <span className="text-slate-600">
                          {" "}({d.submitted_scientific_name})
                        </span>
                      )}
                      {d.model_species && d.submitted_rank !== "species" && (
                        <span className="text-teal-400/80">
                          {" "} — model classification refined to species level
                        </span>
                      )}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Location details row */}
            {hasLocation && (
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-ocean-800/30 bg-abyss-900/40 px-5 py-3">
                <div className="flex items-center gap-2">
                  <IconPin className="h-3.5 w-3.5 text-slate-600" />
                  <span className="text-sm tabular-nums text-slate-300">
                    {d.lat!.toFixed(4)}°, {d.lon!.toFixed(4)}°
                  </span>
                </div>
                {d.gps_source && (
                  <div className="text-xs text-slate-500">
                    via {d.gps_source}
                  </div>
                )}
                {d.h3_cell != null && (
                  <div className="text-xs font-mono text-slate-600">
                    H3 {BigInt(d.h3_cell).toString(16).toUpperCase()}
                  </div>
                )}
              </div>
            )}

            {/* Moderator status banner (if moderator has ruled) */}
            {d.moderator_status && (
              <div
                className={`flex items-center gap-3 rounded-xl border px-5 py-3 ${
                  d.moderator_status === "verified"
                    ? "border-emerald-700/50 bg-emerald-950/30 text-emerald-200"
                    : "border-red-700/50 bg-red-950/30 text-red-200"
                }`}
              >
                <IconShield className="mt-0.5 h-5 w-5 shrink-0" />
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider opacity-70">
                    Moderator {d.moderator_status}
                  </span>
                  {d.moderator_notes && (
                    <p className="mt-0.5 text-sm">{d.moderator_notes}</p>
                  )}
                  {d.moderator_at && (
                    <p className="mt-1 text-[11px] opacity-50">
                      {new Date(d.moderator_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Verification status summary (always visible) */}
            <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
              <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                Verification Status
              </h3>
              {/* Status badge + summary row */}
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${status.bg} ${status.text}`}
                >
                  <span className={`h-2 w-2 rounded-full ${status.dot}`} />
                  {d.moderator_status ? <><IconShield className="inline h-3 w-3" />{" "}</> : null}
                  {STATUS_LABELS[d.verification_status] ?? d.verification_status}
                </span>
                <span className="text-xs text-slate-500">
                  {totalVotes === 0
                    ? "Be the first to verify this sighting!"
                    : `${totalVotes} vote${totalVotes === 1 ? "" : "s"} cast`}
                </span>
              </div>
              {/* Community Trust gauge */}
              <div className="mb-4 rounded-xl border border-ocean-800/20 bg-gradient-to-br from-abyss-800/60 to-abyss-900/60 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                    Community Trust Score
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      d.verification_score != null
                        ? d.verification_score >= 70
                          ? "bg-emerald-500/15 text-emerald-300"
                          : d.verification_score >= 40
                            ? "bg-yellow-500/15 text-yellow-300"
                            : "bg-red-500/15 text-red-300"
                        : "bg-slate-500/10 text-slate-400"
                    }`}
                  >
                    {d.verification_score != null
                      ? d.verification_score >= 70
                        ? "High Trust"
                        : d.verification_score >= 40
                          ? "Mixed"
                          : "Low Trust"
                      : "No votes"}
                  </span>
                </div>
                {/* Large score display */}
                <div className="mb-3 flex items-baseline gap-2">
                  <span
                    className={`text-3xl font-bold tabular-nums ${
                      d.verification_score != null
                        ? d.verification_score >= 70
                          ? "text-emerald-400"
                          : d.verification_score >= 40
                            ? "text-yellow-400"
                            : "text-red-400"
                        : "text-slate-600"
                    }`}
                  >
                    {d.verification_score != null
                      ? `${d.verification_score.toFixed(0)}%`
                      : "—"}
                  </span>
                  <span className="text-xs text-slate-500">
                    from {totalVotes} reputation-weighted vote{totalVotes !== 1 ? "s" : ""}
                  </span>
                </div>
                {/* Trust bar */}
                <div className="mb-3 h-3 overflow-hidden rounded-full bg-abyss-900/80">
                  {d.verification_score != null ? (
                    <div
                      className={`h-full rounded-full transition-all ${
                        d.verification_score >= 70
                          ? "bg-gradient-to-r from-emerald-600 to-emerald-400"
                          : d.verification_score >= 40
                            ? "bg-gradient-to-r from-yellow-600 to-yellow-400"
                            : "bg-gradient-to-r from-red-600 to-red-400"
                      }`}
                      style={{ width: `${d.verification_score}%` }}
                    />
                  ) : (
                    <div className="h-full w-0" />
                  )}
                </div>
                {/* Vote breakdown row */}
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                    <span className="text-green-400 font-medium">{d.community_agree}</span>
                    <span className="text-slate-500">agree</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                    <span className="text-red-400 font-medium">{d.community_disagree}</span>
                    <span className="text-slate-500">disagree</span>
                  </span>
                </div>
                <p className="mt-2 text-[10px] leading-relaxed text-slate-600">
                  Weighted by voter reputation — experienced contributors have more influence.
                </p>
              </div>
              {/* Species Suggestion Bar Chart */}
              {(() => {
                const suggestions = votes.filter(
                  (v) => v.species_suggestion,
                );
                if (suggestions.length === 0) return null;
                const counts: Record<string, number> = {};
                for (const v of suggestions) {
                  const sp = v.species_suggestion!;
                  counts[sp] = (counts[sp] || 0) + 1;
                }
                const sorted = Object.entries(counts).sort(
                  (a, b) => b[1] - a[1],
                );
                const maxCount = sorted[0]?.[1] ?? 1;
                return (
                  <div className="mb-4 rounded-xl border border-ocean-800/20 bg-gradient-to-br from-abyss-800/60 to-abyss-900/60 p-4">
                    <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                      Community Species Suggestions
                    </p>
                    <div className="space-y-2">
                      {sorted.map(([sp, count]) => (
                        <div key={sp} className="flex items-center gap-3">
                          <SpeciesLink
                            species={sp}
                            className="w-28 shrink-0 truncate text-xs capitalize text-slate-300 hover:text-ocean-300"
                          />
                          <div className="h-5 flex-1 overflow-hidden rounded-full bg-abyss-900/80">
                            <div
                              className="flex h-full items-center rounded-full bg-gradient-to-r from-purple-600 to-purple-400 px-2 text-[10px] font-semibold text-white transition-all"
                              style={{
                                width: `${Math.max(
                                  (count / maxCount) * 100,
                                  18,
                                )}%`,
                              }}
                            >
                              {count}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className="mt-2 text-[10px] text-slate-600">
                      Based on {suggestions.length} suggestion{suggestions.length !== 1 ? "s" : ""} from community voters
                    </p>
                  </div>
                );
              })()}
              {/* Individual votes */}
              {votes.length > 0 && (
                <div className="space-y-2 border-t border-ocean-800/30 pt-3">
                  <p className="text-[11px] font-medium text-slate-500">
                    Individual Votes
                  </p>
                  {votes.map((v) => (
                    <div
                      key={v.id}
                      className="flex items-start gap-2 text-xs"
                    >
                      <Link
                        href={`/users/${v.user_id}`}
                        className="shrink-0 hover:opacity-80"
                      >
                        <UserAvatar
                          avatarUrl={v.avatar_url}
                          displayName={v.display_name}
                          size={20}
                        />
                      </Link>
                      <div className="min-w-0 flex-1">
                        <Link
                          href={`/users/${v.user_id}`}
                          className="font-medium text-slate-300 hover:text-white hover:underline"
                        >
                          {v.display_name ?? "Anonymous"}
                        </Link>
                        {v.is_moderator && (
                          <span className="ml-1 inline-flex items-center gap-0.5 text-[10px] text-emerald-400">
                            <IconShield className="h-2.5 w-2.5" /> mod
                          </span>
                        )}
                        <span
                          className={`ml-1.5 inline-flex items-center gap-0.5 ${
                            v.vote === "agree"
                              ? "text-green-400"
                              : v.vote === "refine"
                                ? "text-purple-400"
                                : "text-red-400"
                          }`}
                        >
                          {v.vote === "agree"
                            ? <><IconThumbUp className="h-3 w-3" /> agrees</>
                            : v.vote === "refine"
                              ? <><IconPencil className="h-3 w-3" /> refines</>
                              : <><IconThumbDown className="h-3 w-3" /> disagrees</>}
                        </span>
                        {v.species_suggestion && (
                          <span className="ml-1 text-slate-500">
                            (suggests:{" "}
                            <SpeciesLink
                              species={v.species_suggestion}
                              className="text-ocean-400 hover:text-ocean-300"
                            />
                            {v.suggested_rank && (
                              <span className="ml-0.5 text-[10px] text-slate-600">
                                [{v.suggested_rank}]
                              </span>
                            )}
                            )
                          </span>
                        )}
                        {v.notes && (
                          <p className="mt-0.5 text-slate-500">
                            {v.notes}
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 text-[10px] text-slate-600">
                        {new Date(v.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Verification notes (legacy) */}
            {d.verification_notes && !d.moderator_notes && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Verification Notes
                </h3>
                <p className="text-sm leading-relaxed text-slate-300">
                  {d.verification_notes}
                </p>
                {d.verified_at && (
                  <p className="mt-2 text-xs text-slate-600">
                    Verified{" "}
                    {new Date(d.verified_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            )}

            {/* Community verification / voting form */}
            {user && d.is_public && user.id !== d.submitter_id && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-3 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  {user.is_moderator
                    ? <><IconShield className="h-3.5 w-3.5" /> Moderator Verification</>
                    : "Community Vote"}
                </h3>
                <textarea
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  placeholder={
                    user.is_moderator
                      ? "Moderator notes (visible to all)"
                      : "Optional notes (e.g., I can confirm this is a humpback based on fluke pattern)"
                  }
                  rows={2}
                  className="mb-3 w-full rounded-lg border border-ocean-800/50 bg-abyss-800/60 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
                {/* Species suggestion via SpeciesPicker (for disagree/refine votes) */}
                {!user.is_moderator && (
                  <div className="mb-3">
                    <button
                      type="button"
                      onClick={() => setShowRefinePicker((p) => !p)}
                      className="mb-2 text-[11px] text-ocean-400 hover:text-ocean-300"
                    >
                      {showRefinePicker ? "Hide" : "Suggest"} a different species identification
                    </button>
                    {showRefinePicker && (
                      <SpeciesPicker
                        value={speciesSuggestion}
                        onChange={(sel) => {
                          setSpeciesSuggestion(sel?.value ?? "");
                          setSuggestedRank(sel?.rank ?? "");
                        }}
                        open={refinePickerOpen}
                        onOpenChange={setRefinePickerOpen}
                        onLightbox={() => {}}
                      />
                    )}
                  </div>
                )}
                {user.is_moderator ? (
                  /* Moderator: authoritative verify/reject */
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleModerate("verified")}
                      disabled={verifying}
                      className="inline-flex items-center gap-1 rounded-lg bg-emerald-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 disabled:opacity-50"
                    >
                      <IconShield className="h-3.5 w-3.5" /> Verify (Mod)
                    </button>
                    <button
                      onClick={() => handleModerate("rejected")}
                      disabled={verifying}
                      className="inline-flex items-center gap-1 rounded-lg bg-red-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
                    >
                      <IconShield className="h-3.5 w-3.5" /> Reject (Mod)
                    </button>
                  </div>
                ) : (
                  /* Community: agree / disagree / refine vote */
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => handleVote("agree")}
                        disabled={verifying}
                        className="inline-flex items-center gap-1 rounded-lg bg-green-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-600 disabled:opacity-50"
                      >
                        <IconThumbUp className="h-3.5 w-3.5" /> Agree
                      </button>
                      <button
                        onClick={() => handleVote("refine")}
                        disabled={verifying || !speciesSuggestion}
                        title={
                          speciesSuggestion
                            ? "Sighting is valid but suggest a different species ID"
                            : "Select a species suggestion first"
                        }
                        className="inline-flex items-center gap-1 rounded-lg bg-purple-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-600 disabled:opacity-50"
                      >
                        <IconPencil className="h-3.5 w-3.5" /> Refine ID
                      </button>
                      <button
                        onClick={() => handleVote("disagree")}
                        disabled={verifying}
                        className="inline-flex items-center gap-1 rounded-lg bg-red-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
                      >
                        <IconThumbDown className="h-3.5 w-3.5" /> Disagree
                      </button>
                      <span className="ml-1 rounded-full bg-green-500/10 px-2 py-0.5 text-[11px] font-medium text-green-400">
                        +2 rep per vote
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Vote recorded — next unverified CTA */}
            {voteCast && (
              <div className="flex items-center gap-3 rounded-xl border border-green-500/30 bg-green-500/5 p-4">
                <IconCheck className="h-5 w-5 shrink-0 text-green-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-green-300">
                    Vote recorded — thank you!
                  </p>
                  <p className="text-xs text-slate-400">
                    Your vote helps build community trust in this sighting.
                  </p>
                </div>
                {nextUnverifiedId && (
                  <Link
                    href={`/submissions/${nextUnverifiedId}`}
                    className="shrink-0 rounded-lg bg-ocean-500/20 px-3 py-1.5 text-xs font-medium text-ocean-300 transition-colors hover:bg-ocean-500/30"
                  >
                    Next unverified →
                  </Link>
                )}
              </div>
            )}

            {/* Sign-in prompt for anonymous visitors */}
            {!user && d.is_public && (
              <Link
                href="/auth"
                className="flex items-center gap-3 rounded-xl border border-ocean-700/30 bg-ocean-900/30 p-4 transition-all hover:border-ocean-600/50 hover:bg-ocean-900/50"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ocean-500/15">
                  <IconEye className="h-4 w-4 text-ocean-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-white">
                    Sign in to verify this sighting
                  </p>
                  <p className="text-xs text-slate-400">
                    Help the community and earn{" "}
                    <span className="font-medium text-green-400">+2 reputation</span>{" "}
                    per vote
                  </p>
                </div>
                <span className="shrink-0 text-xs font-medium text-ocean-400">
                  Sign in →
                </span>
              </Link>
            )}

            {/* Comments */}
            {d.is_public && <CommentSection submissionId={d.id} />}
          </div>

          {/* ── Right column: media + map (2/5 width) ─────── */}
          <div className="space-y-5 lg:col-span-2">
            {/* Location mini-map */}
            {hasLocation && (
              <LocationMap
                lat={d.lat!}
                lon={d.lon!}
                label={speciesLabel}
                height={280}
              />
            )}

            {/* Photo (if not already shown in hero, show download) */}
            {d.photo_filename && (
              <div className="overflow-hidden rounded-xl border border-ocean-800/30">
                <div className="flex items-center justify-between bg-abyss-900/60 px-4 py-2.5">
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-400">
                    <IconCamera className="h-3.5 w-3.5" /> Submitted Photo
                  </span>
                  <a
                    href={`${API_BASE}/api/v1/media/${d.id}/photo`}
                    download
                    className="inline-flex items-center gap-1 text-xs text-ocean-400 hover:text-ocean-300"
                  >
                    <IconDownload className="h-3.5 w-3.5" /> Download
                  </a>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${API_BASE}/api/v1/media/${d.id}/photo`}
                  alt="Submitted whale photo"
                  className="w-full object-contain"
                />
              </div>
            )}

            {/* Audio */}
            {d.audio_filename && (
              <div className="overflow-hidden rounded-xl border border-ocean-800/30">
                <div className="flex items-center gap-1.5 bg-abyss-900/60 px-4 py-2.5">
                  <IconMicrophone className="h-3.5 w-3.5 text-slate-400" />
                  <span className="text-xs font-medium text-slate-400">Submitted Audio</span>
                </div>
                <div className="bg-abyss-900/40 p-4">
                  <AudioWaveform
                    src={`${API_BASE}/api/v1/media/${d.id}/audio`}
                    label="Submitted Audio"
                    height={96}
                    color="#1e3a5f"
                    progressColor="#22d3ee"
                  />
                </div>
              </div>
            )}

            {/* If no media and no location — show a placeholder */}
            {!hasMedia && !hasLocation && (
              <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-ocean-800/40 text-sm text-slate-600">
                No media or location data
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Hero content (reused in photo overlay + gradient fallback) */

function HeroContent({
  speciesLabel,
  d,
  tier,
  status,
}: {
  speciesLabel: string;
  d: SubmissionDetail;
  tier: { color: string; icon: ReactNode };
  status: { bg: string; dot: string; text: string };
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold capitalize text-white sm:text-3xl">
          <SpeciesLink
            species={d.model_species ?? d.species_guess ?? "unknown"}
            className="hover:text-ocean-300 transition-colors"
          />
        </h1>
        {d.scientific_name && (
          <span className="text-base italic text-slate-400">
            <SpeciesLink
              species={d.scientific_name}
              className="hover:text-ocean-300 transition-colors"
            />
          </span>
        )}
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${status.bg} ${status.text}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
          {d.moderator_status ? <><IconShield className="inline h-3 w-3" />{" "}</> : null}
          {STATUS_LABELS[d.verification_status] ?? d.verification_status}
        </span>
        {(d.community_agree > 0 || d.community_disagree > 0) && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-abyss-800/50 px-2.5 py-1 text-xs text-slate-400">
            <IconThumbUp className="h-3 w-3" />{d.community_agree} <IconThumbDown className="h-3 w-3" />{d.community_disagree}
          </span>
        )}
      </div>
      {/* Observer vs model mismatch */}
      {d.species_guess && d.model_species && d.species_guess !== d.model_species && (
        <p className="text-xs text-slate-500">
          Observer reported{" "}
          <SpeciesLink species={d.species_guess} className="text-ocean-400 hover:text-ocean-300" />
          {" · Model classified as "}
          <SpeciesLink species={d.model_species} className="text-ocean-400 hover:text-ocean-300" />
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
        <span className="flex items-center gap-1">
          {d.submitter_id ? (
            <Link
              href={`/users/${d.submitter_id}`}
              className="inline-flex items-center gap-1.5 text-slate-300 hover:underline"
            >
              <UserAvatar
                avatarUrl={d.submitter_avatar_url}
                displayName={d.submitter_name}
                size={24}
              />
              <span className={tier.color}>{tier.icon}</span>
              {d.submitter_is_moderator && (
                <span className="text-amber-400" title="Moderator"><IconShield className="h-3.5 w-3.5" /></span>
              )}
              {d.submitter_name ?? "Anonymous"}
            </Link>
          ) : (
            <>
              <UserAvatar
                avatarUrl={d.submitter_avatar_url}
                displayName={d.submitter_name}
                size={24}
              />
              <span className={tier.color}>{tier.icon}</span>
              {d.submitter_is_moderator && (
                <span className="text-amber-400" title="Moderator"><IconShield className="h-3.5 w-3.5" /></span>
              )}
              {d.submitter_name ?? "Anonymous"}
            </>
          )}
        </span>
        <span className="text-slate-600">·</span>
        <span>
          {new Date(d.created_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </span>
        {d.lat != null && (
          <>
            <span className="text-slate-600">·</span>
            <span className="tabular-nums">
              {d.lat.toFixed(2)}°, {d.lon!.toFixed(2)}°
            </span>
          </>
        )}
      </div>
    </div>
  );
}

/* ── Classifier comparison card ───────────────────────────── */

function ClassifierResult({
  icon,
  label,
  species,
  confidence,
}: {
  icon: ReactNode;
  label: string;
  species: string | null;
  confidence: number | null;
}) {
  return (
    <div className="rounded-lg bg-abyss-800/40 px-3.5 py-3">
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className="text-sm">{icon}</span>
        <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
          {label}
        </span>
      </div>
      {species ? (
        <>
          <p className="text-sm font-medium capitalize text-slate-200">
            <SpeciesLink
              species={species}
              className="hover:text-ocean-300 transition-colors"
            />
          </p>
          {confidence != null && (
            <div className="mt-1.5 flex items-center gap-2">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-abyss-700">
                <div
                  className="h-full rounded-full bg-ocean-500/70"
                  style={{ width: `${(confidence * 100).toFixed(0)}%` }}
                />
              </div>
              <span className="text-[11px] tabular-nums text-slate-500">
                {(confidence * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-slate-600">Not submitted</p>
      )}
    </div>
  );
}

/* ── Risk sub-score bar ───────────────────────────────────── */

function SubScoreBar({
  label,
  score,
  weight,
  color,
}: {
  label: string;
  score: number | null;
  weight: number;
  color: string;
}) {
  const pct = score != null ? score * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-[120px] shrink-0 text-xs text-slate-400">
        {label}
      </span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-800">
        {score != null && (
          <div
            className={`h-full rounded-full ${color}`}
            style={{ width: `${pct.toFixed(0)}%`, opacity: 0.7 }}
          />
        )}
      </div>
      <span className="w-10 text-right text-[11px] tabular-nums text-slate-400">
        {score != null ? `${pct.toFixed(0)}%` : "—"}
      </span>
      <span className="w-8 text-right text-[10px] tabular-nums text-slate-600">
        {weight}%
      </span>
    </div>
  );
}
