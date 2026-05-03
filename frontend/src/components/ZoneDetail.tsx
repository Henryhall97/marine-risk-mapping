"use client";

import {
  IconShield,
  IconAnchor,
  IconWaves,
  IconTarget,
  IconWhale,
  IconMap,
  IconWarning,
  IconClock,
} from "@/components/icons/MarineIcons";
import type { ComponentType } from "react";

/* ── Zone type discriminator ─────────────────────────────── */

export type ZoneInfo =
  | { kind: "sma"; zone_name: string; is_active: boolean; season_label: string }
  | { kind: "proposed"; zone_name: string; is_active: boolean; season_label: string }
  | {
      kind: "slow_zone";
      zone_name: string;
      effective_start: string | null;
      effective_end: string | null;
      is_expired: boolean | null;
    }
  | { kind: "mpa"; mpa_name: string; protection_level: string | null }
  | {
      kind: "bia";
      bia_name: string | null;
      cmn_name: string | null;
      bia_type: string | null;
      bia_months: string | null;
    }
  | {
      kind: "critical_habitat";
      species_label: string;
      cmn_name: string | null;
      ch_status: string | null;
      is_proposed: boolean;
    }
  | { kind: "shipping_lane"; zone_type: string; name: string | null }
  | { kind: "contour"; depth_m: number; style: string };

/* ── Shared UI bits ──────────────────────────────────────── */

function Badge({
  text,
  color,
}: {
  text: string;
  color: "red" | "yellow" | "orange" | "green" | "teal" | "purple" | "blue" | "slate";
}) {
  const map: Record<string, string> = {
    red: "bg-red-500/20 text-red-300 border-red-500/30",
    yellow: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
    orange: "bg-orange-500/20 text-orange-300 border-orange-500/30",
    green: "bg-green-500/20 text-green-300 border-green-500/30",
    teal: "bg-teal-500/20 text-teal-300 border-teal-500/30",
    purple: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    blue: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    slate: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  };
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${map[color]}`}
    >
      {text}
    </span>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-sm text-slate-300">
      <span className="text-slate-500">{label}: </span>
      {value}
    </p>
  );
}

function Section({ children }: { children: React.ReactNode }) {
  return <div className="space-y-1">{children}</div>;
}

function Desc({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] leading-snug text-slate-500">{children}</p>
  );
}

/* ── Per-zone detail renderers ───────────────────────────── */

function SMADetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "sma" }>;
}) {
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text="Active SMA" color="red" />
        {z.is_active ? (
          <Badge text="In season" color="red" />
        ) : (
          <Badge text="Off season" color="slate" />
        )}
      </div>
      {z.season_label && <Row label="Season" value={z.season_label} />}
      <Desc>
        Seasonal Management Area under 50 CFR § 224.105. Vessels ≥65 ft
        (19.8 m) must travel at ≤10 knots within this zone during the
        active season to reduce the risk of lethal ship strikes on North
        Atlantic right whales.
      </Desc>
      <Desc>
        SMAs are <strong className="text-slate-400">mandatory</strong> and
        enforced by NOAA Office of Law Enforcement. Penalties for
        non-compliance include fines up to $54,000 per violation under the
        Endangered Species Act.
      </Desc>
      <Desc>
        Speed restrictions reduce strike lethality because the probability
        of a lethal injury drops sharply below 10 knots (Vanderlaan &
        Taggart, 2007).
      </Desc>
    </Section>
  );
}

function ProposedDetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "proposed" }>;
}) {
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text="Proposed" color="yellow" />
        {z.is_active ? (
          <Badge text="Would be active" color="yellow" />
        ) : (
          <Badge text="Off season" color="slate" />
        )}
      </div>
      {z.season_label && <Row label="Season" value={z.season_label} />}
      <Desc>
        NOAA-proposed vessel speed rule amendment that would expand the
        geographic and seasonal scope of mandatory speed restrictions to
        better protect right whales. This zone is{" "}
        <strong className="text-yellow-300">not yet enacted</strong> and
        carries no legal force.
      </Desc>
      <Desc>
        Shown on the map because it indicates areas of recognised collision
        risk identified by NOAA. These zones are deliberately excluded from
        the protection gap sub-score (they provide no real enforcement).
      </Desc>
    </Section>
  );
}

function SlowZoneDetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "slow_zone" }>;
}) {
  const expired = z.is_expired ?? false;
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text="DMA" color="orange" />
        {expired ? (
          <Badge text="Expired" color="slate" />
        ) : (
          <Badge text="Active" color="orange" />
        )}
      </div>
      {(z.effective_start || z.effective_end) && (
        <Row
          label="Period"
          value={`${z.effective_start ?? "?"} – ${z.effective_end ?? "?"}`}
        />
      )}
      <Desc>
        Dynamic Management Area — a temporary voluntary 10-knot speed
        advisory triggered when right whale aggregations are detected
        through aerial surveys or passive acoustic monitoring.
      </Desc>
      <Desc>
        DMAs typically last 15 days and shift geographically as whales
        move. Compliance is{" "}
        <strong className="text-orange-300">voluntary</strong> — studies
        show only ~5% of vessel transits actually slow down in DMAs
        (Silber et al., 2014).
      </Desc>
      <Desc>
        Despite low compliance, DMAs serve as early-warning indicators of
        whale presence and inform mariners about areas of elevated risk.
      </Desc>
    </Section>
  );
}

function MPADetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "mpa" }>;
}) {
  const level = z.protection_level ?? "Unknown";
  const levelColor = level.toLowerCase().includes("no-take")
    ? "green"
    : level.toLowerCase().includes("no impact")
      ? "green"
      : level.toLowerCase().includes("no access")
        ? "green"
        : ("slate" as const);
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text="MPA" color="green" />
        <Badge text={level} color={levelColor} />
      </div>
      <Desc>
        Marine Protected Area from the NOAA MPA Inventory. Protection
        levels range from strict no-take reserves (no extractive activities
        permitted) to multiple-use areas with limited restrictions.
      </Desc>
      <Desc>
        In the collision risk model, MPAs contribute to the{" "}
        <strong className="text-slate-400">protection gap</strong>{" "}
        sub-score: no-take zones score 0.10 (lowest gap), while
        unprotected waters score 1.0 (highest gap). This reflects the
        degree of regulatory oversight present.
      </Desc>
    </Section>
  );
}

function BIADetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "bia" }>;
}) {
  const typeLabel =
    z.bia_type
      ?.replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase()) ?? "Unknown type";
  const typeColor =
    z.bia_type === "feeding"
      ? "teal"
      : z.bia_type === "migratory"
        ? "blue"
        : z.bia_type === "reproductive"
          ? "purple"
          : ("slate" as const);
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text="BIA" color="teal" />
        <Badge text={typeLabel} color={typeColor} />
      </div>
      {z.cmn_name && <Row label="Species" value={z.cmn_name} />}
      <Row label="Active months" value={z.bia_months ?? "Year-round"} />
      <Desc>
        Biologically Important Area identified by NOAA CetMap — a
        science-based delineation of habitat that is particularly important
        for cetacean {z.bia_type ?? "life history functions"}.
      </Desc>
      <Desc>
        BIAs carry{" "}
        <strong className="text-slate-400">no legal protections</strong>,
        but they inform environmental impact assessments, vessel routing
        decisions, and management planning. Overlap between BIAs and
        shipping lanes is a key indicator of elevated collision risk.
      </Desc>
    </Section>
  );
}

function CriticalHabitatDetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "critical_habitat" }>;
}) {
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text="Critical Habitat" color="purple" />
        <Badge
          text={z.is_proposed ? "Proposed" : "Designated"}
          color={z.is_proposed ? "yellow" : "purple"}
        />
      </div>
      {(z.cmn_name || z.species_label) && (
        <Row label="Species" value={z.cmn_name ?? z.species_label} />
      )}
      {z.ch_status && <Row label="Status" value={z.ch_status} />}
      <Desc>
        Critical habitat designated (or proposed) under Section 4 of the
        Endangered Species Act. This is the{" "}
        <strong className="text-purple-300">
          strongest habitat protection
        </strong>{" "}
        under US law.
      </Desc>
      <Desc>
        Federal agencies must ensure their actions do not destroy or
        adversely modify critical habitat. This includes permitting of port
        expansions, offshore energy projects, military exercises, and
        dredging operations that could affect the area.
      </Desc>
      {z.is_proposed && (
        <Desc>
          This designation is currently{" "}
          <strong className="text-yellow-300">proposed</strong> and
          undergoing public comment. Final boundaries may differ.
        </Desc>
      )}
    </Section>
  );
}

function ShippingLaneDetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "shipping_lane" }>;
}) {
  const typeLabel = z.zone_type?.replace(/_/g, " ") ?? "Shipping Lane";
  const isTSS = typeLabel.toLowerCase().includes("traffic separation");
  const isPrecautionary = typeLabel.toLowerCase().includes("precautionary");
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text={typeLabel} color="blue" />
      </div>
      <Desc>
        {isTSS
          ? "Traffic Separation Scheme (TSS) — an IMO-designated routing " +
            "measure that separates opposing streams of vessel traffic into " +
            "defined lanes. TSSes are the primary tool for organising " +
            "commercial shipping in congested waterways."
          : isPrecautionary
            ? "Precautionary area where vessels should navigate with " +
              "particular caution. These zones are often established at the " +
              "convergence of traffic routes or near port approaches."
            : "Designated shipping route from the NOAA Coast Survey. " +
              "These corridors channel vessel traffic into predictable paths."}
      </Desc>
      <Desc>
        Overlap between shipping lanes and whale habitat is one of the
        strongest predictors of collision risk. In some cases, lanes have
        been shifted to reduce overlap — for example, the Boston TSS was
        moved in 2007, reducing right whale overlap by 58% (Fonnesbeck
        et al., 2008).
      </Desc>
    </Section>
  );
}

function ContourDetail({
  z,
}: {
  z: Extract<ZoneInfo, { kind: "contour" }>;
}) {
  const isShelf = z.depth_m <= 200;
  const isSlope = z.depth_m > 200 && z.depth_m <= 1000;
  return (
    <Section>
      <div className="flex flex-wrap items-center gap-2">
        <Badge text={`${z.depth_m} m`} color="blue" />
        <Badge
          text={isShelf ? "Continental shelf" : isSlope ? "Slope" : "Deep ocean"}
          color="slate"
        />
      </div>
      <Desc>
        {isShelf
          ? "Continental shelf — shallow waters (<200 m) over the " +
            "continental plate. High biological productivity supports " +
            "rich prey fields for baleen whales."
          : isSlope
            ? "Continental slope — the transition zone (200–1000 m) where " +
              "the shelf drops into deep water. Upwelling along the shelf " +
              "edge concentrates copepods and krill, making this zone " +
              "critical for feeding whales."
            : "Deep ocean (>1000 m) — open pelagic waters. While less " +
              "productive than the shelf edge, deep waters host sperm " +
              "whales and migrating baleen whales."}
      </Desc>
    </Section>
  );
}

/* ── Icon + title per zone kind ──────────────────────────── */

const ZONE_META: Record<
  ZoneInfo["kind"],
  { title: (z: ZoneInfo) => string; Icon: ComponentType<{ className?: string }>; accent: string }
> = {
  sma: {
    title: (z) => (z as Extract<ZoneInfo, { kind: "sma" }>).zone_name,
    Icon: IconShield,
    accent: "border-red-500/40",
  },
  proposed: {
    title: (z) => (z as Extract<ZoneInfo, { kind: "proposed" }>).zone_name,
    Icon: IconWarning,
    accent: "border-yellow-500/40",
  },
  slow_zone: {
    title: (z) => (z as Extract<ZoneInfo, { kind: "slow_zone" }>).zone_name,
    Icon: IconClock,
    accent: "border-orange-500/40",
  },
  mpa: {
    title: (z) => (z as Extract<ZoneInfo, { kind: "mpa" }>).mpa_name,
    Icon: IconShield,
    accent: "border-green-500/40",
  },
  bia: {
    title: (z) =>
      (z as Extract<ZoneInfo, { kind: "bia" }>).bia_name ?? "Biologically Important Area",
    Icon: IconWhale,
    accent: "border-teal-500/40",
  },
  critical_habitat: {
    title: (z) =>
      (z as Extract<ZoneInfo, { kind: "critical_habitat" }>).cmn_name ??
      (z as Extract<ZoneInfo, { kind: "critical_habitat" }>).species_label,
    Icon: IconTarget,
    accent: "border-purple-500/40",
  },
  shipping_lane: {
    title: (z) =>
      (z as Extract<ZoneInfo, { kind: "shipping_lane" }>).name ??
      (z as Extract<ZoneInfo, { kind: "shipping_lane" }>).zone_type,
    Icon: IconAnchor,
    accent: "border-blue-500/40",
  },
  contour: {
    title: (z) =>
      `Depth contour: ${(z as Extract<ZoneInfo, { kind: "contour" }>).depth_m} m`,
    Icon: IconWaves,
    accent: "border-sky-500/40",
  },
};

/* ── Main component ──────────────────────────────────────── */

export default function ZoneDetail({
  zone,
  onClose,
}: {
  zone: ZoneInfo;
  onClose: () => void;
}) {
  const meta = ZONE_META[zone.kind];
  const { Icon } = meta;
  const title = meta.title(zone);

  return (
    <div
      className={`absolute right-4 top-4 z-30 w-80 overflow-y-auto rounded-2xl border ${meta.accent} bg-abyss-900/95 shadow-2xl backdrop-blur-md`}
      style={{ maxHeight: "calc(100vh - 2rem)" }}
    >
      {/* Header */}
      <div className="flex items-start gap-3 border-b border-white/5 px-4 py-3">
        <Icon className="mt-0.5 h-5 w-5 flex-shrink-0 text-slate-400" />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-bold text-white">
            {title}
          </h3>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Zone detail
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-full p-1 text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
          aria-label="Close zone detail"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="space-y-3 px-4 py-3">
        {zone.kind === "sma" && <SMADetail z={zone} />}
        {zone.kind === "proposed" && <ProposedDetail z={zone} />}
        {zone.kind === "slow_zone" && <SlowZoneDetail z={zone} />}
        {zone.kind === "mpa" && <MPADetail z={zone} />}
        {zone.kind === "bia" && <BIADetail z={zone} />}
        {zone.kind === "critical_habitat" && (
          <CriticalHabitatDetail z={zone} />
        )}
        {zone.kind === "shipping_lane" && <ShippingLaneDetail z={zone} />}
        {zone.kind === "contour" && <ContourDetail z={zone} />}
      </div>
    </div>
  );
}
