"use client";

/**
 * Shared "Field Station" building blocks for the community prototype.
 *
 * Types, conservation/rarity helpers, and the collectible "field card" +
 * compare-tray components are defined once here and imported by the hub,
 * the dedicated interactions page, and the dedicated events page so nothing
 * is duplicated across routes.
 *
 * Underscore-prefixed module → never treated as a route by the App Router.
 */

import Image from "next/image";
import Link from "next/link";
import { useCallback, useState } from "react";
import { API_BASE } from "@/lib/config";
import {
  IconWhale,
  IconDolphin,
  IconCamera,
  IconStar,
  IconPin,
  IconMicrophone,
  IconUser,
  IconEye,
  IconMicroscope,
} from "@/components/icons/MarineIcons";

/* ── Types ─────────────────────────────────────────────────── */

export interface SubmissionSummary {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  species_guess: string | null;
  model_species: string | null;
  model_confidence: number | null;
  interaction_type: string | null;
  risk_category: string | null;
  verification_status: string;
  community_agree: number;
  community_disagree: number;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
  has_photo: boolean;
  has_audio: boolean;
  group_size: number | null;
  behavior: string | null;
  calf_present: boolean | null;
}

export interface GlobeSighting {
  id: string;
  lat: number;
  lon: number;
  species: string;
  submitter_name: string | null;
  created_at: string;
  group_size?: number | null;
  behavior?: string | null;
  calf_present?: boolean | null;
  verification_status?: string;
  risk_category?: string | null;
  has_photo?: boolean;
  has_audio?: boolean;
}

export interface CommunityStats {
  total_sightings: number;
  total_contributors: number;
  species_documented: number;
  verified_count: number;
  needs_review_count: number;
  photo_count: number;
  sightings_this_week: number;
  total_events: number;
}

export interface RecentActivityItem {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  species: string | null;
  interaction_type: string | null;
  verification_status: string;
  has_photo: boolean;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
}

export interface TopContributor {
  user_id: number;
  display_name: string | null;
  reputation_score: number;
  reputation_tier: string;
  avatar_url: string | null;
  submission_count: number;
  species_count: number;
}

export interface WhaleOfTheWeek {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  species: string | null;
  model_confidence: number | null;
  verification_status: string;
  community_agree: number;
  community_disagree: number;
  comment_count: number;
  vote_count: number;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
}

export interface CommunityStatsResponse {
  stats: CommunityStats;
  recent_activity: RecentActivityItem[];
  top_contributors: TopContributor[];
  whale_of_the_week: WhaleOfTheWeek | null;
}

/* ── Species + conservation helpers ───────────────────────── */

const SPECIES_LABELS: Record<string, string> = {
  humpback_whale: "Humpback Whale",
  humpback: "Humpback Whale",
  right_whale: "Right Whale",
  southern_right_whale: "Southern Right Whale",
  fin_whale: "Fin Whale",
  blue_whale: "Blue Whale",
  minke_whale: "Minke Whale",
  sei_whale: "Sei Whale",
  sperm_whale: "Sperm Whale",
  gray_whale: "Gray Whale",
  bowhead: "Bowhead Whale",
  killer_whale: "Orca",
  orca: "Orca",
  pilot_whale: "Pilot Whale",
  beaked_whale: "Beaked Whale",
  bottlenose_dolphin: "Bottlenose Dolphin",
  common_dolphin: "Common Dolphin",
  rissos_dolphin: "Risso's Dolphin",
  harbor_porpoise: "Harbor Porpoise",
};

/** Smooth detailed whale silhouette PNGs (in /whale_detailed_smooth_icons/). */
const SMOOTH_ICON_FILES: Record<string, string> = {
  humpback_whale: "humpback_whale.png",
  humpback: "humpback_whale.png",
  right_whale: "right_whale.png",
  blue_whale: "blue_whale.png",
  fin_whale: "fin_whale.png",
  sei_whale: "sei_whale.png",
  minke_whale: "minke_whale.png",
  sperm_whale: "sperm_whale.png",
  killer_whale: "killer_whale_orca.png",
  orca: "killer_whale_orca.png",
};

export type Rarity = {
  /** Collectible-card rarity label, tied to IUCN status. */
  tier: string;
  status: string;
  /** Hex accent for rings/glows. */
  hex: string;
  /** Tailwind text class. */
  text: string;
  /** CSS filter to tint a white silhouette. */
  tint: string;
};

const TINT = {
  red: "brightness(0.95) sepia(1) saturate(6) hue-rotate(-12deg)",
  orange: "brightness(1) sepia(1) saturate(5) hue-rotate(12deg)",
  amber: "brightness(1) sepia(1) saturate(5) hue-rotate(38deg)",
  green: "brightness(1) sepia(1) saturate(5) hue-rotate(85deg)",
  cyan: "brightness(1) sepia(1) saturate(6) hue-rotate(150deg)",
  slate: "brightness(0.85) sepia(0.2) saturate(0.6) hue-rotate(180deg)",
};

const LEGENDARY: Rarity = { tier: "Legendary", status: "Critically Endangered", hex: "#ef4444", text: "text-red-400", tint: TINT.red };
const EPIC: Rarity = { tier: "Epic", status: "Endangered", hex: "#f97316", text: "text-orange-400", tint: TINT.orange };
const RARE: Rarity = { tier: "Rare", status: "Vulnerable", hex: "#eab308", text: "text-amber-400", tint: TINT.amber };
const COMMON: Rarity = { tier: "Common", status: "Least Concern", hex: "#22c55e", text: "text-emerald-400", tint: TINT.green };
const UNCOMMON: Rarity = { tier: "Uncommon", status: "Least Concern", hex: "#06b6d4", text: "text-cyan-400", tint: TINT.cyan };
const UNKNOWN: Rarity = { tier: "Unknown", status: "Data Deficient", hex: "#94a3b8", text: "text-slate-400", tint: TINT.slate };

const RARITY_BY_SPECIES: Record<string, Rarity> = {
  right_whale: LEGENDARY,
  southern_right_whale: EPIC,
  vaquita: LEGENDARY,
  rices_whale: LEGENDARY,
  blue_whale: EPIC,
  sei_whale: EPIC,
  fin_whale: RARE,
  sperm_whale: RARE,
  hectors_dolphin: RARE,
  humpback_whale: COMMON,
  humpback: COMMON,
  minke_whale: COMMON,
  gray_whale: COMMON,
  bowhead: COMMON,
  common_dolphin: UNCOMMON,
  bottlenose_dolphin: UNCOMMON,
  rissos_dolphin: UNCOMMON,
  harbor_porpoise: UNCOMMON,
  killer_whale: UNKNOWN,
  orca: UNKNOWN,
  beaked_whale: UNKNOWN,
  pilot_whale: UNKNOWN,
};

export function rarityOf(species: string | null | undefined): Rarity {
  if (!species) return UNKNOWN;
  return RARITY_BY_SPECIES[species] ?? UNKNOWN;
}

export function speciesLabel(key: string | null | undefined): string {
  if (!key || key === "unknown") return "Unidentified";
  if (SPECIES_LABELS[key]) return SPECIES_LABELS[key];
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function silhouetteFor(species: string | null | undefined): string | null {
  if (!species) return null;
  const f = SMOOTH_ICON_FILES[species];
  return f ? `/whale_detailed_smooth_icons/${f}` : null;
}

export function timeAgo(iso: string): string {
  const d = new Date(iso).getTime();
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 7) return `${days}d ago`;
  const w = Math.floor(days / 7);
  if (w < 5) return `${w}w ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function basinOf(lat: number, lon: number): string {
  if (lat >= 35 && lat <= 52 && lon >= -82 && lon <= -45) return "NW Atlantic";
  if (lat >= 24 && lat < 35 && lon >= -82 && lon <= -59) return "SE US Atlantic";
  if (lat >= 30 && lat <= 60 && lon >= -140 && lon < -100) return "NE Pacific";
  if (lat >= 18 && lat <= 32 && lon >= -161 && lon <= -154) return "Hawaii";
  if (lat >= 50 && lon >= -180 && lon <= -130) return "Alaska";
  if (lat >= 10 && lat < 26 && lon >= -88 && lon <= -60) return "Caribbean";
  return "Open ocean";
}

/** Great-circle distance in km. */
export function haversineKm(
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const la1 = (a.lat * Math.PI) / 180;
  const la2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(la1) * Math.cos(la2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function confidenceStars(conf: number | null | undefined): number {
  if (conf == null) return 0;
  return Math.max(1, Math.min(5, Math.round(conf * 5)));
}

/* ── Reputation tiers (crew manifest) ─────────────────────── */

const TIER_META: Record<
  string,
  { label: string; text: string; icon: React.ReactNode; pennant: string }
> = {
  newcomer: { label: "Newcomer", text: "text-slate-300", icon: <IconUser className="h-3.5 w-3.5" />, pennant: "#94a3b8" },
  observer: { label: "Observer", text: "text-ocean-300", icon: <IconEye className="h-3.5 w-3.5" />, pennant: "#38bdf8" },
  contributor: { label: "Contributor", text: "text-emerald-300", icon: <IconStar className="h-3.5 w-3.5" />, pennant: "#34d399" },
  expert: { label: "Expert", text: "text-purple-300", icon: <IconMicroscope className="h-3.5 w-3.5" />, pennant: "#c084fc" },
  authority: { label: "Authority", text: "text-amber-300", icon: <IconStar className="h-3.5 w-3.5" />, pennant: "#fbbf24" },
};

export function tierMeta(tier: string | null | undefined) {
  return TIER_META[(tier ?? "newcomer").toLowerCase()] ?? TIER_META.newcomer;
}

/* ── Compare-tray state hook (shared across pages) ─────────── */

export function useCompare() {
  const [compare, setCompare] = useState<string[]>([]);
  const toggle = useCallback((id: string) => {
    setCompare((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 3) return prev; // cap at 3
      return [...prev, id];
    });
  }, []);
  const clear = useCallback(() => setCompare([]), []);
  return { compare, toggle, clear };
}

/* ── Section heading ──────────────────────────────────────── */

export function SectionHeading({
  eyebrow,
  title,
  hint,
}: {
  eyebrow: string;
  title: string;
  hint?: string;
}) {
  return (
    <div>
      <p className="font-mono text-[11px] uppercase tracking-[0.35em] text-ocean-400/70">
        {eyebrow}
      </p>
      <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
        {title}
      </h2>
      {hint && <p className="mt-1.5 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}

/* ── Field card (collectible sighting) ────────────────────── */

export function FieldCard({
  sub,
  selected = false,
  onToggle,
}: {
  sub: SubmissionSummary;
  /** When `onToggle` is provided, a compare toggle appears in the corner. */
  selected?: boolean;
  onToggle?: () => void;
}) {
  const [imgError, setImgError] = useState(false);
  const species = sub.model_species ?? sub.species_guess ?? "unknown";
  const r = rarityOf(species);
  const sil = silhouetteFor(species);
  const stars = confidenceStars(sub.model_confidence);
  const isDolphin = /dolphin|porpoise|orca|killer/.test(species);
  const showPhoto = sub.has_photo && !imgError;
  const photoUrl = `${API_BASE}/api/v1/media/${sub.id}/photo`;

  return (
    <Link
      href={`/submissions/${sub.id}`}
      className="group relative flex flex-col overflow-hidden border bg-abyss-900/50 text-left transition-all hover:-translate-y-0.5"
      style={{
        borderColor: selected ? r.hex : "rgba(255,255,255,0.08)",
        boxShadow: selected
          ? `0 0 0 1px ${r.hex}, 0 0 30px -10px ${r.hex}`
          : `inset 0 0 40px -30px ${r.hex}`,
      }}
    >
      {/* media — uploaded photo (preferred) or silhouette fallback */}
      <div className="relative h-32 overflow-hidden">
        {showPhoto ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={photoUrl}
              alt={speciesLabel(species)}
              className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
              onError={() => setImgError(true)}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-abyss-950/90 via-transparent to-abyss-950/30" />
            {sil && (
              <Image
                src={sil}
                alt=""
                width={120}
                height={60}
                className="absolute bottom-2 right-2 h-7 w-auto opacity-70"
                style={{ filter: `${r.tint} drop-shadow(0 0 6px ${r.hex})` }}
              />
            )}
          </>
        ) : (
          <div
            className="flex h-full items-center justify-center"
            style={{
              background: `radial-gradient(circle at 50% 40%, ${r.hex}14, transparent 70%)`,
            }}
          >
            {sil ? (
              <Image
                src={sil}
                alt=""
                width={200}
                height={100}
                className="h-16 w-auto object-contain transition-transform duration-500 group-hover:scale-110"
                style={{ filter: `${r.tint} drop-shadow(0 0 12px ${r.hex}aa)` }}
              />
            ) : (
              <span style={{ color: r.hex }}>
                {isDolphin ? (
                  <IconDolphin className="h-12 w-12" />
                ) : (
                  <IconWhale className="h-12 w-12" />
                )}
              </span>
            )}
          </div>
        )}

        {/* rarity ribbon */}
        <span
          className="absolute left-2 top-2 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest backdrop-blur-sm"
          style={{ background: `${r.hex}26`, color: r.hex }}
        >
          {r.tier}
        </span>

        {/* compare toggle — only when comparison is enabled */}
        {onToggle && (
          <button
            type="button"
            aria-label={selected ? "Remove from compare" : "Add to compare"}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onToggle();
            }}
            className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full border text-[11px] backdrop-blur-sm transition-colors hover:scale-110"
            style={{
              borderColor: selected ? r.hex : "rgba(255,255,255,0.25)",
              background: selected ? r.hex : "rgba(10,15,26,0.6)",
              color: selected ? "#0a0f1a" : "#cbd5e1",
            }}
          >
            {selected ? "✓" : "+"}
          </button>
        )}
      </div>

      {/* body */}
      <div className="flex flex-1 flex-col gap-1.5 px-3 pb-3 pt-2.5">
        <p className="font-display text-sm font-bold leading-tight text-white">
          {speciesLabel(species)}
        </p>
        {stars > 0 && (
          <div className="flex items-center gap-0.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <span
                key={i}
                style={{ color: i < stars ? r.hex : "rgba(255,255,255,0.12)" }}
              >
                <IconStar className="h-3 w-3" />
              </span>
            ))}
          </div>
        )}
        <div className="mt-auto flex items-center justify-between pt-2 text-[11px] text-slate-500">
          <span className="truncate">{sub.submitter_name ?? "Anon"}</span>
          <span>{timeAgo(sub.created_at)}</span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-600">
          {sub.lat != null && sub.lon != null && (
            <span className="flex items-center gap-1">
              <IconPin className="h-3 w-3" />
              {basinOf(sub.lat, sub.lon)}
            </span>
          )}
          {sub.has_photo && <IconCamera className="h-3 w-3 text-ocean-500" />}
          {sub.has_audio && <IconMicrophone className="h-3 w-3 text-ocean-500" />}
        </div>
      </div>
    </Link>
  );
}

/* ── Compare tray + modal ─────────────────────────────────── */

export function CompareTray({
  items,
  onClear,
  onRemove,
  onOpen,
}: {
  items: SubmissionSummary[];
  onClear: () => void;
  onRemove: (id: string) => void;
  onOpen: () => void;
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-ocean-700/40 bg-abyss-950/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3 sm:px-10">
        <span className="hidden font-mono text-[11px] uppercase tracking-[0.3em] text-ocean-400/70 sm:block">
          Compare tray
        </span>
        <div className="flex flex-1 items-center gap-2">
          {items.map((it) => {
            const species = it.model_species ?? it.species_guess ?? "unknown";
            const r = rarityOf(species);
            return (
              <div
                key={it.id}
                className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs"
                style={{ borderColor: `${r.hex}55`, background: `${r.hex}12` }}
              >
                <span className="font-semibold text-white">{speciesLabel(species)}</span>
                <button
                  type="button"
                  onClick={() => onRemove(it.id)}
                  className="text-slate-400 hover:text-white"
                  aria-label="Remove"
                >
                  ×
                </button>
              </div>
            );
          })}
          {Array.from({ length: Math.max(0, 3 - items.length) }).map((_, i) => (
            <span
              key={i}
              className="hidden rounded-full border border-dashed border-white/10 px-3 py-1.5 text-xs text-slate-600 sm:inline"
            >
              empty slot
            </span>
          ))}
        </div>
        <button
          type="button"
          onClick={onClear}
          className="text-xs text-slate-500 transition-colors hover:text-slate-300"
        >
          Clear
        </button>
        <button
          type="button"
          onClick={onOpen}
          disabled={items.length < 2}
          className="rounded-lg bg-gradient-to-r from-ocean-600 to-bioluminescent-600 px-5 py-2 text-sm font-semibold text-white transition-all enabled:hover:from-ocean-500 enabled:hover:to-bioluminescent-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Compare {items.length}
        </button>
      </div>
    </div>
  );
}

export function CompareModal({
  items,
  onClose,
}: {
  items: SubmissionSummary[];
  onClose: () => void;
}) {
  const geo = items.filter((i) => i.lat != null && i.lon != null);
  const dist =
    geo.length >= 2
      ? haversineKm(
          { lat: geo[0].lat as number, lon: geo[0].lon as number },
          { lat: geo[1].lat as number, lon: geo[1].lon as number },
        )
      : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-h-[85vh] w-full max-w-4xl overflow-auto border border-ocean-700/40 bg-abyss-900 p-6 sm:p-8"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-500 hover:text-white"
          aria-label="Close"
        >
          ✕
        </button>
        <p className="font-mono text-[11px] uppercase tracking-[0.35em] text-ocean-400/70">
          Side by side
        </p>
        <h2 className="mt-2 font-display text-2xl font-bold text-white">
          Sighting comparison
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Line sightings up to see whether observers are seeing the same animal
          or different ones — compare the species call, model confidence, who
          reported it, how it was verified, and how far apart the encounters
          were.
        </p>
        {dist != null && (
          <p className="mt-2 text-sm text-slate-400">
            The first two sightings were{" "}
            <span className="font-semibold text-bioluminescent-300">
              {dist < 1 ? "<1" : Math.round(dist).toLocaleString()} km
            </span>{" "}
            apart.
          </p>
        )}

        <div
          className="mt-6 grid gap-4"
          style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
        >
          {items.map((it) => {
            const species = it.model_species ?? it.species_guess ?? "unknown";
            const r = rarityOf(species);
            const sil = silhouetteFor(species);
            const stars = confidenceStars(it.model_confidence);
            return (
              <div
                key={it.id}
                className="border bg-abyss-950/60 p-4"
                style={{ borderColor: `${r.hex}40` }}
              >
                <div className="flex h-20 items-center justify-center">
                  {sil ? (
                    <Image
                      src={sil}
                      alt=""
                      width={180}
                      height={90}
                      className="h-14 w-auto object-contain"
                      style={{ filter: `${r.tint} drop-shadow(0 0 10px ${r.hex})` }}
                    />
                  ) : (
                    <span style={{ color: r.hex }}>
                      <IconWhale className="h-10 w-10" />
                    </span>
                  )}
                </div>
                <p className="mt-2 font-display text-sm font-bold text-white">
                  {speciesLabel(species)}
                </p>
                <p className={`text-[11px] font-semibold ${r.text}`}>{r.tier}</p>

                <dl className="mt-3 space-y-2 text-xs">
                  <CompareRow label="Confidence">
                    {stars > 0 ? (
                      <span className="flex gap-0.5">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span
                            key={i}
                            style={{ color: i < stars ? r.hex : "rgba(255,255,255,0.12)" }}
                          >
                            <IconStar className="h-3 w-3" />
                          </span>
                        ))}
                      </span>
                    ) : (
                      "—"
                    )}
                  </CompareRow>
                  <CompareRow label="Observer">{it.submitter_name ?? "Anon"}</CompareRow>
                  <CompareRow label="When">{timeAgo(it.created_at)}</CompareRow>
                  <CompareRow label="Where">
                    {it.lat != null && it.lon != null ? basinOf(it.lat, it.lon) : "—"}
                  </CompareRow>
                  <CompareRow label="Verified">
                    <span className="capitalize">
                      {it.verification_status.replace(/_/g, " ")}
                    </span>
                  </CompareRow>
                  <CompareRow label="Votes">
                    <span className="text-emerald-400">+{it.community_agree}</span> /{" "}
                    <span className="text-red-400">−{it.community_disagree}</span>
                  </CompareRow>
                  <CompareRow label="Media">
                    <span className="flex items-center gap-2">
                      {it.has_photo && <IconCamera className="h-3.5 w-3.5 text-ocean-400" />}
                      {it.has_audio && <IconMicrophone className="h-3.5 w-3.5 text-ocean-400" />}
                      {!it.has_photo && !it.has_audio && "—"}
                    </span>
                  </CompareRow>
                </dl>

                <Link
                  href={`/submissions/${it.id}`}
                  className="mt-3 inline-block text-xs font-semibold text-ocean-300 hover:text-bioluminescent-400"
                >
                  Open record →
                </Link>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CompareRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-white/[0.05] pb-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-200">{children}</dd>
    </div>
  );
}
