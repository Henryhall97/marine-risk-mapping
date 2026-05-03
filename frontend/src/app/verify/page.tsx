"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import {
  IconWhale,
  IconCamera,
  IconMicrophone,
  IconWarning,
  IconCheck,
  IconInfo,
  IconShield,
} from "@/components/icons/MarineIcons";
import { API_BASE } from "@/lib/config";

const SpeciesPicker = dynamic(() => import("@/components/SpeciesPicker"), {
  ssr: false,
  loading: () => (
    <div className="h-12 flex items-center justify-center">
      <div className="h-5 w-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

/* ── Types ───────────────────────────────────────────────── */

interface Submission {
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
  community_agree: number;
  community_disagree: number;
  advisory_level: string | null;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
  submitter_is_moderator: boolean;
  has_photo: boolean;
  has_audio: boolean;
  verification_score: number | null;
  group_size: number | null;
  behavior: string | null;
  life_stage: string | null;
  calf_present: boolean | null;
  sea_state_beaufort: number | null;
  observation_platform: string | null;
  scientific_name: string | null;
  sighting_datetime: string | null;
  photo_species?: string | null;
  photo_confidence?: number | null;
  audio_species?: string | null;
  audio_confidence?: number | null;
  description?: string | null;
  direction_of_travel?: string | null;
}

type SwipeDir = "left" | "right" | "up" | null;
type VoteType = "agree" | "disagree" | "refine";

/* ── Constants ───────────────────────────────────────────── */

const SWIPE_THRESHOLD = 100; // px to trigger a swipe
const SWIPE_VELOCITY = 0.3; // px/ms minimum swipe speed
const FLY_DISTANCE = 800; // px card flies off screen
const RISK_COLOURS: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-emerald-500",
  minimal: "bg-sky-400",
};
const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  unverified: { bg: "bg-slate-700/60", text: "text-slate-300" },
  "mod-verified": { bg: "bg-emerald-800/60", text: "text-emerald-200" },
  "community-verified": { bg: "bg-green-800/60", text: "text-green-200" },
  disputed: { bg: "bg-blue-800/60", text: "text-blue-200" },
  rejected: { bg: "bg-red-800/60", text: "text-red-200" },
  "under-review": { bg: "bg-yellow-800/60", text: "text-yellow-200" },
};

/* Species filter groups for grouped dropdown display */
const SPECIES_FILTER_GROUPS: { label: string; species: string[] }[] = [
  {
    label: "Baleen Whales",
    species: [
      "humpback_whale", "right_whale", "southern_right_whale",
      "fin_whale", "blue_whale", "minke_whale", "sei_whale",
      "gray_whale", "bowhead", "brydes_whale", "omuras_whale",
      "rices_whale", "pygmy_right_whale",
    ],
  },
  {
    label: "Toothed Whales",
    species: [
      "sperm_whale", "beaked_whale", "beluga", "narwhal",
      "dwarf_sperm_whale", "pygmy_sperm_whale", "small_sperm_whale",
      "pilot_whale",
    ],
  },
  {
    label: "Dolphins",
    species: [
      "orca", "bottlenose_dolphin", "common_dolphin",
      "spotted_dolphin", "striped_dolphin", "rissos_dolphin",
      "whitesided_dolphin", "hectors_dolphin", "other_dolphin",
    ],
  },
  {
    label: "Porpoises",
    species: [
      "harbor_porpoise", "dalls_porpoise", "vaquita", "other_porpoise",
    ],
  },
  {
    label: "Unidentified",
    species: [
      "unid_baleen", "unid_toothed", "unid_dolphin",
      "unid_rorqual", "unid_cetacean",
    ],
  },
];

const FILTER_SPECIES: { value: string; label: string; group?: string }[] =
  SPECIES_FILTER_GROUPS.flatMap((g) =>
    g.species.map((sp) => ({
      value: sp,
      label: sp.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      group: g.label,
    })),
  );

/* Region bounding boxes: [lat_min, lat_max, lon_min, lon_max] */
const REGION_BBOX: Record<string, [number, number, number, number]> = {
  /* North America */
  north_atlantic: [35, 52, -82, -59],
  south_atlantic: [24, 35, -82, -59],
  gulf: [18, 31, -98, -82],
  pacific: [32, 50, -130, -117],
  alaska: [50, 65, -180, -130],
  hawaii: [18, 23, -162, -154],
  caribbean: [15, 27, -68, -60],
  /* Europe */
  northeast_atlantic: [35, 72, -30, 15],
  mediterranean: [30, 46, -6, 42],
  baltic: [53, 66, 10, 30],
  /* Southern Hemisphere */
  south_pacific: [-60, 0, -180, -70],
  south_atlantic_ocean: [-60, 0, -70, 20],
  southern_ocean: [-80, -60, -180, 180],
  indian_ocean: [-60, 25, 20, 120],
  /* Asia / Oceania */
  northwest_pacific: [20, 60, 100, 180],
  southeast_asia: [-11, 20, 90, 150],
  australasia: [-50, -10, 110, 180],
  /* Africa / Middle East */
  west_africa: [-5, 35, -25, 15],
  east_africa: [-30, 30, 30, 65],
  /* Polar */
  arctic: [66, 90, -180, 180],
};

const REGION_FILTER_GROUPS: { label: string; regions: { value: string; label: string }[] }[] = [
  {
    label: "North America",
    regions: [
      { value: "north_atlantic", label: "N. Atlantic" },
      { value: "south_atlantic", label: "S. Atlantic" },
      { value: "gulf", label: "Gulf of Mexico" },
      { value: "pacific", label: "Pacific" },
      { value: "alaska", label: "Alaska" },
      { value: "hawaii", label: "Hawai'i" },
      { value: "caribbean", label: "Caribbean" },
    ],
  },
  {
    label: "Europe",
    regions: [
      { value: "northeast_atlantic", label: "NE Atlantic" },
      { value: "mediterranean", label: "Mediterranean" },
      { value: "baltic", label: "Baltic" },
    ],
  },
  {
    label: "Southern Hemisphere",
    regions: [
      { value: "south_pacific", label: "South Pacific" },
      { value: "south_atlantic_ocean", label: "South Atlantic" },
      { value: "southern_ocean", label: "Southern Ocean" },
      { value: "indian_ocean", label: "Indian Ocean" },
    ],
  },
  {
    label: "Asia / Oceania",
    regions: [
      { value: "northwest_pacific", label: "NW Pacific" },
      { value: "southeast_asia", label: "SE Asia" },
      { value: "australasia", label: "Australasia" },
    ],
  },
  {
    label: "Africa / Middle East",
    regions: [
      { value: "west_africa", label: "West Africa" },
      { value: "east_africa", label: "East Africa" },
    ],
  },
  {
    label: "Polar / Other",
    regions: [
      { value: "arctic", label: "Arctic" },
    ],
  },
];

const FILTER_REGIONS: { value: string; label: string; group?: string }[] =
  REGION_FILTER_GROUPS.flatMap((g) =>
    g.regions.map((r) => ({ ...r, group: g.label })),
  );

/* ── Helpers ─────────────────────────────────────────────── */

/** Smooth detailed whale silhouette PNGs (/whale_detailed_smooth_icons/).
 *  Only 9 species have these so far — others fall back to the whale tail logo. */
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

function VerifyWhaleIcon({ species, size = 20 }: { species: string | null; size?: number }) {
  const smoothFile = species ? SMOOTH_ICON_FILES[species] : null;
  if (smoothFile) {
    return (
      <Image
        src={`/whale_detailed_smooth_icons/${smoothFile}`}
        alt={species!.replace(/_/g, " ")}
        width={size}
        height={size}
        className="inline-block object-contain"
        style={{ filter: "invert(1) brightness(0.7)" }}
        aria-hidden="true"
      />
    );
  }
  return (
    <Image
      src="/whale_watch_logo.png"
      alt="Whale tail"
      width={size}
      height={size}
      className="inline-block object-contain opacity-50"
      aria-hidden="true"
    />
  );
}

function fmtSpecies(s: string | null): string {
  if (!s) return "Unknown species";
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function confidencePct(c: number | null): string {
  if (c === null || c === undefined) return "—";
  return `${Math.round(c * 100)}%`;
}

/* ── Refine Panel ────────────────────────────────────────── */

function RefinePanel({
  submission,
  onSubmit,
  onCancel,
}: {
  submission: Submission;
  onSubmit: (species: string, notes: string) => void;
  onCancel: () => void;
}) {
  const [species, setSpecies] = useState(
    submission.model_species ?? submission.species_guess ?? "",
  );
  const [speciesLabel, setSpeciesLabel] = useState(
    fmtSpecies(submission.model_species ?? submission.species_guess),
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  const [notes, setNotes] = useState("");
  /* Lightbox photo state (unused in refine panel but required by SpeciesPicker) */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_lbPhoto, setLbPhoto] = useState<string | null>(null);

  return (
    <div
      className="absolute inset-0 z-30 flex items-center justify-center bg-black/60 backdrop-blur-sm rounded-2xl"
      onPointerDown={(e) => e.stopPropagation()}
      onPointerMove={(e) => e.stopPropagation()}
      onPointerUp={(e) => e.stopPropagation()}
    >
      <div className="w-[90%] max-w-sm bg-slate-800 border border-teal-500/40 rounded-xl p-5 shadow-2xl max-h-[85%] overflow-y-auto">
        <div className="flex items-center gap-2 mb-4">
          <div className="p-1.5 rounded-lg bg-purple-500/20">
            <IconInfo className="h-5 w-5 text-purple-400" />
          </div>
          <h3 className="text-lg font-bold text-white">Refine ID</h3>
        </div>

        <p className="text-sm text-slate-400 mb-3">
          Suggest a corrected species identification for this sighting.
        </p>

        {/* Species picker — full ID wizard */}
        <label className="block text-xs font-medium text-slate-400 mb-1">
          Suggested species
        </label>
        <div className="mb-3">
          <SpeciesPicker
            value={speciesLabel}
            onChange={(sel) => {
              setSpecies(sel.value);
              setSpeciesLabel(sel.label);
              setPickerOpen(false);
            }}
            open={pickerOpen}
            onOpenChange={setPickerOpen}
            onLightbox={setLbPhoto}
          />
        </div>

        {/* Notes */}
        <label className="block text-xs font-medium text-slate-400 mb-1">
          Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="Describe what you see..."
          className="w-full rounded-lg bg-slate-900 border border-slate-600 text-white
                     px-3 py-2 text-sm mb-4 resize-none focus:border-teal-500
                     focus:ring-1 focus:ring-teal-500 outline-none"
        />

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-lg bg-slate-700 text-slate-300
                       text-sm font-medium hover:bg-slate-600 transition"
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(species, notes)}
            disabled={!species}
            className="flex-1 py-2 rounded-lg bg-purple-600 text-white text-sm
                       font-semibold hover:bg-purple-500 transition
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Submit Refinement
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Zone indicators (swipe direction overlays) ──────────── */

function SwipeOverlay({
  dir,
  opacity,
}: {
  dir: "left" | "right" | "up";
  opacity: number;
}) {
  if (dir === "left") {
    return (
      <div
        className="absolute inset-0 rounded-2xl flex items-center justify-center pointer-events-none z-20"
        style={{
          background: `rgba(239,68,68,${opacity * 0.4})`,
          opacity,
        }}
      >
        <div className="bg-red-500/90 rounded-full p-4 shadow-lg">
          <svg viewBox="0 0 24 24" className="h-12 w-12 text-white" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <span className="absolute bottom-8 text-red-200 font-bold text-lg tracking-wide">
          DISAGREE
        </span>
      </div>
    );
  }
  if (dir === "right") {
    return (
      <div
        className="absolute inset-0 rounded-2xl flex items-center justify-center pointer-events-none z-20"
        style={{
          background: `rgba(16,185,129,${opacity * 0.4})`,
          opacity,
        }}
      >
        <div className="bg-emerald-500/90 rounded-full p-4 shadow-lg">
          <IconCheck className="h-12 w-12 text-white" />
        </div>
        <span className="absolute bottom-8 text-emerald-200 font-bold text-lg tracking-wide">
          AGREE
        </span>
      </div>
    );
  }
  /* up */
  return (
    <div
      className="absolute inset-0 rounded-2xl flex items-center justify-center pointer-events-none z-20"
      style={{
        background: `rgba(168,85,247,${opacity * 0.4})`,
        opacity,
      }}
    >
      <div className="bg-purple-500/90 rounded-full p-4 shadow-lg">
        <IconInfo className="h-12 w-12 text-white" />
      </div>
      <span className="absolute bottom-8 text-purple-200 font-bold text-lg tracking-wide">
        REFINE
      </span>
    </div>
  );
}

/* ── Swipeable Card ──────────────────────────────────────── */

function SwipeCard({
  submission,
  onVote,
  isTop,
  autoRefine = false,
}: {
  submission: Submission;
  onVote: (vote: VoteType, species?: string, notes?: string) => void;
  isTop: boolean;
  autoRefine?: boolean;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState({ x: 0, y: 0, active: false });
  const [flyDir, setFlyDir] = useState<SwipeDir>(null);
  const [showRefine, setShowRefine] = useState(false);
  const startRef = useRef({ x: 0, y: 0, t: 0 });

  /* Auto-open refine panel for deep-linked submissions */
  useEffect(() => {
    if (isTop && autoRefine) {
      setShowRefine(true);
    }
  }, [isTop, autoRefine]);

  /* ── Onboarding demo wiggle (once per card-stack session) ─── */
  const [demoX, setDemoX] = useState(0);
  const [demoY, setDemoY] = useState(0);
  const demoRan = useRef(false);
  useEffect(() => {
    if (!isTop || demoRan.current || autoRefine) return;
    demoRan.current = true;
    const steps: { x: number; y: number; delay: number }[] = [
      { x: -130, y: 0, delay: 600 },
      { x: -130, y: 0, delay: 1400 },
      { x: 0, y: 0, delay: 1800 },
      { x: 130, y: 0, delay: 2600 },
      { x: 130, y: 0, delay: 3400 },
      { x: 0, y: 0, delay: 3800 },
      { x: 0, y: -110, delay: 4600 },
      { x: 0, y: -110, delay: 5400 },
      { x: 0, y: 0, delay: 5800 },
    ];
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (const s of steps) {
      timers.push(setTimeout(() => { setDemoX(s.x); setDemoY(s.y); }, s.delay));
    }
    return () => timers.forEach(clearTimeout);
  }, [isTop]);

  /* Listen for external refine trigger (from bottom button bar) */
  useEffect(() => {
    const el = cardRef.current;
    if (!el || !isTop) return;
    const handler = () => {
      setFlyDir("up");
      setShowRefine(true);
    };
    el.addEventListener("open-refine", handler);
    return () => el.removeEventListener("open-refine", handler);
  }, [isTop]);

  /* Which direction indicator to show? */
  const activeDir: SwipeDir =
    flyDir ??
    (drag.active
      ? Math.abs(drag.x) > Math.abs(drag.y) * 1.5
        ? drag.x > 30
          ? "right"
          : drag.x < -30
            ? "left"
            : null
        : drag.y < -30
          ? "up"
          : null
      : demoY < 0 ? "up" : demoX > 0 ? "right" : demoX < 0 ? "left" : null);

  const overlayOpacity = flyDir
    ? 1
    : drag.active
      ? Math.min(1, Math.max(Math.abs(drag.x), Math.abs(drag.y) * 0.8) / SWIPE_THRESHOLD)
      : (demoX !== 0 || demoY !== 0)
        ? Math.min(1, Math.max(Math.abs(demoX), Math.abs(demoY)) / SWIPE_THRESHOLD)
        : 0;

  /* ── Touch / pointer handlers ───── */
  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!isTop || showRefine) return;
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
      startRef.current = { x: e.clientX, y: e.clientY, t: Date.now() };
      setDrag({ x: 0, y: 0, active: true });
    },
    [isTop, showRefine],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!drag.active) return;
      setDrag({
        x: e.clientX - startRef.current.x,
        y: e.clientY - startRef.current.y,
        active: true,
      });
    },
    [drag.active],
  );

  const onPointerUp = useCallback(() => {
    if (!drag.active) return;
    const elapsed = Date.now() - startRef.current.t;
    const vx = Math.abs(drag.x) / elapsed;
    const vy = Math.abs(drag.y) / elapsed;

    const horizontalSwipe =
      Math.abs(drag.x) > SWIPE_THRESHOLD || vx > SWIPE_VELOCITY;
    const verticalSwipe =
      -drag.y > SWIPE_THRESHOLD || vy > SWIPE_VELOCITY;
    const isHorizontal = Math.abs(drag.x) > Math.abs(drag.y) * 1.2;

    if (isHorizontal && horizontalSwipe) {
      const dir: SwipeDir = drag.x > 0 ? "right" : "left";
      setFlyDir(dir);
      setTimeout(
        () => onVote(dir === "right" ? "agree" : "disagree"),
        300,
      );
    } else if (!isHorizontal && verticalSwipe && drag.y < 0) {
      setFlyDir("up");
      setShowRefine(true);
    } else {
      setDrag({ x: 0, y: 0, active: false });
    }
  }, [drag, onVote]);

  /* Refine submit */
  const handleRefineSubmit = useCallback(
    (species: string, notes: string) => {
      setShowRefine(false);
      onVote("refine", species, notes);
    },
    [onVote],
  );

  const handleRefineCancel = useCallback(() => {
    setShowRefine(false);
    setFlyDir(null);
    setDrag({ x: 0, y: 0, active: false });
  }, []);

  /* Transform computation — keep card in place when refine panel is open */
  const flying = flyDir && !showRefine;
  const effectiveX = drag.active ? drag.x : demoX;
  const tx = flying ? (flyDir === "left" ? -FLY_DISTANCE : flyDir === "right" ? FLY_DISTANCE : 0) : effectiveX;
  const ty = flying ? (flyDir === "up" ? -FLY_DISTANCE / 2 : 0) : (drag.active ? drag.y * 0.3 : demoY);
  const rot = tx * 0.04;

  const species = submission.model_species ?? submission.species_guess;
  const photoUrl = submission.has_photo
    ? `${API_BASE}/api/v1/submissions/${submission.id}/photo`
    : null;
  const hasLocation =
    submission.lat != null && submission.lon != null;

  /* Reverse-geocode for a human-readable place name */
  const [placeName, setPlaceName] = useState<string | null>(null);
  useEffect(() => {
    if (!hasLocation) return;
    setPlaceName(null);
    const ac = new AbortController();
    fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${submission.lat}&lon=${submission.lon}&format=json&zoom=10`,
      { signal: ac.signal, headers: { "Accept-Language": "en" } },
    )
      .then((r) => r.json())
      .then((data) => {
        const a = data.address;
        const name =
          a?.city ?? a?.town ?? a?.county ?? a?.state ??
          data.display_name?.split(",").slice(0, 2).join(",").trim();
        setPlaceName(
          name ||
            `${submission.lat!.toFixed(2)}°, ${submission.lon!.toFixed(2)}°`,
        );
      })
      .catch(() => {
        setPlaceName(
          `${submission.lat!.toFixed(2)}°, ${submission.lon!.toFixed(2)}°`,
        );
      });
    return () => ac.abort();
  }, [hasLocation, submission.lat, submission.lon]);
  const status = submission.verification_status ?? "unverified";
  const statusStyle = STATUS_STYLES[status] ?? STATUS_STYLES.unverified;
  const riskClass = RISK_COLOURS[submission.risk_category ?? ""] ?? "bg-slate-600";

  return (
    <div
      ref={cardRef}
      className="absolute inset-0 select-none touch-none"
      data-top-card={isTop ? "" : undefined}
      style={{
        transform: `translate(${tx}px, ${ty}px) rotate(${rot}deg)`,
        transition: flying
          ? "transform 0.4s cubic-bezier(0.2, 0, 0, 1), opacity 0.4s"
          : drag.active
            ? "none"
            : "transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
        opacity: flying ? 0 : 1,
        zIndex: isTop ? 10 : 5,
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      {/* Card body */}
      <div className="h-full rounded-2xl bg-slate-800/95 border border-slate-700/60
                       shadow-2xl overflow-hidden flex flex-col relative backdrop-blur-sm">
        {/* Swipe direction overlay */}
        {activeDir && (
          <SwipeOverlay dir={activeDir} opacity={overlayOpacity} />
        )}

        {/* Refine panel */}
        {showRefine && (
          <RefinePanel
            submission={submission}
            onSubmit={handleRefineSubmit}
            onCancel={handleRefineCancel}
          />
        )}

        {/* ── Photo hero ─── */}
        <div className="relative h-[40%] min-h-[160px] bg-slate-900 flex-shrink-0">
          {photoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photoUrl}
              alt={fmtSpecies(species)}
              className="w-full h-full object-cover"
              draggable={false}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-800 to-slate-900">
              <VerifyWhaleIcon species={species} size={96} />
            </div>
          )}
          {/* Gradient scrim */}
          <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-slate-800/95 to-transparent" />

          {/* Top badges */}
          <div className="absolute top-3 left-3 flex gap-2 z-10">
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${statusStyle.bg} ${statusStyle.text}`}>
              {status}
            </span>
            {submission.interaction_type && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800/80 text-slate-300">
                {submission.interaction_type}
              </span>
            )}
          </div>

          {/* Media indicators */}
          <div className="absolute top-3 right-3 flex gap-1.5 z-10">
            {submission.has_photo && (
              <div className="p-1 rounded-full bg-slate-900/70">
                <IconCamera className="h-4 w-4 text-teal-400" />
              </div>
            )}
            {submission.has_audio && (
              <div className="p-1 rounded-full bg-slate-900/70">
                <IconMicrophone className="h-4 w-4 text-purple-400" />
              </div>
            )}
          </div>

          {/* Species name overlaid on scrim */}
          <div className="absolute bottom-3 left-4 right-4">
            <h3 className="text-xl font-bold text-white leading-tight drop-shadow-lg">
              {fmtSpecies(species)}
            </h3>
            {submission.scientific_name && (
              <p className="text-sm text-slate-300 italic mt-0.5">
                {submission.scientific_name}
              </p>
            )}
          </div>
        </div>

        {/* ── Detail section ─── */}
        <div className="flex-1 min-h-0 p-4 overflow-y-auto space-y-3">
          {/* Risk + confidence row */}
          <div className="flex gap-3">
            {/* Risk category */}
            <div className="flex-1 rounded-lg bg-slate-900/60 p-2.5">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                Collision Risk
              </p>
              <div className="flex items-center gap-2">
                <div className={`h-3 w-3 rounded-full ${riskClass}`} />
                <span className="text-sm font-semibold text-white capitalize">
                  {submission.risk_category ?? "N/A"}
                </span>
                {submission.risk_score !== null && (
                  <span className="text-xs text-slate-400 ml-auto">
                    {(submission.risk_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
            {/* Confidence */}
            <div className="flex-1 rounded-lg bg-slate-900/60 p-2.5">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                Model Confidence
              </p>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-teal-400">
                  {confidencePct(submission.model_confidence)}
                </span>
                {submission.model_source && (
                  <span className="text-xs text-slate-500 ml-auto">
                    {submission.model_source}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Community votes */}
          <div className="flex items-center gap-3 rounded-lg bg-slate-900/60 p-2.5">
            <div className="flex items-center gap-1.5">
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 text-emerald-400">
                <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
              </svg>
              <span className="text-sm font-semibold text-emerald-400">
                {submission.community_agree}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 text-red-400">
                <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.106-1.79l-.05-.025A4 4 0 0011.057 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
              </svg>
              <span className="text-sm font-semibold text-red-400">
                {submission.community_disagree}
              </span>
            </div>
            {submission.verification_score !== null && (
              <div className="ml-auto flex items-center gap-1.5">
                <span className="text-xs text-slate-500">Trust</span>
                <div className="w-16 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-teal-500"
                    style={{ width: `${submission.verification_score}%` }}
                  />
                </div>
                <span className="text-xs text-slate-400">
                  {Math.round(submission.verification_score)}%
                </span>
              </div>
            )}
          </div>

          {/* Bio observations */}
          <div className="flex flex-wrap gap-1.5">
            {submission.behavior && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/15 text-blue-300 border border-blue-500/20">
                {submission.behavior}
              </span>
            )}
            {submission.group_size && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-teal-500/15 text-teal-300 border border-teal-500/20">
                Group: {submission.group_size}
              </span>
            )}
            {submission.life_stage && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/15 text-violet-300 border border-violet-500/20">
                {submission.life_stage}
              </span>
            )}
            {submission.calf_present && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-pink-500/15 text-pink-300 border border-pink-500/20">
                Calf present
              </span>
            )}
            {submission.sea_state_beaufort !== null && submission.sea_state_beaufort !== undefined && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/20">
                Sea {submission.sea_state_beaufort}
              </span>
            )}
            {submission.observation_platform && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-300 border border-amber-500/20">
                {submission.observation_platform}
              </span>
            )}
            {submission.direction_of_travel && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/20">
                Travel: {submission.direction_of_travel}
              </span>
            )}
          </div>

          {/* Observer + location */}
          <div className="flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              {submission.submitter_avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`${API_BASE}${submission.submitter_avatar_url}`}
                  alt=""
                  className="h-5 w-5 rounded-full ring-1 ring-slate-600"
                />
              ) : (
                <div className="h-5 w-5 rounded-full bg-slate-700 flex items-center justify-center text-[9px] font-bold text-slate-400">
                  {submission.submitter_name?.[0]?.toUpperCase() ?? "?"}
                </div>
              )}
              <span className="text-slate-400">
                {submission.submitter_name ?? "Anonymous"}
              </span>
              {submission.submitter_is_moderator && (
                <IconShield className="h-3.5 w-3.5 text-amber-400" />
              )}
            </div>
            <span>{timeAgo(submission.created_at)}</span>
          </div>

        </div>

        {/* ── Location & Map ─── */}
        <div className="flex-shrink-0 border-t border-slate-700/50">
          {/* Place name row */}
          <div className="px-3 py-1.5 flex items-center gap-2">
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              className={`h-3.5 w-3.5 flex-shrink-0 ${
                hasLocation ? "text-teal-400" : "text-slate-600"
              }`}
            >
              <path
                fillRule="evenodd"
                d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
                clipRule="evenodd"
              />
            </svg>
            {hasLocation ? (
              <span className="text-xs text-slate-300 truncate">
                {placeName ?? `${submission.lat!.toFixed(3)}°, ${submission.lon!.toFixed(3)}°`}
              </span>
            ) : (
              <span className="text-xs text-slate-500 italic">
                No location reported
              </span>
            )}
          </div>

          {/* Interactive map (OpenStreetMap iframe — zoom + pan, dark-themed) */}
          {hasLocation && (
            <div
              className="h-[110px] mx-2 mb-2 rounded-lg overflow-hidden ring-1 ring-teal-500/30"
              style={{ filter: "invert(0.92) hue-rotate(180deg) saturate(1.6) brightness(0.7) contrast(1.2)" }}
              onPointerDownCapture={(e) => e.stopPropagation()}
              onPointerMoveCapture={(e) => e.stopPropagation()}
              onPointerUpCapture={(e) => e.stopPropagation()}
            >
              <iframe
                title="Sighting location"
                width="100%"
                height="110"
                style={{ border: 0, display: "block" }}
                loading="lazy"
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${submission.lon! - 4},${submission.lat! - 2},${submission.lon! + 4},${submission.lat! + 2}&layer=mapnik&marker=${submission.lat},${submission.lon}`}
              />
            </div>
          )}
        </div>

        {/* ── Action hint bar (inline card actions) ─── */}
        <div className="flex-shrink-0 border-t border-slate-700/50 px-3 py-2
                        flex items-center justify-between">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onVote("disagree"); }}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5
                       bg-red-500/10 border border-red-500/20 text-red-400
                       text-xs font-medium transition hover:bg-red-500/20"
          >
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor">
              <path d="M9.78 4.22a.75.75 0 010 1.06L7.06 8l2.72 2.72a.75.75 0 11-1.06 1.06L5.22 8.53a.75.75 0 010-1.06l3.5-3.5a.75.75 0 011.06 0z" />
            </svg>
            Disagree
          </button>
          <Link
            href={`/submissions/${submission.id}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5
                       bg-slate-500/10 border border-slate-500/30 text-slate-300
                       text-xs font-semibold transition hover:bg-slate-500/20"
          >
            <IconInfo className="h-3.5 w-3.5" />
            More Info
          </Link>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onVote("agree"); }}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5
                       bg-emerald-500/10 border border-emerald-500/20 text-emerald-400
                       text-xs font-medium transition hover:bg-emerald-500/20"
          >
            Agree
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 rotate-180" fill="currentColor">
              <path d="M9.78 4.22a.75.75 0 010 1.06L7.06 8l2.72 2.72a.75.75 0 11-1.06 1.06L5.22 8.53a.75.75 0 010-1.06l3.5-3.5a.75.75 0 011.06 0z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Empty / Loading / Login States ──────────────────────── */

function EmptyState({ reviewed }: { reviewed: number }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6">
      <div className="p-4 rounded-full bg-emerald-500/10 mb-4">
        <IconCheck className="h-12 w-12 text-emerald-400" />
      </div>
      <h2 className="text-xl font-bold text-white mb-2">All caught up!</h2>
      <p className="text-slate-400 text-sm max-w-xs">
        {reviewed > 0
          ? `Great work! You reviewed ${reviewed} sighting${reviewed !== 1 ? "s" : ""}. Check back later for new submissions.`
          : "No unverified sightings right now. Check back later for new submissions."}
      </p>
      <Link
        href="/community"
        className="mt-6 px-5 py-2 rounded-lg bg-teal-600 text-white text-sm
                   font-medium hover:bg-teal-500 transition"
      >
        Back to Community
      </Link>
    </div>
  );
}

function LoginPrompt() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6">
      <div className="p-4 rounded-full bg-amber-500/10 mb-4">
        <IconWarning className="h-12 w-12 text-amber-400" />
      </div>
      <h2 className="text-xl font-bold text-white mb-2">Sign in to verify</h2>
      <p className="text-slate-400 text-sm max-w-xs mb-6">
        Community verification requires an account. Sign in to start reviewing sightings and earn reputation.
      </p>
      <Link
        href="/auth"
        className="px-6 py-2.5 rounded-lg bg-teal-600 text-white text-sm
                   font-semibold hover:bg-teal-500 transition"
      >
        Sign In
      </Link>
    </div>
  );
}

/* ── Toast Feedback ──────────────────────────────────────── */

function VoteToast({
  vote,
  visible,
}: {
  vote: VoteType | null;
  visible: boolean;
}) {
  if (!vote || !visible) return null;
  const config: Record<VoteType, { icon: React.ReactNode; label: string; cls: string }> = {
    agree: {
      icon: <IconCheck className="h-5 w-5" />,
      label: "Agreed  +2 rep",
      cls: "bg-emerald-600 text-white",
    },
    disagree: {
      icon: (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
      label: "Disagreed  +2 rep",
      cls: "bg-red-600 text-white",
    },
    refine: {
      icon: <IconInfo className="h-5 w-5" />,
      label: "Refinement submitted  +2 rep",
      cls: "bg-purple-600 text-white",
    },
  };
  const c = config[vote];
  return (
    <div
      className={`fixed top-20 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2
                  px-4 py-2 rounded-full shadow-xl text-sm font-semibold
                  transition-all duration-300 ${c.cls}
                  ${visible ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4"}`}
    >
      {c.icon}
      {c.label}
    </div>
  );
}

/* ── Stats bar ───────────────────────────────────────────── */

function StatsBar({
  reviewed,
  remaining,
}: {
  reviewed: number;
  remaining: number;
}) {
  const total = reviewed + remaining;
  const pct = total > 0 ? (reviewed / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3 px-1 mb-3">
      <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-teal-500 to-emerald-400 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-slate-500 whitespace-nowrap">
        {reviewed} reviewed
      </span>
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────── */

export default function VerifyPage() {
  const { user, token } = useAuth();

  const searchParams = useSearchParams();
  const targetId = searchParams.get("id");

  const [queue, setQueue] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewed, setReviewed] = useState(0);
  const [lastVote, setLastVote] = useState<VoteType | null>(null);
  const [toastVisible, setToastVisible] = useState(false);
  const [exhausted, setExhausted] = useState(false);
  const reviewedIds = useRef<Set<string>>(new Set());
  const fetchingMore = useRef(false);
  const offsetRef = useRef(0);
  const targetSub = useRef<Submission | null>(null);
  const targetFetched = useRef(false);
  const [autoRefine, setAutoRefine] = useState(false);

  /* ── Filter state ──────────────────────────────────────── */
  const [filterSpecies, setFilterSpecies] = useState("");
  const [filterRegion, setFilterRegion] = useState("");
  const [filterSince, setFilterSince] = useState("");
  const [filterUntil, setFilterUntil] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilterCount =
    (filterSpecies ? 1 : 0)
    + (filterRegion ? 1 : 0)
    + (filterSince ? 1 : 0)
    + (filterUntil ? 1 : 0);

  /* Fetch queue of unverified public submissions */
  const fetchQueue = useCallback(async (append = false) => {
    if (!token) {
      setLoading(false);
      return;
    }
    if (fetchingMore.current && append) return;
    if (append) fetchingMore.current = true;
    if (!append) {
      setExhausted(false);
      offsetRef.current = 0;
    }
    try {
      const offset = append ? offsetRef.current : 0;
      const params = new URLSearchParams({
        status: "unverified",
        limit: "20",
        offset: String(offset),
      });
      if (user?.id) params.set("exclude_user_id", String(user.id));
      if (filterSpecies) params.set("species", filterSpecies);
      if (filterSince) params.set("since", filterSince);
      if (filterUntil) params.set("until", filterUntil);
      if (filterRegion) {
        const bbox = REGION_BBOX[filterRegion];
        if (bbox) {
          params.set("lat_min", String(bbox[0]));
          params.set("lat_max", String(bbox[1]));
          params.set("lon_min", String(bbox[2]));
          params.set("lon_max", String(bbox[3]));
        }
      }

      const res = await fetch(
        `${API_BASE}/api/v1/submissions/public?${params}`,
      );
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      const items: Submission[] = data.submissions ?? [];

      /* Server already excludes user's own — just filter reviewed */
      const filtered = items.filter(
        (s) => !reviewedIds.current.has(s.id),
      );

      /* Exhausted = server returned 0 items (nothing left in DB) */
      if (items.length === 0) {
        setExhausted(true);
        if (!append) {
          /* Keep deep-linked target at front even when server returns 0 */
          const ts = targetSub.current;
          setQueue(ts ? [ts] : []);
        }
      } else {
        /* Advance offset for next page */
        offsetRef.current = offset + items.length;

        if (append) {
          setQueue((q) => {
            const existingIds = new Set(q.map((s) => s.id));
            const newItems = filtered.filter((s) => !existingIds.has(s.id));
            return [...q, ...newItems];
          });
        } else {
          /* Always keep deep-linked target at position 0 */
          const ts = targetSub.current;
          if (ts) {
            const withoutTarget = filtered.filter((s) => s.id !== ts.id);
            setQueue([ts, ...withoutTarget]);
          } else {
            setQueue(filtered);
          }
        }
      }
    } catch {
      /* silently fail — empty state shown */
    } finally {
      setLoading(false);
      fetchingMore.current = false;
    }
  }, [token, user?.id, filterSpecies, filterRegion, filterSince, filterUntil]);

  /* Initial load: if deep-linked, fetch target first then normal queue */
  useEffect(() => {
    if (!token) { setLoading(false); return; }
    if (targetId && !targetFetched.current) {
      targetFetched.current = true;
      (async () => {
        try {
          const res = await fetch(
            `${API_BASE}/api/v1/submissions/${targetId}`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (res.ok) {
            const sub: Submission = await res.json();
            targetSub.current = sub;
            setAutoRefine(true);
          }
        } catch {
          /* target fetch failed — fall through to normal queue */
        }
        fetchQueue();
      })();
      return;
    }
    fetchQueue();
  }, [fetchQueue, targetId, token]);

  /* Auto-fetch more when queue gets low */
  useEffect(() => {
    if (queue.length <= 3 && !exhausted && !loading && token) {
      fetchQueue(true);
    }
  }, [queue.length, exhausted, loading, token, fetchQueue]);

  /* Submit vote to API */
  const submitVote = useCallback(
    async (
      submissionId: string,
      vote: VoteType,
      species?: string,
      notes?: string,
    ) => {
      if (!token) return;
      try {
        await fetch(
          `${API_BASE}/api/v1/submissions/${submissionId}/vote`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              vote,
              notes: notes || null,
              species_suggestion: vote === "refine" ? species : null,
            }),
          },
        );
      } catch {
        /* vote will be silently lost — acceptable for swipe UX */
      }
    },
    [token],
  );

  /* Handle card vote */
  const handleVote = useCallback(
    (vote: VoteType, species?: string, notes?: string) => {
      const current = queue[0];
      if (!current) return;

      /* Track this submission as reviewed */
      reviewedIds.current.add(current.id);
      setAutoRefine(false);

      /* Fire API call (non-blocking) */
      submitVote(current.id, vote, species, notes);

      /* Show toast */
      setLastVote(vote);
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 1500);

      /* Advance queue */
      setTimeout(() => {
        setQueue((q) => q.slice(1));
        setReviewed((r) => r + 1);
      }, 400);
    },
    [queue, submitVote],
  );

  /* Keyboard shortcuts */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === "ArrowLeft" || e.key === "a") handleVote("disagree");
      else if (e.key === "ArrowRight" || e.key === "d") handleVote("agree");
      else if (e.key === "ArrowUp" || e.key === "w" || e.key === "r") {
        /* Open the refine panel on the current card */
        const topCard = document.querySelector('[data-top-card]');
        if (topCard) topCard.dispatchEvent(new CustomEvent('open-refine'));
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleVote, queue]);

  /* ── Render ─── */

  if (!token) {
    return (
      <main className="min-h-screen bg-[#0a1628] pt-20 flex justify-center">
        <div className="w-full max-w-md px-4">
          <LoginPrompt />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0a1628] pt-20 pb-8 flex flex-col items-center overflow-x-clip">
      <VoteToast vote={lastVote} visible={toastVisible} />

      {/* Header */}
      <div className="w-full max-w-md px-4 mb-4">
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-teal-500/20">
              <IconShield className="h-5 w-5 text-teal-400" />
            </div>
            Quick Review
          </h1>
          <Link
            href="/community"
            className="text-sm text-slate-500 hover:text-slate-300 transition"
          >
            Full Feed
          </Link>
        </div>
        <p className="text-sm text-slate-500 mb-3">
          Swipe right to agree, left to disagree, up to refine.
        </p>
        <StatsBar reviewed={reviewed} remaining={queue.length} />

        {/* ── Filter bar ─────────────────────────────────── */}
        <div className="mt-3">
          <button
            onClick={() => setFiltersOpen((o) => !o)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
              activeFilterCount > 0
                ? "bg-teal-500/20 text-teal-300 border border-teal-500/40"
                : "bg-slate-800/60 text-slate-400 border border-slate-700/50 hover:text-slate-300"
            }`}
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
              <path fillRule="evenodd" d="M2.628 1.601C5.028 1.206 7.49 1 10 1s4.973.206 7.372.601a.75.75 0 01.628.74v2.288a2.25 2.25 0 01-.659 1.59l-4.682 4.683a2.25 2.25 0 00-.659 1.59v3.037c0 .684-.31 1.33-.844 1.757l-1.937 1.55A.75.75 0 018 18.25v-5.757a2.25 2.25 0 00-.659-1.591L2.659 6.22A2.25 2.25 0 012 4.629V2.34a.75.75 0 01.628-.74z" clipRule="evenodd" />
            </svg>
            Filters
            {activeFilterCount > 0 && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-teal-500 text-[10px] font-bold text-white">
                {activeFilterCount}
              </span>
            )}
            <svg viewBox="0 0 20 20" fill="currentColor" className={`h-3 w-3 transition ${filtersOpen ? "rotate-180" : ""}`}>
              <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
            </svg>
          </button>

          {/* Collapsible filter panel */}
          <div className={`overflow-hidden transition-all duration-200 ${filtersOpen ? "max-h-60 mt-2.5" : "max-h-0"}`}>
            <div className="space-y-2 rounded-xl border border-ocean-800/40 bg-abyss-900/70 p-3 backdrop-blur-sm">
              {/* Species + Region row */}
              <div className="flex gap-2">
                <select
                  value={filterSpecies}
                  onChange={(e) => {
                    setFilterSpecies(e.target.value);
                    reviewedIds.current.clear();
                    setQueue([]);
                    setLoading(true);
                  }}
                  className="flex-1 rounded-lg border border-ocean-800/60 bg-abyss-900/80 px-2.5 py-[7px] text-xs text-white focus:border-teal-500 focus:outline-none [color-scheme:dark]"
                >
                  <option value="">All Species</option>
                  {SPECIES_FILTER_GROUPS.map((g) => (
                    <optgroup key={g.label} label={g.label}>
                      {g.species.map((sp) => (
                        <option key={sp} value={sp}>
                          {sp.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                <select
                  value={filterRegion}
                  onChange={(e) => {
                    setFilterRegion(e.target.value);
                    reviewedIds.current.clear();
                    setQueue([]);
                    setLoading(true);
                  }}
                  className="flex-1 rounded-lg border border-ocean-800/60 bg-abyss-900/80 px-2.5 py-[7px] text-xs text-white focus:border-teal-500 focus:outline-none [color-scheme:dark]"
                >
                  <option value="">All Regions</option>
                  {REGION_FILTER_GROUPS.map((g) => (
                    <optgroup key={g.label} label={g.label}>
                      {g.regions.map((r) => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              {/* Date row */}
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={filterSince}
                  onChange={(e) => {
                    setFilterSince(e.target.value);
                    reviewedIds.current.clear();
                    setQueue([]);
                    setLoading(true);
                  }}
                  className="flex-1 rounded-lg border border-ocean-800/60 bg-abyss-900/80 px-2.5 py-[7px] text-xs text-white focus:border-teal-500 focus:outline-none [color-scheme:dark]"
                  placeholder="From"
                  title="From date"
                />
                <span className="text-[10px] text-slate-600">–</span>
                <input
                  type="date"
                  value={filterUntil}
                  onChange={(e) => {
                    setFilterUntil(e.target.value);
                    reviewedIds.current.clear();
                    setQueue([]);
                    setLoading(true);
                  }}
                  className="flex-1 rounded-lg border border-ocean-800/60 bg-abyss-900/80 px-2.5 py-[7px] text-xs text-white focus:border-teal-500 focus:outline-none [color-scheme:dark]"
                  placeholder="Until"
                  title="Until date"
                />
              </div>

              {/* Active filters + clear */}
              {activeFilterCount > 0 && (
                <div className="flex items-center justify-between pt-0.5">
                  <div className="flex flex-wrap gap-1">
                    {filterSpecies && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-teal-500/15 px-2 py-0.5 text-[10px] text-teal-300">
                        {FILTER_SPECIES.find((s) => s.value === filterSpecies)?.label}
                        <button onClick={() => { setFilterSpecies(""); reviewedIds.current.clear(); setQueue([]); setLoading(true); }} className="hover:text-white">×</button>
                      </span>
                    )}
                    {filterRegion && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] text-blue-300">
                        {FILTER_REGIONS.find((r) => r.value === filterRegion)?.label}
                        <button onClick={() => { setFilterRegion(""); reviewedIds.current.clear(); setQueue([]); setLoading(true); }} className="hover:text-white">×</button>
                      </span>
                    )}
                    {(filterSince || filterUntil) && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/15 px-2 py-0.5 text-[10px] text-purple-300">
                        {filterSince || "…"} – {filterUntil || "…"}
                        <button onClick={() => { setFilterSince(""); setFilterUntil(""); reviewedIds.current.clear(); setQueue([]); setLoading(true); }} className="hover:text-white">×</button>
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      setFilterSpecies("");
                      setFilterRegion("");
                      setFilterSince("");
                      setFilterUntil("");
                      reviewedIds.current.clear();
                      setQueue([]);
                      setLoading(true);
                    }}
                    className="text-[10px] text-red-400/70 hover:text-red-300 transition"
                  >
                    Clear all
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Card stack + backdrop arrows */}
      <div className="relative w-full max-w-lg px-4 overflow-visible" style={{ height: `calc(100vh - ${filtersOpen ? "380px" : "230px"})`, maxHeight: 640, transition: "height 0.2s ease" }}>
        {/* ── Backdrop swipe-direction arrows (flanking the card) ─── */}
        {!loading && queue.length > 0 && (
          <>
            {/* Left — Disagree: triple stacked chevrons */}
            <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1
                            pointer-events-none z-[1] select-none">
              <div className="flex flex-col items-center">
                <div className="flex">
                  <svg viewBox="0 0 24 24" className="h-16 w-16 text-red-500/20" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                  <svg viewBox="0 0 24 24" className="h-16 w-16 -ml-9 text-red-500/35" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                  <svg viewBox="0 0 24 24" className="h-16 w-16 -ml-9 text-red-400/50" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                </div>
              </div>
            </div>
            {/* Right — Agree: triple stacked chevrons */}
            <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1
                            pointer-events-none z-[1] select-none">
              <div className="flex flex-col items-center">
                <div className="flex">
                  <svg viewBox="0 0 24 24" className="h-16 w-16 text-emerald-400/50" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  <svg viewBox="0 0 24 24" className="h-16 w-16 -ml-9 text-emerald-500/35" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  <svg viewBox="0 0 24 24" className="h-16 w-16 -ml-9 text-emerald-500/20" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
          </>
        )}
        {loading ? (
          <div className="h-full flex items-center justify-center">
            <div className="h-10 w-10 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : queue.length === 0 ? (
          <EmptyState reviewed={reviewed} />
        ) : (
          <>
            {/* Shadow card behind (next in queue) */}
            {queue.length > 1 && (
              <div className="absolute inset-x-3 top-2 bottom-0 rounded-2xl bg-slate-800/50 border border-slate-700/30" />
            )}
            {/* Active card */}
            <SwipeCard
              key={queue[0].id}
              submission={queue[0]}
              onVote={handleVote}
              isTop={true}
              autoRefine={autoRefine && queue[0].id === targetId}
            />
          </>
        )}
      </div>

      {/* Button bar (fallback for non-touch) */}
      {!loading && queue.length > 0 && (
        <div className="w-full max-w-md px-4 mt-4 flex justify-center gap-6">
          <button
            onClick={() => handleVote("disagree")}
            className="group p-4 rounded-full bg-slate-800 border border-red-500/30
                       hover:bg-red-500/20 hover:border-red-500/60 transition shadow-lg"
            title="Disagree (← or A)"
          >
            <svg viewBox="0 0 24 24" className="h-7 w-7 text-red-400 group-hover:text-red-300" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <button
            onClick={() => {
              /* Open refine panel on current card */
              const topCard = document.querySelector('[data-top-card]');
              if (topCard) topCard.dispatchEvent(new CustomEvent('open-refine'));
            }}
            className="group flex flex-col items-center gap-0.5 px-5 py-3 rounded-2xl
                       bg-purple-500/15 border-2 border-purple-500/40
                       hover:bg-purple-500/25 hover:border-purple-500/60
                       transition shadow-lg shadow-purple-500/10"
            title="Refine ID (↑ or R)"
          >
            <IconInfo className="h-7 w-7 text-purple-400 group-hover:text-purple-300" />
            <span className="text-[10px] font-semibold text-purple-300">Refine ID</span>
          </button>
          <button
            onClick={() => handleVote("agree")}
            className="group p-4 rounded-full bg-slate-800 border border-emerald-500/30
                       hover:bg-emerald-500/20 hover:border-emerald-500/60 transition shadow-lg"
            title="Agree (→ or D)"
          >
            <IconCheck className="h-7 w-7 text-emerald-400 group-hover:text-emerald-300" />
          </button>
        </div>
      )}

      {/* Keyboard hint */}
      {!loading && queue.length > 0 && (
        <p className="mt-3 text-[10px] text-slate-700 text-center">
          Keyboard: A / ← disagree &middot; R / ↑ refine &middot; D / → agree
        </p>
      )}
    </main>
  );
}
