"use client";

/**
 * COMMUNITY — "The Field Station"
 *
 * The community hub, reframed as a living research field station / ship's
 * logbook rather than a stack of equal gradient cards. Features:
 *   1. The 3-D SightingGlobe promoted to a full-bleed HERO with floating
 *      impact counters — the page opens on the ocean.
 *   2. A "crew manifest" leaderboard (tier pennants, editorial rows).
 *   3. "Whale of the Week" as a featured field card.
 *   4. Sightings as collectible "field cards" with conservation-tier rarity
 *      (full browser + Compare tray lives on /community/interactions).
 *   5. Recent activity as a sonar/current feed along a spine.
 */

import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import {
  IconCamera,
  IconCalendar,
  IconUsers,
  IconPin,
  IconCheck,
  IconEye,
} from "@/components/icons/MarineIcons";
import {
  type CommunityStatsResponse,
  type GlobeSighting,
  type RecentActivityItem,
  type SubmissionSummary,
  type TopContributor,
  type WhaleOfTheWeek,
  rarityOf,
  speciesLabel,
  silhouetteFor,
  timeAgo,
  basinOf,
  tierMeta,
  SectionHeading,
  FieldCard,
} from "./_field";

const SightingGlobe = dynamic(() => import("@/components/SightingGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-abyss-950 text-xs text-ocean-400/70">
      Charting sightings…
    </div>
  ),
});

/* ═══════════════════════════════════════════════════════════
   Page
   ═══════════════════════════════════════════════════════════ */

export default function CommunityPrototype() {
  const [stats, setStats] = useState<CommunityStatsResponse | null>(null);
  const [subs, setSubs] = useState<SubmissionSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/submissions/community-stats`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !cancelled && d && setStats(d))
      .catch(() => {});
    fetch(`${API_BASE}/api/v1/submissions/public?limit=200&offset=0`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled && d?.submissions) setSubs(d.submissions);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const globeSightings: GlobeSighting[] = useMemo(
    () =>
      subs
        .filter((s) => s.lat != null && s.lon != null)
        .map((s) => ({
          id: s.id,
          lat: s.lat as number,
          lon: s.lon as number,
          species: s.model_species ?? s.species_guess ?? "unknown",
          submitter_name: s.submitter_name,
          created_at: s.created_at,
          group_size: s.group_size,
          behavior: s.behavior,
          calf_present: s.calf_present,
          verification_status: s.verification_status,
          risk_category: s.risk_category,
          has_photo: s.has_photo,
          has_audio: s.has_audio,
        })),
    [subs],
  );

  const s = stats?.stats;

  return (
    <div className="min-h-screen bg-abyss-950 text-slate-200">
      {/* ═══ GLOBE HERO ═══ */}
      <section className="relative h-[78vh] min-h-[560px] w-full overflow-hidden">
        {globeSightings.length > 0 ? (
          <SightingGlobe
            sightings={globeSightings}
            hero
            className="absolute inset-0 h-full w-full"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-b from-abyss-900 to-abyss-950" />
        )}

        {/* Readability gradients over the globe */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-abyss-950/90 to-transparent" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-56 bg-gradient-to-t from-abyss-950 via-abyss-950/70 to-transparent" />

        {/* Title block */}
        <div className="pointer-events-none absolute left-0 right-0 top-24 px-6 sm:px-10">
          <div className="mx-auto max-w-7xl">
            <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-bioluminescent-400/80">
              The Field Station
            </p>
            <h1 className="max-w-2xl font-display text-4xl font-black leading-[0.95] tracking-tight text-white drop-shadow-[0_2px_14px_rgba(0,0,0,0.8)] sm:text-6xl">
              Every sighting is a{" "}
              <span className="text-ocean-bright">data point</span> — and a
              story.
            </h1>
            {s && (
              <p className="mt-5 max-w-xl text-sm leading-relaxed text-slate-300 drop-shadow-[0_1px_6px_rgba(0,0,0,0.8)] sm:text-base">
                {s.total_contributors.toLocaleString()} observers have logged{" "}
                {s.total_sightings.toLocaleString()} cetacean sightings across{" "}
                {s.species_documented} species. Spin the globe — then add yours.
              </p>
            )}
            <div className="pointer-events-auto mt-6 flex flex-wrap gap-3">
              <Link
                href="/report"
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-ocean-600 to-bioluminescent-600 px-6 py-3 text-sm font-semibold text-white shadow-ocean-md transition-all hover:from-ocean-500 hover:to-bioluminescent-500"
              >
                <IconCamera className="h-4 w-4" />
                Log a sighting
              </Link>
              <Link
                href="/community/interactions"
                className="glass-panel inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconPin className="h-4 w-4" />
                Browse sightings
              </Link>
              <Link
                href="/community/events"
                className="glass-panel inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconCalendar className="h-4 w-4" />
                Browse events
              </Link>
            </div>
          </div>
        </div>

        {/* Floating impact counters — bottom-left strip */}
        {s && (
          <div className="absolute bottom-16 left-0 right-0 px-6 sm:px-10">            <div className="mx-auto flex max-w-7xl flex-wrap items-end gap-x-10 gap-y-4">
              <FloatStat value={s.total_sightings} label="sightings" />
              <FloatStat value={s.total_contributors} label="observers" />
              <FloatStat value={s.species_documented} label="species" />
              <FloatStat value={s.total_events} label="events" />
              {s.sightings_this_week > 0 && (
                <div className="flex items-center gap-2 rounded-full bg-ocean-500/15 px-3 py-1.5 text-xs text-ocean-200 ring-1 ring-ocean-400/30 backdrop-blur-sm">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ocean-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-ocean-400" />
                  </span>
                  <span className="font-semibold">{s.sightings_this_week}</span> this week
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      <div className="mx-auto max-w-7xl px-6 sm:px-10">
        {/* ═══ NEEDS REVIEW STRIP ═══ */}
        {s && s.needs_review_count > 0 && (
          <div className="group relative mt-10 overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/[0.10] via-amber-500/[0.05] to-transparent p-6 sm:p-7">
            {/* pulsing beacon accent */}
            <span className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-amber-500/10 blur-3xl" />
            <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-4">
                <span className="relative mt-1 flex h-3.5 w-3.5 shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-amber-400" />
                </span>
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-amber-400">
                    Crow&apos;s nest · take a watch
                  </p>
                  <h2 className="mt-1.5 font-display text-xl font-bold text-white sm:text-2xl">
                    <span className="text-amber-300">
                      {s.needs_review_count.toLocaleString()}
                    </span>{" "}
                    sighting{s.needs_review_count === 1 ? "" : "s"} need a second
                    pair of eyes
                  </h2>
                  <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-slate-300">
                    Every report needs the community to confirm the species
                    before it counts. Spend two minutes in the crow&apos;s nest —
                    swipe to agree, disagree, or refine the ID, and earn{" "}
                    <span className="font-semibold text-amber-200">
                      +2 reputation
                    </span>{" "}
                    for each one you review.
                  </p>
                </div>
              </div>
              <Link
                href="/verify"
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 px-6 py-3 text-sm font-bold text-abyss-950 shadow-lg shadow-amber-500/20 transition-all hover:from-amber-400 hover:to-amber-300 hover:shadow-amber-500/40"
              >
                <IconEye className="h-4 w-4" />
                Review sightings
              </Link>
            </div>
          </div>
        )}

        {/* ═══ CREW MANIFEST + WHALE OF THE WEEK ═══ */}
        <section className="mt-16 grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          {/* Crew manifest */}
          <div>
            <SectionHeading
              eyebrow="The crew"
              title="Top of the manifest"
              hint="Observers ranked by reputation"
            />
            <div className="mt-6 divide-y divide-white/[0.06] border-y border-white/[0.06]">
              {(stats?.top_contributors ?? []).slice(0, 6).map((c, i) => (
                <ManifestRow key={c.user_id} rank={i + 1} c={c} />
              ))}
              {(!stats || stats.top_contributors.length === 0) && (
                <p className="py-8 text-center text-sm text-slate-500">
                  No observers logged yet.
                </p>
              )}
            </div>
            <Link
              href="/community/interactions"
              className="mt-5 inline-block text-sm font-semibold text-ocean-300 transition-colors hover:text-bioluminescent-400"
            >
              See the full manifest →
            </Link>
          </div>

          {/* Whale of the Week */}
          <div>
            <SectionHeading
              eyebrow="Featured catch"
              title="Whale of the week"
              hint="The community's most-discussed sighting"
            />
            {stats?.whale_of_the_week ? (
              <WhaleOfWeekCard item={stats.whale_of_the_week} />
            ) : (
              <div className="mt-6 border border-white/[0.06] bg-abyss-900/40 p-10 text-center text-sm text-slate-500">
                No featured sighting yet — log one to be in the running.
              </div>
            )}
          </div>
        </section>

        {/* ═══ THE LOGBOOK — latest field cards (preview) ═══ */}
        <section className="mt-20">
          <div className="flex items-end justify-between gap-4">
            <SectionHeading
              eyebrow="The logbook"
              title="Latest field cards"
              hint="Tap any card to open the full sighting record"
            />
            <Link
              href="/community/interactions"
              className="hidden shrink-0 text-sm font-semibold text-ocean-300 transition-colors hover:text-bioluminescent-400 sm:inline-block"
            >
              Browse &amp; compare all →
            </Link>
          </div>
          <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {subs.slice(0, 8).map((sub) => (
              <FieldCard key={sub.id} sub={sub} />
            ))}
            {subs.length === 0 && (
              <p className="col-span-full py-12 text-center text-sm text-slate-500">
                The logbook is empty — be the first to log a sighting.
              </p>
            )}
          </div>
          {subs.length > 0 && (
            <Link
              href="/community/interactions"
              className="mt-6 inline-block text-sm font-semibold text-ocean-300 transition-colors hover:text-bioluminescent-400 sm:hidden"
            >
              Browse &amp; compare all →
            </Link>
          )}
        </section>

        {/* ═══ SONAR FEED — recent activity ═══ */}
        {stats && stats.recent_activity.length > 0 && (
          <section className="mt-20 mb-24">
            <SectionHeading
              eyebrow="On the wire"
              title="Live sightings feed"
              hint="Newest reports as they surface"
            />
            <div className="relative mt-8 pl-6">
              {/* spine */}
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-gradient-to-b from-bioluminescent-400/50 via-ocean-500/30 to-transparent" />
              <div className="space-y-5">
                {stats.recent_activity.slice(0, 10).map((a) => (
                  <SonarRow key={a.id} item={a} />
                ))}
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════════ */

function FloatStat({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-display text-2xl font-black tracking-tight text-white drop-shadow-[0_1px_6px_rgba(0,0,0,0.8)] sm:text-3xl">
        {value.toLocaleString()}
      </span>
      <span className="text-[11px] uppercase tracking-wider text-slate-300/80">
        {label}
      </span>
    </div>
  );
}

function ManifestRow({ rank, c }: { rank: number; c: TopContributor }) {
  const tm = tierMeta(c.reputation_tier);
  return (
    <Link
      href={`/users/${c.user_id}`}
      className="group flex items-center gap-4 py-4 transition-colors hover:bg-white/[0.02]"
    >
      <span className="w-6 text-center font-mono text-sm font-bold text-slate-500">
        {rank}
      </span>
      {/* pennant */}
      <span
        className="h-7 w-2 shrink-0 rounded-sm"
        style={{ background: tm.pennant, boxShadow: `0 0 10px ${tm.pennant}55` }}
      />
      <UserAvatar
        avatarUrl={c.avatar_url}
        displayName={c.display_name}
        size={38}
        className="shrink-0"
      />
      <div className="min-w-0 flex-1">
        <p className="truncate font-display text-sm font-bold text-white group-hover:text-ocean-bright">
          {c.display_name ?? "Anonymous"}
        </p>
        <p className={`flex items-center gap-1.5 text-xs ${tm.text}`}>
          {tm.icon}
          {tm.label}
        </p>
      </div>
      <div className="text-right">
        <p className="font-mono text-sm font-bold text-bioluminescent-300">
          {c.reputation_score.toLocaleString()}
        </p>
        <p className="text-[11px] text-slate-500">
          {c.submission_count} logs · {c.species_count} spp.
        </p>
      </div>
    </Link>
  );
}

function WhaleOfWeekCard({ item }: { item: WhaleOfTheWeek }) {
  const r = rarityOf(item.species);
  const sil = silhouetteFor(item.species);
  const photoUrl = `${API_BASE}/api/v1/media/${item.id}/photo`;
  return (
    <div
      className="group relative mt-6 overflow-hidden border border-white/[0.08] bg-abyss-900/50"
      style={{ boxShadow: `inset 0 0 0 1px ${r.hex}22, 0 0 50px -25px ${r.hex}` }}
    >
      <div className="grid sm:grid-cols-[1.1fr_1fr]">
        {/* media / silhouette */}
        <div className="relative aspect-[4/3] overflow-hidden bg-gradient-to-br from-abyss-800 to-abyss-950 sm:aspect-auto">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={photoUrl}
            alt=""
            className="h-full w-full object-cover"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
          {sil && (
            <Image
              src={sil}
              alt=""
              width={220}
              height={120}
              className="absolute bottom-3 right-3 h-16 w-auto opacity-40"
              style={{ filter: `${r.tint} drop-shadow(0 0 14px ${r.hex})` }}
            />
          )}
          <span
            className="absolute left-3 top-3 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest backdrop-blur-sm"
            style={{ background: `${r.hex}22`, color: r.hex, boxShadow: `inset 0 0 0 1px ${r.hex}55` }}
          >
            {r.tier}
          </span>
        </div>

        {/* details */}
        <div className="flex flex-col justify-between gap-4 p-5">
          <div>
            <h3 className="font-display text-2xl font-bold text-white">
              {speciesLabel(item.species)}
            </h3>
            <p className={`mt-1 text-xs font-semibold ${r.text}`}>{r.status}</p>
            {item.lat != null && item.lon != null && (
              <p className="mt-3 flex items-center gap-1.5 text-sm text-slate-400">
                <IconPin className="h-3.5 w-3.5 text-ocean-400" />
                {basinOf(item.lat, item.lon)} · {item.lat.toFixed(2)}°,{" "}
                {item.lon.toFixed(2)}°
              </p>
            )}
          </div>
          <div className="flex items-center gap-4 border-t border-white/[0.06] pt-4">
            <UserAvatar
              avatarUrl={item.submitter_avatar_url}
              displayName={item.submitter_name}
              size={34}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-200">
                {item.submitter_name ?? "Anonymous"}
              </p>
              <p className="text-[11px] text-slate-500">{timeAgo(item.created_at)}</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <span className="flex items-center gap-1 text-emerald-400">
                <IconCheck className="h-3.5 w-3.5" />
                {item.community_agree}
              </span>
              <span className="flex items-center gap-1">
                <IconUsers className="h-3.5 w-3.5" />
                {item.vote_count}
              </span>
            </div>
          </div>
          <Link
            href={`/submissions/${item.id}`}
            className="text-sm font-semibold text-ocean-300 transition-colors hover:text-bioluminescent-400"
          >
            Open the full record →
          </Link>
        </div>
      </div>
    </div>
  );
}

function SonarRow({ item }: { item: RecentActivityItem }) {
  const r = rarityOf(item.species);
  return (
    <div className="relative">
      {/* ping dot on the spine */}
      <span
        className="absolute -left-[22px] top-1.5 flex h-3.5 w-3.5 items-center justify-center"
        aria-hidden
      >
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
          style={{ background: r.hex }}
        />
        <span
          className="relative inline-flex h-2 w-2 rounded-full"
          style={{ background: r.hex }}
        />
      </span>
      <div className="flex items-center gap-3">
        <UserAvatar
          avatarUrl={item.submitter_avatar_url}
          displayName={item.submitter_name}
          size={30}
          className="shrink-0"
        />
        <p className="min-w-0 flex-1 text-sm text-slate-300">
          <span className="font-semibold text-white">
            {item.submitter_name ?? "Someone"}
          </span>{" "}
          logged a{" "}
          <span className="font-semibold" style={{ color: r.hex }}>
            {speciesLabel(item.species)}
          </span>
          {item.lat != null && item.lon != null && (
            <span className="text-slate-500"> off {basinOf(item.lat, item.lon)}</span>
          )}
        </p>
        <span className="shrink-0 text-[11px] text-slate-500">
          {timeAgo(item.created_at)}
        </span>
      </div>
    </div>
  );
}
