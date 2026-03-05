"use client";

import Link from "next/link";
import Image from "next/image";
import dynamic from "next/dynamic";
import { useState, useEffect, useRef } from "react";
import WaveDivider from "@/components/icons/WaveDivider";
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
} from "@/components/icons/MarineIcons";

/* ── Animated counter ────────────────────────────────────── */

function Counter({ end, suffix = "" }: { end: number; suffix?: string }) {
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
        setCount(Math.round(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [end, started]);

  return (
    <span ref={ref}>
      {count.toLocaleString()}
      {suffix}
    </span>
  );
}

/* ── Data ────────────────────────────────────────────────── */

const CoverageMap = dynamic(() => import("@/components/CoverageMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[340px] items-center justify-center rounded-2xl border border-ocean-800/30 bg-abyss-900/50">
      <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-ocean-500 border-t-transparent" />
    </div>
  ),
});

const STATS = [
  { label: "H3 Cells Modelled", value: 1800000, suffix: "+", icon: IconMap },
  { label: "Traffic Records", value: 9700000, suffix: "+", icon: IconShip },
  { label: "Cetacean Sightings", value: 364000, suffix: "+", icon: IconEye },
  { label: "Species Tracked", value: 71, suffix: "", icon: IconWhale },
];

const FEATURES = [
  {
    Icon: IconMap,
    title: "Interactive Risk Map",
    desc: "Explore whale–vessel collision risk across all US coastal waters with 7 expert-weighted sub-scores per H3 cell. Toggle between macro heatmap overview and high-resolution hex detail.",
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
    title: "Sighting Reports",
    desc: "Report whale sightings with optional photo and audio evidence. Our AI classifies the species, assesses local collision risk, and generates real-time advisories.",
    href: "/report",
    cta: "Report Sighting",
    accent: "from-coral-400 to-coral-600",
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
    desc: "OBIS sighting density, baleen whale concentration, recent observations",
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
  { name: "Cetacean Sightings", source: "OBIS (364K records)", Icon: IconWhale },
  { name: "Ship Strike Records", source: "NOAA (261 incidents)", Icon: IconWarning },
  { name: "Bathymetry", source: "GEBCO 2023", Icon: IconWaves },
  { name: "Ocean Covariates", source: "Copernicus (SST, MLD, SLA, PP)", Icon: IconThermometer },
  { name: "Marine Protected Areas", source: "NOAA MPA Inventory", Icon: IconShield },
  { name: "Speed Zones", source: "50 CFR § 224.105 (SMAs)", Icon: IconChart },
  { name: "Reference Risk Grid", source: "Nisi et al. 2024", Icon: IconChart },
];

/* ── Decorative particles (bubbles) ──────────────────────── */
function Bubbles() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {[...Array(12)].map((_, i) => (
        <div
          key={i}
          className="absolute rounded-full bg-bioluminescent-400/[0.06]"
          style={{
            width: `${6 + Math.random() * 14}px`,
            height: `${6 + Math.random() * 14}px`,
            left: `${5 + Math.random() * 90}%`,
            bottom: `-${10 + Math.random() * 30}px`,
            animation: `bubble-rise ${8 + Math.random() * 12}s ease-in ${Math.random() * 8}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────── */

export default function Home() {
  return (
    <>
      <main className="min-h-screen bg-abyss-950">
        {/* ── Hero ── */}
        <section className="relative flex min-h-[90vh] flex-col items-center justify-center overflow-hidden px-6 pt-16 text-center">
          {/* Animated ocean gradient background */}
          <div className="bg-ocean-animated pointer-events-none absolute inset-0" />

          {/* Radial glow */}
          <div className="pointer-events-none absolute left-1/2 top-1/4 h-[700px] w-[700px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-ocean-500/[0.07] blur-[140px]" />
          <div className="pointer-events-none absolute right-1/4 top-2/3 h-[400px] w-[400px] rounded-full bg-bioluminescent-500/[0.05] blur-[100px]" />

          {/* Bubbles */}
          <Bubbles />

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

            <h1 className="font-display text-5xl font-extrabold leading-tight tracking-tight sm:text-6xl lg:text-7xl">
              Track, classify &amp;{" "}
              <span className="text-ocean-bright">protect</span>{" "}
              whales
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-400">
              Map whale–vessel collision risk across US coastal waters, identify
              species from photos and audio with AI, report and verify sightings
              with a growing community — all powered by 12 machine learning
              models, AIS traffic data, and satellite ocean observations.
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
                href="/classify"
                className="glass-panel group flex items-center gap-2 rounded-xl px-8 py-3.5 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconMicrophone className="h-4 w-4" />
                Classify Species
              </Link>
            </div>
          </div>

          {/* Animated stats */}
          <div className="relative z-10 mx-auto mt-24 grid max-w-4xl grid-cols-2 gap-6 sm:grid-cols-4">
            {STATS.map((s) => (
              <div
                key={s.label}
                className="stat-card glass-panel rounded-xl px-4 py-5 text-center transition-all hover:glow-ocean"
              >
                <s.icon className="mx-auto mb-2 h-5 w-5 text-ocean-400/60" />
                <p className="font-display text-2xl font-bold text-white sm:text-3xl">
                  <Counter end={s.value} suffix={s.suffix} />
                </p>
                <p className="mt-1 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Wave divider: hero → species */}
        <WaveDivider color="#0b1a30" />

        {/* ── Species at Risk ── */}
        <section className="bg-abyss-900 px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Species at Risk
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              Why these whales need our help
            </p>
            <p className="mx-auto mb-12 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              Ship strikes are among the leading causes of death for large
              whales. These seven species are the most frequently struck in US
              waters — and the ones our platform is built to protect.
            </p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
                    "The smallest and most abundant baleen whale in US waters, but their small size makes them hard to spot. Frequently struck by recreational boats and ferries in coastal areas.",
                },
                {
                  name: "Killer Whale",
                  status: "Data Deficient",
                  statusColor: "text-slate-400",
                  pop: "~50,000",
                  reason:
                    "Southern Resident killer whales (only ~75 individuals) are critically endangered. Vessel disturbance, noise pollution, and occasional strikes compound prey depletion threats in the Salish Sea.",
                },
              ].map((sp) => (
                <div
                  key={sp.name}
                  className="glass-panel group rounded-xl p-5 transition-all hover:border-ocean-500/30 hover:shadow-ocean-md"
                >
                  <h3 className="font-display text-base font-bold text-white">
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
              ))}
            </div>
          </div>
        </section>

        {/* Wave divider: species → coverage */}
        <WaveDivider color="#0b1a30" className="bg-abyss-900" />

        {/* ── Coverage Area ── */}
        <section className="bg-abyss-900 px-6 py-20">
          <div className="mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Coverage Area
            </h2>
            <p className="mb-4 text-center font-display text-3xl font-bold tracking-tight text-white">
              All US waters
            </p>
            <p className="mx-auto mb-10 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
              The platform covers all US waters from the Aleutians to the
              Galápagos, and east to Barbados — spanning 2°S to 52°N
              latitude and 180°W to 59°W longitude at H3 resolution 7
              (~1.22 km cells).
            </p>
            <div className="overflow-hidden rounded-2xl border border-ocean-800/20 shadow-ocean-lg">
              <CoverageMap />
            </div>
          </div>
        </section>

        {/* Wave divider: coverage → features */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950" />

        {/* ── Features ── */}
        <section className="bg-abyss-950 px-6 py-24">
          <div className="mx-auto max-w-6xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Platform Features
            </h2>
            <p className="mb-16 text-center font-display text-3xl font-bold tracking-tight text-white">
              Everything you need to assess marine risk
            </p>

            <div className="grid gap-6 sm:grid-cols-2">
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
            </div>
          </div>
        </section>

        {/* Wave divider: features → risk model */}
        <WaveDivider color="#0b1a30" />

        {/* ── Risk Model ── */}
        <section className="relative bg-abyss-900 px-6 py-24">
          <Bubbles />
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

            <div className="space-y-3">
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
            </div>
          </div>
        </section>

        {/* Wave divider: risk → data sources */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950" />

        {/* ── Data Sources ── */}
        <section className="bg-abyss-950 px-6 py-24">
          <div className="mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Data Sources
            </h2>
            <p className="mb-12 text-center font-display text-3xl font-bold tracking-tight text-white">
              Built on authoritative marine datasets
            </p>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
            </div>
          </div>
        </section>

        {/* Wave divider: data → ML */}
        <WaveDivider color="#0b1a30" />

        {/* ── ML Pipeline ── */}
        <section className="relative bg-abyss-900 px-6 py-24">
          <div className="relative z-10 mx-auto max-w-5xl">
            <h2 className="mb-2 text-center font-display text-sm font-semibold uppercase tracking-[0.2em] text-ocean-400">
              Machine Learning
            </h2>
            <p className="mb-12 text-center font-display text-3xl font-bold tracking-tight text-white">
              12 trained models, 3 classification pipelines
            </p>

            <div className="grid gap-6 md:grid-cols-3">
              {[
                {
                  Icon: IconWhale,
                  title: "Species Distribution (ISDM)",
                  desc: "4 XGBoost models trained on OBIS sightings with 7 environmental covariates (SST, MLD, SLA, PP, depth). Predicts P(whale presence) per H3 cell per season for blue, fin, humpback, and sperm whales.",
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
            </div>
          </div>
        </section>

        {/* Wave divider: ML → footer CTA */}
        <WaveDivider flip color="#0b1a30" className="bg-abyss-950" />

        {/* ── Footer CTA ── */}
        <section className="relative bg-abyss-950 px-6 py-24 text-center">
          <Bubbles />
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
              Open the interactive risk map to see collision risk across 1.8
              million H3 cells, or upload whale media for AI species
              classification.
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
                <IconMicrophone className="h-4 w-4" />
                Classify Species
              </Link>
              <Link
                href="/report"
                className="glass-panel flex items-center gap-2 rounded-xl px-8 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
              >
                <IconWhale className="h-4 w-4" />
                Report Sighting
              </Link>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="border-t border-ocean-800/20 bg-abyss-950 px-6 py-8">
          <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <div className="flex items-center gap-2.5 text-sm text-slate-600">
              <Image
                src="/whale_watch_logo.png"
                alt="Whale Watch"
                width={48}
                height={32}
                className="h-8 w-12 object-contain"
              />
              <span className="font-display font-semibold tracking-wide">
                Whale<span className="text-ocean-500">Watch</span>
              </span>
            </div>
            <p className="text-center text-xs text-slate-600">
              Built with Next.js, deck.gl, PostGIS, XGBoost &amp; EfficientNet
              · Data from NOAA, OBIS, Copernicus, MarineCadastre
            </p>
          </div>
        </footer>
      </main>
    </>
  );
}
