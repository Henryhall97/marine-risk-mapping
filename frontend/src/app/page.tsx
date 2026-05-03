"use client";

import Link from "next/link";
import Image from "next/image";
import dynamic from "next/dynamic";
import { useState, useEffect, useRef } from "react";
import WaveDivider from "@/components/icons/WaveDivider";
import { API_BASE } from "@/lib/config";
import {
  IconMap,
  IconCamera,
  IconMicrophone,
  IconWhale,
  IconShip,
  IconWaves,
  IconWarning,
  IconShield,
  IconThermometer,
  IconChart,
  IconEye,
  IconUsers,
  IconLightbulb,
  IconPin,
  IconBuilding,
  IconMicroscope,
  IconAnchor,
  IconTrendUp,
  IconCalendarFuture,
  IconGlobe,
} from "@/components/icons/MarineIcons";
import {
  AnimatedWhaleTail,
  CausticRays,
  PodFormation,
  SonarPing,
  WhaleSongDivider,
} from "@/components/animations";
import RevealOnScroll from "@/components/RevealOnScroll";

// Species-specific detailed whale silhouette icons for tile backgrounds
const WHALE_ICON_FILES: Record<string, string> = {
  "North Atlantic Right Whale": "right_whale.png",
  "Humpback Whale": "humpback_whale.png",
  "Fin Whale": "fin_whale.png",
  "Blue Whale": "blue_whale.png",
  "Sei Whale": "sei_whale.png",
  "Sperm Whale": "sperm_whale.png",
  "Minke Whale": "minke_whale.png",
  "Killer Whale": "killer_whale_orca.png",
};

const OceanScene = dynamic(
  () => import("@/components/animations/OceanScene"),
  { ssr: false },
);
const BioluminescentTrail = dynamic(
  () => import("@/components/animations/BioluminescentTrail"),
  { ssr: false },
);

/* ── Animated counter ────────────────────────────────────── */

function Counter({
  end,
  suffix = "",
  precision = 0,
}: {
  end: number;
  suffix?: string;
  precision?: number;
}) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setStarted(true);
      },
      { threshold: 0.3 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
    const duration = 1400;
    const steps = 50;
    const inc = end / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += inc;
      if (current >= end) {
        setCount(end);
        clearInterval(timer);
      } else {
        setCount(precision > 0 ? current : Math.round(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [end, started, precision]);

  return (
    <span ref={ref}>
      {precision > 0 ? count.toFixed(precision) : count.toLocaleString("en-US")}
      {suffix}
    </span>
  );
}

/* ── Data ────────────────────────────────────────────────── */

const CoverageMap = dynamic(() => import("@/components/CoverageMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[340px] flex-col items-center justify-center gap-2 rounded-2xl border border-ocean-800/30 bg-abyss-900/50">
      <SonarPing size={56} ringCount={3} active />
      <span className="text-xs text-ocean-400/70">Loading coverage map…</span>
    </div>
  ),
});

const STATS = [
  { label: "H3 Cells Modelled", value: 1.8, suffix: "M+", precision: 1, icon: IconMap },
  { label: "AIS Pings Processed", value: 3.1, suffix: "B+", precision: 1, icon: IconShip },
  { label: "Cetacean Sightings", value: 1.0, suffix: "M+", precision: 1, icon: IconEye },
  { label: "Community Reports", value: 0, suffix: "+", precision: 0, icon: IconUsers },
  { label: "Species Tracked", value: 77, suffix: "", precision: 0, icon: IconWhale },
  { label: "Climate Decades Projected", value: 4, suffix: "", precision: 0, icon: IconTrendUp },
];

const FEATURES = [
  {
    Icon: IconMap,
    title: "Interactive Risk Map",
    desc: "Explore whale–vessel collision risk across the study area with 7 expert-weighted sub-scores per H3 cell. Toggle between macro heatmap overview and high-resolution hex detail.",
    href: "/map",
    cta: "Open Map",
    accent: "from-ocean-500 to-bioluminescent-500",
  },
  {
    Icon: IconCamera,
    title: "Photo Classification",
    desc: "Upload a whale photograph and our EfficientNet-B4 model identifies the species from 8 target classes. GPS-tagged photos get automatic H3 risk context.",
    href: "/classify",
    cta: "Classify Photo",
    accent: "from-seafoam-500 to-ocean-500",
  },
  {
    Icon: IconMicrophone,
    title: "Audio Classification",
    desc: "Submit underwater audio recordings and our XGBoost/CNN pipeline segments them into 4-second windows, extracting 64 acoustic features to identify whale species.",
    href: "/classify",
    cta: "Classify Audio",
    accent: "from-ocean-400 to-abyss-400",
  },
  {
    Icon: IconWhale,
    title: "Interaction Reports",
    desc: "Report whale interactions with optional photo and audio evidence. Our AI classifies the species, assesses local collision risk, and generates real-time advisories.",
    href: "/report",
    cta: "Report Interaction",
    accent: "from-coral-400 to-coral-600",
  },
  {
    Icon: IconShip,
    title: "Vessel Violations",
    desc: "Flag vessels speeding through active slow zones, entering marine protected areas, or suspected of disabling AIS transponders. Community-reviewed reports improve collision risk data.",
    href: "/report-vessel",
    cta: "Report Violation",
    accent: "from-red-500 to-orange-500",
  },
  {
    Icon: IconTrendUp,
    title: "Climate Forecasting",
    desc: "Explore how whale habitat and collision risk shift under CMIP6 climate scenarios (SSP2-4.5 & SSP5-8.5) from the 2030s through the 2080s. Compare projected SST, ocean conditions, and species distributions against today.",
    href: "/map",
    cta: "View Projections",
    accent: "from-purple-500 to-bioluminescent-500",
  },
];

const SUB_SCORES: {
  name: string;
  weight: string;
  pct: number;
  color: string;
  accent: string;
  desc: string;
}[] = [
  {
    name: "Traffic Intensity",
    weight: "25%",
    pct: 25,
    color: "bg-coral-500",
    accent: "text-coral-400",
    desc: "Vessel speed, volume, lethality potential, draft risk, night operations",
  },
  {
    name: "Cetacean Presence",
    weight: "25%",
    pct: 25,
    color: "bg-ocean-500",
    accent: "text-ocean-400",
    desc: "OBIS sighting records, baleen whale concentration, recent observations",
  },
  {
    name: "Proximity Blend",
    weight: "15%",
    pct: 15,
    color: "bg-bioluminescent-500",
    accent: "text-bioluminescent-400",
    desc: "Distance-decay from whales, strikes, and unprotected areas",
  },
  {
    name: "Strike History",
    weight: "10%",
    pct: 10,
    color: "bg-orange-500",
    accent: "text-orange-400",
    desc: "Historical NOAA ship strike records at this location",
  },
  {
    name: "Habitat Suitability",
    weight: "10%",
    pct: 10,
    color: "bg-seafoam-500",
    accent: "text-seafoam-400",
    desc: "Bathymetry (shelf edge) and primary productivity",
  },
  {
    name: "Protection Gap",
    weight: "10%",
    pct: 10,
    color: "bg-purple-500",
    accent: "text-purple-400",
    desc: "Distance from no-take zones, MPAs, and seasonal management areas",
  },
  {
    name: "Reference Risk",
    weight: "5%",
    pct: 5,
    color: "bg-abyss-400",
    accent: "text-abyss-300",
    desc: "Nisi et al. 2024 global collision risk baseline",
  },
];

const DATA_SOURCES: {
  name: string;
  source: string;
  Icon: typeof IconShip;
}[] = [
  { name: "AIS Vessel Traffic", source: "MarineCadastre", Icon: IconShip },
  { name: "Cetacean Sightings", source: "OBIS (~1M records)", Icon: IconWhale },
  { name: "Ship Strike Records", source: "NOAA (261 incidents)", Icon: IconWarning },
  { name: "Bathymetry", source: "GEBCO 2023", Icon: IconWaves },
  { name: "Ocean Covariates", source: "Copernicus (SST, MLD, SLA, PP)", Icon: IconThermometer },
  { name: "Marine Protected Areas", source: "NOAA MPA Inventory", Icon: IconShield },
  { name: "Speed Zones", source: "50 CFR \u00a7 224.105 (SMAs)", Icon: IconChart },
  { name: "CMIP6 Projections", source: "SSP2-4.5 & SSP5-8.5, 2030s–2080s", Icon: IconTrendUp },
  { name: "Community Reports", source: "Verified user submissions", Icon: IconUsers },
];

/* ── Deterministic seeded PRNG (avoids SSR/client hydration mismatch) ── */
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/* ── Decorative particles (bubbles) ──────────────────────── */
function Bubbles({ seed = 1 }: { seed?: number }) {
  const rng = seededRandom(seed);
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {[...Array(12)].map((_, i) => {
        const w = 6 + rng() * 14;
        const left = 5 + rng() * 90;
        const bottom = 10 + rng() * 30;
        const dur = 8 + rng() * 12;
        const delay = rng() * 8;
        return (
          <div
            key={i}
            className="absolute rounded-full bg-bioluminescent-400/[0.06]"
            style={{
              width: `${w}px`,
              height: `${w}px`,
              left: `${left}%`,
              bottom: `-${bottom}px`,
              animation: `bubble-rise ${dur}s ease-in ${delay}s infinite`,
            }}
          />
        );
      })}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────── */

export default function Home() {
  const [communityCount, setCommunityCount] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/submissions/public?limit=1&offset=0`)
      .then((r) => r.json())
      .then((d: { total?: number }) => {
        if (d.total) setCommunityCount(d.total);
      })
      .catch(() => {});
  }, []);

  return (
    <>
      {/* 3D underwater scene — fixed behind everything */}
      <OceanScene />

      <main className="relative z-10 min-h-screen">
        {/* Bioluminescent cursor trail (landing page only) */}
        <BioluminescentTrail />

        {/* ── Hero ── */}
        <section className="relative z-10 flex min-h-[90vh] flex-col items-center justify-center overflow-hidden px-6 pt-16 text-center">
          {/* Caustic light rays */}
          <CausticRays rayCount={6} opacity={0.035} />

          {/* Radial glow */}
          <div className="pointer-events-none absolute left-1/2 top-1/4 h-[700px] w-[700px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-ocean-500/[0.07] blur-[140px]" />
          <div className="pointer-events-none absolute right-1/4 top-2/3 h-[400px] w-[400px] rounded-full bg-bioluminescent-500/[0.05] blur-[100px]" />

          {/* Bubbles */}
          <Bubbles seed={42} />

          {/* Depth rings */}
          <div className="depth-ring pointer-events-none absolute left-1/2 top-1/3 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 opacity-[0.04]" />
          <div className="depth-ring pointer-events-none absolute left-1/2 top-1/3 h-[350px] w-[350px] -translate-x-1/2 -translate-y-1/2 opacity-[0.06]" style={{ animationDelay: "1s" }} />
          <div className="depth-ring pointer-events-none absolute left-1/2 top-1/3 h-[200px] w-[200px] -translate-x-1/2 -translate-y-1/2 opacity-[0.08]" style={{ animationDelay: "2s" }} />

          <div className="relative z-10 max-w-4xl animate-fade-in-up">
            {/* Logo */}
            <div className="mx-auto mb-8 flex items-center justify-center">
              <Image
                src="/whale_watch_logo.png"
                alt="Whale Watch"
                width={480}
                height={320}
                className="h-auto w-[320px] animate-float object-contain drop-shadow-[0_0_60px_rgba(34,211,238,0.3)] sm:w-[400px]"
                priority
              />
            </div>

            {/* Animated tail flick accent */}
            <div className="mx-auto mb-6 flex justify-center">
              <AnimatedWhaleTail
                className="h-10 w-16 text-ocean-400/40"
                glowColor="rgba(34,211,238,0.15)"
              />
            </div>

            <h1 className="font-display text-5xl font-extrabold leading-tight tracking-tight drop-shadow-[0_2px_10px_rgba(0,0,0,0.8)] sm:text-6xl lg:text-7xl">
              Track, classify &amp;{" "}
              <span className="text-ocean-bright">protect</span>{" "}
              marine life
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-300 drop-shadow-[0_1px_6px_rgba(0,0,0,0.7)]">
              Spot a whale, dolphin or porpoise — anywhere in the world?
              Snap a photo or record its call and our AI identifies the
              species instantly. Every sighting you share builds a global
              picture of cetacean life.
            </p>
            <p className="mx-auto mt-3 max-w-2xl text-base leading-relaxed text-slate-400 drop-shadow-[0_1px_6px_rgba(0,0,0,0.7)]">
              Across US waters — from Alaska to the Caribbean — we combine
              those sightings with AIS vessel traffic, satellite ocean data
              and climate projections to model where whales and ships are
              most likely to collide, so the right areas get protected.
            </p>

            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/map"
                className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-ocean-600 to-ocean-500 px-8 py-3.5 text-sm font-semibold text-white shadow-ocean-md transition-all hover:from-ocean-500 hover:to-bioluminescent-600 hover:shadow-ocean-lg"
              >
                <IconMap className="h-4 w-4 transition-transform group-hover:scale-110" />
                Explore the Map
              </Link>
              <Link
                href="/map?checkRisk=true"
                className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-coral-500 to-coral-400 px-8 py-3.5 text-sm font-semibold text-white shadow-md transition-all hover:from-coral-400 hover:to-orange-500 hover:shadow-lg"
              >
                <IconPin className="h-4 w-4" />
                Check My Risk
              </Link>
              <Link
                href="/report"
                className="glass-panel group flex items-center gap-2 rounded-xl px-8 py-3.5 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconWhale className="h-4 w-4" />
                Report Interaction
              </Link>
            </div>
          </div>

          {/* Animated stats */}
          <RevealOnScroll
            delay={200}
            className="relative z-10 mx-auto mt-24 grid max-w-5xl grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-6"
          >
            {STATS.map((s) => (
              <div
                key={s.label}
                className="stat-card glass-panel rounded-xl px-4 py-5 text-center transition-all hover:glow-ocean"
              >
                <s.icon className="mx-auto mb-2 h-5 w-5 text-ocean-400/60" />
                <p className="font-display text-2xl font-bold text-white sm:text-3xl">
                  {s.label === "Community Reports" && communityCount === null ? (
                    <span className="inline-block h-7 w-10 animate-pulse rounded bg-ocean-900/60" />
                  ) : (
                    <Counter
                      end={
                        s.label === "Community Reports"
                          ? (communityCount ?? 0)
                          : s.value
                      }
                      suffix={s.suffix}
                      precision={s.precision}
                    />
                  )}
                </p>
                <p className="mt-1 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  {s.label}
                </p>
              </div>
            ))}
          </RevealOnScroll>
        </section>

        {/* Wave divider: hero → problem */}
        <WaveDivider color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── The Problem ── */}
        <section className="relative bg-abyss-900/80 px-6 py-24 backdrop-blur-sm">
          <Bubbles seed={77} />
          <div className="relative z-10 mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-coral-400">
              The Problem
            </h2>
            <p className="mb-6 text-center font-display text-3xl font-bold tracking-tight text-white">
              Whales are being killed by ships
            </p>
            <p className="mx-auto mb-12 max-w-3xl text-center text-base leading-relaxed text-slate-300">
              Every year, large whales are struck and killed by commercial and
              recreational vessels. Most strikes go undetected — the crew often
              doesn&apos;t know it happened, and the whale sinks before it can be
              found. Scientists estimate that reported strikes represent only a
              fraction of the true number.
            </p>

            <RevealOnScroll className="grid gap-6 md:grid-cols-3">
              {/* Scale */}
              <div className="glass-panel rounded-2xl p-6 text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-coral-500/10">
                  <IconWarning className="h-6 w-6 text-coral-400" />
                </div>
                <p className="font-display text-3xl font-bold text-white">
                  20,000+
                </p>
                <p className="mt-1 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Estimated whale deaths from ship strikes per year globally
                </p>
                <p className="mt-3 text-xs leading-relaxed text-slate-400">
                  A 2024 study estimated that global ship strikes kill over
                  20,000 whales annually — far more than previous estimates
                  suggested. The vast majority are never recorded.
                </p>
              </div>

              {/* Why it happens */}
              <div className="glass-panel rounded-2xl p-6 text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-ocean-500/10">
                  <IconShip className="h-6 w-6 text-ocean-400" />
                </div>
                <p className="font-display text-3xl font-bold text-white">
                  60,000+
                </p>
                <p className="mt-1 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Large vessels in these waters each year
                </p>
                <p className="mt-3 text-xs leading-relaxed text-slate-400">
                  Shipping lanes overlap directly with whale feeding,
                  breeding, and migration routes. Whales surface to breathe
                  and rest — putting them in the path of vessels that are
                  often too large to stop or steer in time.
                </p>
              </div>

              {/* What helps */}
              <div className="glass-panel rounded-2xl p-6 text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-seafoam-500/10">
                  <IconShield className="h-6 w-6 text-seafoam-400" />
                </div>
                <p className="font-display text-3xl font-bold text-white">
                  80–90%
                </p>
                <p className="mt-1 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Reduction in lethal strikes when ships slow to 10 knots
                </p>
                <p className="mt-3 text-xs leading-relaxed text-slate-400">
                  Speed reductions are the single most effective mitigation.
                  Below 10 knots, the probability of a strike being fatal
                  drops dramatically. Seasonal speed zones and route
                  adjustments save lives — but only where risk is known.
                </p>
              </div>
            </RevealOnScroll>

            <div className="mx-auto mt-10 max-w-3xl rounded-xl border border-ocean-800/30 bg-abyss-800/40 px-6 py-5 text-center">
              <p className="text-sm leading-relaxed text-slate-300">
                <span className="font-semibold text-ocean-400">
                  That&apos;s why we built Whale Watch.
                </span>{" "}
                By mapping collision risk in real time — combining vessel
                traffic, whale sightings, ocean conditions, and community
                reports — we help mariners, regulators, and researchers know
                exactly where whales are most at risk, and what to do about it.
              </p>
            </div>
          </div>
        </section>

        {/* Wave divider: problem → species */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── Species at Risk ── */}
        <section className="bg-abyss-900/80 px-6 py-20 backdrop-blur-sm">
          <div className="mx-auto max-w-6xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Focal Species
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              8 priority species, 77 taxa tracked
            </p>
            <p className="mx-auto mb-6 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              Our platform tracks{" "}
              <Link href="/species" className="text-ocean-300 underline decoration-ocean-500/40 underline-offset-2 hover:text-ocean-200">
                77 cetacean taxa
              </Link>{" "}
              across species, genus, family, and higher ranks — unifying OBIS
              sightings, Nisi ISDM predictions, and NMFS strike records through
              a single crosswalk. These eight species are the focal targets of
              our collision risk models because they are the most frequently
              struck in US waters.
            </p>
            <div className="mb-12 flex flex-wrap items-center justify-center gap-3 text-[11px] text-slate-500">
              <span className="rounded-full border border-ocean-800/30 bg-ocean-900/30 px-3 py-1">
                55 species-level · 34 groups · 77 total entries
              </span>
              <Link href="/species" className="rounded-full border border-ocean-700/40 bg-ocean-500/10 px-3 py-1 font-medium text-ocean-300 transition-all hover:bg-ocean-500/20">
                View full crosswalk →
              </Link>
            </div>
            <RevealOnScroll className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  name: "North Atlantic Right Whale",
                  status: "Critically Endangered",
                  statusColor: "text-red-400",
                  pop: "~350",
                  reason:
                    "The most endangered large whale on Earth. Slow-moving and coastal, they overlap heavily with shipping lanes along the US East Coast. Ship strikes and entanglement account for the majority of known deaths.",
                },
                {
                  name: "Humpback Whale",
                  status: "Least Concern",
                  statusColor: "text-emerald-400",
                  pop: "~80,000",
                  reason:
                    "Despite overall recovery, several distinct population segments remain endangered. Their coastal feeding habits and surface behaviours — lunging, breaching, resting — put them in direct conflict with vessels.",
                },
                {
                  name: "Fin Whale",
                  status: "Vulnerable",
                  statusColor: "text-amber-400",
                  pop: "~100,000",
                  reason:
                    "The second-largest animal ever to live. Fast swimmers, but they rest at the surface and are frequently struck by large commercial vessels — the single largest source of human-caused fin whale mortality.",
                },
                {
                  name: "Blue Whale",
                  status: "Endangered",
                  statusColor: "text-red-400",
                  pop: "~10,000",
                  reason:
                    "The largest animal on Earth, still recovering from whaling. They feed in productive coastal upwelling zones that overlap with major shipping routes, particularly off California.",
                },
                {
                  name: "Sei Whale",
                  status: "Endangered",
                  statusColor: "text-red-400",
                  pop: "~50,000",
                  reason:
                    "One of the fastest baleen whales, but unpredictable surface feeding makes them vulnerable. Poorly studied and often misidentified, making accurate monitoring critical.",
                },
                {
                  name: "Sperm Whale",
                  status: "Vulnerable",
                  statusColor: "text-amber-400",
                  pop: "~800,000",
                  reason:
                    "Deep divers that rest motionless at the surface between dives — making them nearly invisible to approaching ships. Strikes often go undetected in deep water.",
                },
                {
                  name: "Minke Whale",
                  status: "Least Concern",
                  statusColor: "text-emerald-400",
                  pop: "~500,000",
                  reason:
                    "The smallest and most abundant baleen whale in the study area, but their small size makes them hard to spot. Frequently struck by recreational boats and ferries in coastal areas.",
                },
                {
                  name: "Killer Whale",
                  status: "Data Deficient",
                  statusColor: "text-slate-400",
                  pop: "~50,000",
                  reason:
                    "Southern Resident killer whales (only ~75 individuals) are critically endangered. Vessel disturbance, noise pollution, and occasional strikes compound prey depletion threats in the Salish Sea.",
                },
              ].map((sp) => {
                const iconFile = WHALE_ICON_FILES[sp.name] ?? "right_whale.png";
                return (
                <div
                  key={sp.name}
                  className="glass-panel group relative overflow-hidden rounded-xl p-5 transition-all hover:border-ocean-500/30 hover:shadow-ocean-md"
                >
                  {/* Species silhouette — centred, soft ocean glow */}
                  <div
                    className="pointer-events-none absolute inset-0 opacity-[0.1] transition-opacity duration-500 group-hover:opacity-[0.18]"
                    style={{
                      backgroundImage: `url(/whale_detailed_smooth_icons/${iconFile})`,
                      backgroundSize: "70% auto",
                      backgroundRepeat: "no-repeat",
                      backgroundPosition: "center center",
                      filter: "invert(1) brightness(1.6) sepia(1) saturate(4) hue-rotate(170deg) blur(1px)",
                    }}
                    aria-hidden="true"
                  />
                  <h3 className="relative font-display text-base font-bold text-white">
                    {sp.name}
                  </h3>
                  <div className="mt-1.5 flex items-center gap-3 text-xs">
                    <span className={`font-semibold ${sp.statusColor}`}>
                      {sp.status}
                    </span>
                    <span className="text-slate-500">
                      Est. pop: {sp.pop}
                    </span>
                  </div>
                  <p className="mt-3 text-xs leading-relaxed text-slate-400">
                    {sp.reason}
                  </p>
                </div>
                );
              })}
            </RevealOnScroll>
          </div>
        </section>

        {/* Whale song waveform divider: species → coverage */}
        <WhaleSongDivider className="bg-abyss-900/80" height={50} />

        {/* ── Coverage Area ── */}
        <section className="bg-abyss-900/80 px-6 py-20 backdrop-blur-sm">
          <div className="mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Risk Modelling Area
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              US Atlantic, Pacific &amp; Caribbean waters
            </p>
            <p className="mx-auto mb-10 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              You can report sightings from anywhere, but our collision-risk
              models focus on US waters — the continental US, Alaska &amp;
              the Aleutians, Hawaii, Puerto Rico, and the US Virgin Islands.
              The modelled area spans 2°S to 52°N latitude and 180°W to
              59°W longitude at H3 resolution 7 (~1.22 km cells).
            </p>
            <div className="overflow-hidden rounded-2xl border border-ocean-800/20 shadow-ocean-lg">
              <CoverageMap />
            </div>
          </div>
        </section>

        {/* Wave divider: coverage → features */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── Features ── */}
        <section className="bg-abyss-950/80 px-6 py-24 backdrop-blur-sm">
          <div className="mx-auto max-w-6xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Platform Features
            </h2>
            <p className="mb-16 text-center font-display text-3xl font-bold tracking-tight text-white">
              Map, classify, report &amp; collaborate
            </p>

            <RevealOnScroll className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <Link
                  key={f.title}
                  href={f.href}
                  className="border-glow-hover glass-panel group relative overflow-hidden rounded-2xl p-8 transition-all hover:shadow-ocean-md"
                >
                  {/* Subtle gradient accent top-left */}
                  <div className={`pointer-events-none absolute -left-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br ${f.accent} opacity-[0.08] blur-2xl transition-opacity group-hover:opacity-[0.15]`} />

                  <div className="relative z-10">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-ocean-500/10 text-ocean-400 transition-colors group-hover:bg-ocean-500/20 group-hover:text-bioluminescent-400">
                      <f.Icon className="h-6 w-6" />
                    </div>
                    <h3 className="font-display text-lg font-bold text-white">
                      {f.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-400">
                      {f.desc}
                    </p>
                    <p className="mt-4 text-sm font-semibold text-ocean-400 transition-colors group-hover:text-bioluminescent-400">
                      {f.cta}
                      <span className="ml-1 inline-block transition-transform group-hover:translate-x-1">
                        →
                      </span>
                    </p>
                  </div>
                </Link>
              ))}
            </RevealOnScroll>
          </div>
        </section>

        {/* Wave divider: features → risk model */}
        <WaveDivider color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── Risk Model ── */}
        <section className="relative bg-abyss-900/80 px-6 py-24 backdrop-blur-sm">
          <Bubbles seed={137} />
          <div className="relative z-10 mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Risk Scoring Model
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              7 expert-weighted sub-scores
            </p>
            <p className="mx-auto mb-12 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              Each H3 hex cell receives a composite collision risk score from 7
              sub-scores. All are percentile-ranked (0–100%) relative to all US
              coastal cells, then combined with expert-elicited weights from
              published literature (Vanderlaan &amp; Taggart 2007, Rockwood
              et al. 2021, Nisi et al. 2024).
            </p>

            <RevealOnScroll className="space-y-3">
              {SUB_SCORES.map((s) => (
                <div
                  key={s.name}
                  className="border-glow-hover glass-panel group flex items-center gap-4 rounded-xl px-5 py-4"
                >
                  <div className={`h-3 w-3 flex-shrink-0 rounded-full ${s.color} shadow-sm`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <h4 className={`text-sm font-semibold ${s.accent}`}>
                        {s.name}
                      </h4>
                      <span className="rounded-full bg-abyss-800/80 px-2.5 py-0.5 text-[10px] font-bold text-slate-400">
                        {s.weight}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">{s.desc}</p>
                  </div>
                  {/* Weight bar */}
                  <div className="hidden h-2 w-24 overflow-hidden rounded-full bg-abyss-800/60 sm:block">
                    <div
                      className={`h-full rounded-full ${s.color} opacity-60 transition-all group-hover:opacity-90`}
                      style={{ width: `${s.pct * 4}%` }}
                    />
                  </div>
                </div>
              ))}
            </RevealOnScroll>
          </div>
        </section>

        {/* Wave divider: risk → data sources */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── Data Sources ── */}
        <section className="bg-abyss-950/80 px-6 py-24 backdrop-blur-sm">
          <div className="mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Data Sources
            </h2>
            <p className="mb-12 text-center font-display text-3xl font-bold tracking-tight text-white">
              Built on authoritative marine datasets
            </p>

            <RevealOnScroll className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {DATA_SOURCES.map((d) => (
                <div
                  key={d.name}
                  className="border-glow-hover glass-panel group rounded-xl p-5 text-center transition-all"
                >
                  <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-ocean-500/10 text-ocean-400 transition-colors group-hover:bg-ocean-500/20 group-hover:text-bioluminescent-400">
                    <d.Icon className="h-5 w-5" />
                  </div>
                  <h4 className="text-sm font-semibold text-slate-200">
                    {d.name}
                  </h4>
                  <p className="mt-1 text-xs text-slate-500">{d.source}</p>
                </div>
              ))}
            </RevealOnScroll>
          </div>
        </section>

        {/* Pod formation divider: data → community */}
        <PodFormation className="bg-abyss-900/80" height={52} whaleCount={5} />

        {/* ── Community & Insights ── */}
        <section className="relative bg-abyss-900/80 px-6 py-24 backdrop-blur-sm">
          <Bubbles seed={421} />
          <div className="relative z-10 mx-auto max-w-6xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Community &amp; Insights
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              Citizen science meets expert analysis
            </p>
            <p className="mx-auto mb-14 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              Everyone from recreational boaters to marine researchers can
              contribute sightings, verify reports, and access role-specific
              dashboards — turning collective observations into actionable
              protection.
            </p>

            <div className="grid gap-6 md:grid-cols-2">
              {/* Community card */}
              <Link
                href="/community"
                className="border-glow-hover glass-panel group relative overflow-hidden rounded-2xl p-8 transition-all hover:shadow-ocean-md"
              >
                <div className="pointer-events-none absolute -left-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br from-emerald-500 to-seafoam-500 opacity-[0.08] blur-2xl transition-opacity group-hover:opacity-[0.15]" />
                <div className="relative z-10">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 transition-colors group-hover:bg-emerald-500/20 group-hover:text-seafoam-400">
                    <IconUsers className="h-6 w-6" />
                  </div>
                  <h3 className="font-display text-lg font-bold text-white">
                    Community Sightings
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">
                    Submit whale sightings with photo and audio evidence,
                    pinpointed on an interactive map. Community members vote to
                    verify reports, building a trusted database. Earn reputation
                    as a contributor and climb the tier system from Observer to
                    Expert.
                  </p>
                  <div className="mt-5 grid grid-cols-3 gap-3">
                    {[
                      { label: "Report", detail: "Photo + audio + GPS" },
                      { label: "Verify", detail: "Agree / dispute votes" },
                      { label: "Earn", detail: "Reputation & tiers" },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="rounded-lg bg-abyss-800/60 px-3 py-2 text-center"
                      >
                        <p className="text-xs font-semibold text-emerald-400">
                          {item.label}
                        </p>
                        <p className="mt-0.5 text-[10px] text-slate-500">
                          {item.detail}
                        </p>
                      </div>
                    ))}
                  </div>
                  <p className="mt-5 text-sm font-semibold text-emerald-400 transition-colors group-hover:text-seafoam-400">
                    Browse Community Feed
                    <span className="ml-1 inline-block transition-transform group-hover:translate-x-1">
                      →
                    </span>
                  </p>
                </div>
              </Link>

              {/* Insights card */}
              <Link
                href="/insights"
                className="border-glow-hover glass-panel group relative overflow-hidden rounded-2xl p-8 transition-all hover:shadow-ocean-md"
              >
                <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 opacity-[0.08] blur-2xl transition-opacity group-hover:opacity-[0.15]" />
                <div className="relative z-10">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 transition-colors group-hover:bg-amber-500/20 group-hover:text-orange-400">
                    <IconLightbulb className="h-6 w-6" />
                  </div>
                  <h3 className="font-display text-lg font-bold text-white">
                    Stakeholder Insights
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">
                    Five tailored dashboards translate complex risk data into
                    actionable guidance for each audience. Route-specific
                    advisories for captains, regulatory analysis for policy
                    makers, SDM outputs for researchers, threat mapping for
                    conservationists, and traffic analytics for ports.
                  </p>
                  <div className="mt-5 grid grid-cols-5 gap-2">
                    {[
                      { Icon: IconShip, role: "Captains" },
                      { Icon: IconBuilding, role: "Policy" },
                      { Icon: IconMicroscope, role: "Research" },
                      { Icon: IconWhale, role: "Conservation" },
                      { Icon: IconAnchor, role: "Ports" },
                    ].map((s) => (
                      <div
                        key={s.role}
                        className="rounded-lg bg-abyss-800/60 px-2 py-2 text-center"
                      >
                        <div className="flex justify-center">
                          <s.Icon className="h-4 w-4 text-amber-400/70" />
                        </div>
                        <p className="mt-0.5 text-[10px] text-slate-500">
                          {s.role}
                        </p>
                      </div>
                    ))}
                  </div>
                  <p className="mt-5 text-sm font-semibold text-amber-400 transition-colors group-hover:text-orange-400">
                    Explore Insights
                    <span className="ml-1 inline-block transition-transform group-hover:translate-x-1">
                      →
                    </span>
                  </p>
                </div>
              </Link>
            </div>
          </div>
        </section>

        {/* Whale song divider: community → ML */}
        <WhaleSongDivider className="bg-abyss-900/80" height={50} />

        {/* ── ML Pipeline ── */}
        <section className="relative bg-abyss-900/80 px-6 py-24 backdrop-blur-sm">
          <div className="relative z-10 mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Machine Learning
            </h2>
            <p className="mb-12 text-center font-display text-3xl font-bold tracking-tight text-white">
              12 trained models, climate-projected habitat
            </p>

            <RevealOnScroll className="grid gap-6 md:grid-cols-3">
              {[
                {
                  Icon: IconWhale,
                  title: "Species Distribution",
                  desc: "ISDM+SDM ensemble for 6 whale species: expert-trained ISDM and OBIS observation-trained SDMs fused into habitat probability maps. Scored on CMIP6-projected covariates for 2030s–2080s under two emission scenarios.",
                  accent: "from-ocean-500 to-bioluminescent-500",
                },
                {
                  Icon: IconCamera,
                  title: "Photo Classifier",
                  desc: 'EfficientNet-B4 fine-tuned on Happywhale data. 8 species classes including an "other cetacean" rejection class. 380×380 input, differential learning rates, cosine annealing.',
                  accent: "from-seafoam-500 to-ocean-500",
                },
                {
                  Icon: IconMicrophone,
                  title: "Audio Classifier",
                  desc: "XGBoost on 64 acoustic features (MFCCs, spectral shape) or CNN on mel spectrograms. 8 species, 4-second segments, 97.9% (XGB) / 99.3% (CNN) accuracy. Three-stage class balancing.",
                  accent: "from-ocean-400 to-abyss-400",
                },
              ].map((ml) => (
                <div
                  key={ml.title}
                  className="border-glow-hover glass-panel group relative overflow-hidden rounded-2xl p-6 transition-all"
                >
                  <div className={`pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br ${ml.accent} opacity-[0.06] blur-xl transition-opacity group-hover:opacity-[0.12]`} />
                  <div className="relative z-10">
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-ocean-500/10 text-ocean-400">
                      <ml.Icon className="h-5 w-5" />
                    </div>
                    <h4 className="font-display text-sm font-bold text-white">
                      {ml.title}
                    </h4>
                    <p className="mt-2 text-xs leading-relaxed text-slate-400">
                      {ml.desc}
                    </p>
                  </div>
                </div>
              ))}
            </RevealOnScroll>
          </div>
        </section>

        {/* Wave divider: ML → climate */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── Climate Forecasting ── */}
        <section className="relative bg-abyss-950/80 px-6 py-24 backdrop-blur-sm">
          <Bubbles seed={503} />
          <div className="relative z-10 mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-purple-400">
              Climate Forecasting
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              See how risk shifts through 2080
            </p>
            <p className="mx-auto mb-14 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              We project whale habitat and collision risk into the future using
              CMIP6 climate model outputs under two emission scenarios. Our
              ISDM+SDM ensemble predicts how ocean warming, changing
              productivity, and shifting currents will reshape where whales
              go — and where new collision hotspots will emerge.
            </p>

            <RevealOnScroll className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  Icon: IconThermometer,
                  title: "Ocean Projections",
                  desc: "CMIP6 ensemble-mean SST, MLD, SLA, and primary productivity projected at ~0.25° resolution across the full study area.",
                  accent: "text-orange-400",
                  bg: "bg-orange-500/10",
                },
                {
                  Icon: IconWhale,
                  title: "Species Redistribution",
                  desc: "6-species ISDM+SDM ensemble predicts how blue, fin, humpback, sperm, right, and minke whale habitat shifts under warming.",
                  accent: "text-ocean-400",
                  bg: "bg-ocean-500/10",
                },
                {
                  Icon: IconCalendarFuture,
                  title: "Four Decades",
                  desc: "Risk projections for the 2030s, 2040s, 2060s, and 2080s — far enough to inform long-term infrastructure and policy.",
                  accent: "text-purple-400",
                  bg: "bg-purple-500/10",
                },
                {
                  Icon: IconGlobe,
                  title: "Two Scenarios",
                  desc: "SSP2-4.5 (moderate emissions) and SSP5-8.5 (high emissions) bracket the plausible future, showing best- and worst-case risk.",
                  accent: "text-bioluminescent-400",
                  bg: "bg-bioluminescent-500/10",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="border-glow-hover glass-panel group rounded-xl p-6 text-center transition-all"
                >
                  <div className={`mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-lg ${item.bg} ${item.accent} transition-colors group-hover:brightness-125`}>
                    <item.Icon className="h-5 w-5" />
                  </div>
                  <h4 className={`text-sm font-semibold ${item.accent}`}>
                    {item.title}
                  </h4>
                  <p className="mt-2 text-xs leading-relaxed text-slate-400">
                    {item.desc}
                  </p>
                </div>
              ))}
            </RevealOnScroll>

            {/* Scenario comparison highlight */}
            <div className="mx-auto mt-12 max-w-3xl rounded-xl border border-purple-800/30 bg-abyss-800/40 px-6 py-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-purple-300">
                    58 million projected risk cells
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">
                    1.8M H3 cells × 4 seasons × 2 scenarios × 4 decades.
                    Every cell carries 6 sub-scores, per-species whale
                    probabilities, and projected ocean conditions — all
                    explorable on the interactive map.
                  </p>
                </div>
                <Link
                  href="/map"
                  className="flex-shrink-0 rounded-lg bg-gradient-to-r from-purple-600 to-bioluminescent-600 px-5 py-2.5 text-xs font-semibold text-white shadow-md transition-all hover:from-purple-500 hover:to-bioluminescent-500"
                >
                  Explore Projections →
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Wave divider: climate → footer CTA */}
        <WaveDivider color="#0b1a30" className="bg-abyss-950/80" />

        {/* ── Footer CTA ── */}
        <section className="relative bg-abyss-950/80 px-6 py-24 text-center backdrop-blur-sm">
          <Bubbles seed={293} />

          <div className="relative z-10">
            <Image
              src="/whale_watch_logo.png"
              alt="Whale Watch"
              width={150}
              height={100}
              className="mx-auto mb-6 h-auto w-[150px] animate-float object-contain opacity-40 drop-shadow-[0_0_20px_rgba(34,211,238,0.15)]"
            />
            <h2 className="font-display text-3xl font-bold tracking-tight text-white">
              Ready to explore?
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-sm text-slate-400">
              Open the interactive risk map, explore climate projections
              through 2080, upload whale media for AI classification, report
              a sighting, or dive into stakeholder-tailored insights.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/map"
                className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-ocean-600 to-ocean-500 px-8 py-3 text-sm font-semibold text-white shadow-ocean-md transition-all hover:from-ocean-500 hover:to-bioluminescent-600 hover:shadow-ocean-lg"
              >
                <IconMap className="h-4 w-4" />
                Open Risk Map
              </Link>
              <Link
                href="/classify"
                className="glass-panel flex items-center gap-2 rounded-xl px-8 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconCamera className="h-4 w-4" />
                Classify Species
              </Link>
              <Link
                href="/report"
                className="glass-panel flex items-center gap-2 rounded-xl px-8 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconWhale className="h-4 w-4" />
                Report Interaction
              </Link>
              <Link
                href="/community"
                className="glass-panel flex items-center gap-2 rounded-xl px-8 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-emerald-500/30 hover:text-white"
              >
                <IconUsers className="h-4 w-4" />
                Community
              </Link>
              <Link
                href="/insights"
                className="glass-panel flex items-center gap-2 rounded-xl px-8 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-amber-500/30 hover:text-white"
              >
                <IconLightbulb className="h-4 w-4" />
                Insights
              </Link>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="border-t border-ocean-800/20 bg-abyss-950/80 px-6 pb-10 pt-12 backdrop-blur-sm">
          <div className="mx-auto max-w-5xl">
            <div className="mb-8 grid gap-8 sm:grid-cols-3">
              {/* Brand */}
              <div>
                <div className="mb-3 flex items-center gap-2.5">
                  <Image
                    src="/whale_watch_logo.png"
                    alt="Whale Watch"
                    width={48}
                    height={32}
                    className="h-8 w-12 object-contain"
                  />
                  <span className="font-display font-semibold tracking-wide text-slate-300">
                    Whale<span className="text-ocean-500">Watch</span>
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-slate-500">
                  Mapping whale–vessel collision risk across CONUS,
                  Alaska, Hawaii &amp; Caribbean waters. Open-source
                  data, AI classification, and community science.
                </p>
              </div>

              {/* Platform links */}
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Platform
                </p>
                <div className="space-y-2">
                  {[
                    { href: "/map", label: "Risk Map" },
                    { href: "/insights", label: "Stakeholder Insights" },
                    { href: "/classify", label: "Classify Species" },
                    { href: "/report", label: "Report Interaction" },
                    { href: "/report-vessel", label: "Vessel Violations" },
                    { href: "/community", label: "Community Feed" },
                  ].map((l) => (
                    <Link
                      key={l.href}
                      href={l.href}
                      className="block text-xs text-slate-500 transition-colors hover:text-slate-300"
                    >
                      {l.label}
                    </Link>
                  ))}
                </div>
              </div>

              {/* Data sources */}
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Data Sources
                </p>
                <div className="space-y-2 text-xs text-slate-500">
                  <p>MarineCadastre AIS (BOEM/NOAA)</p>
                  <p>OBIS Cetacean Sightings (IOC-UNESCO)</p>
                  <p>NOAA Ship Strike Records</p>
                  <p>E.U. Copernicus Marine Service</p>
                  <p>GEBCO Bathymetry 2023</p>
                  <p>CMIP6 Climate Projections (CC-BY 4.0)</p>
                  <Link
                    href="/attribution"
                    className="mt-1 block text-ocean-400/70 underline decoration-ocean-400/30 transition-colors hover:text-ocean-300"
                  >
                    Full attribution &amp; licenses →
                  </Link>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-center justify-between gap-3 border-t border-ocean-800/20 pt-6 sm:flex-row">
              <p className="text-xs text-slate-500">
                Built with Next.js · deck.gl · PostGIS · XGBoost · EfficientNet
              </p>
              <p className="text-xs text-slate-500">
                3D whale models by{" "}
                <a
                  href="https://sketchfab.com/Nestaeric"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400/70 underline decoration-ocean-400/30 transition-colors hover:text-ocean-300"
                >
                  Nestaeric
                </a>
              </p>
              <p className="text-xs text-slate-500">© 2026 Whale Watch</p>
            </div>
            <div className="mt-4 text-center text-[10px] leading-relaxed text-slate-600">
              Ocean data: E.U. Copernicus Marine Service Information ·
              Map tiles © CARTO · Map data © OpenStreetMap contributors
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
