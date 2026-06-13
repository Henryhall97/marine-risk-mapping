"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/config";
import {
  type SubmissionSummary,
  useCompare,
  SectionHeading,
  FieldCard,
  CompareTray,
  CompareModal,
} from "../_field";

const PAGE_SIZE = 24;

type StatusFilter = "all" | "verified" | "needs_review";

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All sightings" },
  { key: "verified", label: "Verified" },
  { key: "needs_review", label: "Needs review" },
];

const GROUP_OPTIONS: { key: string; label: string }[] = [
  { key: "all", label: "All animals" },
  { key: "whale", label: "Whales" },
  { key: "dolphin", label: "Dolphins" },
  { key: "porpoise", label: "Porpoises" },
];

function speciesGroup(species: string): string {
  if (/porpoise/.test(species)) return "porpoise";
  if (/dolphin|orca|killer|pilot/.test(species)) return "dolphin";
  if (/whale|bowhead|minke|humpback|right|fin|blue|sei|sperm|gray/.test(species))
    return "whale";
  return "other";
}

export default function PrototypeInteractionsPage() {
  const [subs, setSubs] = useState<SubmissionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [group, setGroup] = useState<string>("all");
  const { compare, toggle: toggleCompare, clear: clearCompare } = useCompare();
  const [showCompare, setShowCompare] = useState(false);

  const load = useCallback(async (pageIndex: number, replace: boolean) => {
    setLoading(true);
    try {
      const offset = pageIndex * PAGE_SIZE;
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/public?limit=${PAGE_SIZE}&offset=${offset}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const data: SubmissionSummary[] = json?.submissions ?? [];
      setHasMore(data.length === PAGE_SIZE);
      setSubs((prev) => (replace ? data : [...prev, ...data]));
    } catch {
      if (replace) setSubs([]);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setPage(0);
    load(0, true);
  }, [load]);

  const loadMore = () => {
    const next = page + 1;
    setPage(next);
    load(next, false);
  };

  const filtered = useMemo(() => {
    return subs.filter((sub) => {
      if (status === "verified" && sub.verification_status !== "verified")
        return false;
      if (
        status === "needs_review" &&
        sub.verification_status === "verified"
      )
        return false;
      if (group !== "all") {
        const species = sub.model_species ?? sub.species_guess ?? "unknown";
        if (speciesGroup(species) !== group) return false;
      }
      return true;
    });
  }, [subs, status, group]);

  const compareItems = useMemo(
    () =>
      compare
        .map((id) => subs.find((sx) => sx.id === id))
        .filter(Boolean) as SubmissionSummary[],
    [compare, subs],
  );

  return (
    <div className="min-h-screen bg-abyss-950 text-slate-200">
      <div className="mx-auto max-w-7xl px-6 pb-32 pt-10 sm:px-10">
        <Link
          href="/community"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-ocean-300 transition-colors hover:text-bioluminescent-400"
        >
          ← Back to the field station
        </Link>

        <div className="mt-8">
          <SectionHeading
            eyebrow="The logbook"
            title="Browse every field card"
            hint="Tap the + on any card to stack it in the compare tray — then line 2–3 up side by side"
          />
        </div>

        {/* Filters */}
        <div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-4 border-y border-white/[0.06] py-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.3em] text-ocean-400/60">
              Status
            </span>
            {STATUS_TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setStatus(t.key)}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                  status === t.key
                    ? "bg-ocean-500/20 text-ocean-200 ring-1 ring-ocean-400/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.3em] text-ocean-400/60">
              Group
            </span>
            {GROUP_OPTIONS.map((g) => (
              <button
                key={g.key}
                type="button"
                onClick={() => setGroup(g.key)}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                  group === g.key
                    ? "bg-bioluminescent-500/15 text-bioluminescent-300 ring-1 ring-bioluminescent-400/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>

        {/* Card grid */}
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {filtered.map((sub) => (
            <FieldCard
              key={sub.id}
              sub={sub}
              selected={compare.includes(sub.id)}
              onToggle={() => toggleCompare(sub.id)}
            />
          ))}
        </div>

        {filtered.length === 0 && !loading && (
          <p className="py-16 text-center text-sm text-slate-500">
            No sightings match these filters.
          </p>
        )}

        {/* Load more */}
        <div className="mt-10 flex justify-center">
          {hasMore ? (
            <button
              type="button"
              onClick={loadMore}
              disabled={loading}
              className="glass-panel rounded-xl px-6 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white disabled:opacity-50"
            >
              {loading ? "Surfacing more…" : "Load more field cards"}
            </button>
          ) : (
            subs.length > 0 && (
              <p className="text-xs text-slate-600">
                That&apos;s the whole logbook — {subs.length.toLocaleString()}{" "}
                sightings.
              </p>
            )
          )}
        </div>
      </div>

      {/* Compare tray (sticky) */}
      {compareItems.length > 0 && (
        <CompareTray
          items={compareItems}
          onClear={clearCompare}
          onRemove={(id) => toggleCompare(id)}
          onOpen={() => setShowCompare(true)}
        />
      )}

      {showCompare && compareItems.length > 0 && (
        <CompareModal
          items={compareItems}
          onClose={() => setShowCompare(false)}
        />
      )}
    </div>
  );
}
