"use client";

/**
 * Homepage — "The Descent"
 *
 * The landing experience is a scroll-driven dive from the sunlit surface to
 * the abyss:
 *   1. A depth-gauge rail (left) — a submersible bead descends as you scroll,
 *      lighting each ocean zone as the story passes it.
 *   2. A real 3D humpback swims down an undulating path, arriving as the
 *      scene darkens into "The Problem".
 *   3. Editorial sections — oversized ghost numerals, ragged prose, hairline
 *      rules — carry the narrative through the problem, the species at risk,
 *      the solution (the live map), the model, the climate projections, and
 *      the community, before ascending back toward the surface CTA.
 */

import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CausticRays } from "@/components/animations";

// Same perfected surface scene as the live homepage — DO NOT alter.
const OceanScene = dynamic(
  () => import("@/components/animations/OceanScene"),
  { ssr: false },
);

// Real 3D humpback that swims down an undulating path as you scroll.
const ScrollDownWhale = dynamic(
  () => import("@/components/animations/ScrollDownWhale"),
  { ssr: false },
);

// Small 3D humpback that dives down the left depth-gauge rail.
const RailWhale = dynamic(
  () => import("@/components/animations/RailWhale"),
  { ssr: false },
);

const CoverageMap = dynamic(() => import("@/components/CoverageMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[340px] items-center justify-center bg-abyss-900/50 text-xs text-ocean-400/70">
      Loading coverage map…
    </div>
  ),
});

/* ── Data ─────────────────────────────────────────────────── */

const STATS = [
  { value: "1.8M+", label: "ocean cells modelled" },
  { value: "3.1B+", label: "AIS pings processed" },
  { value: "1M+", label: "cetacean sightings" },
  { value: "77", label: "species tracked" },
  { value: "58M", label: "projected risk cells" },
];

type SubScore = {
  name: string;
  pct: number;
  accent: string;
  bar: string;
  desc: string;
};

const SUB_SCORES: SubScore[] = [
  {
    name: "Traffic intensity",
    pct: 25,
    accent: "text-coral-400",
    bar: "bg-coral-500",
    desc: "Vessel speed, volume, lethality, draft risk, night ops",
  },
  {
    name: "Cetacean presence",
    pct: 25,
    accent: "text-ocean-300",
    bar: "bg-ocean-500",
    desc: "OBIS sightings, baleen concentration, recency",
  },
  {
    name: "Proximity blend",
    pct: 15,
    accent: "text-bioluminescent-400",
    bar: "bg-bioluminescent-500",
    desc: "Distance-decay from whales, strikes, unprotected waters",
  },
  {
    name: "Strike history",
    pct: 10,
    accent: "text-orange-400",
    bar: "bg-orange-500",
    desc: "Historical NOAA ship-strike records here",
  },
  {
    name: "Habitat suitability",
    pct: 10,
    accent: "text-seafoam-400",
    bar: "bg-seafoam-500",
    desc: "Shelf-edge bathymetry and primary productivity",
  },
  {
    name: "Protection gap",
    pct: 10,
    accent: "text-purple-400",
    bar: "bg-purple-500",
    desc: "Distance from MPAs, no-take and seasonal zones",
  },
  {
    name: "Reference risk",
    pct: 5,
    accent: "text-abyss-300",
    bar: "bg-abyss-400",
    desc: "Nisi et al. 2024 global collision baseline",
  },
];

type Feature = {
  title: string;
  desc: string;
  href: string;
  cta: string;
};

const FEATURES: Feature[] = [
  {
    title: "Interactive risk map",
    desc: "Explore collision risk across the study area with 7 expert-weighted sub-scores per cell. Macro heatmap or high-res hex detail.",
    href: "/map",
    cta: "Open map",
  },
  {
    title: "Photo classification",
    desc: "Upload a whale photo; an EfficientNet-B4 model identifies the species from 8 classes. GPS photos get automatic risk context.",
    href: "/classify",
    cta: "Classify a photo",
  },
  {
    title: "Audio classification",
    desc: "Submit underwater audio; an XGBoost/CNN pipeline segments it and extracts 64 acoustic features to identify the species.",
    href: "/classify",
    cta: "Classify audio",
  },
  {
    title: "Interaction reports",
    desc: "Report whale interactions with photo and audio evidence. The AI classifies the species and generates a real-time advisory.",
    href: "/report",
    cta: "Report an interaction",
  },
  {
    title: "Vessel violations",
    desc: "Flag vessels speeding through slow zones, entering MPAs, or going dark on AIS. Community review sharpens the risk data.",
    href: "/report-vessel",
    cta: "Report a violation",
  },
  {
    title: "Climate forecasting",
    desc: "See how habitat and risk shift under CMIP6 scenarios from the 2030s to the 2080s. Compare projected oceans against today.",
    href: "/map",
    cta: "View projections",
  },
];

const CLIMATE: { title: string; desc: string }[] = [
  {
    title: "Ocean projections",
    desc: "CMIP6 ensemble-mean SST, MLD, SLA and primary productivity at ~0.25° across the full study area.",
  },
  {
    title: "Species redistribution",
    desc: "A 6-species ISDM+SDM ensemble predicts how blue, fin, humpback, sperm, right and minke habitat shifts under warming.",
  },
  {
    title: "Four decades, two scenarios",
    desc: "The 2030s through 2080s under SSP2-4.5 and SSP5-8.5 — bracketing the plausible best- and worst-case futures.",
  },
];

type Species = {
  name: string;
  status: string;
  statusColor: string;
  pop: string;
  icon: string;
  note: string;
};

const SPECIES: Species[] = [
  {
    name: "North Atlantic Right Whale",
    status: "Critically Endangered",
    statusColor: "text-red-400",
    pop: "~350",
    icon: "right_whale.png",
    note: "The most endangered large whale on Earth. Slow and coastal, overlapping heavily with East Coast shipping lanes.",
  },
  {
    name: "Blue Whale",
    status: "Endangered",
    statusColor: "text-red-400",
    pop: "~10,000",
    icon: "blue_whale.png",
    note: "The largest animal on Earth, still recovering from whaling. Feeds in upwelling zones that overlap major routes.",
  },
  {
    name: "Fin Whale",
    status: "Vulnerable",
    statusColor: "text-amber-400",
    pop: "~100,000",
    icon: "fin_whale.png",
    note: "Fast but surface-resting. Ship strikes are the single largest source of human-caused fin whale mortality.",
  },
  {
    name: "Humpback Whale",
    status: "Least Concern",
    statusColor: "text-emerald-400",
    pop: "~80,000",
    icon: "humpback_whale.png",
    note: "Several populations remain endangered. Coastal lunging, breaching and resting bring them into vessel paths.",
  },
  {
    name: "Sei Whale",
    status: "Endangered",
    statusColor: "text-red-400",
    pop: "~50,000",
    icon: "sei_whale.png",
    note: "One of the fastest baleen whales, but unpredictable surface feeding and frequent misID make monitoring hard.",
  },
  {
    name: "Sperm Whale",
    status: "Vulnerable",
    statusColor: "text-amber-400",
    pop: "~800,000",
    icon: "sperm_whale.png",
    note: "Deep divers that rest motionless at the surface — nearly invisible to approaching ships in deep water.",
  },
  {
    name: "Minke Whale",
    status: "Least Concern",
    statusColor: "text-emerald-400",
    pop: "~500,000",
    icon: "minke_whale.png",
    note: "Small and hard to spot, frequently struck by recreational boats and ferries in coastal areas.",
  },
  {
    name: "Killer Whale",
    status: "Data Deficient",
    statusColor: "text-slate-400",
    pop: "~50,000",
    icon: "killer_whale_orca.png",
    note: "Southern Resident orcas (~75 left) face vessel disturbance, noise and strikes atop prey depletion.",
  },
];

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden text-slate-200">
      {/* Perfected 3D surface scene — fixed behind everything, untouched */}
      <OceanScene />

      {/* Content layer sits ABOVE the scene (z-10), exactly like the live
         homepage. The surface section stays transparent so the scene shows
         through; deeper sections paint their own darkness to occlude it. */}
      <main className="relative z-10">
        <CausticRays rayCount={5} opacity={0.025} />

        {/* ── Depth-gauge rail ── */}
        <DepthRail />

        {/* ── 3D humpback diving the rail (lg only) ── */}
        <RailWhale />

        {/* ── Real 3D humpback that swims down the page with you ── */}
        <ScrollDownWhale />

        {/* ── SUNLIGHT ZONE — transparent so the perfected scene shows ── */}
        <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-8 text-center">
          {/* God-rays raining down on the logo */}
          <CausticRays rayCount={6} opacity={0.04} />
          {/* Soft surface spotlight — sits behind the logo so the light reads
             as emitting from it */}
          <div className="pointer-events-none absolute left-1/2 top-[38%] h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-bioluminescent-500/[0.07] blur-[130px]" />

          <div className="relative z-10 flex max-w-3xl flex-col items-center animate-fade-in-up">
            {/* Whale Watch logo — shining down from the surface */}
            <Image
              src="/whale_watch_logo.png"
              alt="Whale Watch"
              width={480}
              height={320}
              priority
              className="h-auto w-[260px] animate-float object-contain drop-shadow-[0_0_60px_rgba(34,211,238,0.35)] sm:w-[340px]"
            />

            <p
              id="depth-anchor-0"
              className="mb-4 mt-8 font-mono text-[11px] uppercase tracking-[0.35em] text-bioluminescent-400/70"
            >
              0 m · Sunlight Zone
            </p>
            <h1 className="font-display text-5xl font-extrabold leading-[0.95] tracking-tight text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.8)] sm:text-7xl">
              Spot them.{" "}
              <span className="text-ocean-bright">Protect</span> them.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300 drop-shadow-[0_1px_6px_rgba(0,0,0,0.7)]">
              A living map of where whales and ships collide — built from
              sightings, satellites, and the people who watch the water.
            </p>
            <p className="mt-10 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.3em] text-slate-400">
              Scroll to descend
              <span className="inline-block animate-bounce text-bioluminescent-400">
                ↓
              </span>
            </p>
          </div>
        </section>

        {/* ── Stats band — thin editorial strip, not boxes ── */}
        <section className="relative border-y border-white/[0.06] bg-abyss-950/80 px-8 py-10 pl-20 backdrop-blur-sm sm:pl-28">
          <div className="flex flex-wrap items-baseline gap-x-12 gap-y-6">
            {STATS.map((s) => (
              <div key={s.label} className="flex items-baseline gap-3">
                <span className="font-display text-2xl font-black tracking-tight text-white sm:text-3xl">
                  {s.value}
                </span>
                <span className="text-[11px] uppercase tracking-wider text-slate-500">
                  {s.label}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ── TWILIGHT ZONE — "The Problem" editorial split ── */}
        <section
          id="problem-section"
          className="relative px-8 py-28 pl-20 sm:pl-28"
        >
          {/* This section fades its own darkness OVER the scene as you descend */}
          <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-transparent via-abyss-950/90 to-abyss-950" />

          <p
            id="depth-anchor-1"
            className="relative z-10 mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-coral-400/80"
          >
            200 m · Twilight Zone
          </p>
          <p className="relative z-10 mb-16 font-display text-sm font-semibold uppercase tracking-[0.2em] text-coral-400">
            The Problem
          </p>

          {/* Editorial two-column: oversized ghost numeral | ragged prose */}
          <div className="relative z-10 grid gap-x-12 gap-y-10 lg:grid-cols-[1.1fr_0.9fr]">
            {/* Left — the number as a monument */}
            <div className="relative">
              <p className="font-display text-[clamp(5rem,14vw,12rem)] font-black leading-[0.82] tracking-tighter text-white/[0.38]">
                20,000
              </p>
              <p className="mt-10 max-w-md font-display text-2xl font-bold leading-tight text-white sm:text-3xl">
                whales killed by ships every year — and most are never even
                recorded.
              </p>
              <div className="mt-8 h-px w-40 bg-gradient-to-r from-coral-500/60 to-transparent" />
              <p className="mt-6 max-w-md text-sm leading-relaxed text-slate-400">
                A 2024 study put global ship-strike mortality at over twenty
                thousand large whales annually — far above earlier estimates.
                The crew rarely knows it happened. The animal sinks before it
                can be found.
              </p>
            </div>

            {/* Right — prose column, ragged, left-aligned */}
            <div className="space-y-10 lg:pt-16">
              <Stat
                big="60,000+"
                tone="ocean"
                label="large vessels transit U.S. waters each year"
                body="Shipping lanes lie directly over whale feeding, breeding and
                migration routes. Whales surface to breathe and rest — into the
                path of ships too large to stop or turn in time."
              />
              <Stat
                big="80–90%"
                tone="seafoam"
                label="fewer lethal strikes when ships slow to 10 knots"
                body="Speed is the single most effective lever. Below ten knots
                the odds of a strike being fatal collapse. Seasonal slow zones
                save lives — but only where the risk is actually known."
              />
            </div>
          </div>

          {/* Closing editorial line — full bleed feel, asymmetric */}
          <div className="relative z-10 mt-24 max-w-2xl">
            <p className="font-display text-xl font-medium leading-snug text-slate-300 sm:text-2xl">
              <span className="text-ocean-bright">
                That&apos;s why we built Whale Watch.
              </span>{" "}
              We map collision risk in real time, so mariners, regulators and
              researchers know exactly where whales are most at risk — and what
              to do about it.
            </p>
            <Link
              href="/map"
              className="group mt-8 inline-flex items-center gap-2 text-sm font-semibold text-ocean-300 transition-colors hover:text-ocean-200"
            >
              See where they&apos;re dying
              <span className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </div>
        </section>

        {/* ── MIDNIGHT ZONE — teaser of where the map would bleed in ── */}
        {/* ── MESOPELAGIC — Species at Risk (the victims) ── */}
        <section className="relative bg-abyss-950 px-8 py-28 pl-20 sm:pl-28">
          <p
            id="depth-anchor-2"
            className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-ocean-400/70"
          >
            500 m · The Victims
          </p>
          <h2 className="max-w-2xl font-display text-3xl font-bold leading-tight text-white sm:text-4xl">
            Eight species bear the brunt.
          </h2>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-slate-400">
            We model 77 cetacean taxa, but these eight are struck most often in
            US waters. Each is a focal target of our collision-risk models.{" "}
            <Link
              href="/species"
              className="text-ocean-300 underline decoration-ocean-500/40 underline-offset-2 hover:text-ocean-200"
            >
              View the full crosswalk →
            </Link>
          </p>

          {/* Editorial species rows — silhouette + name + status, hairline ruled */}
          <div className="mt-14 divide-y divide-white/[0.06] border-y border-white/[0.06]">
            {SPECIES.map((sp, i) => (
              <SpeciesRow key={sp.name} sp={sp} index={i} />
            ))}
          </div>
        </section>

        {/* ── MIDNIGHT — The Solution: the map as hero moment ── */}
        <section className="relative bg-[#04101b] px-8 py-32 pl-20 sm:pl-28">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_70%_40%,rgba(34,211,238,0.10),transparent_60%)]" />
          <div className="relative z-10">
            <p
              id="depth-anchor-3"
              className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-bioluminescent-400/70"
            >
              1 000 m · Midnight Zone
            </p>
            <h2 className="max-w-3xl font-display text-4xl font-bold leading-[1.05] text-white sm:text-6xl">
              So we lit up the dark.
            </h2>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
              Whale Watch maps collision risk across 1.8 million ocean cells —
              combining vessel traffic, whale sightings, ocean conditions and
              community reports into a single, living risk surface.
            </p>

            {/* The one full-bleed map moment */}
            <div className="mt-12 overflow-hidden rounded-2xl border border-bioluminescent-500/20 shadow-[0_0_80px_-20px_rgba(34,211,238,0.35)]">
              <CoverageMap />
            </div>

            <p className="mt-6 max-w-xl text-sm leading-relaxed text-slate-400">
              From the continental US to Alaska, Hawaii and the Caribbean — 2°S
              to 52°N, at ~1.22 km resolution. Zoom out for the coast-wide
              heatmap; zoom in for individual hexes.
            </p>
            <Link
              href="/map"
              className="group mt-8 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-ocean-600 to-bioluminescent-600 px-7 py-3 text-sm font-semibold text-white shadow-ocean-md transition-all hover:from-ocean-500 hover:to-bioluminescent-500"
            >
              Open the risk map
              <span className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </div>
        </section>

        {/* ── How it works — 7 sub-scores as editorial weighted bars ── */}
        <section className="relative bg-abyss-950 px-8 py-28 pl-20 sm:pl-28">
          <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-ocean-400/70">
            How the score is built
          </p>
          <h2 className="max-w-2xl font-display text-3xl font-bold leading-tight text-white sm:text-4xl">
            Seven signals, one risk score.
          </h2>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-slate-400">
            Every hex is percentile-ranked on seven sub-scores, then fused with
            expert-elicited weights from the literature (Vanderlaan &amp;
            Taggart 2007, Rockwood 2021, Nisi 2024).
          </p>

          <div className="mt-14 space-y-px">
            {SUB_SCORES.map((s) => (
              <ScoreRow key={s.name} s={s} />
            ))}
          </div>
        </section>

        {/* ── What you can do — feature pathways, editorial 2-col list ── */}
        <section className="relative bg-[#04101b] px-8 py-28 pl-20 sm:pl-28">
          <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-bioluminescent-400/70">
            What you can do
          </p>
          <h2 className="max-w-2xl font-display text-3xl font-bold leading-tight text-white sm:text-4xl">
            Map it. Classify it. Report it.
          </h2>

          <div className="mt-14 grid gap-x-14 gap-y-12 lg:grid-cols-2">
            {FEATURES.map((f, i) => (
              <FeatureItem key={f.title} f={f} index={i} />
            ))}
          </div>
        </section>

        {/* ── ABYSS — the deep machinery: ML + climate ── */}
        <section className="relative bg-abyss-950 px-8 py-32 pl-20 sm:pl-28">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-[#02060f] to-[#010409]" />
          <div className="relative z-10">
            <p
              id="depth-anchor-4"
              className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-abyss-300/80"
            >
              4 000 m · The Abyss
            </p>
            <h2 className="max-w-3xl font-display text-4xl font-bold leading-[1.05] text-white sm:text-5xl">
              And we ran it forward to 2080.
            </h2>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-300">
              Twelve trained models power the platform — species distribution,
              photo and audio classifiers. Then we scored whale habitat on CMIP6
              climate projections to see where tomorrow&apos;s hotspots emerge.
            </p>

            {/* The big projected-cells monument */}
            <div className="mt-16 grid gap-10 lg:grid-cols-[0.9fr_1.1fr]">
              <div>
                <p className="font-display text-[clamp(4rem,11vw,9rem)] font-black leading-[0.82] tracking-tighter text-bioluminescent-400/25">
                  58M
                </p>
                <p className="mt-5 max-w-sm font-display text-xl font-bold leading-tight text-white sm:text-2xl">
                  projected risk cells, looking forward six decades.
                </p>
                <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
                  1.8M hexes × 4 seasons × 2 emission scenarios × 4 decades.
                  Each carries six sub-scores, per-species whale probabilities,
                  and projected ocean conditions.
                </p>
                <Link
                  href="/map"
                  className="group mt-6 inline-flex items-center gap-2 text-sm font-semibold text-bioluminescent-300 transition-colors hover:text-bioluminescent-200"
                >
                  Explore the projections
                  <span className="transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </Link>
              </div>

              <div className="space-y-8 lg:pt-10">
                {CLIMATE.map((c) => (
                  <div key={c.title} className="border-l border-white/10 pl-5">
                    <p className="font-display text-base font-semibold text-white">
                      {c.title}
                    </p>
                    <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-slate-400">
                      {c.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── ASCENT — community + lighten toward the surface ── */}
        <section className="relative bg-gradient-to-b from-[#010409] via-abyss-950 to-abyss-900 px-8 py-32 pl-20 sm:pl-28">
          <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.35em] text-seafoam-400/70">
            Back toward the light
          </p>
          <h2 className="max-w-3xl font-display text-4xl font-bold leading-[1.05] text-white sm:text-5xl">
            None of this works without you.
          </h2>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
            Every sighting you share sharpens the map. Recreational boaters,
            researchers and regulators all feed the same living record — and
            read it back through dashboards built for them.
          </p>

          <div className="mt-12 grid gap-x-14 gap-y-10 sm:grid-cols-2">
            <PathwayCard
              href="/community"
              eyebrow="Citizen science"
              title="Community sightings"
              body="Report whales with photo, audio and GPS. Members vote to verify; you earn reputation from Observer to Expert."
              cta="Browse the feed"
              tone="seafoam"
            />
            <PathwayCard
              href="/insights"
              eyebrow="Expert analysis"
              title="Stakeholder insights"
              body="Five tailored dashboards — captains, policy, research, conservation, ports — translate the data into action."
              cta="Explore insights"
              tone="ocean"
            />
          </div>
        </section>

        {/* ── Surface CTA ── */}
        <section className="relative flex flex-col items-center bg-abyss-900 px-8 py-28 text-center">
          <Image
            src="/whale_watch_logo.png"
            alt="Whale Watch"
            width={180}
            height={120}
            className="h-auto w-[150px] animate-float object-contain opacity-60 drop-shadow-[0_0_30px_rgba(34,211,238,0.25)]"
          />
          <h2 className="mt-8 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Ready to surface?
          </h2>
          <p className="mt-4 max-w-lg text-sm leading-relaxed text-slate-400">
            Open the map, classify a whale, report a sighting, or dive into the
            climate projections through 2080.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/map"
              className="rounded-xl bg-gradient-to-r from-ocean-600 to-ocean-500 px-7 py-3 text-sm font-semibold text-white shadow-ocean-md transition-all hover:from-ocean-500 hover:to-bioluminescent-600"
            >
              Open Risk Map
            </Link>
            <Link
              href="/classify"
              className="glass-panel rounded-xl px-7 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
            >
              Classify Species
            </Link>
            <Link
              href="/report"
              className="glass-panel rounded-xl px-7 py-3 text-sm font-semibold text-slate-200 transition-all hover:border-ocean-500/30 hover:text-white"
            >
              Report Interaction
            </Link>
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
                  Mapping whale–vessel collision risk across CONUS, Alaska,
                  Hawaii &amp; Caribbean waters. Open-source data, AI
                  classification, and community science.
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
              Ocean data: E.U. Copernicus Marine Service Information · Map tiles
              © CARTO · Map data © OpenStreetMap contributors
            </div>
          </div>
        </footer>

      {/* local keyframes */}
      <style jsx global>{`
        @keyframes proto-bead {
          0%,
          100% {
            box-shadow:
              0 0 8px 2px rgba(34, 211, 238, 0.5),
              0 0 18px 6px rgba(34, 211, 238, 0.25);
          }
          50% {
            box-shadow:
              0 0 12px 3px rgba(34, 211, 238, 0.7),
              0 0 26px 9px rgba(34, 211, 238, 0.35);
          }
        }
      `}</style>
      </main>
    </div>
  );
}

/* ── Scroll-driven depth gauge ───────────────────────────────
   A submersible bead descends the rail as you scroll. The track
   above the bead is "lit"; each ocean zone activates as the bead
   passes it, and a live depth readout follows the bead down. This
   ties the rail directly into the story's descent. */
function DepthRail() {
  const [progress, setProgress] = useState(0); // 0..1 scroll fraction

  // Each zone is anchored to the real DOM position of its section's depth
  // label (id="depth-anchor-N"), so the rail markers line up exactly with
  // the depth titles as they scroll past — no hand-tuned fractions.
  const zones = [
    { id: "depth-anchor-0", d: "0 m", z: "Sunlight", dot: "bg-bioluminescent-400" },
    { id: "depth-anchor-1", d: "200 m", z: "Twilight", dot: "bg-coral-400" },
    { id: "depth-anchor-2", d: "500 m", z: "The Victims", dot: "bg-ocean-300" },
    { id: "depth-anchor-3", d: "1 000 m", z: "Midnight", dot: "bg-ocean-400" },
    { id: "depth-anchor-4", d: "4 000 m", z: "Abyss", dot: "bg-abyss-300" },
  ];

  const [positions, setPositions] = useState<number[]>(() =>
    zones.map(() => 0),
  );

  useEffect(() => {
    const measure = () => {
      const max =
        document.documentElement.scrollHeight - window.innerHeight;
      const sy = window.scrollY;
      setProgress(max > 0 ? Math.min(1, sy / max) : 0);
      // Convert each label's document position into the same 0..1 scale the
      // bead uses: the fraction at which the label reaches viewport centre.
      setPositions(
        zones.map((zone) => {
          const el = document.getElementById(zone.id);
          if (!el || max <= 0) return 0;
          const absTop = el.getBoundingClientRect().top + sy;
          return Math.min(
            1,
            Math.max(0, (absTop - window.innerHeight / 2) / max),
          );
        }),
      );
    };
    measure();
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    // Re-measure once async content (maps/images) has settled the layout.
    const t = window.setTimeout(measure, 600);
    return () => {
      window.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
      window.clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Real depth value for each anchored marker, in metres.
  const depthValues = [0, 200, 500, 1000, 4000];
  // Floor the readout descends toward below the last (4 000 m) anchor, so the
  // number keeps moving as the whale glides to the page bottom.
  const DEEP_FLOOR = 6000;
  // Interpolate the readout across the *measured* marker positions so the
  // number always agrees with whichever marker the whale is at/between —
  // the markers aren't linearly spaced in scroll, so a flat progress×4000
  // would disagree with them.
  const measured = positions.some((p) => p > 0);
  let liveDepth = Math.round(progress * 4000);
  if (measured) {
    const last = positions.length - 1;
    let d = depthValues[0];
    if (progress >= positions[last]) {
      // Past the deepest anchor (4 000 m abyss): keep descending toward the
      // abyssal-plain floor as the whale glides to the page bottom, so the
      // readout never freezes.
      const span = Math.max(1e-6, 1 - positions[last]);
      const f = Math.min(1, Math.max(0, (progress - positions[last]) / span));
      d = depthValues[last] + f * (DEEP_FLOOR - depthValues[last]);
    } else {
      for (let i = 1; i < positions.length; i++) {
        if (progress <= positions[i]) {
          const span = Math.max(1e-6, positions[i] - positions[i - 1]);
          const f = Math.max(0, (progress - positions[i - 1]) / span);
          d = depthValues[i - 1] + f * (depthValues[i] - depthValues[i - 1]);
          break;
        }
        d = depthValues[i];
      }
    }
    liveDepth = Math.round(d);
  }

  return (
    <div className="pointer-events-none fixed left-6 top-0 z-30 hidden h-screen flex-col justify-center sm:flex">
      <div className="relative h-[68vh] w-px">
        {/* dim full-length track */}
        <div className="absolute inset-0 w-px bg-gradient-to-b from-bioluminescent-400/20 via-slate-500/15 to-abyss-300/10" />

        {/* lit portion from surface down to the whale */}
        <div
          className="absolute left-0 top-0 w-px bg-gradient-to-b from-bioluminescent-400/80 via-bioluminescent-400/50 to-coral-400/50"
          style={{ height: `${progress * 100}%` }}
        />

        {/* zone markers — anchored to real section positions */}
        {zones.map((zone, i) => {
          const at = positions[i];
          const active = progress >= at - 0.02;
          return (
            <div
              key={zone.id}
              className="absolute left-0 flex items-center gap-3 transition-[top] duration-150 ease-out"
              style={{
                top: `${at * 100}%`,
                transform: "translateY(-50%)",
              }}
            >
              <span
                className={`h-[7px] w-[7px] rounded-full transition-all duration-500 ${
                  active ? zone.dot : "bg-slate-600"
                } ${active ? "scale-125" : "scale-100"}`}
              />
              <span
                className={`whitespace-nowrap font-mono text-[10px] uppercase tracking-widest transition-colors duration-500 ${
                  active ? "text-slate-300" : "text-slate-600"
                }`}
              >
                {zone.d}
                <span className="ml-2 text-slate-600">{zone.z}</span>
              </span>
            </div>
          );
        })}

        {/* travelling depth marker + live readout. On lg the 3D RailWhale
           dives this same line; here we keep the glowing halo + readout and
           a small bead fallback for sm/md where the 3D canvas is disabled. */}
        <div
          className="absolute left-0 transition-[top] duration-150 ease-out"
          style={{
            top: `${progress * 100}%`,
            transform: "translate(-50%, -50%)",
          }}
        >
          {/* pulsing bioluminescent halo (sits behind the 3D whale) */}
          <span className="absolute left-1/2 top-1/2 h-9 w-9 -translate-x-1/2 -translate-y-1/2 animate-pulse rounded-full bg-bioluminescent-400/25 blur-md" />
          {/* glowing bead — fallback for sm/md, hidden where 3D whale runs */}
          <span
            className="block h-3 w-3 rounded-full bg-bioluminescent-300 lg:hidden"
            style={{ animation: "proto-bead 2.4s ease-in-out infinite" }}
          />
          <span className="absolute left-9 top-1/2 -translate-y-1/2 whitespace-nowrap font-mono text-[10px] font-semibold tracking-widest text-bioluminescent-300">
            {liveDepth.toLocaleString()} m
          </span>
        </div>
      </div>
    </div>
  );
}


/* ── Editorial stat (no card, no icon chip) ─────────────────── */
function Stat({
  big,
  label,
  body,
  tone,
}: {
  big: string;
  label: string;
  body: string;
  tone: "ocean" | "seafoam" | "coral";
}) {
  const accent = {
    ocean: "text-ocean-300",
    seafoam: "text-seafoam-400",
    coral: "text-coral-400",
  }[tone];
  const rule = {
    ocean: "from-ocean-500/60",
    seafoam: "from-seafoam-500/60",
    coral: "from-coral-500/60",
  }[tone];
  return (
    <div>
      <p className={`font-display text-5xl font-black tracking-tight ${accent}`}>
        {big}
      </p>
      <p className="mt-2 max-w-xs font-display text-base font-semibold leading-tight text-white">
        {label}
      </p>
      <div className={`mt-4 h-px w-24 bg-gradient-to-r ${rule} to-transparent`} />
      <p className="mt-3 max-w-sm text-sm leading-relaxed text-slate-400">
        {body}
      </p>
    </div>
  );
}

/* ── Species row — silhouette + name + status, hairline ruled ── */
function SpeciesRow({ sp, index }: { sp: Species; index: number }) {
  return (
    <div className="group grid grid-cols-[auto_1fr] items-center gap-6 py-6 transition-colors hover:bg-white/[0.02] sm:grid-cols-[3rem_minmax(0,16rem)_1fr_auto]">
      {/* index numeral */}
      <span className="hidden font-mono text-xs text-slate-600 sm:block">
        {String(index + 1).padStart(2, "0")}
      </span>

      {/* silhouette + name */}
      <div className="flex items-center gap-4">
        <Image
          src={`/whale_detailed_smooth_icons/${sp.icon}`}
          alt=""
          width={72}
          height={36}
          className="h-9 w-[72px] flex-shrink-0 object-contain opacity-50 brightness-0 invert transition-opacity duration-300 group-hover:opacity-90"
        />
        <span className="font-display text-base font-bold leading-tight text-white">
          {sp.name}
        </span>
      </div>

      {/* note */}
      <p className="hidden max-w-xl text-sm leading-relaxed text-slate-400 sm:block">
        {sp.note}
      </p>

      {/* status */}
      <div className="text-right">
        <p className={`text-xs font-semibold ${sp.statusColor}`}>{sp.status}</p>
        <p className="mt-0.5 font-mono text-[10px] text-slate-500">
          pop. {sp.pop}
        </p>
      </div>
    </div>
  );
}

/* ── Sub-score row — editorial weighted bar ─────────────────── */
function ScoreRow({ s }: { s: SubScore }) {
  return (
    <div className="group flex items-center gap-5 border-b border-white/[0.05] py-4">
      <span className="w-10 flex-shrink-0 font-mono text-sm font-semibold text-slate-500">
        {s.pct}%
      </span>
      <div className="min-w-0 flex-1">
        <h4 className={`font-display text-sm font-bold ${s.accent}`}>
          {s.name}
        </h4>
        <p className="mt-0.5 text-xs text-slate-500">{s.desc}</p>
      </div>
      {/* weight bar — scaled so 25% fills the track */}
      <div className="hidden h-1.5 w-40 overflow-hidden rounded-full bg-white/[0.04] sm:block">
        <div
          className={`h-full rounded-full ${s.bar} opacity-70 transition-opacity group-hover:opacity-100`}
          style={{ width: `${(s.pct / 25) * 100}%` }}
        />
      </div>
    </div>
  );
}

/* ── Feature item — numbered editorial entry, no card ───────── */
function FeatureItem({ f, index }: { f: Feature; index: number }) {
  return (
    <Link href={f.href} className="group block">
      <div className="flex items-baseline gap-4">
        <span className="font-mono text-xs text-bioluminescent-400/50">
          {String(index + 1).padStart(2, "0")}
        </span>
        <h3 className="font-display text-xl font-bold text-white transition-colors group-hover:text-ocean-bright">
          {f.title}
        </h3>
      </div>
      <p className="mt-3 max-w-md pl-8 text-sm leading-relaxed text-slate-400">
        {f.desc}
      </p>
      <p className="mt-3 pl-8 text-sm font-semibold text-ocean-300 transition-colors group-hover:text-bioluminescent-400">
        {f.cta}
        <span className="ml-1 inline-block transition-transform group-hover:translate-x-1">
          →
        </span>
      </p>
    </Link>
  );
}

/* ── Pathway card — community / insights, minimal hairline ──── */
function PathwayCard({
  href,
  eyebrow,
  title,
  body,
  cta,
  tone,
}: {
  href: string;
  eyebrow: string;
  title: string;
  body: string;
  cta: string;
  tone: "seafoam" | "ocean";
}) {
  const accent = tone === "seafoam" ? "text-seafoam-400" : "text-ocean-300";
  const rule =
    tone === "seafoam" ? "border-seafoam-500/40" : "border-ocean-500/40";
  return (
    <Link
      href={href}
      className={`group block border-l-2 ${rule} pl-6 transition-colors hover:bg-white/[0.02]`}
    >
      <p
        className={`font-mono text-[11px] uppercase tracking-[0.3em] ${accent}`}
      >
        {eyebrow}
      </p>
      <h3 className="mt-3 font-display text-2xl font-bold text-white">
        {title}
      </h3>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-slate-400">
        {body}
      </p>
      <p
        className={`mt-4 text-sm font-semibold ${accent} transition-transform group-hover:translate-x-1`}
      >
        {cta} →
      </p>
    </Link>
  );
}
