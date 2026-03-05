"use client";

import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import dynamic from "next/dynamic";
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
  submitter_avatar_url: string | null;
  has_photo: boolean;
  has_audio: boolean;
}

type StatusFilter = "all" | "unverified" | "verified" | "disputed" | "rejected";
type ViewMode = "list" | "map";

const STATUS_STYLE: Record<string, { bg: string; dot: string; text: string }> = {
  unverified: { bg: "bg-slate-500/10", dot: "bg-slate-400", text: "text-slate-400" },
  verified: { bg: "bg-green-500/10", dot: "bg-green-400", text: "text-green-400" },
  rejected: { bg: "bg-red-500/10", dot: "bg-red-400", text: "text-red-400" },
  disputed: { bg: "bg-yellow-500/10", dot: "bg-yellow-400", text: "text-yellow-400" },
};

const RISK_ACCENT: Record<string, string> = {
  critical: "from-red-600/30",
  high: "from-orange-600/25",
  medium: "from-yellow-600/20",
  low: "from-green-600/15",
};

const RISK_TEXT: Record<string, string> = {
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

const SPECIES_EMOJI: Record<string, string> = {
  humpback_whale: "🐋",
  right_whale: "🐋",
  fin_whale: "🐳",
  blue_whale: "🐳",
  minke_whale: "🐳",
  sei_whale: "🐳",
  sperm_whale: "🐋",
  killer_whale: "🐬",
};

/* ── Page ───────────────────────────────────────────────── */

export default function CommunityPage() {
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [fetching, setFetching] = useState(false);
  const [view, setView] = useState<ViewMode>("list");
  const [mapData, setMapData] = useState<SubmissionSummary[]>([]);
  const PAGE_SIZE = 20;

  const fetchPublic = useCallback(async () => {
    setFetching(true);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(page * PAGE_SIZE),
      });
      if (filter !== "all") params.set("status", filter);
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/public?${params}`,
      );
      if (res.ok) {
        const data = await res.json();
        setSubmissions(data.submissions);
        setTotal(data.total);
      }
    } finally {
      setFetching(false);
    }
  }, [page, filter]);

  const fetchMapData = useCallback(async () => {
    const params = new URLSearchParams({ limit: "200", offset: "0" });
    if (filter !== "all") params.set("status", filter);
    const res = await fetch(
      `${API_BASE}/api/v1/submissions/public?${params}`,
    );
    if (res.ok) {
      const data = await res.json();
      setMapData(data.submissions);
      setTotal(data.total);
    }
  }, [filter]);

  useEffect(() => {
    if (view === "list") fetchPublic();
    else fetchMapData();
  }, [fetchPublic, fetchMapData, view]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

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

  /* ── Derived stats ──────────────────────────────────────── */
  const source = view === "map" ? mapData : submissions;
  const verifiedCount = source.filter(
    (s) => s.verification_status === "verified",
  ).length;
  const withPhotoCount = source.filter((s) => s.has_photo).length;
  const speciesSet = new Set(
    source.map((s) => s.model_species ?? s.species_guess).filter(Boolean),
  );

  return (
    <div className="min-h-screen bg-abyss-950 pt-20 pb-12">
      <div className="mx-auto max-w-7xl px-4">
        {/* ── Hero header ─────────────────────────────────── */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Community Sightings
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-400">
            Browse public whale sighting reports from observers across US
            coastal waters. Help verify species identifications and contribute
            to marine conservation science.
          </p>

          {/* Stats pills */}
          <div className="mt-4 flex flex-wrap gap-3">
            <StatPill label="Total reports" value={total} />
            <StatPill
              label="Verified"
              value={verifiedCount}
              accent="text-green-400"
            />
            <StatPill
              label="Species"
              value={speciesSet.size}
              accent="text-ocean-400"
            />
            <StatPill
              label="With photos"
              value={withPhotoCount}
              accent="text-purple-400"
            />
          </div>
        </div>

        {/* ── Toolbar ─────────────────────────────────────── */}
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Filters */}
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                "all",
                "unverified",
                "verified",
                "disputed",
                "rejected",
              ] as StatusFilter[]
            ).map((f) => {
              const active = filter === f;
              const st = STATUS_STYLE[f] ?? STATUS_STYLE.unverified;
              return (
                <button
                  key={f}
                  onClick={() => {
                    setFilter(f);
                    setPage(0);
                  }}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                    active
                      ? "bg-ocean-600/90 text-white shadow-sm shadow-ocean-600/30"
                      : "border border-ocean-800/60 text-slate-400 hover:border-ocean-700 hover:text-slate-200"
                  }`}
                >
                  {f !== "all" && (
                    <span
                      className={`inline-block h-1.5 w-1.5 rounded-full ${active ? "bg-white" : st.dot}`}
                    />
                  )}
                  {f === "all"
                    ? "All"
                    : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              );
            })}
          </div>

          {/* View toggle */}
          <div className="flex items-center gap-1 rounded-lg border border-ocean-800/60 bg-abyss-900/80 p-0.5">
            {(["list", "map"] as ViewMode[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-md px-3.5 py-1.5 text-xs font-medium transition-all ${
                  view === v
                    ? "bg-ocean-600/90 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {v === "list" ? "☰ List" : "🗺 Map"}
              </button>
            ))}
          </div>
        </div>

        {/* ── Map view ────────────────────────────────────── */}
        {view === "map" && (
          <div className="mb-8 h-[600px] overflow-hidden rounded-2xl border border-ocean-800/60 shadow-lg shadow-black/20">
            <SubmissionMap
              data={toMapSubmissions(mapData)}
              onClickSubmission={(id) =>
                window.open(`/submissions/${id}`, "_blank")
              }
            />
          </div>
        )}

        {/* ── Card grid ───────────────────────────────────── */}
        {view === "list" && (
          <>
            {fetching && submissions.length === 0 ? (
              <div className="py-24 text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-ocean-600 border-t-transparent" />
                <p className="mt-4 text-sm text-slate-500">
                  Loading sightings…
                </p>
              </div>
            ) : submissions.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-ocean-800/60 py-24 text-center">
                <p className="text-4xl">🐋</p>
                <p className="mt-3 text-slate-400">
                  No sightings
                  {filter !== "all" ? ` with status "${filter}"` : ""} yet.
                </p>
                <Link
                  href="/report"
                  className="mt-4 inline-block rounded-lg bg-ocean-700 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-600"
                >
                  Submit the first sighting
                </Link>
              </div>
            ) : (
              <>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {submissions.map((s) => (
                    <SightingCard key={s.id} s={s} />
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-8 flex items-center justify-center gap-2">
                    <button
                      disabled={page === 0}
                      onClick={() => setPage((p) => p - 1)}
                      className="rounded-lg border border-ocean-800/60 px-3 py-1.5 text-sm text-slate-400 transition-colors hover:border-ocean-700 hover:text-white disabled:pointer-events-none disabled:opacity-30"
                    >
                      ←
                    </button>
                    {Array.from(
                      { length: Math.min(totalPages, 7) },
                      (_, i) => {
                        let p: number;
                        if (totalPages <= 7) {
                          p = i;
                        } else if (page < 4) {
                          p = i;
                        } else if (page > totalPages - 5) {
                          p = totalPages - 7 + i;
                        } else {
                          p = page - 3 + i;
                        }
                        return (
                          <button
                            key={p}
                            onClick={() => setPage(p)}
                            className={`h-8 w-8 rounded-lg text-sm font-medium transition-all ${
                              page === p
                                ? "bg-ocean-600 text-white"
                                : "text-slate-500 hover:bg-abyss-800 hover:text-slate-300"
                            }`}
                          >
                            {p + 1}
                          </button>
                        );
                      },
                    )}
                    <button
                      disabled={page >= totalPages - 1}
                      onClick={() => setPage((p) => p + 1)}
                      className="rounded-lg border border-ocean-800/60 px-3 py-1.5 text-sm text-slate-400 transition-colors hover:border-ocean-700 hover:text-white disabled:pointer-events-none disabled:opacity-30"
                    >
                      →
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

/* ── Sighting Card ────────────────────────────────────────── */

function SightingCard({ s }: { s: SubmissionSummary }) {
  const species = s.model_species ?? s.species_guess ?? "unknown";
  const speciesLabel = species.replace(/_/g, " ");
  const emoji = SPECIES_EMOJI[species] ?? "🐋";
  const tier = TIER_STYLE[s.submitter_tier ?? ""] ?? TIER_STYLE.newcomer;
  const status =
    STATUS_STYLE[s.verification_status] ?? STATUS_STYLE.unverified;
  const riskAccent =
    RISK_ACCENT[s.risk_category ?? ""] ?? "from-transparent";
  const riskText = RISK_TEXT[s.risk_category ?? ""] ?? "text-slate-500";
  const conf =
    s.model_confidence != null
      ? `${(s.model_confidence * 100).toFixed(0)}%`
      : null;

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 3_600_000)
      return `${Math.max(1, Math.floor(diff / 60_000))}m`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
    if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)}d`;
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  };

  return (
    <Link
      href={`/submissions/${s.id}`}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-ocean-800/50 bg-gradient-to-b ${riskAccent} to-abyss-900/90 transition-all hover:border-ocean-600/70 hover:shadow-lg hover:shadow-ocean-900/30`}
    >
      {/* Photo thumbnail or species icon */}
      {s.has_photo ? (
        <div className="relative h-40 overflow-hidden bg-abyss-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${API_BASE}/api/v1/media/${s.id}/photo`}
            alt={speciesLabel}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/80 via-transparent to-transparent" />
          {/* Floating badges on photo */}
          <div className="absolute bottom-2 left-3 right-3 flex items-end justify-between">
            <span className="text-lg font-semibold leading-tight text-white drop-shadow">
              {speciesLabel}
            </span>
            {s.has_audio && (
              <span className="rounded-full bg-black/50 px-2 py-0.5 text-xs text-slate-300 backdrop-blur-sm">
                🎙️
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="flex h-28 items-center justify-center bg-gradient-to-br from-abyss-800/80 to-abyss-900/80">
          <span className="text-4xl opacity-60">{emoji}</span>
        </div>
      )}

      {/* Card body */}
      <div className="flex flex-1 flex-col gap-3 p-4">
        {/* Species + audio badge (only if no photo — photo has overlay) */}
        {!s.has_photo && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-white">
              {speciesLabel}
            </span>
            {s.has_audio && (
              <span className="text-xs text-slate-500">🎙️</span>
            )}
          </div>
        )}

        {/* Metadata chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${status.bg} ${status.text}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${status.dot}`}
            />
            {s.verification_status}
          </span>
          {s.risk_category && (
            <span
              className={`rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] font-medium ${riskText}`}
            >
              {s.risk_category} risk
            </span>
          )}
          {s.interaction_type && (
            <span className="rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] text-slate-500">
              {s.interaction_type.replace(/_/g, " ")}
            </span>
          )}
        </div>

        {/* Confidence bar */}
        {conf && (
          <div className="flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-abyss-800">
              <div
                className="h-full rounded-full bg-ocean-500/70"
                style={{ width: conf }}
              />
            </div>
            <span className="text-[11px] tabular-nums text-slate-500">
              {conf}
            </span>
          </div>
        )}

        {/* Footer: submitter + time + location */}
        <div className="mt-auto flex items-center justify-between border-t border-ocean-900/40 pt-2.5 text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5 truncate">
            <UserAvatar
              avatarUrl={s.submitter_avatar_url}
              displayName={s.submitter_name}
              size={18}
            />
            <span className={tier.color}>{tier.icon}</span>
            <span className="truncate">
              {s.submitter_name ?? "Anonymous"}
            </span>
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {s.lat != null && (
              <span className="tabular-nums">
                {s.lat.toFixed(1)}°,{s.lon!.toFixed(1)}°
              </span>
            )}
            <span className="tabular-nums">{timeAgo(s.created_at)}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

/* ── Stat Pill ────────────────────────────────────────────── */

function StatPill({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-ocean-800/40 bg-abyss-900/60 px-3 py-1">
      <span
        className={`text-sm font-semibold tabular-nums ${accent ?? "text-white"}`}
      >
        {value.toLocaleString()}
      </span>
      <span className="text-[11px] text-slate-500">{label}</span>
    </div>
  );
}
