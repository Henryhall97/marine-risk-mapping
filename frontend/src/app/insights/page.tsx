"use client";

import Link from "next/link";
import Image from "next/image";
import {
  IconShip,
  IconShield,
  IconMicroscope,
  IconWhale,
  IconChart,
  IconSatellite,
  IconWaves,
  IconMap,
  IconBuilding,
  IconTrending,
} from "@/components/icons/MarineIcons";

/* ── Stakeholder cards ─────────────────────────────────── */

const STAKEHOLDERS = [
  {
    href: "/insights/captains",
    title: "Vessel Captains",
    subtitle: "Navigation & Compliance",
    description:
      "Real-time route risk assessment, speed reduction zones, species awareness alerts, and seasonal guidance to minimise strike risk during transits.",
    Icon: IconShip,
    gradient: "from-blue-600 to-cyan-500",
    border: "border-blue-700/40",
    glow: "shadow-[0_0_30px_rgba(59,130,246,0.15)]",
    accent: "text-blue-400",
    features: [
      "Route risk scoring by season",
      "Speed zone compliance guidance",
      "Species encounter likelihood",
      "Climate-projected future risk zones",
    ],
  },
  {
    href: "/insights/policy",
    title: "Policy Makers",
    subtitle: "Regulation & Protection",
    description:
      "Identify protection gaps, evaluate SMA and MPA effectiveness, analyse seasonal risk patterns, and prioritise areas for new regulatory action.",
    Icon: IconShield,
    gradient: "from-amber-600 to-yellow-500",
    border: "border-amber-700/40",
    glow: "shadow-[0_0_30px_rgba(245,158,11,0.15)]",
    accent: "text-amber-400",
    features: [
      "Protection gap analysis",
      "SMA/MPA effectiveness metrics",
      "Projected future regulatory needs",
      "SSP scenario comparison",
    ],
  },
  {
    href: "/insights/researchers",
    title: "Marine Researchers",
    subtitle: "Whale Habitat & Distribution",
    description:
      "Explore expert and observation-based whale habitat models, covariate correlations, and access model performance diagnostics.",
    Icon: IconMicroscope,
    gradient: "from-purple-600 to-violet-500",
    border: "border-purple-700/40",
    glow: "shadow-[0_0_30px_rgba(147,51,234,0.15)]",
    accent: "text-purple-400",
    features: [
      "SDM & ISDM model outputs",
      "CMIP6 covariate projections",
      "Spatial cross-validation results",
      "Climate-driven habitat shifts",
    ],
  },
  {
    href: "/insights/conservation",
    title: "Conservation Groups",
    subtitle: "Priority Species & Threats",
    description:
      "Identify critical habitats, track species vulnerability, evaluate threat hotspots, and leverage community sighting data for advocacy.",
    Icon: IconWhale,
    gradient: "from-emerald-600 to-green-500",
    border: "border-emerald-700/40",
    glow: "shadow-[0_0_30px_rgba(16,185,129,0.15)]",
    accent: "text-emerald-400",
    features: [
      "Species vulnerability rankings",
      "Critical habitat identification",
      "Projected habitat change impacts",
      "Community sighting trends",
    ],
  },
  {
    href: "/insights/ports",
    title: "Port Authorities",
    subtitle: "Traffic Management & Safety",
    description:
      "Monitor vessel traffic density near port approaches, assess seasonal management area compliance, and evaluate local strike risk trends.",
    Icon: IconChart,
    gradient: "from-rose-600 to-pink-500",
    border: "border-rose-700/40",
    glow: "shadow-[0_0_30px_rgba(244,63,94,0.15)]",
    accent: "text-rose-400",
    features: [
      "Port-approach traffic density",
      "Commercial vessel breakdowns",
      "Climate-projected port risk trends",
      "Seasonal risk shift forecasting",
    ],
  },
];

/* ── Page ───────────────────────────────────────────────── */

export default function InsightsPage() {
  return (
    <main className="min-h-screen bg-abyss-950 px-4 pb-20 pt-24">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-12 text-center">
          <div className="mb-4 flex items-center justify-center gap-3">
            <Image
              src="/whale_watch_logo.png"
              alt="Whale Watch"
              width={60}
              height={40}
              className="h-10 w-[60px] object-contain opacity-60"
            />
            <h1 className="font-display text-4xl font-extrabold tracking-tight text-white">
              Stakeholder{" "}
              <span className="bg-gradient-to-r from-ocean-400 to-bioluminescent-400 bg-clip-text text-transparent">
                Insights
              </span>
            </h1>
          </div>
          <p className="mx-auto max-w-2xl text-sm leading-relaxed text-slate-400">
            Our collision risk data serves different audiences with different
            needs. Choose your stakeholder perspective below to see tailored
            recommendations, risk interpretations, and actionable guidance
            derived from 1.8 million analysed ocean cells — now including
            CMIP6 climate projections through the 2080s.
          </p>
        </div>

        {/* Stakeholder grid */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {STAKEHOLDERS.map((s) => (
            <Link
              key={s.href}
              href={s.href}
              className={`group relative overflow-hidden rounded-2xl border ${s.border} bg-abyss-900/70 p-6 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:bg-abyss-900 ${s.glow}`}
            >
              {/* Gradient accent bar */}
              <div
                className={`absolute left-0 top-0 h-1 w-full bg-gradient-to-r ${s.gradient} opacity-60 transition-opacity group-hover:opacity-100`}
              />

              {/* Icon + title */}
              <div className="mb-4 flex items-start gap-3">
                <div
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${s.gradient} shadow-lg`}
                >
                  <s.Icon className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">
                    {s.title}
                  </h2>
                  <p className={`text-xs font-medium ${s.accent}`}>
                    {s.subtitle}
                  </p>
                </div>
              </div>

              {/* Description */}
              <p className="mb-5 text-sm leading-relaxed text-slate-400">
                {s.description}
              </p>

              {/* Feature list */}
              <ul className="mb-4 space-y-1.5">
                {s.features.map((f) => (
                  <li
                    key={f}
                    className="flex items-center gap-2 text-xs text-slate-500"
                  >
                    <span
                      className={`h-1 w-1 shrink-0 rounded-full bg-gradient-to-r ${s.gradient}`}
                    />
                    {f}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <div
                className={`flex items-center gap-1 text-xs font-semibold ${s.accent} transition-all group-hover:gap-2`}
              >
                View insights
                <span className="transition-transform group-hover:translate-x-1">
                  →
                </span>
              </div>
            </Link>
          ))}
        </div>

        {/* Data provenance note */}
        <div className="mt-16 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-8 text-center">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-widest text-slate-500">
            About Our Data
          </h3>
          <p className="mx-auto max-w-3xl text-sm leading-relaxed text-slate-400">
            All insights are derived from our composite collision risk model
            covering 1.8M H3 resolution-7 cells (~5.2 km² each) across US
            coastal waters. The model integrates AIS vessel traffic (3.1B
            pings), OBIS cetacean sightings (1M records), NOAA ship strike
            history, Copernicus ocean covariates, bathymetry, regulatory
            zone data, and CMIP6 climate projections (SSP2-4.5 &amp; SSP5-8.5,
            2030s–2080s). Risk scores are relative (percentile-ranked 0–1),
            not absolute probabilities.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1"><IconSatellite className="h-4 w-4" /> MarineCadastre AIS</span>
            <span className="inline-flex items-center gap-1"><IconWhale className="h-4 w-4" /> OBIS Cetacean Records</span>
            <span className="inline-flex items-center gap-1"><IconWaves className="h-4 w-4" /> Copernicus Marine</span>
            <span className="inline-flex items-center gap-1"><IconMap className="h-4 w-4" /> GEBCO Bathymetry</span>
            <span className="inline-flex items-center gap-1"><IconBuilding className="h-4 w-4" /> NOAA MPA Inventory</span>
            <span className="inline-flex items-center gap-1"><IconTrending className="h-4 w-4" /> CMIP6 Projections</span>
          </div>
        </div>
      </div>
    </main>
  );
}
