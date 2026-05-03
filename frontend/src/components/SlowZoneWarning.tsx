"use client";

import { useState, useEffect, useCallback } from "react";
import type { SlowZone } from "@/lib/types";
import { fetchSlowZones } from "@/lib/api";
import { IconWhale } from "@/components/icons/MarineIcons";

/* ── Props ───────────────────────────────────────────────── */

interface SlowZoneWarningProps {
  /** Called when the user clicks "View on Map" — parent should enable the overlay and zoom to fit. */
  onViewZones: (zones: SlowZone[]) => void;
}

/* ── Constants ───────────────────────────────────────────── */

const NOAA_DMA_URL =
  "https://www.fisheries.noaa.gov/national/endangered-species-conservation/reducing-vessel-strikes-north-atlantic-right-whales";

/* ── Component ───────────────────────────────────────────── */

export default function SlowZoneWarning({ onViewZones }: SlowZoneWarningProps) {
  const [zones, setZones] = useState<SlowZone[]>([]);
  const [dismissed, setDismissed] = useState(false);
  const [expanded, setExpanded] = useState(false);

  /* Fetch active slow zones once on mount */
  useEffect(() => {
    const controller = new AbortController();
    fetchSlowZones(controller.signal)
      .then((res) => {
        const active = res.data.filter((z) => !z.is_expired);
        setZones(active);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const handleView = useCallback(() => {
    onViewZones(zones);
    setDismissed(true);
  }, [onViewZones, zones]);

  /* Nothing to show */
  if (zones.length === 0 || dismissed) return null;

  return (
    <div className="pointer-events-auto absolute right-4 top-16 z-30 w-80 animate-slide-in-right">
      {/* Main banner */}
      <div className="overflow-hidden rounded-xl border border-orange-500/30 bg-gradient-to-br from-abyss-900/95 to-abyss-950/95 shadow-lg shadow-orange-500/10 backdrop-blur-md">
        {/* Header bar */}
        <div className="flex items-center gap-2 border-b border-orange-500/20 bg-orange-500/10 px-3 py-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-orange-500" />
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider text-orange-300">
            NOAA Active Alert
          </span>
          <button
            onClick={() => setDismissed(true)}
            className="ml-auto rounded p-0.5 text-slate-400 transition hover:bg-white/10 hover:text-white"
            aria-label="Dismiss warning"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M1 1l12 12M13 1L1 13" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-3 py-2.5">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-white">
            <IconWhale className="h-4 w-4 text-ocean-400" />
            {zones.length} Active Slow Zone{zones.length !== 1 ? "s" : ""}
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            NOAA has designated {zones.length} Dynamic Management{" "}
            {zones.length !== 1 ? "Areas" : "Area"} with{" "}
            <span className="font-medium text-orange-300">10-knot speed restrictions</span>{" "}
            to protect North Atlantic right whales.
          </p>

          {/* Expandable zone list */}
          {expanded && (
            <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto pr-1 text-xs text-slate-300">
              {zones.map((z) => (
                <li
                  key={z.zone_name}
                  className="flex items-start gap-1.5 rounded-md bg-white/5 px-2 py-1"
                >
                  <span className="mt-0.5 text-orange-400">▸</span>
                  <div>
                    <span className="font-medium text-slate-200">{z.zone_name}</span>
                    {z.effective_start && z.effective_end && (
                      <span className="ml-1 text-slate-500">
                        ({z.effective_start} – {z.effective_end})
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {zones.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1.5 text-xs text-orange-400/80 transition hover:text-orange-300"
            >
              {expanded ? "Hide zones ▴" : `Show ${zones.length} zone${zones.length !== 1 ? "s" : ""} ▾`}
            </button>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 border-t border-white/5 px-3 py-2">
          <button
            onClick={handleView}
            className="flex items-center gap-1.5 rounded-lg bg-orange-500/20 px-3 py-1.5 text-xs font-medium text-orange-300 transition hover:bg-orange-500/30"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
              <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
            </svg>
            View on Map
          </button>
          <a
            href={NOAA_DMA_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-lg bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-400 transition hover:bg-white/10 hover:text-white"
          >
            NOAA Details
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3.5 1.5h7v7M10.5 1.5l-9 9" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}
