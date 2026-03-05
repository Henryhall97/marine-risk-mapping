"use client";

import { useAuth } from "@/contexts/AuthContext";
import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const AudioWaveform = dynamic(() => import("@/components/AudioWaveform"), {
  ssr: false,
});

const LocationPin = dynamic(() => import("@/components/LocationPin"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[280px] items-center justify-center rounded-xl bg-abyss-800/50 text-xs text-slate-500">
      Loading map…
    </div>
  ),
});

const CommentSection = dynamic(() => import("@/components/CommentSection"), {
  ssr: false,
});

/* ── Types ──────────────────────────────────────────────── */

interface SubmissionDetail {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  h3_cell: number | null;
  gps_source: string | null;
  species_guess: string | null;
  description: string | null;
  interaction_type: string | null;
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
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
  photo_filename: string | null;
  audio_filename: string | null;
}

/* ── Constants ─────────────────────────────────────────── */

const STATUS_STYLE: Record<string, { bg: string; dot: string; text: string }> = {
  unverified: { bg: "bg-slate-500/10", dot: "bg-slate-400", text: "text-slate-300" },
  verified: { bg: "bg-green-500/15", dot: "bg-green-400", text: "text-green-300" },
  rejected: { bg: "bg-red-500/15", dot: "bg-red-400", text: "text-red-300" },
  disputed: { bg: "bg-yellow-500/15", dot: "bg-yellow-400", text: "text-yellow-300" },
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

const TIER_STYLE: Record<string, { color: string; icon: string }> = {
  newcomer: { color: "text-slate-400", icon: "🌱" },
  observer: { color: "text-ocean-400", icon: "👁️" },
  contributor: { color: "text-green-400", icon: "⭐" },
  expert: { color: "text-purple-400", icon: "🔬" },
  authority: { color: "text-yellow-400", icon: "👑" },
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

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleVerify = async (
    status: "verified" | "rejected" | "disputed",
  ) => {
    if (!authHeader) return;
    setVerifying(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${id}/verify`,
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
        <p className="text-4xl">🐋</p>
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

  return (
    <div className="min-h-screen bg-abyss-950 pt-20 pb-12">
      <div className="mx-auto max-w-6xl px-4">
        {/* Breadcrumb */}
        <Link
          href="/community"
          className="mb-5 inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-white"
        >
          <span>←</span>
          <span>Community sightings</span>
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
            <span className="mt-0.5 text-lg">
              {d.advisory_level === "critical"
                ? "🚨"
                : d.advisory_level === "high"
                  ? "⚠️"
                  : "ℹ️"}
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
                      {d.model_species.replace(/_/g, " ")}
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

            {/* Classifier breakdown — horizontal comparison */}
            {(d.photo_species || d.audio_species || d.species_guess) && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Classifier Breakdown
                </h3>
                <div className="grid gap-3 sm:grid-cols-3">
                  <ClassifierResult
                    icon="📷"
                    label="Photo"
                    species={d.photo_species}
                    confidence={d.photo_confidence}
                  />
                  <ClassifierResult
                    icon="🎙️"
                    label="Audio"
                    species={d.audio_species}
                    confidence={d.audio_confidence}
                  />
                  <ClassifierResult
                    icon="👤"
                    label="User Guess"
                    species={d.species_guess}
                    confidence={null}
                  />
                </div>
              </div>
            )}

            {/* Location details row */}
            {hasLocation && (
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-ocean-800/30 bg-abyss-900/40 px-5 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-slate-600">📍</span>
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
                    H3 {d.h3_cell.toString(16).toUpperCase()}
                  </div>
                )}
              </div>
            )}

            {/* Verification notes */}
            {d.verification_notes && (
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

            {/* Community verification form */}
            {user && d.is_public && (
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-5">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Community Verification
                </h3>
                <textarea
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  placeholder="Optional notes (e.g., I can confirm this is a humpback based on fluke pattern)"
                  rows={2}
                  className="mb-3 w-full rounded-lg border border-ocean-800/50 bg-abyss-800/60 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleVerify("verified")}
                    disabled={verifying}
                    className="rounded-lg bg-green-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-600 disabled:opacity-50"
                  >
                    ✓ Verify
                  </button>
                  <button
                    onClick={() => handleVerify("disputed")}
                    disabled={verifying}
                    className="rounded-lg bg-yellow-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-yellow-600 disabled:opacity-50"
                  >
                    ⚠ Dispute
                  </button>
                  <button
                    onClick={() => handleVerify("rejected")}
                    disabled={verifying}
                    className="rounded-lg bg-red-700/80 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
                  >
                    ✗ Reject
                  </button>
                </div>
              </div>
            )}

            {/* Comments */}
            {d.is_public && <CommentSection submissionId={d.id} />}
          </div>

          {/* ── Right column: media + map (2/5 width) ─────── */}
          <div className="space-y-5 lg:col-span-2">
            {/* Location mini-map */}
            {hasLocation && (
              <div className="overflow-hidden rounded-xl border border-ocean-800/30">
                <LocationPin
                  lat={d.lat!}
                  lon={d.lon!}
                  label={speciesLabel}
                  height={280}
                  zoom={5}
                />
              </div>
            )}

            {/* Photo (if not already shown in hero, show download) */}
            {d.photo_filename && (
              <div className="overflow-hidden rounded-xl border border-ocean-800/30">
                <div className="flex items-center justify-between bg-abyss-900/60 px-4 py-2.5">
                  <span className="text-xs font-medium text-slate-400">
                    📷 Submitted Photo
                  </span>
                  <a
                    href={`${API_BASE}/api/v1/media/${d.id}/photo`}
                    download
                    className="text-xs text-ocean-400 hover:text-ocean-300"
                  >
                    ⬇ Download
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
              <div className="overflow-hidden rounded-xl border border-ocean-800/30 bg-abyss-900/40 p-4">
                <AudioWaveform
                  src={`${API_BASE}/api/v1/media/${d.id}/audio`}
                  label="🎙️ Submitted Audio"
                  height={96}
                  color="#1e3a5f"
                  progressColor="#22d3ee"
                />
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
  tier: { color: string; icon: string };
  status: { bg: string; dot: string; text: string };
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold capitalize text-white sm:text-3xl">
          {speciesLabel}
        </h1>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${status.bg} ${status.text}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
          {d.verification_status}
        </span>
      </div>
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
  icon: string;
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
            {species.replace(/_/g, " ")}
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
