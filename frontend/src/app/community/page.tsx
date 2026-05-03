"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import { SonarPing } from "@/components/animations";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import dynamic from "next/dynamic";
import Image from "next/image";
import { useSearchParams, useRouter } from "next/navigation";
import { Fragment, type ReactNode, Suspense, useCallback, useEffect, useRef, useState } from "react";
import type { MapSubmission } from "@/components/SubmissionMap";
import {
  IconWhale,
  IconDolphin,
  IconEye,
  IconStar,
  IconMicroscope,
  IconMap,
  IconChart,
  IconMicrophone,
  IconShield,
  IconThumbUp,
  IconThumbDown,
  IconCamera,
  IconPin,
  IconWaves,
  IconClipboard,
  IconCheck,
  IconWarning,
  IconUser,
  IconCalendar,
  IconUsers,
  IconClock,
  IconShip,
  IconAnchor,
  IconComment,
  IconInfo,
} from "@/components/icons/MarineIcons";

const SubmissionMap = dynamic(() => import("@/components/SubmissionMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full flex-col items-center justify-center gap-2 bg-abyss-900">
      <SonarPing size={56} ringCount={3} active />
      <span className="text-xs text-ocean-400/70">Loading map…</span>
    </div>
  ),
});

const EventsPanel = dynamic(() => import("@/components/EventsPanel"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center gap-2 py-20">
      <SonarPing size={56} ringCount={3} active />
      <span className="text-xs text-ocean-400/70">Loading events…</span>
    </div>
  ),
});

const SightingGlobe = dynamic(() => import("@/components/SightingGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border border-ocean-800/30 bg-abyss-900/50">
      <SonarPing size={56} ringCount={3} active />
      <span className="text-xs text-ocean-400/70">Loading globe…</span>
    </div>
  ),
});

/* ── Types ──────────────────────────────────────────────── */

interface SubmissionSummary {
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
  moderator_status: string | null;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar_url: string | null;
  submitter_is_moderator: boolean;
  has_photo: boolean;
  has_audio: boolean;
  verification_score: number | null;
  /* Biological observation fields */
  group_size: number | null;
  behavior: string | null;
  life_stage: string | null;
  calf_present: boolean | null;
  sea_state_beaufort: number | null;
  observation_platform: string | null;
  scientific_name: string | null;
  sighting_datetime: string | null;
}

type StatusFilter =
  | "all"
  | "unverified"
  | "verified"
  | "community_verified"
  | "under_review"
  | "disputed"
  | "rejected";
type SpeciesFilter = "all" | string;
type RegionFilter = "all" | string;
type ViewMode = "tiles" | "list" | "map" | "stats";

/* ── Community stats types ──────────────────────────────── */
interface CommunityStatsData {
  total_sightings: number;
  total_contributors: number;
  species_documented: number;
  verified_count: number;
  needs_review_count: number;
  photo_count: number;
  sightings_this_week: number;
  total_events: number;
}

interface RecentActivityItem {
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

interface TopContributorItem {
  user_id: number;
  display_name: string | null;
  reputation_score: number;
  reputation_tier: string;
  avatar_url: string | null;
  submission_count: number;
  species_count: number;
}

interface ActivityDay {
  date: string;
  count: number;
}

interface WotWComment {
  id: number;
  body: string;
  created_at: string;
  display_name: string | null;
  reputation_tier: string | null;
  avatar_url: string | null;
  user_id: number | null;
}

interface WhaleOfTheWeekItem {
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
  top_comments: WotWComment[];
}

interface CommunityStatsResponse {
  stats: CommunityStatsData;
  recent_activity: RecentActivityItem[];
  top_contributors: TopContributorItem[];
  activity_histogram: ActivityDay[];
  whale_of_the_week: WhaleOfTheWeekItem | null;
}

/* ── Boat leaderboard types ─────────────────────────────── */
interface BoatLeaderboardItem {
  vessel_id: number;
  vessel_name: string;
  vessel_type: string;
  profile_photo_url: string | null;
  owner_name: string | null;
  owner_id: number | null;
  crew_count: number;
  submission_count: number;
  species_count: number;
}

interface BoatLeaderboardResponse {
  boats: BoatLeaderboardItem[];
}

const STATUS_STYLE: Record<string, { bg: string; dot: string; text: string }> = {
  unverified: { bg: "bg-slate-500/10", dot: "bg-slate-400", text: "text-slate-300" },
  verified: { bg: "bg-emerald-500/15", dot: "bg-emerald-400", text: "text-emerald-300" },
  community_verified: { bg: "bg-green-500/15", dot: "bg-green-400", text: "text-green-300" },
  under_review: { bg: "bg-blue-500/15", dot: "bg-blue-400", text: "text-blue-300" },
  rejected: { bg: "bg-red-500/15", dot: "bg-red-400", text: "text-red-300" },
  disputed: { bg: "bg-yellow-500/15", dot: "bg-yellow-400", text: "text-yellow-300" },
};

const STATUS_LABELS: Record<string, string> = {
  unverified: "Unverified",
  verified: "Mod Verified",
  community_verified: "Community Verified",
  under_review: "Under Review",
  rejected: "Rejected",
  disputed: "Disputed",
};

const RISK_ACCENT: Record<string, string> = {
  critical: "from-red-600/30",
  high: "from-orange-600/25",
  medium: "from-yellow-600/20",
  low: "from-green-600/15",
};

const RISK_TEXT: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

const RISK_BAR_COLOR: Record<string, string> = {
  critical: "bg-red-500/70",
  high: "bg-orange-500/70",
  medium: "bg-yellow-500/70",
  low: "bg-green-500/70",
};

const TIER_STYLE: Record<string, { color: string; icon: ReactNode }> = {
  newcomer: { color: "text-slate-400", icon: <IconUser className="h-3.5 w-3.5" /> },
  observer: { color: "text-ocean-400", icon: <IconEye className="h-3.5 w-3.5" /> },
  contributor: { color: "text-green-400", icon: <IconStar className="h-3.5 w-3.5" /> },
  expert: { color: "text-purple-400", icon: <IconMicroscope className="h-3.5 w-3.5" /> },
  authority: { color: "text-yellow-400", icon: <IconStar className="h-3.5 w-3.5" /> },
};

const SPECIES_EMOJI: Record<string, ReactNode> = {
  humpback_whale: <IconWhale className="h-5 w-5" />,
  humpback: <IconWhale className="h-5 w-5" />,
  right_whale: <IconWhale className="h-5 w-5" />,
  southern_right_whale: <IconWhale className="h-5 w-5" />,
  fin_whale: <IconWhale className="h-5 w-5" />,
  blue_whale: <IconWhale className="h-5 w-5" />,
  minke_whale: <IconWhale className="h-5 w-5" />,
  sei_whale: <IconWhale className="h-5 w-5" />,
  sperm_whale: <IconWhale className="h-5 w-5" />,
  gray_whale: <IconWhale className="h-5 w-5" />,
  bowhead: <IconWhale className="h-5 w-5" />,
  brydes_whale: <IconWhale className="h-5 w-5" />,
  omuras_whale: <IconWhale className="h-5 w-5" />,
  rices_whale: <IconWhale className="h-5 w-5" />,
  pygmy_right_whale: <IconWhale className="h-5 w-5" />,
  beaked_whale: <IconWhale className="h-5 w-5" />,
  beluga: <IconWhale className="h-5 w-5" />,
  narwhal: <IconWhale className="h-5 w-5" />,
  dwarf_sperm_whale: <IconWhale className="h-5 w-5" />,
  pygmy_sperm_whale: <IconWhale className="h-5 w-5" />,
  small_sperm_whale: <IconWhale className="h-5 w-5" />,
  pilot_whale: <IconWhale className="h-5 w-5" />,
  killer_whale: <IconDolphin className="h-5 w-5" />,
  orca: <IconDolphin className="h-5 w-5" />,
  bottlenose_dolphin: <IconDolphin className="h-5 w-5" />,
  common_dolphin: <IconDolphin className="h-5 w-5" />,
  spotted_dolphin: <IconDolphin className="h-5 w-5" />,
  striped_dolphin: <IconDolphin className="h-5 w-5" />,
  rissos_dolphin: <IconDolphin className="h-5 w-5" />,
  whitesided_dolphin: <IconDolphin className="h-5 w-5" />,
  hectors_dolphin: <IconDolphin className="h-5 w-5" />,
  other_dolphin: <IconDolphin className="h-5 w-5" />,
  harbor_porpoise: <IconDolphin className="h-5 w-5" />,
  dalls_porpoise: <IconDolphin className="h-5 w-5" />,
  vaquita: <IconDolphin className="h-5 w-5" />,
  other_porpoise: <IconDolphin className="h-5 w-5" />,
};

/** Map species_group → species icon .jpg filename (in /species/) */
const SPECIES_ICON_FILES: Record<string, string> = {
  humpback_whale: "humpback_whale.jpg",
  humpback: "humpback.jpg",
  right_whale: "right_whale.jpg",
  southern_right_whale: "southern_right_whale.jpg",
  fin_whale: "fin_whale.jpg",
  blue_whale: "blue_whale.jpg",
  minke_whale: "minke_whale.jpg",
  sei_whale: "sei_whale.jpg",
  sperm_whale: "sperm_whale.jpg",
  gray_whale: "gray_whale.jpg",
  bowhead: "bowhead.jpg",
  brydes_whale: "brydes_whale.jpg",
  omuras_whale: "omuras_whale.jpg",
  rices_whale: "rices_whale.jpg",
  pygmy_right_whale: "pygmy_right_whale.jpg",
  beaked_whale: "beaked_whale.jpg",
  beluga: "beluga.jpg",
  narwhal: "narwhal.jpg",
  dwarf_sperm_whale: "dwarf_sperm_whale.jpg",
  pygmy_sperm_whale: "pygmy_sperm_whale.jpg",
  small_sperm_whale: "small_sperm_whale.jpg",
  pilot_whale: "pilot_whale.jpg",
  killer_whale: "orca.jpg",
  orca: "orca.jpg",
  bottlenose_dolphin: "bottlenose_dolphin.jpg",
  common_dolphin: "common_dolphin.jpg",
  spotted_dolphin: "spotted_dolphin.jpg",
  striped_dolphin: "striped_dolphin.jpg",
  rissos_dolphin: "rissos_dolphin.jpg",
  whitesided_dolphin: "whitesided_dolphin.jpg",
  hectors_dolphin: "hectors_dolphin.jpg",
  other_dolphin: "other_dolphin.jpg",
  harbor_porpoise: "harbor_porpoise.jpg",
  dalls_porpoise: "dalls_porpoise.jpg",
  vaquita: "vaquita.jpg",
  other_porpoise: "other_porpoise.jpg",
  unid_baleen: "unid_baleen.jpg",
  unid_toothed: "unid_toothed.jpg",
  unid_dolphin: "unid_dolphin.jpg",
  unid_rorqual: "unid_rorqual.jpg",
  unid_cetacean: "unid_cetacean.jpg",
  other_cetacean: "unid_cetacean.jpg",
};

/** Smooth detailed whale silhouette PNGs (in /whale_detailed_smooth_icons/).
 *  Only the 9 original species have these — others fall back to the whale tail
 *  logo. More will be added over time. */
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

/** CSS filter tint per species based on IUCN conservation status.
 *  Applied after `invert` (white base) to produce a coloured silhouette.
 *  Red = critically endangered, orange = endangered,
 *  yellow = vulnerable, green = least concern, slate = data deficient. */
const TINT_GREEN = "brightness(1) sepia(1) saturate(5) hue-rotate(85deg)";
const TINT_RED = "brightness(0.9) sepia(1) saturate(6) hue-rotate(-10deg)";
const TINT_ORANGE = "brightness(1) sepia(1) saturate(5) hue-rotate(15deg)";
const TINT_YELLOW = "brightness(1) sepia(1) saturate(5) hue-rotate(40deg)";
const TINT_SLATE = "brightness(0.8) sepia(0.2) saturate(0.5) hue-rotate(180deg)";

const SPECIES_RISK_TINT: Record<string, string> = {
  /* Least Concern — green */
  humpback_whale: TINT_GREEN, humpback: TINT_GREEN,
  minke_whale: TINT_GREEN, gray_whale: TINT_GREEN,
  common_dolphin: TINT_GREEN, bottlenose_dolphin: TINT_GREEN,
  striped_dolphin: TINT_GREEN, spotted_dolphin: TINT_GREEN,
  whitesided_dolphin: TINT_GREEN, rissos_dolphin: TINT_GREEN,
  harbor_porpoise: TINT_GREEN, dalls_porpoise: TINT_GREEN,
  beluga: TINT_GREEN, narwhal: TINT_GREEN,
  /* Critically Endangered — red */
  right_whale: TINT_RED, vaquita: TINT_RED, rices_whale: TINT_RED,
  /* Endangered — orange */
  blue_whale: TINT_ORANGE, sei_whale: TINT_ORANGE,
  southern_right_whale: TINT_ORANGE,
  /* Vulnerable — yellow */
  fin_whale: TINT_YELLOW, sperm_whale: TINT_YELLOW,
  hectors_dolphin: TINT_YELLOW,
  /* Data Deficient / LC — slate */
  killer_whale: TINT_SLATE, orca: TINT_SLATE,
  beaked_whale: TINT_SLATE, pilot_whale: TINT_SLATE,
  bowhead: TINT_SLATE, brydes_whale: TINT_SLATE,
  omuras_whale: TINT_SLATE, pygmy_right_whale: TINT_SLATE,
  dwarf_sperm_whale: TINT_SLATE, pygmy_sperm_whale: TINT_SLATE,
  small_sperm_whale: TINT_SLATE,
  other_dolphin: TINT_SLATE, other_porpoise: TINT_SLATE,
  other_cetacean: TINT_SLATE,
  unid_baleen: TINT_SLATE, unid_toothed: TINT_SLATE,
  unid_dolphin: TINT_SLATE, unid_rorqual: TINT_SLATE,
  unid_cetacean: TINT_SLATE,
};

const SPECIES_LABELS: Record<string, string> = {
  /* ── Baleen whales ── */
  humpback_whale: "Humpback Whale",
  humpback: "Humpback Whale",
  right_whale: "Right Whale",
  southern_right_whale: "Southern Right Whale",
  fin_whale: "Fin Whale",
  blue_whale: "Blue Whale",
  minke_whale: "Minke Whale",
  sei_whale: "Sei Whale",
  bowhead: "Bowhead Whale",
  brydes_whale: "Bryde's Whale",
  rices_whale: "Rice's Whale",
  omuras_whale: "Omura's Whale",
  gray_whale: "Gray Whale",
  pygmy_right_whale: "Pygmy Right Whale",
  /* ── Toothed whales ── */
  sperm_whale: "Sperm Whale",
  pygmy_sperm_whale: "Pygmy Sperm Whale",
  dwarf_sperm_whale: "Dwarf Sperm Whale",
  small_sperm_whale: "Small Sperm Whale",
  killer_whale: "Orca",
  orca: "Orca",
  beaked_whale: "Beaked Whale",
  beluga: "Beluga",
  narwhal: "Narwhal",
  pilot_whale: "Pilot Whale",
  /* ── Dolphins ── */
  bottlenose_dolphin: "Bottlenose Dolphin",
  common_dolphin: "Common Dolphin",
  rissos_dolphin: "Risso's Dolphin",
  spotted_dolphin: "Spotted Dolphin",
  striped_dolphin: "Striped Dolphin",
  whitesided_dolphin: "White-sided Dolphin",
  hectors_dolphin: "Hector's Dolphin",
  other_dolphin: "Other Dolphin",
  /* ── Porpoises ── */
  harbor_porpoise: "Harbor Porpoise",
  dalls_porpoise: "Dall's Porpoise",
  vaquita: "Vaquita",
  other_porpoise: "Other Porpoise",
  /* ── Unidentified ── */
  unid_cetacean: "Unidentified Cetacean",
  unid_baleen: "Unidentified Baleen",
  unid_toothed: "Unidentified Toothed Whale",
  unid_rorqual: "Unidentified Rorqual",
  unid_dolphin: "Unidentified Dolphin",
  other_cetacean: "Other Cetacean",
};

/** Grouped species for filter dropdowns — full crosswalk taxonomy. */
const SPECIES_FILTER_GROUPS: {
  label: string;
  items: { value: string; label: string }[];
}[] = [
  {
    label: "Baleen Whales",
    items: [
      { value: "humpback_whale", label: "Humpback Whale" },
      { value: "right_whale", label: "Right Whale" },
      { value: "southern_right_whale", label: "Southern Right Whale" },
      { value: "blue_whale", label: "Blue Whale" },
      { value: "fin_whale", label: "Fin Whale" },
      { value: "sei_whale", label: "Sei Whale" },
      { value: "minke_whale", label: "Minke Whale" },
      { value: "bowhead", label: "Bowhead Whale" },
      { value: "brydes_whale", label: "Bryde's Whale" },
      { value: "rices_whale", label: "Rice's Whale" },
      { value: "gray_whale", label: "Gray Whale" },
      { value: "omuras_whale", label: "Omura's Whale" },
      { value: "pygmy_right_whale", label: "Pygmy Right Whale" },
    ],
  },
  {
    label: "Toothed Whales",
    items: [
      { value: "sperm_whale", label: "Sperm Whale" },
      { value: "killer_whale", label: "Orca" },
      { value: "beaked_whale", label: "Beaked Whale" },
      { value: "pilot_whale", label: "Pilot Whale" },
      { value: "beluga", label: "Beluga" },
      { value: "narwhal", label: "Narwhal" },
      { value: "pygmy_sperm_whale", label: "Pygmy Sperm Whale" },
      { value: "dwarf_sperm_whale", label: "Dwarf Sperm Whale" },
    ],
  },
  {
    label: "Dolphins",
    items: [
      { value: "bottlenose_dolphin", label: "Bottlenose Dolphin" },
      { value: "common_dolphin", label: "Common Dolphin" },
      { value: "rissos_dolphin", label: "Risso's Dolphin" },
      { value: "spotted_dolphin", label: "Spotted Dolphin" },
      { value: "striped_dolphin", label: "Striped Dolphin" },
      { value: "whitesided_dolphin", label: "White-sided Dolphin" },
      { value: "hectors_dolphin", label: "Hector's Dolphin" },
      { value: "other_dolphin", label: "Other Dolphin" },
    ],
  },
  {
    label: "Porpoises",
    items: [
      { value: "harbor_porpoise", label: "Harbor Porpoise" },
      { value: "dalls_porpoise", label: "Dall's Porpoise" },
      { value: "vaquita", label: "Vaquita" },
      { value: "other_porpoise", label: "Other Porpoise" },
    ],
  },
  {
    label: "Unidentified",
    items: [
      { value: "unid_cetacean", label: "Unidentified Cetacean" },
      { value: "unid_baleen", label: "Unidentified Baleen" },
      { value: "unid_toothed", label: "Unidentified Toothed Whale" },
      { value: "unid_dolphin", label: "Unidentified Dolphin" },
      { value: "other_cetacean", label: "Other Cetacean" },
    ],
  },
];

/** Flat list of all species values for quick lookup. */
const ALL_SPECIES_VALUES = SPECIES_FILTER_GROUPS.flatMap(
  (g) => g.items.map((i) => i.value),
);

const SPECIES_ORDER = ALL_SPECIES_VALUES;

const REGION_LABELS: Record<string, string> = {
  all: "All Regions",
  /* ── North America ── */
  north_atlantic: "N. Atlantic (US/Canada)",
  south_atlantic: "S. Atlantic (US)",
  gulf: "Gulf of Mexico",
  pacific: "Pacific (US/Canada)",
  alaska: "Alaska",
  hawaii: "Hawai'i",
  caribbean: "Caribbean",
  /* ── Europe ── */
  northeast_atlantic: "NE Atlantic / N. Sea",
  mediterranean: "Mediterranean",
  baltic: "Baltic Sea",
  /* ── Southern Hemisphere ── */
  south_pacific: "South Pacific",
  south_atlantic_ocean: "South Atlantic",
  southern_ocean: "Southern Ocean",
  indian_ocean: "Indian Ocean",
  /* ── Asia / Oceania ── */
  northwest_pacific: "NW Pacific (Asia)",
  southeast_asia: "Southeast Asia",
  australasia: "Australasia",
  /* ── Africa / Middle East ── */
  west_africa: "West Africa",
  east_africa: "East Africa / Red Sea",
  /* ── Arctic ── */
  arctic: "Arctic",
  /* ── Catch-all ── */
  other_region: "Other / Open Ocean",
};

/** Region filter groups for grouped dropdown display. */
const REGION_FILTER_GROUPS: { label: string; regions: string[] }[] = [
  {
    label: "North America",
    regions: [
      "north_atlantic", "south_atlantic", "gulf", "pacific",
      "alaska", "hawaii", "caribbean",
    ],
  },
  { label: "Europe", regions: ["northeast_atlantic", "mediterranean", "baltic"] },
  {
    label: "Southern Hemisphere",
    regions: ["south_pacific", "south_atlantic_ocean", "southern_ocean", "indian_ocean"],
  },
  { label: "Asia / Oceania", regions: ["northwest_pacific", "southeast_asia", "australasia"] },
  { label: "Africa / Middle East", regions: ["west_africa", "east_africa"] },
  { label: "Polar / Other", regions: ["arctic", "other_region"] },
];

/** Regional summaries — geography, key species, risk context. */
const REGION_SUMMARIES: Record<
  string,
  {
    fullName: string;
    description: string;
    keySpecies: string[];
    bbox: string;
    riskLevel: string;
    riskColor: string;
    keyThreats: string[];
    notableAreas: string[];
  }
> = {
  north_atlantic: {
    fullName: "North Atlantic",
    description:
      "The most critical waters for whale–vessel collision risk in "
      + "the US. Home to the critically endangered North Atlantic right "
      + "whale and major shipping lanes serving Boston, New York, and "
      + "Philadelphia. Seasonal Management Areas enforce voluntary speed "
      + "reductions Nov–May.",
    keySpecies: ["right_whale", "humpback_whale", "fin_whale", "minke_whale"],
    bbox: "35°N–52°N, 59°W–82°W",
    riskLevel: "Critical",
    riskColor: "text-red-400",
    keyThreats: [
      "Dense shipping traffic",
      "Right whale calving migration",
      "Fishing gear entanglement",
    ],
    notableAreas: [
      "Cape Cod Bay",
      "Stellwagen Bank",
      "Great South Channel",
      "Gulf of Maine",
    ],
  },
  south_atlantic: {
    fullName: "South Atlantic",
    description:
      "Right whale calving grounds off Georgia and Florida make this "
      + "region critical in winter months. Port traffic from Jacksonville, "
      + "Savannah, and Charleston intersects with mother–calf pairs "
      + "during the calving season (Nov–Apr).",
    keySpecies: ["right_whale", "humpback_whale", "fin_whale"],
    bbox: "24°N–35°N, 59°W–82°W",
    riskLevel: "High",
    riskColor: "text-orange-400",
    keyThreats: [
      "Calving ground overlap with ports",
      "Military sonar exercises",
      "Coastal development",
    ],
    notableAreas: [
      "Right whale calving grounds (FL/GA)",
      "Cape Hatteras",
      "Charleston Bump",
    ],
  },
  gulf: {
    fullName: "Gulf of Mexico",
    description:
      "A resident population of Bryde's whales (recently described as "
      + "Rice's whale, ~50 individuals) makes the Gulf a hotspot for "
      + "conservation. Heavy oil and gas vessel traffic, plus tanker "
      + "routes to Houston and New Orleans, compound the risk.",
    keySpecies: ["sperm_whale", "fin_whale", "humpback_whale"],
    bbox: "18°N–31°N, 82°W–98°W",
    riskLevel: "High",
    riskColor: "text-orange-400",
    keyThreats: [
      "Oil & gas vessel traffic",
      "Seismic surveys",
      "Deepwater Horizon legacy",
    ],
    notableAreas: [
      "De Soto Canyon",
      "Mississippi Canyon",
      "Flower Garden Banks",
    ],
  },
  pacific: {
    fullName: "Pacific Coast",
    description:
      "Blue, humpback, and fin whales feed along the productive "
      + "California Current from Baja to British Columbia. Vessel traffic "
      + "serving LA/Long Beach, San Francisco, and Seattle–Tacoma creates "
      + "significant overlap with whale foraging grounds, particularly "
      + "in the Santa Barbara Channel.",
    keySpecies: ["blue_whale", "humpback_whale", "fin_whale", "killer_whale"],
    bbox: "32°N–50°N, 130°W–117°W",
    riskLevel: "High",
    riskColor: "text-orange-400",
    keyThreats: [
      "Santa Barbara Channel shipping",
      "Container ship speed",
      "Krill decline from warming",
    ],
    notableAreas: [
      "Santa Barbara Channel",
      "Monterey Bay",
      "Channel Islands NMS",
      "Olympic Coast NMS",
    ],
  },
  alaska: {
    fullName: "Alaska",
    description:
      "Nutrient-rich subarctic waters support large seasonal "
      + "aggregations of humpback, fin, and killer whales. Vessel traffic "
      + "is lower than the lower-48 but concentrated in narrow passes "
      + "and cruise ship corridors through the Inside Passage.",
    keySpecies: [
      "humpback_whale", "fin_whale", "killer_whale", "sperm_whale",
    ],
    bbox: "50°N–65°N, 180°W–130°W",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: [
      "Cruise ship corridors",
      "Arctic shipping expansion",
      "Prey availability shifts",
    ],
    notableAreas: [
      "Inside Passage",
      "Glacier Bay",
      "Kodiak Island",
      "Aleutian Islands",
    ],
  },
  hawaii: {
    fullName: "Hawai'i",
    description:
      "Primary breeding and calving grounds for North Pacific "
      + "humpback whales (Dec–May). The shallow warm waters between "
      + "Maui, Lana'i, and Kaho'olawe host the densest whale "
      + "aggregations. Inter-island ferry and tour boat traffic "
      + "creates localised collision risk.",
    keySpecies: ["humpback_whale", "sperm_whale", "fin_whale"],
    bbox: "18°N–23°N, 162°W–154°W",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: [
      "Tour boat crowding",
      "Inter-island ferries",
      "Navy sonar exercises",
    ],
    notableAreas: [
      "Maui Nui Basin",
      "Hawaiian Islands Humpback Whale NMS",
      "Penguin Bank",
    ],
  },
  caribbean: {
    fullName: "Caribbean",
    description:
      "Humpback whales breed in the warm waters north of Puerto Rico "
      + "and the US Virgin Islands (Jan–Apr). Cruise ship traffic and "
      + "cargo routes to San Juan create seasonal overlap with whale "
      + "aggregations on Silver Bank and Navidad Bank.",
    keySpecies: ["humpback_whale", "sperm_whale"],
    bbox: "15°N–27°N, 68°W–60°W",
    riskLevel: "Low",
    riskColor: "text-green-400",
    keyThreats: [
      "Cruise ship traffic",
      "Underwater noise",
      "Climate-driven habitat shifts",
    ],
    notableAreas: [
      "Silver Bank",
      "Mona Passage",
      "Virgin Islands",
    ],
  },
  /* ── Europe ── */
  northeast_atlantic: {
    fullName: "NE Atlantic / North Sea",
    description:
      "Busy shipping lanes through the English Channel, North Sea, "
      + "and Bay of Biscay overlap with fin, minke, and humpback whale "
      + "habitat. IMO-designated Traffic Separation Schemes help but "
      + "vessel density remains very high.",
    keySpecies: ["fin_whale", "minke_whale", "humpback_whale", "harbor_porpoise"],
    bbox: "35°N–72°N, 30°W–15°E",
    riskLevel: "High",
    riskColor: "text-orange-400",
    keyThreats: ["Dense shipping lanes", "Offshore wind construction", "Fisheries bycatch"],
    notableAreas: ["English Channel", "Bay of Biscay", "Norwegian coast", "Azores"],
  },
  mediterranean: {
    fullName: "Mediterranean Sea",
    description:
      "The Mediterranean's resident fin and sperm whale populations "
      + "face heavy vessel traffic from cruise ships, ferries, and cargo "
      + "routes. The Pelagos Sanctuary provides some protection in the "
      + "Ligurian Sea.",
    keySpecies: ["fin_whale", "sperm_whale", "striped_dolphin", "bottlenose_dolphin"],
    bbox: "30°N–46°N, 6°W–42°E",
    riskLevel: "High",
    riskColor: "text-orange-400",
    keyThreats: ["Ferry traffic", "Cruise ships", "Noise pollution"],
    notableAreas: ["Pelagos Sanctuary", "Strait of Gibraltar", "Hellenic Trench"],
  },
  baltic: {
    fullName: "Baltic Sea",
    description:
      "A semi-enclosed sea with critically endangered harbor porpoise "
      + "populations. Intense shipping traffic through narrow straits "
      + "and military activity pose ongoing threats.",
    keySpecies: ["harbor_porpoise", "minke_whale"],
    bbox: "53°N–66°N, 10°E–30°E",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Shipping density", "Noise", "Fisheries bycatch"],
    notableAreas: ["Danish Straits", "Gulf of Finland", "Gotland Basin"],
  },
  /* ── Southern Hemisphere ── */
  south_pacific: {
    fullName: "South Pacific",
    description:
      "Breeding grounds for humpback and blue whales span from Tonga "
      + "and New Caledonia to the Chilean coast. Vessel traffic is "
      + "growing with Pacific trade routes.",
    keySpecies: ["humpback_whale", "blue_whale", "sperm_whale"],
    bbox: "0°–60°S, 70°W–180°",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Increasing shipping", "Krill fishing", "Climate change"],
    notableAreas: ["Tonga", "Galápagos", "Humboldt Current", "Easter Island"],
  },
  south_atlantic_ocean: {
    fullName: "South Atlantic Ocean",
    description:
      "Southern right whales calve along the coasts of Argentina, "
      + "Brazil, and South Africa. Tanker and bulk carrier routes "
      + "cross important whale habitat.",
    keySpecies: ["southern_right_whale", "humpback_whale", "sei_whale"],
    bbox: "0°–60°S, 70°W–20°E",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Tanker routes", "Offshore oil", "Fisheries"],
    notableAreas: ["Valdés Peninsula", "Abrolhos Bank", "Tristan da Cunha"],
  },
  southern_ocean: {
    fullName: "Southern Ocean / Antarctic",
    description:
      "Critical krill-feeding grounds for blue, fin, and humpback "
      + "whales. Increasing tourism and fishing vessel traffic in "
      + "the Antarctic Peninsula region raises collision risk.",
    keySpecies: ["blue_whale", "fin_whale", "humpback_whale", "minke_whale"],
    bbox: "60°S–80°S, all longitudes",
    riskLevel: "Low",
    riskColor: "text-green-400",
    keyThreats: ["Tourism vessels", "Krill fishing", "Ice retreat"],
    notableAreas: ["Antarctic Peninsula", "South Georgia", "Ross Sea"],
  },
  indian_ocean: {
    fullName: "Indian Ocean",
    description:
      "Blue whales, humpbacks, and sperm whales migrate through "
      + "the Indian Ocean. Busy tanker routes from the Persian Gulf "
      + "and container traffic through the Strait of Malacca overlap "
      + "with cetacean habitat.",
    keySpecies: ["blue_whale", "humpback_whale", "sperm_whale", "brydes_whale"],
    bbox: "25°N–60°S, 20°E–120°E",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Tanker traffic", "Seismic surveys", "Ship noise"],
    notableAreas: ["Sri Lanka", "Madagascar", "Maldives", "Mozambique Channel"],
  },
  /* ── Asia / Oceania ── */
  northwest_pacific: {
    fullName: "NW Pacific (Asia)",
    description:
      "Some of the world's busiest shipping lanes serve Japan, South "
      + "Korea, and China. Right, gray, and humpback whales migrate "
      + "through these congested waters.",
    keySpecies: ["gray_whale", "humpback_whale", "minke_whale", "sperm_whale"],
    bbox: "20°N–60°N, 100°E–180°",
    riskLevel: "High",
    riskColor: "text-orange-400",
    keyThreats: ["Extreme shipping density", "Military sonar", "Coastal development"],
    notableAreas: ["Sea of Japan", "East China Sea", "Ogasawara Islands"],
  },
  southeast_asia: {
    fullName: "Southeast Asia",
    description:
      "Warm tropical waters host Bryde's whales, Irrawaddy dolphins, "
      + "and a diversity of tropical cetaceans. Rapidly growing shipping "
      + "through the Strait of Malacca and South China Sea.",
    keySpecies: ["brydes_whale", "sperm_whale", "bottlenose_dolphin"],
    bbox: "11°S–20°N, 90°E–150°E",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Strait of Malacca traffic", "Coastal development", "Pollution"],
    notableAreas: ["Strait of Malacca", "Sulu Sea", "Coral Triangle"],
  },
  australasia: {
    fullName: "Australasia",
    description:
      "Humpback and southern right whales migrate along both coasts "
      + "of Australia and around New Zealand. Major ports and offshore "
      + "energy development create collision risks.",
    keySpecies: ["humpback_whale", "southern_right_whale", "blue_whale"],
    bbox: "10°S–50°S, 110°E–180°",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Port approaches", "Offshore energy", "Naval exercises"],
    notableAreas: ["Great Barrier Reef", "Great Australian Bight", "Kaikōura Canyon"],
  },
  /* ── Africa / Middle East ── */
  west_africa: {
    fullName: "West Africa",
    description:
      "Humpback whales breed off West Africa (Gabon, Cape Verde). "
      + "Growing oil and gas activity and increasing ship traffic "
      + "along the coast threaten cetacean habitat.",
    keySpecies: ["humpback_whale", "sperm_whale", "bottlenose_dolphin"],
    bbox: "5°S–35°N, 25°W–15°E",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Oil & gas exploration", "Fisheries", "Coastal development"],
    notableAreas: ["Cape Verde", "Gulf of Guinea", "Canary Current"],
  },
  east_africa: {
    fullName: "East Africa / Red Sea",
    description:
      "Humpback whales migrate along the East African coast. The "
      + "Suez Canal and Red Sea shipping corridor are among the "
      + "world's busiest maritime chokepoints.",
    keySpecies: ["humpback_whale", "sperm_whale", "brydes_whale"],
    bbox: "30°S–30°N, 30°E–65°E",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["Suez traffic", "Naval activity", "Coastal development"],
    notableAreas: ["Red Sea", "Mozambique Channel", "Zanzibar"],
  },
  /* ── Polar ── */
  arctic: {
    fullName: "Arctic Ocean",
    description:
      "As sea ice retreats, Arctic shipping routes are opening up "
      + "through the Northern Sea Route and Northwest Passage. Bowhead "
      + "whales, belugas, and narwhals face increasing vessel encounters.",
    keySpecies: ["bowhead", "beluga", "narwhal"],
    bbox: "66°N–90°N, all longitudes",
    riskLevel: "Medium",
    riskColor: "text-yellow-400",
    keyThreats: ["New shipping routes", "Ice-breaking vessels", "Seismic surveys"],
    notableAreas: ["Bering Strait", "Northwest Passage", "Beaufort Sea"],
  },
  other_region: {
    fullName: "Other / Open Ocean",
    description:
      "Open ocean areas outside defined coastal regions. Sperm whales "
      + "and beaked whales use deep pelagic waters year-round.",
    keySpecies: ["sperm_whale", "beaked_whale"],
    bbox: "Global pelagic",
    riskLevel: "Low",
    riskColor: "text-green-400",
    keyThreats: ["Transiting vessels", "Noise", "Climate shifts"],
    notableAreas: ["Mid-Atlantic Ridge", "Sargasso Sea", "Central Pacific"],
  },
};

const REGION_ORDER: string[] = [
  "all",
  /* North America */
  "north_atlantic",
  "south_atlantic",
  "gulf",
  "pacific",
  "alaska",
  "hawaii",
  "caribbean",
  /* Europe */
  "northeast_atlantic",
  "mediterranean",
  "baltic",
  /* Southern Hemisphere */
  "south_pacific",
  "south_atlantic_ocean",
  "southern_ocean",
  "indian_ocean",
  /* Asia / Oceania */
  "northwest_pacific",
  "southeast_asia",
  "australasia",
  /* Africa / Middle East */
  "west_africa",
  "east_africa",
  /* Polar */
  "arctic",
  /* Catch-all */
  "other_region",
];

/** Classify a submission into a global ocean region by lat/lon. */
function classifyRegion(
  lat: number | null,
  lon: number | null,
): string {
  if (lat == null || lon == null) return "all";
  /* ── Arctic / Antarctic ── */
  if (lat > 66) return "arctic";
  if (lat < -60) return "southern_ocean";
  /* ── Alaska ── */
  if (lat > 50 && lon >= -180 && lon < -130) return "alaska";
  /* ── Hawai'i ── */
  if (lat >= 16 && lat <= 25 && lon >= -162 && lon <= -154) return "hawaii";
  /* ── Caribbean ── */
  if (lat >= 8 && lat <= 27 && lon >= -90 && lon <= -58) return "caribbean";
  /* ── Gulf of Mexico ── */
  if (lat >= 18 && lat <= 31 && lon >= -98 && lon < -82) return "gulf";
  /* ── US/Canada Atlantic ── */
  if (lat >= 35 && lat <= 52 && lon >= -82 && lon <= -45) return "north_atlantic";
  if (lat >= 24 && lat < 35 && lon >= -82 && lon <= -59) return "south_atlantic";
  /* ── US/Canada Pacific ── */
  if (lat >= 30 && lat <= 60 && lon >= -140 && lon < -100) return "pacific";
  /* ── NE Atlantic / Europe ── */
  if (lat >= 35 && lat <= 72 && lon >= -30 && lon <= 15) return "northeast_atlantic";
  /* ── Mediterranean ── */
  if (lat >= 30 && lat <= 46 && lon >= -6 && lon <= 42) return "mediterranean";
  /* ── Baltic ── */
  if (lat >= 53 && lat <= 66 && lon >= 10 && lon <= 30) return "baltic";
  /* ── NW Pacific (Asia) ── */
  if (lat >= 20 && lat <= 60 && lon >= 100 && lon <= 180) return "northwest_pacific";
  /* ── SE Asia ── */
  if (lat >= -11 && lat < 20 && lon >= 90 && lon <= 150) return "southeast_asia";
  /* ── Australasia ── */
  if (lat >= -50 && lat <= -10 && lon >= 110 && lon <= 180) return "australasia";
  /* ── South Pacific ── */
  if (lat >= -60 && lat < 0 && lon >= -180 && lon < -70) return "south_pacific";
  if (lat >= -60 && lat < -10 && lon >= 150 && lon <= 180) return "south_pacific";
  /* ── Indian Ocean ── */
  if (lat >= -60 && lat <= 25 && lon >= 20 && lon <= 120) return "indian_ocean";
  /* ── South Atlantic Ocean ── */
  if (lat >= -60 && lat <= 0 && lon >= -70 && lon <= 20) return "south_atlantic_ocean";
  /* ── West Africa ── */
  if (lat >= -5 && lat <= 35 && lon >= -25 && lon <= 15) return "west_africa";
  /* ── East Africa / Red Sea ── */
  if (lat >= -30 && lat <= 30 && lon >= 30 && lon <= 65) return "east_africa";
  return "other_region";
}

/** Species conservation summary data. */
const SPECIES_SUMMARIES: Record<
  string,
  {
    status: string;
    statusColor: string;
    population: string;
    threats: string[];
    description: string;
    avgSize: string;
    range: string;
  }
> = {
  humpback_whale: {
    status: "Least Concern",
    statusColor: "text-green-400",
    population: "~80,000",
    threats: [
      "Ship strikes",
      "Entanglement",
      "Noise pollution",
    ],
    description:
      "Known for complex songs and acrobatic breaching. "
      + "Populations have recovered well since the whaling moratorium.",
    avgSize: "14–17 m",
    range: "All major oceans — seasonal migration",
  },
  right_whale: {
    status: "Critically Endangered",
    statusColor: "text-red-400",
    population: "~350",
    threats: [
      "Ship strikes (leading cause)",
      "Fishing gear entanglement",
      "Climate-driven prey shifts",
    ],
    description:
      "North Atlantic right whales are among the most endangered "
      + "large whales. Calving rates have declined and vessel strikes "
      + "remain the primary mortality driver.",
    avgSize: "13–17 m",
    range: "NW Atlantic — Cape Cod to Florida calving grounds",
  },
  fin_whale: {
    status: "Vulnerable",
    statusColor: "text-yellow-400",
    population: "~100,000",
    threats: [
      "Ship strikes",
      "Ocean noise",
      "Climate change",
    ],
    description:
      "The second-largest animal on Earth. Fast swimmers, "
      + "but their speed corridors overlap with major shipping lanes.",
    avgSize: "18–25 m",
    range: "All major oceans — temperate & polar waters",
  },
  blue_whale: {
    status: "Endangered",
    statusColor: "text-orange-400",
    population: "~10,000–25,000",
    threats: [
      "Ship strikes",
      "Ocean noise",
      "Krill decline",
    ],
    description:
      "The largest animal ever to live. Recovery from whaling has been "
      + "slow and populations remain a fraction of historical numbers.",
    avgSize: "24–30 m",
    range: "All major oceans — follows krill blooms",
  },
  minke_whale: {
    status: "Least Concern",
    statusColor: "text-green-400",
    population: "~500,000",
    threats: [
      "Bycatch",
      "Ship strikes",
      "Whaling (Norway, Japan)",
    ],
    description:
      "The smallest baleen whale in North American waters. "
      + "Relatively abundant but face localised threats near busy ports.",
    avgSize: "7–10 m",
    range: "All oceans — temperate & polar",
  },
  sei_whale: {
    status: "Endangered",
    statusColor: "text-orange-400",
    population: "~50,000",
    threats: [
      "Ship strikes",
      "Entanglement",
      "Pollution",
    ],
    description:
      "One of the fastest baleen whales, capable of 50 km/h bursts. "
      + "Difficult to study due to offshore habits.",
    avgSize: "14–18 m",
    range: "All oceans — prefer deep offshore waters",
  },
  sperm_whale: {
    status: "Vulnerable",
    statusColor: "text-yellow-400",
    population: "~300,000",
    threats: [
      "Ship strikes",
      "Plastic ingestion",
      "Noise pollution",
    ],
    description:
      "The largest toothed whale and deepest-diving mammal. "
      + "Their echolocation clicks are among the loudest biological sounds.",
    avgSize: "11–18 m",
    range: "All deep oceans — females tropical, males polar",
  },
  killer_whale: {
    status: "Data Deficient",
    statusColor: "text-slate-400",
    population: "~50,000",
    threats: [
      "Prey depletion",
      "Vessel disturbance",
      "Toxic contamination",
    ],
    description:
      "Southern Resident orcas (~75 individuals) are critically endangered. "
      + "Vessel noise interferes with echolocation-based foraging.",
    avgSize: "6–8 m",
    range: "All oceans — resident & transient ecotypes",
  },
};

/* ── Page ───────────────────────────────────────────────── */

type CommunityTab = "interactions" | "events";

function CommunityPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, authHeader } = useAuth();
  const initialTab =
    searchParams.get("tab") === "events" ? "events" : "interactions";
  const [activeTab, setActiveTab] = useState<CommunityTab>(initialTab);

  const switchTab = (tab: CommunityTab) => {
    setActiveTab(tab);
    const url = tab === "events" ? "/community?tab=events" : "/community";
    router.replace(url, { scroll: false });
  };

  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [speciesFilter, setSpeciesFilter] =
    useState<SpeciesFilter>("all");
  const [regionFilter, setRegionFilter] =
    useState<RegionFilter>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [fetching, setFetching] = useState(false);
  const [view, setView] = useState<ViewMode>("tiles");
  const [mapData, setMapData] = useState<SubmissionSummary[]>([]);
  const PAGE_SIZE = 20;

  /* ── Community stats (hero, feed, leaderboard) ────────── */
  const [communityStats, setCommunityStats] =
    useState<CommunityStatsResponse | null>(null);
  const [boatLeaderboard, setBoatLeaderboard] =
    useState<BoatLeaderboardItem[]>([]);
  const [leaderboardTab, setLeaderboardTab] =
    useState<"people" | "boats">("people");

  /* ── Globe sightings (fetch 200 geo-located for 3-D globe) ─── */
  const [globeSightings, setGlobeSightings] = useState<
    { id: string; lat: number; lon: number; species: string; submitter_name: string | null; created_at: string; group_size?: number | null; behavior?: string | null; calf_present?: boolean | null; verification_status?: string; risk_category?: string | null; has_photo?: boolean; has_audio?: boolean }[]
  >([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/submissions/public?limit=200&offset=0`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.submissions) {
          const geoSubs = (data.submissions as SubmissionSummary[])
            .filter((s) => s.lat != null && s.lon != null)
            .map((s) => ({
              id: s.id,
              lat: s.lat!,
              lon: s.lon!,
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
            }));
          setGlobeSightings(geoSubs);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/submissions/community-stats`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setCommunityStats(data);
      })
      .catch(() => {});
    fetch(`${API_BASE}/api/v1/vessels/leaderboard?limit=8`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: BoatLeaderboardResponse | null) => {
        if (!cancelled && data) setBoatLeaderboard(data.boats);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const fetchPublic = useCallback(async () => {
    setFetching(true);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(page * PAGE_SIZE),
      });
      if (filter !== "all") params.set("status", filter);
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/public?${params}`,
      );
      if (res.ok) {
        const data = await res.json();
        setSubmissions(data.submissions);
        setTotal(data.total);
      }
    } finally {
      setFetching(false);
    }
  }, [page, filter]);

  const fetchMapData = useCallback(async () => {
    const params = new URLSearchParams({ limit: "200", offset: "0" });
    if (filter !== "all") params.set("status", filter);
    const res = await fetch(
      `${API_BASE}/api/v1/submissions/public?${params}`,
    );
    if (res.ok) {
      const data = await res.json();
      setMapData(data.submissions);
      setTotal(data.total);
    }
  }, [filter]);

  useEffect(() => {
    if (view === "map" || view === "stats") fetchMapData();
    else fetchPublic();
  }, [fetchPublic, fetchMapData, view]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const toMapSubmissions = (list: SubmissionSummary[]): MapSubmission[] =>
    list
      .filter((s) => s.lat != null && s.lon != null)
      .map((s) => ({
        id: s.id,
        lat: s.lat!,
        lon: s.lon!,
        species: s.model_species ?? s.species_guess ?? "unknown",
        interaction_type: s.interaction_type,
        verification_status: s.verification_status,
        submitter_name: s.submitter_name,
        created_at: s.created_at,
      }));

  /* ── Client-side species + region filtering ──────────── */
  const applyClientFilters = (list: SubmissionSummary[]) =>
    list.filter((s) => {
      if (speciesFilter !== "all") {
        const sp = s.model_species ?? s.species_guess ?? "";
        if (sp !== speciesFilter) return false;
      }
      if (regionFilter !== "all") {
        if (classifyRegion(s.lat, s.lon) !== regionFilter) return false;
      }
      if (dateFrom) {
        if (s.created_at < dateFrom) return false;
      }
      if (dateTo) {
        if (s.created_at > dateTo + "T23:59:59") return false;
      }
      return true;
    });

  const filteredSubmissions = applyClientFilters(submissions);
  const filteredMapData = applyClientFilters(mapData);

  /* ── Derived stats ──────────────────────────────────────── */
  const source =
    view === "map" || view === "stats"
      ? filteredMapData
      : filteredSubmissions;
  const verifiedCount = source.filter(
    (s) => s.verification_status === "verified",
  ).length;
  const withPhotoCount = source.filter((s) => s.has_photo).length;
  const speciesSet = new Set(
    source.map((s) => s.model_species ?? s.species_guess).filter(Boolean),
  );
  /* All species from unfiltered data — drives the species filter dropdown */
  const allSpeciesSet = new Set(
    [...submissions, ...mapData]
      .map((s) => s.model_species ?? s.species_guess)
      .filter((v): v is string => !!v),
  );

  /* ── Quick vote handler for inline card buttons ─────── */
  const handleQuickVote = useCallback(
    async (submissionId: string, vote: "agree" | "disagree") => {
      if (!authHeader) return;
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/submissions/${submissionId}/vote`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: authHeader,
            },
            body: JSON.stringify({ vote, notes: null }),
          },
        );
        if (res.ok) {
          const updated = await res.json();
          // Update the submission in place
          setSubmissions((prev) =>
            prev.map((s) =>
              s.id === submissionId
                ? {
                    ...s,
                    verification_status:
                      updated.verification_status ?? s.verification_status,
                    community_agree: updated.community_agree ?? s.community_agree,
                    community_disagree:
                      updated.community_disagree ?? s.community_disagree,
                    verification_score:
                      updated.verification_score ?? s.verification_score,
                  }
                : s,
            ),
          );
        }
      } catch {
        /* silently fail — user can always click into detail */
      }
    },
    [authHeader],
  );

  return (
    <div className="min-h-screen bg-abyss-950 pt-20 pb-12">
      <div className="mx-auto max-w-7xl px-4">
        {/* ── Welcoming hero ──────────────────────────────── */}
        <div className="relative mb-8 overflow-hidden rounded-2xl border border-ocean-700/30 bg-gradient-to-br from-ocean-900/60 via-abyss-900/80 to-abyss-950 p-6 sm:p-8">
          {/* Decorative glow */}
          <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-ocean-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -left-10 bottom-0 h-40 w-40 rounded-full bg-bioluminescent-500/8 blur-2xl" />

          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            {/* Left: welcome text */}
            <div className="max-w-xl">
              <h1 className="flex items-center gap-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
                <IconWaves className="h-8 w-8 text-ocean-400" />
                Community Hub
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-slate-300 sm:text-base">
                Every sighting, every report, every event helps build a
                safer ocean for whales. Join{" "}
                <span className="font-semibold text-ocean-300">
                  {communityStats?.stats.total_contributors ?? "—"}
                </span>{" "}
                observers documenting marine life across US waters.
              </p>
              {/* Quick action buttons */}
              <div className="mt-4 flex flex-wrap gap-3">
                <Link
                  href="/report"
                  className="inline-flex items-center gap-2 rounded-lg bg-ocean-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-ocean-500/25 transition hover:bg-ocean-400"
                >
                  <IconCamera className="h-4 w-4" />
                  Report a Sighting
                </Link>
                <Link
                  href="/community?tab=events"
                  onClick={(e) => {
                    e.preventDefault();
                    switchTab("events");
                  }}
                  className="inline-flex items-center gap-2 rounded-lg border border-ocean-600/40 bg-ocean-900/40 px-4 py-2 text-sm font-medium text-ocean-300 transition hover:bg-ocean-800/50"
                >
                  <IconCalendar className="h-4 w-4" />
                  Browse Events
                </Link>
              </div>
            </div>

            {/* Right: impact counters */}
            {communityStats && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2 lg:gap-4">
                <ImpactCounter
                  icon={<IconWhale className="h-5 w-5 text-ocean-400" />}
                  value={communityStats.stats.total_sightings}
                  label="Sightings"
                />
                <ImpactCounter
                  icon={<IconUsers className="h-5 w-5 text-bioluminescent-400" />}
                  value={communityStats.stats.total_contributors}
                  label="Observers"
                />
                <ImpactCounter
                  icon={<IconDolphin className="h-5 w-5 text-emerald-400" />}
                  value={communityStats.stats.species_documented}
                  label="Species"
                />
                <ImpactCounter
                  icon={<IconCalendar className="h-5 w-5 text-purple-400" />}
                  value={communityStats.stats.total_events}
                  label="Events"
                />
              </div>
            )}
          </div>

          {/* ── This-week pulse ────────────────────────────── */}
          {communityStats && communityStats.stats.sightings_this_week > 0 && (
            <div className="relative mt-5 flex items-center gap-2 rounded-lg bg-ocean-500/10 px-3 py-2 text-xs text-ocean-300">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ocean-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-ocean-400" />
              </span>
              <span className="font-medium">{communityStats.stats.sightings_this_week}</span>{" "}
              new sighting{communityStats.stats.sightings_this_week !== 1 ? "s" : ""} this week
            </div>
          )}
        </div>

        {/* ── 3-D Sighting Globe ──────────────────────────── */}
        {globeSightings.length > 0 && (
          <div className="relative mb-8 overflow-hidden rounded-2xl border border-ocean-700/30 bg-gradient-to-b from-abyss-950 via-abyss-900 to-abyss-950">
            <SightingGlobe
              sightings={globeSightings}
              className="h-[420px] sm:h-[480px]"
            />
          </div>
        )}

        {/* ── Needs-review CTA banner ─────────────────────── */}
        {communityStats && communityStats.stats.needs_review_count > 0 && (
          <Link
            href="/verify"
            className="group relative mb-6 block w-full overflow-hidden rounded-2xl border border-amber-500/25 bg-gradient-to-br from-amber-500/10 via-abyss-900/80 to-ocean-900/30 transition-all hover:border-amber-400/50 hover:shadow-xl hover:shadow-amber-900/25"
          >
            {/* Ambient glow */}
            <div className="pointer-events-none absolute -right-20 -top-20 h-52 w-52 rounded-full bg-amber-500/8 blur-3xl transition-opacity group-hover:opacity-100 opacity-60" />
            <div className="pointer-events-none absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-ocean-500/8 blur-2xl" />

            <div className="relative flex items-center gap-5 px-5 py-5 sm:px-6">
              {/* ── Mini card-stack illustration ─────── */}
              <div className="relative hidden h-[88px] w-[68px] shrink-0 sm:block">
                {/* Back card (left-tilted) */}
                <div className="absolute left-0 top-1 h-[72px] w-[56px] rounded-lg border border-red-500/20 bg-gradient-to-b from-red-500/10 to-red-900/15 shadow-md"
                     style={{ transform: "rotate(-12deg)", transformOrigin: "bottom center" }}>
                  <div className="flex h-full flex-col items-center justify-center opacity-50">
                    <IconThumbDown className="h-3.5 w-3.5 text-red-400" />
                  </div>
                </div>
                {/* Back card (right-tilted) */}
                <div className="absolute right-0 top-1 h-[72px] w-[56px] rounded-lg border border-emerald-500/20 bg-gradient-to-b from-emerald-500/10 to-emerald-900/15 shadow-md"
                     style={{ transform: "rotate(12deg)", transformOrigin: "bottom center" }}>
                  <div className="flex h-full flex-col items-center justify-center opacity-50">
                    <IconThumbUp className="h-3.5 w-3.5 text-emerald-400" />
                  </div>
                </div>
                {/* Front card (animated wiggle) */}
                <div className="absolute inset-x-0 mx-auto top-0 h-[72px] w-[56px] rounded-lg border border-amber-400/30 bg-gradient-to-b from-abyss-800 to-abyss-900 shadow-lg ring-1 ring-white/5 group-hover:animate-cta-wiggle">
                  <div className="flex h-full flex-col items-center justify-center gap-1">
                    <IconWhale className="h-4 w-4 text-amber-300" />
                    <div className="h-1.5 w-8 rounded-full bg-amber-500/20" />
                    <div className="h-1 w-6 rounded-full bg-slate-600/40" />
                  </div>
                </div>
                {/* Swipe arrows overlay */}
                <div className="pointer-events-none absolute -bottom-1 left-1/2 -translate-x-1/2">
                  <div className="flex items-center gap-3 text-[9px] font-bold tracking-wide">
                    <span className="text-red-400/60">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="inline h-2.5 w-2.5"><path d="M10.354 3.354a.5.5 0 0 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L6.707 7l3.647-3.646Z"/></svg>
                    </span>
                    <span className="text-purple-400/60">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="inline h-2.5 w-2.5"><path d="M3.354 10.354a.5.5 0 0 1-.708-.708l4-4a.5.5 0 0 1 .708 0l4 4a.5.5 0 0 1-.708.708L7 6.707l-3.646 3.647Z"/></svg>
                    </span>
                    <span className="text-emerald-400/60">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="inline h-2.5 w-2.5"><path d="M5.646 3.354a.5.5 0 0 1 .708-.708l4 4a.5.5 0 0 1 0 .708l-4 4a.5.5 0 0 1-.708-.708L9.293 7 5.646 3.354Z"/></svg>
                    </span>
                  </div>
                </div>
              </div>

              {/* ── Text content ───────────────────── */}
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-amber-400">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-amber-400" />
                    </span>
                    {communityStats.stats.needs_review_count} pending
                  </span>
                </div>
                <p className="text-[15px] font-semibold leading-snug text-slate-100">
                  Swipe to verify sightings
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-slate-400">
                  Quick-review reports with a swipe —{" "}
                  <span className="font-medium text-red-400/80">left</span>{" "}
                  to disagree,{" "}
                  <span className="font-medium text-emerald-400/80">right</span>{" "}
                  to confirm,{" "}
                  <span className="font-medium text-purple-400/80">up</span>{" "}
                  to refine. Earn{" "}
                  <span className="font-semibold text-amber-300">+2 rep</span> per review.
                </p>
              </div>

              {/* ── CTA button ─────────────────────── */}
              <div className="hidden shrink-0 sm:block">
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500/15 px-4 py-2 text-sm font-semibold text-amber-300 ring-1 ring-amber-500/25 transition-all group-hover:bg-amber-500/25 group-hover:ring-amber-400/40 group-hover:shadow-lg group-hover:shadow-amber-500/10">
                  Start reviewing
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"><path d="M5.646 3.354a.5.5 0 0 1 .708-.708l4 4a.5.5 0 0 1 0 .708l-4 4a.5.5 0 0 1-.708-.708L9.293 7 5.646 3.354Z"/></svg>
                </span>
              </div>
            </div>

          </Link>
        )}

        {/* ── Whale of the Week ───────────────────────────── */}
        {communityStats?.whale_of_the_week && (
          <WhaleOfTheWeek item={communityStats.whale_of_the_week} />
        )}

        {/* ── Activity chart + Feed + Leaderboard row ─────── */}
        {communityStats && (
          <div className="mb-8 grid gap-5 lg:grid-cols-3">
            {/* Left column: bar chart + activity feed (2 cols) */}
            <div className="lg:col-span-2 space-y-5">
              {/* Activity over time bar chart */}
              {communityStats.activity_histogram.length > 0 && (
                <ActivityBarChart data={communityStats.activity_histogram} />
              )}

              {/* Recent activity feed */}
              <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-4">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
                  <IconClock className="h-4 w-4 text-ocean-400" />
                  Recent Activity
                </h2>
                {communityStats.recent_activity.length === 0 ? (
                  <p className="py-6 text-center text-xs text-slate-500">
                    No sightings yet — be the first!
                  </p>
                ) : (
                  <div className="space-y-2">
                    {communityStats.recent_activity.map((a) => (
                      <ActivityItem key={a.id} item={a} />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Top contributors / boats leaderboard (1 col) */}
            <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-4">
              {/* Leaderboard tabs */}
              <div className="mb-3 flex items-center gap-1 rounded-lg border border-ocean-800/40 bg-abyss-950/50 p-0.5">
                <button
                  onClick={() => setLeaderboardTab("people")}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
                    leaderboardTab === "people"
                      ? "bg-ocean-500/20 text-ocean-300 shadow-sm"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  <IconStar className="h-3.5 w-3.5 text-yellow-400" />
                  Top Contributors
                </button>
                <button
                  onClick={() => setLeaderboardTab("boats")}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
                    leaderboardTab === "boats"
                      ? "bg-ocean-500/20 text-ocean-300 shadow-sm"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  <IconShip className="h-3.5 w-3.5 text-ocean-400" />
                  Top Boats
                </button>
              </div>

              {/* People tab */}
              {leaderboardTab === "people" && (
                <>
                  {communityStats.top_contributors.length === 0 ? (
                    <p className="py-6 text-center text-xs text-slate-500">
                      No contributors yet
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {communityStats.top_contributors.slice(0, 8).map((c, i) => (
                        <LeaderboardRow key={c.user_id} rank={i + 1} contributor={c} />
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* Boats tab */}
              {leaderboardTab === "boats" && (
                <>
                  {boatLeaderboard.length === 0 ? (
                    <p className="py-6 text-center text-xs text-slate-500">
                      No boats registered yet
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {boatLeaderboard.map((b, i) => (
                        <BoatLeaderboardRow key={b.vessel_id} rank={i + 1} boat={b} />
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Tab toggle ──────────────────────────────────── */}
        <div className="mb-6 flex items-center gap-1 rounded-xl border border-ocean-800/40 bg-abyss-900/60 p-1 w-fit">
          <button
            onClick={() => switchTab("interactions")}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
              activeTab === "interactions"
                ? "bg-ocean-500/20 text-ocean-300 shadow-sm"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <IconWhale className="h-4 w-4" />
            Interactions
          </button>
          <button
            onClick={() => switchTab("events")}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
              activeTab === "events"
                ? "bg-ocean-500/20 text-ocean-300 shadow-sm"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <IconCalendar className="h-4 w-4" />
            Events
          </button>
        </div>

        {/* ── Events tab ──────────────────────────────────── */}
        {activeTab === "events" && <EventsPanel />}

        {/* ── Interactions tab ────────────────────────────── */}
        {activeTab === "interactions" && (
          <>
          {/* Stats pills */}
          <div className="mb-5 flex flex-wrap gap-3">
            <StatPill label="Total reports" value={total} />
            <StatPill
              label="Verified"
              value={verifiedCount}
              accent="text-green-400"
            />
            <button
              onClick={() => { setFilter("unverified"); setPage(0); }}
              className="group"
            >
              <StatPill
                label="Needs review"
                value={total - verifiedCount}
                accent="text-amber-400"
              />
            </button>
            <StatPill
              label="Species"
              value={speciesSet.size}
              accent="text-ocean-400"
            />
            <StatPill
              label="With photos"
              value={withPhotoCount}
              accent="text-purple-400"
            />
          </div>

        {/* ── Toolbar ─────────────────────────────────────── */}
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Dropdowns */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Status dropdown */}
            <FilterDropdown
              label="Status"
              value={filter}
              onChange={(v) => { setFilter(v as StatusFilter); setPage(0); }}
              options={[
                { value: "all", label: "All Statuses" },
                { value: "unverified", label: "Unverified", dot: "bg-slate-400" },
                { value: "verified", label: "Mod Verified", dot: "bg-emerald-400" },
                { value: "community_verified", label: "Community Verified", dot: "bg-green-400" },
                { value: "under_review", label: "Under Review", dot: "bg-blue-400" },
                { value: "disputed", label: "Disputed", dot: "bg-yellow-400" },
                { value: "rejected", label: "Rejected", dot: "bg-red-400" },
              ]}
            />

            {/* Species dropdown — grouped by taxonomy */}
            <FilterDropdown
              label="Species"
              value={speciesFilter}
              onChange={(v) => { setSpeciesFilter(v); setPage(0); }}
              options={[
                { value: "all", label: "All Species" },
                ...SPECIES_FILTER_GROUPS.flatMap((g) =>
                  g.items.map((sp) => ({
                    value: sp.value,
                    label: sp.label,
                    icon: SPECIES_ICON_FILES[sp.value],
                    group: g.label,
                  })),
                ),
                /* Any extra species from data not in our groups */
                ...[...allSpeciesSet]
                  .filter((sp): sp is string =>
                    !!sp && !SPECIES_ORDER.includes(sp),
                  )
                  .sort()
                  .map((sp) => ({
                    value: sp,
                    label: sp.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
                    icon: SPECIES_ICON_FILES[sp],
                    group: "Other",
                  })),
              ]}
            />

            {/* Region dropdown — grouped by geography */}
            <FilterDropdown
              label="Region"
              value={regionFilter}
              onChange={(v) => { setRegionFilter(v as RegionFilter); setPage(0); }}
              options={[
                { value: "all", label: "All Regions" },
                ...REGION_FILTER_GROUPS.flatMap((g) =>
                  g.regions.map((r) => ({
                    value: r,
                    label: REGION_LABELS[r] ?? r,
                    group: g.label,
                  })),
                ),
              ]}
            />

            {/* Date range */}
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => { setDateFrom(e.target.value); setPage(0); }}
                className="rounded-lg border border-ocean-800/60 bg-abyss-900/60 px-2.5 py-[7px] text-xs text-white focus:border-ocean-500 focus:outline-none [color-scheme:dark]"
                title="From date"
              />
              <span className="text-[10px] text-slate-600">–</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => { setDateTo(e.target.value); setPage(0); }}
                className="rounded-lg border border-ocean-800/60 bg-abyss-900/60 px-2.5 py-[7px] text-xs text-white focus:border-ocean-500 focus:outline-none [color-scheme:dark]"
                title="To date"
              />
              {(dateFrom || dateTo) && (
                <button
                  onClick={() => { setDateFrom(""); setDateTo(""); setPage(0); }}
                  className="rounded-md px-1.5 py-1 text-xs text-slate-500 transition hover:text-red-400"
                  title="Clear dates"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* View toggle: Tiles / List / Map / Stats */}
          <div className="flex items-center gap-1 rounded-lg border border-ocean-800/60 bg-abyss-900/80 p-0.5">
            {(
              [
                { key: "tiles" as ViewMode, icon: "▦", label: "Tiles" },
                { key: "list" as ViewMode, icon: "☰", label: "List" },
                { key: "map" as ViewMode, icon: <IconMap className="h-3.5 w-3.5 inline-block" />, label: "Map" },
                { key: "stats" as ViewMode, icon: <IconChart className="h-3.5 w-3.5 inline-block" />, label: "Stats" },
              ]
            ).map(({ key, icon, label }) => (
              <button
                key={key}
                onClick={() => setView(key)}
                className={`rounded-md px-3.5 py-1.5 text-xs font-medium transition-all ${
                  view === key
                    ? "bg-ocean-600/90 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {icon} {label}
              </button>
            ))}
          </div>

          {/* Quick Review (swipe mode) link */}
          {user && (
            <Link
              href="/verify"
              className="flex items-center gap-1.5 rounded-lg border border-teal-500/30 bg-teal-600/20
                         px-3.5 py-1.5 text-xs font-semibold text-teal-400
                         hover:bg-teal-600/30 hover:border-teal-500/50 transition-all"
            >
              <IconShield className="h-3.5 w-3.5" />
              Quick Review
            </Link>
          )}
        </div>

        {/* ── Species Summary Panel ───────────────────────── */}
        {speciesFilter !== "all" &&
          SPECIES_SUMMARIES[speciesFilter] && (
            <SpeciesSummaryPanel
              species={speciesFilter}
              sightingCount={filteredSubmissions.length}
            />
          )}

        {/* ── Region Summary Panel ────────────────────────── */}
        {regionFilter !== "all" && (
          <RegionSummaryPanel
            region={regionFilter}
            sightingCount={filteredSubmissions.length}
            speciesInRegion={[
              ...new Set(
                filteredSubmissions
                  .map((s) => s.model_species ?? s.species_guess)
                  .filter(Boolean) as string[],
              ),
            ]}
          />
        )}

        {/* ── Map view ────────────────────────────────────── */}
        {view === "map" && (
          <div className="mb-8 h-[400px] overflow-hidden rounded-2xl border border-ocean-800/60 shadow-lg shadow-black/20 sm:h-[600px]">
            <SubmissionMap
              data={toMapSubmissions(filteredMapData)}
              onClickSubmission={(id) =>
                window.open(`/submissions/${id}`, "_blank")
              }
            />
          </div>
        )}

        {/* ── Stats view ─────────────────────────────────── */}
        {view === "stats" && (
          <StatsView data={filteredMapData} />
        )}

        {/* ── Card grid / compact list ────────────────────── */}
        {(view === "tiles" || view === "list") && (
          <>
            {fetching && submissions.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 py-24">
                <SonarPing size={56} ringCount={3} active />
                <p className="text-sm text-slate-500">
                  Loading interactions…
                </p>
              </div>
            ) : filteredSubmissions.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-ocean-800/60 py-24 text-center">
                <div className="flex justify-center"><IconWhale className="h-10 w-10 text-slate-400" /></div>
                <p className="mt-3 text-slate-400">
                  No interactions
                  {filter !== "all" ? ` with status "${filter}"` : ""}
                  {speciesFilter !== "all"
                    ? ` for ${SPECIES_LABELS[speciesFilter] ?? speciesFilter}`
                    : ""}
                  {regionFilter !== "all"
                    ? ` in ${REGION_LABELS[regionFilter]}`
                    : ""}
                  {" "}yet.
                </p>
                <Link
                  href="/report"
                  className="mt-4 inline-block rounded-lg bg-ocean-700 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-600"
                >
                  Submit the first interaction
                </Link>
              </div>
            ) : (
              <>
                {/* Tile view — card grid */}
                {view === "tiles" && (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredSubmissions.map((s) => (
                      <SightingCard
                        key={s.id}
                        s={s}
                        onQuickVote={handleQuickVote}
                        currentUserId={user?.id}
                      />
                    ))}
                  </div>
                )}

                {/* Compact list view */}
                {view === "list" && (
                  <div className="overflow-x-auto rounded-2xl border border-ocean-800/60">
                    {/* Header */}
                    <div className="min-w-[700px] grid grid-cols-[1fr_100px_70px_90px_40px_40px_55px_80px_80px_70px] gap-2 border-b border-ocean-800/40 bg-abyss-900/80 px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                      <span>Species</span>
                      <span>Observer</span>
                      <span>Classif.</span>
                      <span>Status</span>
                      <span><IconThumbUp className="h-3 w-3" /></span>
                      <span><IconThumbDown className="h-3 w-3" /></span>
                      <span>C.Trust</span>
                      <span>Risk</span>
                      <span>Location</span>
                      <span className="text-right">Date</span>
                    </div>
                    {/* Rows */}
                    {filteredSubmissions.map((s) => (
                      <SightingRow key={s.id} s={s} />
                    ))}
                  </div>
                )}

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
                    <button
                      disabled={page === 0}
                      onClick={() => setPage((p) => p - 1)}
                      className="rounded-lg border border-ocean-800/60 px-3 py-1.5 text-sm text-slate-400 transition-colors hover:border-ocean-700 hover:text-white disabled:pointer-events-none disabled:opacity-30"
                    >
                      ←
                    </button>
                    {Array.from(
                      { length: Math.min(totalPages, 5) },
                      (_, i) => {
                        let p: number;
                        if (totalPages <= 5) {
                          p = i;
                        } else if (page < 3) {
                          p = i;
                        } else if (page > totalPages - 4) {
                          p = totalPages - 5 + i;
                        } else {
                          p = page - 2 + i;
                        }
                        return (
                          <button
                            key={p}
                            onClick={() => setPage(p)}
                            className={`h-8 w-8 rounded-lg text-sm font-medium transition-all ${
                              page === p
                                ? "bg-ocean-600 text-white"
                                : "text-slate-500 hover:bg-abyss-800 hover:text-slate-300"
                            }`}
                          >
                            {p + 1}
                          </button>
                        );
                      },
                    )}
                    <button
                      disabled={page >= totalPages - 1}
                      onClick={() => setPage((p) => p + 1)}
                      className="rounded-lg border border-ocean-800/60 px-3 py-1.5 text-sm text-slate-400 transition-colors hover:border-ocean-700 hover:text-white disabled:pointer-events-none disabled:opacity-30"
                    >
                      →
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}
        </>
        )}
      </div>
    </div>
  );
}

/* ── Species Link helper ───────────────────────────────── */

/** Render a species label as a clickable link to the species page (with search pre-fill).
 *  Stops propagation so it doesn't trigger the parent Link to /submissions/{id}. */
function SpeciesLink({
  species,
  className,
  children,
}: {
  species: string;
  className?: string;
  children?: React.ReactNode;
}) {
  const label = species.replace(/_/g, " ");
  return (
    <a
      href={`/species?q=${encodeURIComponent(label)}`}
      className={`hover:underline ${className ?? ""}`}
      onClick={(e) => e.stopPropagation()}
    >
      {children ?? label}
    </a>
  );
}

/* ── Bio Info Chips ───────────────────────────────────────── */

const BEHAVIOR_LABELS: Record<string, string> = {
  traveling: "Traveling",
  feeding: "Feeding",
  resting: "Resting",
  socializing: "Socializing",
  breaching: "Breaching",
  diving: "Diving",
  milling: "Milling",
  nursing: "Nursing",
  unknown: "Unknown",
};

const LIFE_STAGE_LABELS: Record<string, string> = {
  adult: "Adult",
  juvenile: "Juvenile",
  calf: "Calf",
  mother_calf_pair: "Mother-Calf Pair",
  unknown: "Unknown",
};

const PLATFORM_LABELS: Record<string, string> = {
  shore: "Shore",
  vessel_small: "Small Vessel",
  vessel_large: "Large Vessel",
  aircraft: "Aircraft",
  drone: "Drone",
  kayak_paddle: "Kayak/Paddle",
  research_vessel: "Research Vessel",
  whale_watch: "Whale Watch",
  unknown: "Unknown",
};

/* ── Interaction Card ──────────────────────────────────────── */

function SightingCard({
  s,
  onQuickVote,
  currentUserId,
}: {
  s: SubmissionSummary;
  onQuickVote?: (id: string, vote: "agree" | "disagree") => Promise<void>;
  currentUserId?: number;
}) {
  const species = s.model_species ?? s.species_guess ?? "unknown";
  const speciesLabel = species.replace(/_/g, " ");
  const emoji = SPECIES_EMOJI[species] ?? <IconWhale className="h-5 w-5" />;
  const tier = TIER_STYLE[s.submitter_tier ?? ""] ?? TIER_STYLE.newcomer;
  const status =
    STATUS_STYLE[s.verification_status] ?? STATUS_STYLE.unverified;
  const riskAccent =
    RISK_ACCENT[s.risk_category ?? ""] ?? "from-transparent";
  const riskText = RISK_TEXT[s.risk_category ?? ""] ?? "text-slate-500";
  const conf =
    s.model_confidence != null
      ? `${(s.model_confidence * 100).toFixed(0)}%`
      : null;

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 3_600_000)
      return `${Math.max(1, Math.floor(diff / 60_000))}m`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
    if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)}d`;
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  };

  return (
    <Link
      href={`/submissions/${s.id}`}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-ocean-800/50 bg-gradient-to-b ${riskAccent} to-abyss-900/90 transition-all hover:border-ocean-600/70 hover:shadow-lg hover:shadow-ocean-900/30`}
    >
      {/* Photo thumbnail or species icon */}
      {s.has_photo ? (
        <div className="relative h-40 overflow-hidden bg-abyss-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${API_BASE}/api/v1/media/${s.id}/photo`}
            alt={speciesLabel}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/80 via-transparent to-transparent" />
          {/* Floating badges on photo */}
          <div className="absolute bottom-2 left-3 right-3 flex items-end justify-between">
            <SpeciesLink
              species={species}
              className="text-lg font-semibold leading-tight text-white drop-shadow hover:text-ocean-300"
            />
            {s.has_audio && (
              <span className="rounded-full bg-black/50 px-2 py-0.5 text-xs text-slate-300 backdrop-blur-sm">
                <IconMicrophone className="h-3.5 w-3.5 inline-block" />
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="flex h-28 items-center justify-center bg-gradient-to-br from-abyss-800/80 to-abyss-900/80">
          <WhaleIcon species={species} size={84} />
        </div>
      )}

      {/* Card body */}
      <div className="flex flex-1 flex-col gap-3 p-4">
        {/* Species + audio badge (only if no photo — photo has overlay) */}
        {!s.has_photo && (
          <div className="flex items-center justify-between">
            <SpeciesLink
              species={species}
              className="text-sm font-semibold text-white hover:text-ocean-300"
            />
            {s.has_audio && (
              <span className="text-xs text-slate-500"><IconMicrophone className="h-3.5 w-3.5 inline-block" /></span>
            )}
          </div>
        )}

        {/* Metadata chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${status.bg} ${status.text}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${status.dot}`}
            />
            {s.moderator_status ? <><IconShield className="h-3 w-3 inline-block" />{" "}</> : ""}
            {STATUS_LABELS[s.verification_status] ?? s.verification_status}
          </span>
          {(s.community_agree > 0 || s.community_disagree > 0) && (
            <span className="inline-flex items-center gap-1 rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] text-slate-400">
              <span className="text-green-400">
                <IconThumbUp className="h-3 w-3 inline-block mr-0.5" />{s.community_agree}
              </span>
              <span className="text-red-400">
                <IconThumbDown className="h-3 w-3 inline-block mr-0.5" />{s.community_disagree}
              </span>
            </span>
          )}
          {s.risk_category && (
            <span
              className={`rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] font-medium ${riskText}`}
            >
              {s.risk_category} risk
            </span>
          )}
          {s.interaction_type && (
            <span className="rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] text-slate-500">
              {s.interaction_type.replace(/_/g, " ")}
            </span>
          )}
        </div>

        {/* Scientific name + species guess vs model mismatch */}
        {(s.scientific_name || (s.species_guess && s.model_species && s.species_guess !== s.model_species)) && (
          <div className="flex flex-col gap-0.5 text-[11px]">
            {s.scientific_name && (
              <span className="italic text-slate-500">
                {s.scientific_name}
              </span>
            )}
            {s.species_guess && s.model_species && s.species_guess !== s.model_species && (
              <span className="text-slate-500">
                Observer:{" "}
                <SpeciesLink species={s.species_guess} className="text-ocean-400 hover:text-ocean-300" />{" "}
                · Model:{" "}
                <SpeciesLink species={s.model_species} className="text-ocean-400 hover:text-ocean-300" />
              </span>
            )}
          </div>
        )}

        {/* Bio observation chips */}
        {(s.group_size != null || s.behavior || s.life_stage || s.calf_present || s.observation_platform || s.sea_state_beaufort != null) && (
          <div className="flex flex-wrap items-center gap-1.5">
            {s.group_size != null && (
              <span className="inline-flex items-center gap-1 rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-ocean-300">
                <IconUsers className="h-3 w-3" />
                {s.group_size} {s.group_size === 1 ? "animal" : "animals"}
              </span>
            )}
            {s.behavior && (
              <span className="rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-ocean-300">
                {BEHAVIOR_LABELS[s.behavior] ?? s.behavior.replace(/_/g, " ")}
              </span>
            )}
            {s.life_stage && (
              <span className="rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-ocean-300">
                {LIFE_STAGE_LABELS[s.life_stage] ?? s.life_stage.replace(/_/g, " ")}
              </span>
            )}
            {s.calf_present && (
              <span className="inline-flex items-center gap-1 rounded-full bg-teal-900/40 px-2 py-0.5 text-[11px] text-teal-300">
                <IconCheck className="h-3 w-3" /> Calf present
              </span>
            )}
            {s.observation_platform && s.observation_platform !== "unknown" && (
              <span className="rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-slate-400">
                {PLATFORM_LABELS[s.observation_platform] ?? s.observation_platform.replace(/_/g, " ")}
              </span>
            )}
            {s.sea_state_beaufort != null && (
              <span className="rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-slate-400">
                <IconWaves className="mr-0.5 inline-block h-3 w-3" />
                Sea {s.sea_state_beaufort}
              </span>
            )}
          </div>
        )}

        {/* Confidence bar */}
        {conf && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-[11px] text-slate-500">Classification</span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-abyss-800">
              <div
                className="h-full rounded-full bg-ocean-500/70"
                style={{ width: conf }}
              />
            </div>
            <span className="text-[11px] tabular-nums text-slate-500">
              {conf}
            </span>
          </div>
        )}

        {/* Risk assessment bar */}
        {s.risk_score != null && s.risk_category && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-[11px] text-slate-500">Risk</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-800">
              <div
                className={`h-full rounded-full ${RISK_BAR_COLOR[s.risk_category] ?? "bg-slate-500/50"}`}
                style={{ width: `${(s.risk_score * 100).toFixed(0)}%` }}
              />
            </div>
            <span className={`text-[11px] font-medium tabular-nums ${riskText}`}>
              {(s.risk_score * 100).toFixed(0)}%
            </span>
          </div>
        )}

        {/* Verification score bar */}
        {s.verification_score != null && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-[11px] text-slate-500">Community Trust</span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-abyss-800">
              <div
                className={`h-full rounded-full ${
                  s.verification_score >= 70
                    ? "bg-emerald-500/70"
                    : s.verification_score >= 40
                      ? "bg-yellow-500/70"
                      : "bg-red-500/70"
                }`}
                style={{ width: `${s.verification_score}%` }}
              />
            </div>
            <span className="text-[11px] tabular-nums text-slate-500">
              {s.verification_score.toFixed(0)}%
            </span>
          </div>
        )}

        {/* Footer: submitter + time + location */}
        <div className="mt-auto flex items-center justify-between border-t border-ocean-900/40 pt-2.5 text-[11px] text-slate-500">
          <span
            className="flex cursor-pointer items-center gap-1.5 truncate hover:text-white"
            onClick={(e) => {
              if (s.submitter_id) {
                e.preventDefault();
                e.stopPropagation();
                window.location.href = `/users/${s.submitter_id}`;
              }
            }}
          >
            <UserAvatar
              avatarUrl={s.submitter_avatar_url}
              displayName={s.submitter_name}
              size={18}
            />
            <span className={tier.color}>{tier.icon}</span>
            {s.submitter_is_moderator && (
              <span className="text-amber-400" title="Moderator"><IconShield className="h-3.5 w-3.5" /></span>
            )}
            <span className="truncate">
              {s.submitter_name ?? "Anonymous"}
            </span>
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {s.lat != null && (
              <span className="tabular-nums">
                {s.lat.toFixed(1)}°,{s.lon!.toFixed(1)}°
              </span>
            )}
            <span className="tabular-nums" title={s.sighting_datetime ? "Sighting time" : "Submitted"}>
              {s.sighting_datetime && <IconClock className="mr-0.5 inline-block h-3 w-3" />}
              {timeAgo(s.sighting_datetime ?? s.created_at)}
            </span>
          </div>
        </div>

        {/* Quick vote bar — shown for public unverified cards when user is not submitter */}
        {onQuickVote &&
          s.is_public &&
          s.verification_status === "unverified" &&
          currentUserId &&
          currentUserId !== s.submitter_id && (
          <div className="flex items-center gap-2 border-t border-ocean-900/40 pt-2.5">
            <span className="text-[11px] text-slate-500">Verify:</span>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onQuickVote(s.id, "agree");
              }}
              className="inline-flex items-center gap-1 rounded-md bg-green-800/40 px-2.5 py-1 text-[11px] font-medium text-green-300 transition-colors hover:bg-green-700/60"
            >
              <IconThumbUp className="h-3 w-3" /> Agree
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onQuickVote(s.id, "disagree");
              }}
              className="inline-flex items-center gap-1 rounded-md bg-red-800/40 px-2.5 py-1 text-[11px] font-medium text-red-300 transition-colors hover:bg-red-700/60"
            >
              <IconThumbDown className="h-3 w-3" /> Disagree
            </button>
            <Link
              href={`/verify?id=${s.id}`}
              onClick={(e) => { e.stopPropagation(); }}
              className="inline-flex items-center gap-1 rounded-md bg-purple-800/40 px-2.5 py-1 text-[11px] font-medium text-purple-300 transition-colors hover:bg-purple-700/60"
            >
              <IconInfo className="h-3 w-3" /> Refine
            </Link>
            <span className="ml-auto text-[10px] text-green-500/60">+2 rep</span>
          </div>
        )}
      </div>
    </Link>
  );
}

/* ── Stat Pill ────────────────────────────────────────────── */

function StatPill({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-ocean-800/40 bg-abyss-900/60 px-3 py-1">
      <span
        className={`text-sm font-semibold tabular-nums ${accent ?? "text-white"}`}
      >
        {value.toLocaleString()}
      </span>
      <span className="text-[11px] text-slate-500">{label}</span>
    </div>
  );
}

/* ── Compact List Row ─────────────────────────────────────── */

function SightingRow({ s }: { s: SubmissionSummary }) {
  const species = s.model_species ?? s.species_guess ?? "unknown";
  const speciesLabel = species.replace(/_/g, " ");
  const status =
    STATUS_STYLE[s.verification_status] ?? STATUS_STYLE.unverified;
  const riskText = RISK_TEXT[s.risk_category ?? ""] ?? "text-slate-500";
  const conf =
    s.model_confidence != null
      ? `${(s.model_confidence * 100).toFixed(0)}%`
      : null;

  return (
    <Link
      href={`/submissions/${s.id}`}
      className="min-w-[700px] grid grid-cols-[1fr_100px_70px_90px_40px_40px_55px_80px_80px_70px] items-center gap-2 border-b border-ocean-900/30 px-4 py-2.5 text-sm transition-colors hover:bg-abyss-800/50"
    >
      {/* Species */}
      <div className="flex items-center gap-2 truncate">
        <WhaleIcon species={species} size={30} />
        <div className="min-w-0 flex flex-col truncate">
          <SpeciesLink
            species={species}
            className="truncate font-medium text-white hover:text-ocean-300"
          />
          {s.scientific_name && (
            <span className="truncate text-[10px] italic text-slate-500">
              {s.scientific_name}
            </span>
          )}
        </div>
        {s.group_size != null && (
          <span className="shrink-0 text-[10px] text-ocean-400" title="Group size">
            <IconUsers className="mr-0.5 inline-block h-3 w-3" />{s.group_size}
          </span>
        )}
        {s.has_photo && (
          <span className="shrink-0 text-slate-600"><IconCamera className="h-3.5 w-3.5" /></span>
        )}
        {s.has_audio && (
          <span className="shrink-0 text-slate-600"><IconMicrophone className="h-3.5 w-3.5" /></span>
        )}
      </div>
      {/* Observer */}
      <div
        className="flex cursor-pointer items-center gap-1.5 truncate text-xs text-slate-400 hover:text-white"
        onClick={(e) => {
          if (s.submitter_id) {
            e.preventDefault();
            e.stopPropagation();
            window.location.href = `/users/${s.submitter_id}`;
          }
        }}
      >
        <UserAvatar
          avatarUrl={s.submitter_avatar_url}
          displayName={s.submitter_name}
          size={18}
        />
        <span className="truncate">
          {s.submitter_is_moderator && <><IconShield className="h-3 w-3 inline-block" />{" "}</>}
          {s.submitter_name ?? "Anon"}
        </span>
      </div>
      {/* Confidence */}
      <span className="text-[11px] tabular-nums text-ocean-400">
        {conf ?? "—"}
      </span>
      {/* Status */}
      <div>
        <span
          className={`inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${status.bg} ${status.text}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
          {s.moderator_status ? <IconShield className="h-3 w-3 inline-block" /> : null}
          {STATUS_LABELS[s.verification_status] ?? s.verification_status}
        </span>
      </div>
      {/* Agree */}
      <span className="text-[11px] tabular-nums text-green-400">
        {s.community_agree > 0 ? s.community_agree : "—"}
      </span>
      {/* Disagree */}
      <span className="text-[11px] tabular-nums text-red-400">
        {s.community_disagree > 0 ? s.community_disagree : "—"}
      </span>
      {/* Trust score */}
      <span
        className={`text-[11px] tabular-nums ${
          s.verification_score != null
            ? s.verification_score >= 70
              ? "text-emerald-400"
              : s.verification_score >= 40
                ? "text-yellow-400"
                : "text-red-400"
            : "text-slate-600"
        }`}
      >
        {s.verification_score != null
          ? `${s.verification_score.toFixed(0)}%`
          : "—"}
      </span>
      {/* Risk */}
      <div className="flex items-center gap-1.5">
        {s.risk_score != null ? (
          <>
            <div className="h-1.5 w-12 overflow-hidden rounded-full bg-abyss-800">
              <div
                className={`h-full rounded-full ${RISK_BAR_COLOR[s.risk_category ?? ""] ?? "bg-slate-500/50"}`}
                style={{ width: `${(s.risk_score * 100).toFixed(0)}%` }}
              />
            </div>
            <span className={`text-[11px] font-medium tabular-nums ${riskText}`}>
              {(s.risk_score * 100).toFixed(0)}%
            </span>
          </>
        ) : (
          <span className="text-xs text-slate-600">—</span>
        )}
      </div>
      {/* Location */}
      <span className="text-[11px] tabular-nums text-slate-500">
        {s.lat != null
          ? `${s.lat.toFixed(1)}°, ${s.lon!.toFixed(1)}°`
          : "—"}
      </span>
      {/* Date */}
      <span
        className="text-right text-[11px] tabular-nums text-slate-500"
        title={s.sighting_datetime ? "Sighting time" : "Submitted"}
      >
        {new Date(s.sighting_datetime ?? s.created_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          year: "2-digit",
        })}
      </span>
    </Link>
  );
}

/* ── Species Summary Panel ────────────────────────────────── */

function SpeciesSummaryPanel({
  species,
  sightingCount,
}: {
  species: string;
  sightingCount: number;
}) {
  const info = SPECIES_SUMMARIES[species];
  if (!info) return null;
  const label = species.replace(/_/g, " ");
  const iconFile = SPECIES_ICON_FILES[species];

  return (
    <div className="mb-6 overflow-hidden rounded-2xl border border-ocean-800/50 bg-gradient-to-r from-abyss-900/90 to-abyss-900/70">
      <div className="flex flex-col gap-5 p-5 md:flex-row md:items-start md:gap-8">
        {/* Left: Icon + headline */}
        <div className="flex shrink-0 flex-col items-center gap-2 md:w-32">
          {iconFile ? (
            <Image
              src={`/whale_detailed_smooth_icons/${iconFile}`}
              alt={label}
              width={108}
              height={108}
              className="object-contain"
              style={{
                filter: `invert(1) ${SPECIES_RISK_TINT[species] ?? ""}`,
              }}
            />
          ) : (
            <span className="text-5xl">{SPECIES_EMOJI[species] ?? <IconWhale className="h-12 w-12" />}</span>
          )}
          <h3 className="text-center text-sm font-bold capitalize text-white">
            {label}
          </h3>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${info.statusColor} bg-white/5`}
          >
            {info.status}
          </span>
        </div>

        {/* Center: Description + threats */}
        <div className="min-w-0 flex-1 space-y-3">
          <p className="text-sm leading-relaxed text-slate-300">
            {info.description}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {info.threats.map((t) => (
              <span
                key={t}
                className="rounded-full border border-red-900/40 bg-red-950/30 px-2.5 py-0.5 text-[11px] text-red-400"
              >
                <IconWarning className="h-3 w-3 inline-block mr-0.5" /> {t}
              </span>
            ))}
          </div>
        </div>

        {/* Right: Stats */}
        <div className="grid shrink-0 grid-cols-2 gap-3 md:w-56 md:grid-cols-1">
          <MiniStat label="Est. Population" value={info.population} />
          <MiniStat label="Avg. Size" value={info.avgSize} />
          <MiniStat label="Range" value={info.range} />
          <MiniStat
            label="Community Interactions"
            value={String(sightingCount)}
            accent="text-ocean-400"
          />
        </div>
      </div>
    </div>
  );
}

/* ── Region Summary Panel ─────────────────────────────────── */

function RegionSummaryPanel({
  region,
  sightingCount,
  speciesInRegion,
}: {
  region: string;
  sightingCount: number;
  speciesInRegion: string[];
}) {
  const info = REGION_SUMMARIES[region];
  if (!info) return null;

  return (
    <div className="mb-6 overflow-hidden rounded-2xl border border-ocean-800/50 bg-gradient-to-r from-abyss-900/90 to-abyss-900/70">
      <div className="flex flex-col gap-5 p-5 md:flex-row md:items-start md:gap-8">
        {/* Left: Region badge + risk */}
        <div className="flex shrink-0 flex-col items-center gap-2 md:w-36">
          <span className="text-4xl"><IconWaves className="h-10 w-10 text-ocean-400" /></span>
          <h3 className="text-center text-sm font-bold text-white">
            {info.fullName}
          </h3>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${info.riskColor} bg-white/5`}
          >
            {info.riskLevel} Risk
          </span>
          <span className="text-center text-[10px] tabular-nums text-slate-500">
            {info.bbox}
          </span>
        </div>

        {/* Centre: Description + threats + notable areas */}
        <div className="min-w-0 flex-1 space-y-3">
          <p className="text-sm leading-relaxed text-slate-300">
            {info.description}
          </p>

          {/* Threats */}
          <div className="flex flex-wrap gap-1.5">
            {info.keyThreats.map((t) => (
              <span
                key={t}
                className="rounded-full border border-red-900/40 bg-red-950/30 px-2.5 py-0.5 text-[11px] text-red-400"
              >
                <IconWarning className="h-3 w-3 inline-block mr-0.5" /> {t}
              </span>
            ))}
          </div>

          {/* Notable areas */}
          <div className="flex flex-wrap gap-1.5">
            {info.notableAreas.map((a) => (
              <span
                key={a}
                className="rounded-full border border-ocean-800/50 bg-ocean-900/30 px-2.5 py-0.5 text-[11px] text-ocean-300"
              >
                <IconPin className="h-3 w-3 inline-block mr-0.5" /> {a}
              </span>
            ))}
          </div>

          {/* Key species silhouettes */}
          <div className="flex items-start gap-3">
            <span className="mr-0.5 mt-1 text-[11px] text-slate-500">
              Key species:
            </span>
            {info.keySpecies.map((sp) => (
              <div key={sp} className="flex flex-col items-center gap-0.5">
                <WhaleIcon species={sp} size={28} />
                <span className="text-[9px] leading-tight text-slate-500">
                  {sp.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Live stats */}
        <div className="grid shrink-0 grid-cols-2 gap-3 md:w-48 md:grid-cols-1">
          <MiniStat
            label="Community Interactions"
            value={String(sightingCount)}
            accent="text-ocean-400"
          />
          <MiniStat
            label="Species Observed"
            value={String(speciesInRegion.length)}
            accent="text-cyan-400"
          />
          <MiniStat
            label="Risk Level"
            value={info.riskLevel}
            accent={info.riskColor}
          />
        </div>
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p
        className={`text-sm font-semibold ${accent ?? "text-white"}`}
      >
        {value}
      </p>
    </div>
  );
}

/* ── Stats Dashboard View ─────────────────────────────────── */

function StatsView({ data }: { data: SubmissionSummary[] }) {
  if (data.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-ocean-800/60 py-24 text-center">
        <div className="flex justify-center"><IconChart className="h-10 w-10 text-slate-400" /></div>
        <p className="mt-3 text-slate-400">
          No data matching current filters.
        </p>
      </div>
    );
  }

  /* ── Compute stats ────────────────────────────────────── */
  const total = data.length;
  const verified = data.filter(
    (s) => s.verification_status === "verified",
  ).length;
  const disputed = data.filter(
    (s) => s.verification_status === "disputed",
  ).length;
  const rejected = data.filter(
    (s) => s.verification_status === "rejected",
  ).length;
  const unverified = total - verified - disputed - rejected;

  const withPhoto = data.filter((s) => s.has_photo).length;
  const withAudio = data.filter((s) => s.has_audio).length;
  const withBoth = data.filter((s) => s.has_photo && s.has_audio).length;
  const withLocation = data.filter(
    (s) => s.lat != null && s.lon != null,
  ).length;

  // Species breakdown
  const speciesCounts: Record<string, number> = {};
  for (const s of data) {
    const sp = s.model_species ?? s.species_guess ?? "unknown";
    speciesCounts[sp] = (speciesCounts[sp] ?? 0) + 1;
  }
  const speciesRanked = Object.entries(speciesCounts)
    .sort((a, b) => b[1] - a[1]);

  // Risk breakdown
  const riskCounts: Record<string, number> = {};
  for (const s of data) {
    const r = s.risk_category ?? "unknown";
    riskCounts[r] = (riskCounts[r] ?? 0) + 1;
  }

  // Region breakdown
  const regionCounts: Record<string, number> = {};
  for (const s of data) {
    const r = classifyRegion(s.lat, s.lon);
    const label =
      r === "all" ? "Unknown" : (REGION_LABELS[r] ?? r);
    regionCounts[label] = (regionCounts[label] ?? 0) + 1;
  }
  const regionRanked = Object.entries(regionCounts)
    .sort((a, b) => b[1] - a[1]);

  // Interaction types
  const interactionCounts: Record<string, number> = {};
  for (const s of data) {
    const t = s.interaction_type ?? "not specified";
    interactionCounts[t] = (interactionCounts[t] ?? 0) + 1;
  }

  // Confidence stats
  const confidences = data
    .map((s) => s.model_confidence)
    .filter((c): c is number => c != null);
  const avgConf =
    confidences.length > 0
      ? confidences.reduce((a, b) => a + b, 0) / confidences.length
      : null;
  const highConf = confidences.filter((c) => c >= 0.8).length;

  // Top observers
  const observerCounts: Record<string, number> = {};
  for (const s of data) {
    const name = s.submitter_name ?? "Anonymous";
    observerCounts[name] = (observerCounts[name] ?? 0) + 1;
  }
  const topObservers = Object.entries(observerCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  // Timeline — interactions per day (last 30 days)
  const dayCounts: Record<string, number> = {};
  for (const s of data) {
    const day = s.created_at.slice(0, 10);
    dayCounts[day] = (dayCounts[day] ?? 0) + 1;
  }
  const recentDays = Object.entries(dayCounts)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-30);
  const maxDayCount = Math.max(1, ...recentDays.map(([, c]) => c));

  const pct = (n: number) =>
    total > 0 ? `${((n / total) * 100).toFixed(1)}%` : "0%";

  return (
    <div className="space-y-6">
      {/* ── Row 1: Key metrics ─────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Interactions"
          value={total}
          icon={<IconClipboard className="h-5 w-5 text-slate-400" />}
        />
        <StatCard
          label="Verified"
          value={verified}
          sub={pct(verified)}
          icon={<IconCheck className="h-5 w-5 text-green-400" />}
          accent="text-green-400"
        />
        <StatCard
          label="With Photos"
          value={withPhoto}
          sub={pct(withPhoto)}
          icon={<IconCamera className="h-5 w-5 text-purple-400" />}
          accent="text-purple-400"
        />
        <StatCard
          label="Geolocated"
          value={withLocation}
          sub={pct(withLocation)}
          icon={<IconPin className="h-5 w-5 text-cyan-400" />}
          accent="text-cyan-400"
        />
      </div>

      {/* ── Row 2: Species + Risk + Region breakdowns ──── */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Species breakdown */}
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Species Breakdown
          </h3>
          <div className="space-y-2.5">
            {speciesRanked.map(([sp, count]) => (
              <div key={sp} className="flex items-center gap-2">
                <WhaleIcon species={sp} size={22} />
                <span className="min-w-0 flex-1 truncate text-xs text-slate-300">
                  {sp.replace(/_/g, " ")}
                </span>
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-abyss-800">
                  <div
                    className="h-full rounded-full bg-ocean-500/70"
                    style={{ width: `${(count / total) * 100}%` }}
                  />
                </div>
                <span className="w-8 text-right text-[11px] tabular-nums text-slate-500">
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Risk breakdown */}
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Risk Level Distribution
          </h3>
          <div className="space-y-2.5">
            {(["critical", "high", "medium", "low", "unknown"] as const).map(
              (level) => {
                const count = riskCounts[level] ?? 0;
                if (count === 0) return null;
                const color = RISK_TEXT[level] ?? "text-slate-500";
                return (
                  <div key={level} className="flex items-center gap-2">
                    <span
                      className={`w-16 text-xs font-medium capitalize ${color}`}
                    >
                      {level}
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-800">
                      <div
                        className="h-full rounded-full bg-ocean-500/70"
                        style={{ width: `${(count / total) * 100}%` }}
                      />
                    </div>
                    <span className="w-12 text-right text-[11px] tabular-nums text-slate-500">
                      {count} ({pct(count)})
                    </span>
                  </div>
                );
              },
            )}
          </div>

          {/* Verification status mini-bars */}
          <h4 className="mb-2 mt-6 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
            Verification Status
          </h4>
          <div className="space-y-1.5">
            {(
              [
                { key: "verified", count: verified, color: "bg-green-500" },
                { key: "unverified", count: unverified, color: "bg-slate-500" },
                { key: "disputed", count: disputed, color: "bg-yellow-500" },
                { key: "rejected", count: rejected, color: "bg-red-500" },
              ] as const
            ).map(({ key, count, color }) =>
              count === 0 ? null : (
                <div key={key} className="flex items-center gap-2">
                  <span className="w-16 text-[11px] capitalize text-slate-400">
                    {key}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-800">
                    <div
                      className={`h-full rounded-full ${color}/60`}
                      style={{ width: `${(count / total) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-[11px] tabular-nums text-slate-500">
                    {count}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>

        {/* Region breakdown */}
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Region Distribution
          </h3>
          <div className="space-y-2.5">
            {regionRanked.map(([region, count]) => (
              <div key={region} className="flex items-center gap-2">
                <span className="w-24 truncate text-xs text-slate-300">
                  {region}
                </span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-800">
                  <div
                    className="h-full rounded-full bg-cyan-500/60"
                    style={{ width: `${(count / total) * 100}%` }}
                  />
                </div>
                <span className="w-12 text-right text-[11px] tabular-nums text-slate-500">
                  {count} ({pct(count)})
                </span>
              </div>
            ))}
          </div>

          {/* Interaction types */}
          <h4 className="mb-2 mt-6 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
            Interaction Types
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(interactionCounts)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => (
                <span
                  key={type}
                  className="rounded-full border border-ocean-800/50 bg-abyss-800/60 px-2.5 py-0.5 text-[11px] text-slate-400"
                >
                  {type.replace(/_/g, " ")}{" "}
                  <span className="tabular-nums text-slate-500">({count})</span>
                </span>
              ))}
          </div>
        </div>
      </div>

      {/* ── Row 3: Media + confidence + timeline ───────── */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Media stats */}
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Media Attached
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-2xl font-bold text-purple-400">{withPhoto}</p>
              <p className="flex items-center gap-1 text-[11px] text-slate-500"><IconCamera className="h-3 w-3" /> Photos</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-cyan-400">{withAudio}</p>
              <p className="flex items-center gap-1 text-[11px] text-slate-500"><IconMicrophone className="h-3 w-3" /> Audio</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-ocean-400">{withBoth}</p>
              <p className="flex items-center gap-1 text-[11px] text-slate-500"><IconCamera className="h-3 w-3" /><span>+</span><IconMicrophone className="h-3 w-3" /> Both</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-400">
                {total - withPhoto - withAudio + withBoth}
              </p>
              <p className="text-[11px] text-slate-500">No media</p>
            </div>
          </div>
        </div>

        {/* Model confidence */}
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Model Confidence
          </h3>
          {avgConf != null ? (
            <div className="space-y-3">
              <div>
                <p className="text-[11px] text-slate-500">
                  Average Confidence
                </p>
                <p className="text-2xl font-bold text-white">
                  {(avgConf * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">
                  High Confidence (≥80%)
                </p>
                <p className="text-lg font-bold text-green-400">
                  {highConf}{" "}
                  <span className="text-xs font-normal text-slate-500">
                    / {confidences.length} classified
                  </span>
                </p>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-abyss-800">
                <div
                  className="h-full rounded-full bg-green-500/60"
                  style={{
                    width: `${(highConf / confidences.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              No ML classifications in current filter.
            </p>
          )}
        </div>

        {/* Top observers */}
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Top Observers
          </h3>
          <div className="space-y-2">
            {topObservers.map(([name, count], i) => (
              <div key={name} className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ocean-800/60 text-[10px] font-bold text-ocean-300">
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs text-slate-300">
                  {name}
                </span>
                <span className="text-[11px] tabular-nums text-slate-500">
                  {count} report{count !== 1 ? "s" : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Row 4: Activity timeline ───────────────────── */}
      {recentDays.length > 1 && (
        <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Recent Activity (last 30 days)
          </h3>
          <div className="flex h-24 items-end gap-[2px]">
            {recentDays.map(([day, count]) => (
              <div
                key={day}
                className="group relative flex-1"
                title={`${day}: ${count} interaction${count !== 1 ? "s" : ""}`}
              >
                <div
                  className="w-full rounded-t bg-ocean-500/60 transition-colors group-hover:bg-ocean-400/80"
                  style={{
                    height: `${(count / maxDayCount) * 100}%`,
                    minHeight: "2px",
                  }}
                />
              </div>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-slate-600">
            <span>{recentDays[0]?.[0]}</span>
            <span>{recentDays[recentDays.length - 1]?.[0]}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  icon,
  accent,
}: {
  label: string;
  value: number;
  sub?: string;
  icon: ReactNode;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-ocean-800/50 bg-abyss-900/70 p-5">
      <div className="flex items-center justify-between">
        <span>{icon}</span>
        {sub && (
          <span className="text-[11px] tabular-nums text-slate-500">
            {sub}
          </span>
        )}
      </div>
      <p
        className={`mt-2 text-2xl font-bold tabular-nums ${accent ?? "text-white"}`}
      >
        {value.toLocaleString()}
      </p>
      <p className="mt-0.5 text-[11px] text-slate-500">{label}</p>
    </div>
  );
}

/* ── Whale Icon Helper ────────────────────────────────────── */

function WhaleIcon({ species, size = 20 }: { species: string; size?: number }) {
  const smoothFile = SMOOTH_ICON_FILES[species];
  if (smoothFile) {
    const tint = SPECIES_RISK_TINT[species] ?? "";
    return (
      <Image
        src={`/whale_detailed_smooth_icons/${smoothFile}`}
        alt={species.replace(/_/g, " ")}
        width={size}
        height={size}
        className="inline-block object-contain"
        style={{ filter: `invert(1) ${tint}` }}
        aria-hidden="true"
      />
    );
  }
  /* Fallback: whale tail logo for species without a smooth icon */
  return (
    <Image
      src="/whale_watch_logo.png"
      alt="Whale tail"
      width={size}
      height={size}
      className="inline-block object-contain opacity-60"
      aria-hidden="true"
    />
  );
}

/* ── Filter Dropdown ──────────────────────────────────────── */

interface DropdownOption {
  value: string;
  label: string;
  dot?: string;   // coloured dot (for status)
  icon?: string;  // whale icon filename
  group?: string; // optional group header (rendered before first item in group)
}

function FilterDropdown({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: DropdownOption[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const selected = options.find((o) => o.value === value) ?? options[0];
  const isDefault = value === "all";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
          isDefault
            ? "border border-ocean-800/60 text-slate-400 hover:border-ocean-700 hover:text-slate-200"
            : "bg-ocean-600/90 text-white shadow-sm shadow-ocean-600/30"
        }`}
      >
        {selected.icon && (
          <Image
            src={`/species/${selected.icon}`}
            alt=""
            width={16}
            height={16}
            className="inline-block rounded-sm object-cover opacity-80"
            aria-hidden="true"
          />
        )}
        {selected.dot && (
          <span className={`h-1.5 w-1.5 rounded-full ${selected.dot}`} />
        )}
        <span>{isDefault ? label : selected.label}</span>
        <svg
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 z-50 mt-1 max-h-80 w-64 overflow-y-auto rounded-xl border border-ocean-800/60 bg-abyss-900/95 py-1 shadow-xl shadow-black/30 backdrop-blur-xl">
          {options.map((opt, idx) => {
            const active = opt.value === value;
            const showGroup = opt.group && (idx === 0 || options[idx - 1]?.group !== opt.group);
            return (
              <Fragment key={opt.value}>
              {showGroup && (
                <div className="sticky top-0 bg-abyss-900/95 px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-ocean-400/80">
                  {opt.group}
                </div>
              )}
              <button
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs transition-colors ${
                  active
                    ? "bg-ocean-600/20 text-white"
                    : "text-slate-400 hover:bg-ocean-800/30 hover:text-slate-200"
                }`}
              >
                {opt.icon && (
                  <Image
                    src={`/species/${opt.icon}`}
                    alt=""
                    width={22}
                    height={22}
                    className="shrink-0 rounded-sm object-cover opacity-80"
                    aria-hidden="true"
                  />
                )}
                {opt.dot && (
                  <span className={`h-2 w-2 shrink-0 rounded-full ${opt.dot}`} />
                )}
                <span className="truncate">{opt.label}</span>
                {active && (
                  <svg className="ml-auto h-3.5 w-3.5 shrink-0 text-ocean-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Impact counter (hero) ────────────────────────────────── */

function ImpactCounter({
  icon,
  value,
  label,
}: {
  icon: ReactNode;
  value: number;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-ocean-800/30 bg-abyss-900/60 px-4 py-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ocean-500/10">
        {icon}
      </div>
      <div>
        <div className="text-lg font-bold tabular-nums text-white">
          {value.toLocaleString()}
        </div>
        <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
          {label}
        </div>
      </div>
    </div>
  );
}

/* ── Activity feed item ───────────────────────────────────── */

function _timeAgo(iso: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(iso).getTime()) / 1000,
  );
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

const INTERACTION_VERBS: Record<string, string> = {
  visual: "spotted",
  acoustic: "heard",
  vessel_interaction: "observed a vessel interaction with",
  entanglement: "reported an entangled",
  stranding: "reported a stranded",
  collision: "reported a collision with",
  unknown: "reported",
};

function _speciesLabel(sp: string | null): string {
  if (!sp) return "a marine mammal";
  return sp.replace(/_/g, " ");
}

function ActivityItem({ item }: { item: RecentActivityItem }) {
  const verb =
    INTERACTION_VERBS[item.interaction_type ?? "unknown"] ?? "reported";
  const name = item.submitter_name ?? "Anonymous";
  const species = _speciesLabel(item.species);

  return (
    <Link
      href={`/submissions/${item.id}`}
      className="group flex items-start gap-3 rounded-lg px-2 py-2 transition hover:bg-ocean-900/40"
    >
      {/* Avatar */}
      <div className="shrink-0 pt-0.5">
        {item.submitter_avatar_url ? (
          <UserAvatar
            displayName={name}
            avatarUrl={`${API_BASE}${item.submitter_avatar_url}`}
            size={28}
          />
        ) : (
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-ocean-800/60 text-[10px] font-bold text-ocean-300">
            {name.charAt(0).toUpperCase()}
          </div>
        )}
      </div>
      {/* Description */}
      <div className="min-w-0 flex-1">
        <p className="text-xs leading-snug text-slate-400">
          <span className="font-medium text-slate-200">{name}</span>{" "}
          {verb}{" "}
          <span className="font-medium text-ocean-300">{species}</span>
          {item.has_photo && (
            <span className="ml-1 text-purple-400"><IconCamera className="inline-block h-3 w-3" /></span>
          )}
        </p>
        <span className="text-[10px] text-slate-600">
          {_timeAgo(item.created_at)}
        </span>
      </div>
      {/* Status dot */}
      <div className="shrink-0 pt-1">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${
            item.verification_status === "verified" ||
            item.verification_status === "community_verified"
              ? "bg-emerald-400"
              : "bg-slate-600"
          }`}
        />
      </div>
    </Link>
  );
}

/* ── Leaderboard row ──────────────────────────────────────── */

const RANK_STYLE: Record<number, string> = {
  1: "text-yellow-400",
  2: "text-slate-300",
  3: "text-amber-600",
};

function LeaderboardRow({
  rank,
  contributor: c,
}: {
  rank: number;
  contributor: TopContributorItem;
}) {
  const name = c.display_name ?? "Anonymous";
  const tierColor = TIER_STYLE[c.reputation_tier]?.color ?? "text-slate-400";
  const tierLabel = c.reputation_tier.charAt(0).toUpperCase()
    + c.reputation_tier.slice(1);

  return (
    <Link
      href={`/users/${c.user_id}`}
      className="group flex items-center gap-3 rounded-lg px-2 py-2 transition hover:bg-ocean-900/40"
    >
      {/* Rank */}
      <span
        className={`w-5 text-center text-xs font-bold tabular-nums ${
          RANK_STYLE[rank] ?? "text-slate-500"
        }`}
      >
        {rank}
      </span>
      {/* Avatar */}
      {c.avatar_url ? (
        <UserAvatar
          displayName={name}
          avatarUrl={`${API_BASE}${c.avatar_url}`}
          size={28}
        />
      ) : (
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-ocean-800/60 text-[10px] font-bold text-ocean-300">
          {name.charAt(0).toUpperCase()}
        </div>
      )}
      {/* Name + tier */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-slate-200 group-hover:text-white">
          {name}
        </p>
        <p className={`text-[10px] ${tierColor}`}>
          {tierLabel}
        </p>
      </div>
      {/* Count */}
      <div className="text-right">
        <div className="text-xs font-semibold tabular-nums text-slate-300">
          {c.submission_count}
        </div>
        <div className="text-[10px] text-slate-600">
          reports
        </div>
      </div>
    </Link>
  );
}

/* ── Boat leaderboard row ─────────────────────────────────── */

const VESSEL_TYPE_LABELS: Record<string, string> = {
  sailing_yacht: "Sailing Yacht",
  motorboat: "Motorboat",
  kayak_canoe: "Kayak / Canoe",
  research_vessel: "Research Vessel",
  whale_watch_boat: "Whale Watch",
  fishing_vessel: "Fishing Vessel",
  cargo_ship: "Cargo Ship",
  tanker: "Tanker",
  ferry_passenger: "Ferry",
  tug_workboat: "Tug",
  coast_guard: "Coast Guard",
  other: "Other",
};

function BoatLeaderboardRow({
  rank,
  boat: b,
}: {
  rank: number;
  boat: BoatLeaderboardItem;
}) {
  return (
    <Link
      href={`/boat/${b.vessel_id}`}
      className="group flex items-center gap-3 rounded-lg px-2 py-2 transition hover:bg-ocean-900/40"
    >
      {/* Rank */}
      <span
        className={`w-5 text-center text-xs font-bold tabular-nums ${
          RANK_STYLE[rank] ?? "text-slate-500"
        }`}
      >
        {rank}
      </span>
      {/* Boat icon / photo */}
      {b.profile_photo_url ? (
        <div className="relative h-7 w-7 overflow-hidden rounded-lg bg-ocean-800/60">
          <Image
            src={`${API_BASE}${b.profile_photo_url}`}
            alt={b.vessel_name}
            fill
            unoptimized
            className="object-cover"
          />
        </div>
      ) : (
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-ocean-800/60">
          <IconShip className="h-3.5 w-3.5 text-ocean-400/60" />
        </div>
      )}
      {/* Name + type */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-slate-200 group-hover:text-white">
          {b.vessel_name}
        </p>
        <p className="text-[10px] text-ocean-400/80">
          {VESSEL_TYPE_LABELS[b.vessel_type] ?? b.vessel_type}
          {b.crew_count > 1 && (
            <span className="ml-1.5 text-slate-500">
              {b.crew_count} crew
            </span>
          )}
        </p>
      </div>
      {/* Count */}
      <div className="text-right">
        <div className="text-xs font-semibold tabular-nums text-slate-300">
          {b.submission_count}
        </div>
        <div className="text-[10px] text-slate-600">
          reports
        </div>
      </div>
    </Link>
  );
}

/* ── Activity Bar Chart ───────────────────────────────────── */

function ActivityBarChart({ data }: { data: ActivityDay[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <IconChart className="h-4 w-4 text-ocean-400" />
          Sightings Over Time
        </h2>
        <span className="text-[10px] font-medium text-slate-500">
          {total} in the last 30 days
        </span>
      </div>

      {/* Bar chart */}
      <div className="flex items-end gap-[3px]" style={{ height: 80 }}>
        {data.map((d, i) => {
          const h = max > 0 ? (d.count / max) * 100 : 0;
          const dateObj = new Date(d.date + "T12:00:00");
          const isToday = i === data.length - 1;
          return (
            <div
              key={d.date}
              className="group relative flex flex-1 flex-col items-center justify-end"
              style={{ height: "100%" }}
            >
              {/* Tooltip */}
              <div className="pointer-events-none absolute -top-8 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-abyss-800 px-1.5 py-0.5 text-[9px] text-slate-300 opacity-0 shadow-lg ring-1 ring-ocean-800/40 transition-opacity group-hover:opacity-100">
                {dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                {" · "}
                <span className="font-semibold text-ocean-300">{d.count}</span>
              </div>
              {/* Bar */}
              <div
                className={`w-full min-h-[2px] rounded-t transition-all duration-300 ${
                  isToday
                    ? "bg-ocean-400 shadow-sm shadow-ocean-400/30"
                    : d.count > 0
                      ? "bg-ocean-500/60 group-hover:bg-ocean-400/80"
                      : "bg-ocean-900/40"
                }`}
                style={{ height: `${Math.max(h, 3)}%` }}
              />
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div className="mt-1.5 flex items-center gap-[3px]">
        {data.map((d, i) => {
          const dateObj = new Date(d.date + "T12:00:00");
          const showLabel = i === 0 || i === data.length - 1 || i % 7 === 0;
          return (
            <div key={d.date} className="flex-1 text-center">
              {showLabel && (
                <span className="text-[8px] text-slate-600">
                  {i === data.length - 1
                    ? "Today"
                    : dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Whale of the Week ────────────────────────────────────── */

function WhaleOfTheWeek({ item }: { item: WhaleOfTheWeekItem }) {
  const species = _speciesLabel(item.species);
  const photoUrl = `${API_BASE}/api/v1/media/${item.id}/photo`;

  return (
    <div className="group relative mb-8 overflow-hidden rounded-2xl border border-ocean-800/30 bg-gradient-to-br from-abyss-900/90 via-abyss-900/70 to-ocean-950/50">
      {/* Background glow */}
      <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-purple-500/5 blur-3xl" />
      <div className="pointer-events-none absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-ocean-500/5 blur-2xl" />

      {/* Header */}
      <div className="flex items-center gap-2 border-b border-ocean-800/20 px-5 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500/20 to-amber-600/10">
          <IconStar className="h-3.5 w-3.5 text-amber-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-slate-100">Whale of the Week</h2>
          <p className="text-[10px] text-slate-500">Most discussed sighting this fortnight</p>
        </div>
        <Link
          href={`/submissions/${item.id}`}
          className="text-[10px] font-medium text-ocean-400 hover:text-ocean-300 transition-colors"
        >
          View full report &rarr;
        </Link>
      </div>

      {/* Content: photo + details + comments */}
      <div className="grid gap-0 sm:grid-cols-5">
        {/* Photo column */}
        <div className="relative sm:col-span-2 aspect-[4/3] sm:aspect-auto bg-abyss-950">
          <Image
            src={photoUrl}
            alt={species}
            fill
            unoptimized
            className="object-cover"
          />
          {/* Species badge overlaid on photo */}
          <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full bg-abyss-900/80 px-2.5 py-1 backdrop-blur-sm ring-1 ring-white/10">
            <IconWhale className="h-3 w-3 text-ocean-400" />
            <span className="text-xs font-semibold capitalize text-slate-100">
              {species}
            </span>
          </div>
          {/* Verification badge */}
          {(item.verification_status === "verified" || item.verification_status === "community_verified") && (
            <div className="absolute top-3 right-3 flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 backdrop-blur-sm ring-1 ring-emerald-500/30">
              <IconCheck className="h-2.5 w-2.5 text-emerald-400" />
              <span className="text-[9px] font-bold text-emerald-300">Verified</span>
            </div>
          )}
        </div>

        {/* Details + comments column */}
        <div className="sm:col-span-3 flex flex-col">
          {/* Engagement stats */}
          <div className="flex items-center gap-4 border-b border-ocean-800/20 px-4 py-2.5">
            <div className="flex items-center gap-1.5">
              <IconThumbUp className="h-3.5 w-3.5 text-emerald-400/70" />
              <span className="text-xs font-semibold tabular-nums text-slate-300">{item.community_agree}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <IconThumbDown className="h-3.5 w-3.5 text-red-400/70" />
              <span className="text-xs font-semibold tabular-nums text-slate-300">{item.community_disagree}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <IconComment className="h-3.5 w-3.5 text-ocean-400/70" />
              <span className="text-xs font-semibold tabular-nums text-slate-300">{item.comment_count}</span>
            </div>
            <div className="flex-1" />
            {/* Submitter */}
            <div className="flex items-center gap-1.5">
              {item.submitter_avatar_url ? (
                <UserAvatar
                  displayName={item.submitter_name ?? "Anonymous"}
                  avatarUrl={`${API_BASE}${item.submitter_avatar_url}`}
                  size={18}
                />
              ) : (
                <div className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-ocean-800/60 text-[8px] font-bold text-ocean-300">
                  {(item.submitter_name ?? "A").charAt(0).toUpperCase()}
                </div>
              )}
              <span className="text-[10px] font-medium text-slate-400">
                {item.submitter_name ?? "Anonymous"}
              </span>
            </div>
          </div>

          {/* Comments list */}
          <div className="flex-1 overflow-y-auto px-4 py-3" style={{ maxHeight: 200 }}>
            {item.top_comments.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
                <IconComment className="h-6 w-6 text-slate-700" />
                <p className="text-[10px] text-slate-600">No comments yet — be the first!</p>
              </div>
            ) : (
              <div className="space-y-3">
                {item.top_comments.map((c) => (
                  <WotWCommentBubble key={c.id} comment={c} />
                ))}
              </div>
            )}
          </div>

          {/* "Join the conversation" footer */}
          <Link
            href={`/submissions/${item.id}`}
            className="flex items-center gap-2 border-t border-ocean-800/20 px-4 py-2.5 text-[11px] font-medium text-ocean-400 transition-colors hover:bg-ocean-900/30 hover:text-ocean-300"
          >
            <IconComment className="h-3 w-3" />
            Join the conversation
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ── Single comment bubble for Whale of the Week ──────────── */

function WotWCommentBubble({ comment: c }: { comment: WotWComment }) {
  const name = c.display_name ?? "Anonymous";
  const tierColor = TIER_STYLE[c.reputation_tier ?? "newcomer"]?.color ?? "text-slate-400";

  return (
    <div className="flex gap-2.5">
      {/* Avatar */}
      {c.avatar_url ? (
        <UserAvatar
          displayName={name}
          avatarUrl={`${API_BASE}${c.avatar_url}`}
          size={24}
        />
      ) : (
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ocean-800/60 text-[9px] font-bold text-ocean-300">
          {name.charAt(0).toUpperCase()}
        </div>
      )}
      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold text-slate-200">{name}</span>
          {c.reputation_tier && c.reputation_tier !== "newcomer" && (
            <span className={`text-[8px] font-bold uppercase tracking-wider ${tierColor}`}>
              {c.reputation_tier}
            </span>
          )}
          <span className="text-[9px] text-slate-600">{_timeAgo(c.created_at)}</span>
        </div>
        <p className="mt-0.5 text-xs leading-relaxed text-slate-400">
          {c.body}
        </p>
      </div>
    </div>
  );
}

export default function CommunityPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-abyss-950 text-slate-100 flex items-center justify-center">
          <div className="text-slate-400">Loading...</div>
        </main>
      }
    >
      <CommunityPageInner />
    </Suspense>
  );
}
