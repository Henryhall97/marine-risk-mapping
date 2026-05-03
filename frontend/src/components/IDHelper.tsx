"use client";

import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  IconWhale,
  IconDolphin,
  IconInfo,
  IconMicroscope,
  IconCamera,
  IconPin,
} from "@/components/icons/MarineIcons";
import { SPECIES_DESC } from "@/components/SpeciesPicker";

/* ── Shared constants ───────────────────────────────────── */

export const WIZARD_GROUPS: Record<string, string[]> = {
  baleen: [
    "right_whale", "humpback", "blue_whale", "fin_whale",
    "minke_whale", "sei_whale", "gray_whale", "bowhead",
    "brydes_whale", "rices_whale", "omuras_whale",
    "pygmy_right_whale", "southern_right_whale",
  ],
  toothed_whale: [
    "sperm_whale", "beaked_whale", "narwhal", "beluga",
    "dwarf_sperm_whale", "pygmy_sperm_whale",
  ],
  dolphin: [
    "orca", "bottlenose_dolphin", "common_dolphin",
    "pilot_whale", "spotted_dolphin", "striped_dolphin",
    "whitesided_dolphin", "rissos_dolphin", "hectors_dolphin",
  ],
  porpoise: [
    "harbor_porpoise", "dalls_porpoise", "vaquita",
  ],
};

export const WIZARD_CATCHALL: Record<
  string,
  { group: string; label: string; desc: string }
> = {
  baleen: {
    group: "unid_baleen",
    label: "Unidentified Baleen Whale",
    desc: "I saw a large whale — possibly filter-feeding or with visible baleen — but couldn't identify the species.",
  },
  toothed_whale: {
    group: "unid_toothed",
    label: "Unidentified Toothed Whale",
    desc: "I saw a toothed whale (not a dolphin or porpoise) but couldn't determine the species.",
  },
  dolphin: {
    group: "unid_dolphin",
    label: "Unidentified Dolphin",
    desc: "I saw a dolphin but couldn't narrow it to a specific species. Small, fast-moving dolphins at distance are often impossible to ID.",
  },
  porpoise: {
    group: "other_porpoise",
    label: "Unidentified Porpoise",
    desc: "I saw a small porpoise but couldn't determine which species. Porpoises surface briefly and are hard to distinguish.",
  },
  whale_unsure: {
    group: "unid_cetacean",
    label: "Unidentified Whale",
    desc: "I saw a whale but couldn't tell whether it was baleen or toothed. Distant sightings often can't be narrowed further.",
  },
  unsure: {
    group: "unid_cetacean",
    label: "Unidentified Cetacean",
    desc: "I saw something in the water but couldn't determine what type of cetacean it was. That's completely fine — brief or distant sightings are very common.",
  },
};

/** Photo filename stem by species group (shared with species page). */
export const SPECIES_PHOTOS: Record<string, string> = {
  right_whale: "right_whale",
  humpback: "humpback_whale",
  fin_whale: "fin_whale",
  blue_whale: "blue_whale",
  sperm_whale: "sperm_whale",
  minke_whale: "minke_whale",
  sei_whale: "sei_whale",
  orca: "orca",
  gray_whale: "gray_whale",
  bowhead: "bowhead",
  bottlenose_dolphin: "bottlenose_dolphin",
  common_dolphin: "common_dolphin",
  harbor_porpoise: "harbor_porpoise",
  pilot_whale: "pilot_whale",
  beluga: "beluga",
  beaked_whale: "beaked_whale",
  brydes_whale: "brydes_whale",
  rissos_dolphin: "rissos_dolphin",
  spotted_dolphin: "spotted_dolphin",
  striped_dolphin: "striped_dolphin",
  whitesided_dolphin: "whitesided_dolphin",
  dalls_porpoise: "dalls_porpoise",
  vaquita: "vaquita",
  southern_right_whale: "right_whale",
  dwarf_sperm_whale: "dwarf_sperm_whales",
  pygmy_sperm_whale: "dwarf_sperm_whales",
  small_sperm_whale: "dwarf_sperm_whales",
  narwhal: "narwhal",
};

/* ── Identification guidance ─────────────────────────────
   Each stage and species has tips explaining what to look for.
   Every entry has an `imgKey` field — a stable string key that
   will map to a future illustration/graphic for that stage.
   ──────────────────────────────────────────────────────── */

/** Stage-level guidance: what to look for at each decision point. */
export const STAGE_GUIDANCE: Record<
  string,
  {
    title: string;
    tips: string[];
    imgKey: string;
  }
> = {
  start: {
    title: "How to tell them apart",
    tips: [
      "These are practical field categories — whale, dolphin, or porpoise — based on how the animal looks and behaves at sea, the same approach used by professional field guides.",
      "Dolphins and porpoises are technically toothed whales (Odontoceti) but look and behave very differently, so field guides treat them as separate groups.",
      "Size is the strongest first clue: whales are typically 4–30 m, dolphins 1.5–4 m, and porpoises 1.2–2.5 m.",
      "Blow: Only large whales produce a visible spout when breathing. Dolphins and porpoises don't.",
      "Behaviour: Dolphins often leap, bow-ride, and travel in large energetic groups. Porpoises surface quietly with a rolling motion. Whales surface slowly with long, arching rolls.",
      "Dorsal fin: Porpoises have small triangular fins. Dolphins have curved or hooked fins. Some whales have no dorsal fin at all.",
      "Exceptions exist — orca (up to 9 m) is technically a dolphin, and pygmy/dwarf sperm whales (2–3.5 m) are whale-sized in behaviour but much smaller in body. If something doesn't fit neatly, pick the closest match or choose 'Not sure'.",
    ],
    imgKey: "stage_start_comparison",
  },
  whale_kind: {
    title: "Baleen vs toothed whales",
    tips: [
      "Blowhole: Count the holes — baleen whales have TWO blowholes side-by-side (wide/V-shaped blow). Toothed whales have ONE blowhole (forward-angled blow).",
      "Mouth: Look for baleen plates — comb-like structures hanging from the upper jaw. If you see teeth, it's a toothed whale.",
      "Throat grooves: Baleen whales (rorquals) have ventral pleats running from chin to belly that expand when feeding. Toothed whales have smooth bellies.",
      "Head: Baleen whales have broad, flat or arched heads. Toothed whales have a bulbous rounded forehead (melon) used for echolocation.",
      "Feeding style: Lunging through shoals with mouth agape = baleen. Deep diving for long periods (45+ min) = toothed.",
    ],
    imgKey: "stage_whale_kind_comparison",
  },
  baleen: {
    title: "Identifying baleen whales",
    tips: [
      "Dorsal fin: Right whales and bowheads have no dorsal fin. Rorquals (humpback, fin, blue, minke, sei) have a dorsal fin in the last third of the body.",
      "Head: Right whales have callosities (rough white patches). Humpbacks have bumps (tubercles). Fin/blue/sei have smooth, streamlined heads.",
      "Pectoral fins: Humpbacks have extremely long flippers (up to ⅓ body length). Other rorquals have short flippers.",
      "Flukes: Humpbacks lift flukes high when diving — each pattern is unique. Blue and fin whales rarely show flukes.",
      "Blow: Blue whales have a tall columnar blow (9 m). Humpbacks have a bushy blow. Right whales have a distinctive V-shaped blow.",
    ],
    imgKey: "stage_baleen_species",
  },
  toothed_whale: {
    title: "Identifying toothed whales",
    tips: [
      "Head shape: Sperm whales have a massive, squared head (~⅓ of body length). Beaked whales have a pronounced beak.",
      "Blow angle: Sperm whale blow angles forward-left (unique among whales). Beaked whales have a low, inconspicuous blow.",
      "Colour: Belugas are bright white as adults. Narwhals are mottled grey with spots.",
      "Tusk: Only narwhals have a long spiral tusk (males). No other cetacean has this feature.",
      "Diving: Sperm whales lift flukes high before deep dives. Beaked whales arch their backs and slip below with minimal splash.",
    ],
    imgKey: "stage_toothed_species",
  },
  dolphin: {
    title: "Identifying dolphins",
    tips: [
      "Colour pattern: Common dolphins have an hourglass pattern. Striped dolphins have a dark eye-to-flipper stripe. Spotted dolphins develop spots with age.",
      "Size: Orcas (killer whales) are the largest dolphins (6–9 m) with a tall dorsal fin. Most dolphins are 2–4 m.",
      "Dorsal fin: Orcas have a tall, erect fin (up to 1.8 m in males). Pilot whales have a low, rounded fin. Bottlenose and common dolphins have a curved, hook-shaped fin.",
      "Head: Risso's dolphins have a blunt, bulbous head with no beak. Pilot whales have a rounded melon head. Most other dolphins have a distinct beak.",
      "Scarring: Risso's dolphins become almost entirely white with age from extensive scarring. Heavily scarred = likely Risso's.",
      "Behaviour: Bottlenose dolphins are curious and approach boats. Spinner dolphins spin on their axis when leaping. Common dolphins often travel in pods of 100+.",
    ],
    imgKey: "stage_dolphin_species",
  },
  porpoise: {
    title: "Identifying porpoises",
    tips: [
      "Key difference from dolphins: Porpoises have rounded (spade-shaped) teeth, a blunt head with no beak, and a small triangular dorsal fin.",
      "Behaviour: Porpoises are shy — they surface briefly to breathe with a quick rolling motion and rarely leap or bow-ride.",
      "Harbour porpoise: Small (1.5 m), grey-brown. Triangular dorsal fin. The most commonly sighted porpoise in the Northern Hemisphere.",
      "Dall's porpoise: Stocky, black-and-white. Creates a distinctive rooster-tail spray when swimming fast. North Pacific only.",
      "Vaquita: World's rarest cetacean (<10 left). Dark eye rings. Gulf of California only — if you're there, report any porpoise sighting.",
    ],
    imgKey: "stage_porpoise_species",
  },
};

/* ── Commonly confused species ───────────────────────────
   For each wizard species, lists the 2–3 most easily mistaken
   look-alikes with a concise distinguishing field mark.
   Keys are wizard species keys (e.g. "humpback" not "humpback_whale").
   Sources: NOAA field guides + model confusion matrix.
   ──────────────────────────────────────────────────────── */

interface ConfusedPair {
  /** Wizard species key of the look-alike */
  key: string;
  /** One-line distinguishing mark */
  mark: string;
}

const CONFUSED_WITH: Record<string, ConfusedPair[]> = {
  /* ── Baleen whales ── */
  right_whale: [
    { key: "bowhead", mark: "Bowhead has no callosities and has a white chin patch" },
    { key: "humpback", mark: "Humpback has long white pectoral fins and knobby tubercles" },
  ],
  southern_right_whale: [
    { key: "right_whale", mark: "North Atlantic right whale is only in the north — ranges don't overlap" },
    { key: "bowhead", mark: "Bowhead has a white chin and lives in Arctic waters" },
  ],
  humpback: [
    { key: "fin_whale", mark: "Fin whale has a tall sickle dorsal and rarely shows flukes" },
    { key: "minke_whale", mark: "Minke is much smaller (7–10 m) with a pointed snout" },
    { key: "gray_whale", mark: "Gray whale has mottled grey skin with barnacles and no long flippers" },
  ],
  fin_whale: [
    { key: "blue_whale", mark: "Blue is mottled blue-grey with a tiny dorsal far back" },
    { key: "sei_whale", mark: "Sei surfaces at a shallow angle; fin has asymmetric jaw colouring" },
    { key: "brydes_whale", mark: "Bryde's has 3 head ridges; fin has 1 ridge and asymmetric jaw" },
  ],
  blue_whale: [
    { key: "fin_whale", mark: "Fin has asymmetric jaw (right side white) and a taller dorsal fin" },
    { key: "sei_whale", mark: "Sei is smaller (15–18 m) and uniformly dark grey" },
  ],
  minke_whale: [
    { key: "sei_whale", mark: "Sei is much larger (15–18 m) and lacks white flipper bands" },
    { key: "fin_whale", mark: "Fin is much larger (18–25 m) with asymmetric jaw" },
  ],
  sei_whale: [
    { key: "brydes_whale", mark: "Bryde's has 3 head ridges; sei has only 1 central ridge" },
    { key: "fin_whale", mark: "Fin has asymmetric jaw; sei has uniform dark colouring" },
    { key: "minke_whale", mark: "Minke is much smaller with white flipper bands" },
  ],
  gray_whale: [
    { key: "humpback", mark: "Humpback has long pectoral fins and knobby head" },
    { key: "right_whale", mark: "Right whale has white callosities; gray whale has barnacle clusters" },
  ],
  bowhead: [
    { key: "right_whale", mark: "Right whale has rough white callosities; bowhead has a white chin" },
  ],
  brydes_whale: [
    { key: "sei_whale", mark: "Sei has 1 head ridge; Bryde's has 3 parallel ridges" },
    { key: "fin_whale", mark: "Fin has asymmetric jaw; Bryde's has 3 head ridges" },
  ],
  rices_whale: [
    { key: "brydes_whale", mark: "Rice's and Bryde's are nearly identical — Rice's is restricted to the Gulf of Mexico" },
    { key: "sei_whale", mark: "Sei has 1 head ridge; Rice's has 3 (like Bryde's)" },
  ],
  /* ── Toothed whales ── */
  sperm_whale: [
    { key: "beaked_whale", mark: "Beaked whales have a pronounced beak; sperm whale has a massive squared head" },
  ],
  beaked_whale: [
    { key: "sperm_whale", mark: "Sperm whale has a huge squared head (⅓ of body); beaked whale has a distinct beak" },
    { key: "dwarf_sperm_whale", mark: "Dwarf/pygmy sperm whales are much smaller (2–3.5 m)" },
  ],
  dwarf_sperm_whale: [
    { key: "pygmy_sperm_whale", mark: "Pygmy sperm whale is slightly larger with a more forward dorsal fin" },
    { key: "harbor_porpoise", mark: "Harbor porpoise has a triangular dorsal; dwarf sperm whale has a tiny hooked fin" },
  ],
  pygmy_sperm_whale: [
    { key: "dwarf_sperm_whale", mark: "Dwarf sperm whale is smaller with a taller, more central dorsal fin" },
  ],
  beluga: [
    { key: "narwhal", mark: "Narwhal is mottled grey with spots (adults); beluga is all white" },
  ],
  narwhal: [
    { key: "beluga", mark: "Beluga is bright white with no tusk; narwhal has a spiral tusk (males)" },
  ],
  /* ── Dolphins ── */
  orca: [
    { key: "pilot_whale", mark: "Pilot whale is all dark with a rounded melon; orca has bold black-and-white pattern" },
    { key: "dalls_porpoise", mark: "Dall's is much smaller (2 m) with small triangular dorsal" },
  ],
  pilot_whale: [
    { key: "orca", mark: "Orca has bold black-and-white markings and a tall dorsal" },
    { key: "rissos_dolphin", mark: "Risso's becomes pale/white with age from scarring; pilot whale stays dark" },
  ],
  bottlenose_dolphin: [
    { key: "common_dolphin", mark: "Common dolphin has a yellow hourglass pattern; bottlenose is uniform grey" },
    { key: "spotted_dolphin", mark: "Spotted dolphin develops spots with age; bottlenose is unspotted" },
  ],
  common_dolphin: [
    { key: "bottlenose_dolphin", mark: "Bottlenose is larger and uniform grey; common dolphin has an hourglass pattern" },
    { key: "striped_dolphin", mark: "Striped has a dark eye-to-flipper stripe; common dolphin has a yellow side patch" },
  ],
  spotted_dolphin: [
    { key: "bottlenose_dolphin", mark: "Bottlenose is unspotted; spotted dolphin has spots that increase with age" },
    { key: "common_dolphin", mark: "Common dolphin has an hourglass pattern; spotted has scattered spots" },
  ],
  striped_dolphin: [
    { key: "common_dolphin", mark: "Common dolphin has a yellow hourglass; striped has a bold eye-to-flipper stripe" },
  ],
  whitesided_dolphin: [
    { key: "common_dolphin", mark: "Common dolphin has a yellow hourglass; white-sided has a white flank patch" },
  ],
  rissos_dolphin: [
    { key: "pilot_whale", mark: "Pilot whale stays uniformly dark; Risso's becomes pale with heavy scarring" },
    { key: "bottlenose_dolphin", mark: "Bottlenose has a prominent beak; Risso's has a blunt, beakless head" },
  ],
  /* ── Porpoises ── */
  harbor_porpoise: [
    { key: "dalls_porpoise", mark: "Dall's is stocky and black-and-white; harbour is small and grey-brown" },
  ],
  dalls_porpoise: [
    { key: "harbor_porpoise", mark: "Harbor porpoise is smaller and plain grey-brown; Dall's has bold black-and-white" },
    { key: "orca", mark: "Orca is much larger (6–9 m) with a tall dorsal; Dall's is 2 m" },
  ],
};

/* ── Observable field traits for narrowing species ────────
   Trait definitions + per-species mappings. Used for AND-
   filtering in the result step.
   ──────────────────────────────────────────────────────── */

interface TraitDef {
  label: string;
  category: "size" | "behavior" | "feature" | "blow";
}

const FIELD_TRAITS: Record<string, TraitDef> = {
  /* Size estimate */
  small:        { label: "Small (< 5 m)", category: "size" },
  medium:       { label: "Medium (5–12 m)", category: "size" },
  large:        { label: "Large (12–20 m)", category: "size" },
  very_large:   { label: "Very large (> 20 m)", category: "size" },
  /* Behaviours observed */
  breaching:    { label: "Breaching / leaping", category: "behavior" },
  fluking:      { label: "Raising tail flukes", category: "behavior" },
  bow_riding:   { label: "Bow-riding", category: "behavior" },
  lunge_feed:   { label: "Lunge-feeding", category: "behavior" },
  logging:      { label: "Floating motionless", category: "behavior" },
  tail_slap:    { label: "Tail / flipper slapping", category: "behavior" },
  spy_hop:      { label: "Spy-hopping", category: "behavior" },
  pod:          { label: "In a group / pod", category: "behavior" },
  /* Physical features */
  no_dorsal:    { label: "No dorsal fin", category: "feature" },
  tall_dorsal:  { label: "Tall dorsal fin", category: "feature" },
  small_dorsal: { label: "Small / hooked dorsal", category: "feature" },
  callosities:  { label: "White rough patches (callosities)", category: "feature" },
  long_flipper: { label: "Very long flippers", category: "feature" },
  white_marks:  { label: "Distinctive white markings", category: "feature" },
  spotted:      { label: "Spotted pattern", category: "feature" },
  scarred:      { label: "Heavy body scarring", category: "feature" },
  beak:         { label: "Prominent beak / snout", category: "feature" },
  blunt_head:   { label: "Blunt / rounded head", category: "feature" },
  /* Blow / spout */
  v_blow:       { label: "V-shaped blow", category: "blow" },
  bushy_blow:   { label: "Bushy round blow", category: "blow" },
  tall_blow:    { label: "Tall columnar blow", category: "blow" },
  forward_blow: { label: "Forward-angled blow", category: "blow" },
};

const TRAIT_CATEGORY_LABELS: Record<string, string> = {
  size: "Estimated Size",
  behavior: "Behaviour Observed",
  feature: "Physical Features",
  blow: "Blow / Spout",
};

/** Which observable traits apply to each species. AND-filtering. */
const SPECIES_TRAITS: Record<string, string[]> = {
  /* Baleen whales */
  right_whale:          ["large", "no_dorsal", "callosities", "v_blow", "fluking", "logging", "breaching"],
  southern_right_whale: ["large", "no_dorsal", "callosities", "v_blow", "fluking", "breaching"],
  humpback:             ["large", "long_flipper", "bushy_blow", "breaching", "fluking", "tail_slap", "lunge_feed", "pod"],
  fin_whale:            ["very_large", "tall_dorsal", "tall_blow", "white_marks"],
  blue_whale:           ["very_large", "small_dorsal", "tall_blow", "lunge_feed"],
  minke_whale:          ["medium", "small_dorsal", "white_marks", "breaching"],
  sei_whale:            ["large", "tall_dorsal", "tall_blow"],
  gray_whale:           ["large", "no_dorsal", "bushy_blow", "fluking", "spy_hop", "breaching"],
  bowhead:              ["very_large", "no_dorsal", "v_blow", "white_marks", "fluking"],
  brydes_whale:         ["large", "small_dorsal", "lunge_feed"],
  rices_whale:          ["large", "small_dorsal"],
  omuras_whale:         ["medium", "white_marks", "small_dorsal"],
  pygmy_right_whale:    ["small", "small_dorsal"],
  /* Toothed whales */
  sperm_whale:          ["very_large", "blunt_head", "forward_blow", "fluking", "logging"],
  beaked_whale:         ["medium", "small_dorsal", "beak", "scarred"],
  narwhal:              ["medium", "no_dorsal", "pod"],
  beluga:               ["medium", "white_marks", "blunt_head", "no_dorsal", "pod"],
  dwarf_sperm_whale:    ["small", "small_dorsal", "logging"],
  pygmy_sperm_whale:    ["small", "small_dorsal", "logging"],
  /* Dolphins */
  orca:                 ["large", "tall_dorsal", "white_marks", "pod", "breaching", "spy_hop"],
  bottlenose_dolphin:   ["medium", "beak", "small_dorsal", "pod", "bow_riding", "breaching"],
  common_dolphin:       ["small", "beak", "small_dorsal", "pod", "bow_riding", "breaching"],
  spotted_dolphin:      ["small", "spotted", "beak", "pod", "bow_riding", "breaching"],
  striped_dolphin:      ["small", "beak", "pod", "breaching"],
  whitesided_dolphin:   ["small", "white_marks", "pod", "breaching"],
  rissos_dolphin:       ["medium", "blunt_head", "scarred", "pod"],
  pilot_whale:          ["medium", "blunt_head", "small_dorsal", "pod", "logging", "spy_hop"],
  hectors_dolphin:      ["small", "small_dorsal", "pod"],
  /* Porpoises */
  harbor_porpoise:      ["small", "small_dorsal", "blunt_head"],
  dalls_porpoise:       ["small", "white_marks", "blunt_head", "bow_riding"],
  vaquita:              ["small", "small_dorsal", "blunt_head"],
};

/* ── Anatomy primer — key terms shown at wizard start ── */
const ANATOMY_TERMS: { term: string; desc: string }[] = [
  { term: "Dorsal fin", desc: "Fin on top of the back — shape is one of the most important ID features" },
  { term: "Fluke", desc: "Horizontal tail fin — underside patterns can identify individuals" },
  { term: "Blowhole", desc: "Breathing opening on top of the head; baleen whales have two, toothed whales have one" },
  { term: "Rostrum / Beak", desc: "Snout area — dolphins have a prominent beak, porpoises don\u2019t" },
  { term: "Pectoral flipper", desc: "Side fins used for steering — humpback\u2019s are extra-long" },
  { term: "Melon", desc: "Rounded forehead — large in toothed whales and dolphins (used for echolocation)" },
  { term: "Peduncle", desc: "Narrow tail stock connecting the body to the flukes" },
  { term: "Blow / Spout", desc: "Visible exhaled breath — height and shape help ID species at a distance" },
];

/* ── Anatomy diagram ───────────────────────────────────── */
const ANATOMY_DIAGRAM = {
  src: "/wizard/guides/baleen_vs_toothed.png",
  alt: "Baleen whale vs toothed whale — labeled body parts comparison (double blowhole, baleen plates vs single blowhole, teeth, melon)",
  aspect: "aspect-[3/4]",
  credit: "Chris huh, Public Domain, via Wikimedia Commons",
};

/* ── Baleen vs Toothed visual comparison ─────────────── */

interface IDCue { label: string; detail: string }

const BALEEN_CUES: IDCue[] = [
  { label: "Two blowholes", detail: "Wide or V-shaped blow" },
  { label: "Flat or arched head", detail: "No melon — broad rostrum, some species have callosities" },
  { label: "Baleen plates", detail: "Flexible combs hang from upper jaw — no teeth" },
  { label: "Ventral pleats", detail: "Throat grooves expand when lunge-feeding" },
  { label: "Filter feeders", detail: "Lunge or skim-feed on krill and small fish" },
  { label: "Slow, predictable", detail: "Seasonal migrations along known coastal routes" },
];

const TOOTHED_CUES: IDCue[] = [
  { label: "Single blowhole", detail: "Forward-angled blow" },
  { label: "Melon or flat head", detail: "Rounded melon (orca, beaked whales) or blunt flat head (sperm whale)" },
  { label: "Conical teeth", detail: "Visible in jaws — no baleen" },
  { label: "Smooth belly", detail: "No pleats or throat grooves" },
  { label: "Active hunters", detail: "Use echolocation to pursue fish and squid" },
  { label: "Deep divers", detail: "Sperm whales dive 2 000 m+; agile, erratic routes" },
];

/* ── Reference guide images shown in species expanded detail ── */
const SPECIES_GUIDES: Record<string, { src: string; alt: string; caption: string }[]> = {
  right_whale: [
    {
      src: "/wizard/guides/narw_identification.png",
      alt: "North Atlantic Right Whale — key identification features",
      caption: "Physical characteristics",
    },
    {
      src: "/wizard/guides/narw_behaviors.png",
      alt: "North Atlantic Right Whale — common behaviors",
      caption: "Common behaviors",
    },
    {
      src: "/wizard/guides/narw_vs_humpback.png",
      alt: "Right whale vs. humpback whale comparison",
      caption: "Right whale vs. humpback",
    },
  ],
  humpback: [
    {
      src: "/wizard/guides/narw_vs_humpback.png",
      alt: "Right whale vs. humpback whale — how to tell them apart",
      caption: "Humpback vs. right whale — key differences",
    },
  ],
};

/** Per-species identification tips — brief 1-2 line field marks. */
export const SPECIES_ID_TIPS: Record<string, string> = {
  /* Baleen whales */
  right_whale:
    "Look for: no dorsal fin, white callosities (rough patches) on head and jaw, V-shaped blow up to 5 m. 13–16 m long, dark body. Often skim-feeds at surface with mouth agape. Endangered — ~350 remaining.",
  southern_right_whale:
    "Look for: same as right whale — no dorsal fin, callosities on head. Southern Hemisphere only. Frequently seen close to shore.",
  humpback:
    "Look for: very long pectoral fins (up to 5 m, white underneath), knobby tubercles on head and lower jaw, unique black-and-white fluke pattern raised high when diving. 12–16 m. Bushy blow 3 m. Frequent breaching, lob-tailing, and flipper-slapping.",
  fin_whale:
    "Look for: asymmetric jaw (right side white, left side dark — unique among whales), tall columnar blow 4–6 m, very large (18–25 m). Tall sickle dorsal fin. Surfaces in a long arc. Rarely shows flukes. One of the fastest whales — up to 37 km/h.",
  blue_whale:
    "Look for: enormous size (up to 30 m, largest animal ever), mottled blue-grey skin, tiny dorsal fin far back on body, broad flat U-shaped head. Extremely tall blow up to 9 m, visible from great distance. Throat grooves expand when lunge-feeding.",
  minke_whale:
    "Look for: small size (7–10 m), pointed triangular snout, white bands on flippers, curved dorsal fin appears simultaneously with the blowhole. Often curious.",
  sei_whale:
    "Look for: single central ridge on head (not three like Bryde's), tall sickle-shaped dorsal fin, uniform dark grey. Surfaces at a shallow angle. Fast.",
  gray_whale:
    "Look for: mottled grey with barnacles and orange whale lice, no dorsal fin — instead a low hump and knuckle-like ridges along the tail stock. Heart-shaped blow.",
  bowhead:
    "Look for: massive triangular head (40% of body), no dorsal fin, strongly bowed lower jaw showing white chin patch. Arctic only — often seen near ice.",
  brydes_whale:
    "Look for: three parallel ridges on top of head (unique among rorquals). Tropical waters. Often changes direction suddenly when feeding.",
  rices_whale:
    "Look for: very similar to Bryde's whale — three head ridges. Gulf of Mexico only. Extremely rare (~50 remaining). Any sighting is significant.",
  omuras_whale:
    "Look for: asymmetric jaw colouring similar to fin whale, but much smaller. Tropical waters. Only formally described in 2003 — very few confirmed sightings.",
  pygmy_right_whale:
    "Look for: smallest baleen whale (~6 m), arched jawline, small hooked dorsal fin. Southern Hemisphere only. One of the world's least-seen whales.",

  /* Toothed whales */
  sperm_whale:
    "Look for: massive squared head (⅓ of body), wrinkled prune-like skin, blow angled forward-left at 45° (unique among whales). 11–18 m. Lifts broad triangular flukes high before diving to 1000+ m depths. Dives last 45–60 min.",
  beaked_whale:
    "Look for: elongated beak, small dorsal fin set far back, body often covered in linear scars. Very deep diver — rare at the surface. Brief, inconspicuous surfacing.",
  narwhal:
    "Look for: mottled grey-brown body, no dorsal fin — just a low dorsal ridge. Males have a long spiral tusk (left canine). Arctic only, often near sea ice.",
  beluga:
    "Look for: all-white adult (calves are grey-brown, lighten over 5+ years), rounded bulbous forehead (melon) used for echolocation, no dorsal fin — just a low dorsal ridge. 3–5 m. Flexible neck — only cetacean that can turn its head. Called 'canaries of the sea' for vocal repertoire.",
  dwarf_sperm_whale:
    "Look for: very small (~2.7 m), shark-like profile, bracket-shaped pale mark behind eye ('false gill'). Taller dorsal fin than pygmy sperm whale. Rarely seen.",
  pygmy_sperm_whale:
    "Look for: small (~3.5 m), shark-like appearance, 'false gill' mark behind eye. Lower dorsal fin than dwarf sperm whale. Often floats motionless at surface.",

  /* Dolphins */
  orca:
    "Look for: striking black-and-white pattern, tall dorsal fin (up to 1.8 m in males, curved in females), white eye patch, grey saddle patch behind dorsal. 6–9 m. Largest member of the dolphin family. Travels in matrilineal pods of 5–30.",
  bottlenose_dolphin:
    "Look for: robust grey body, short stubby beak, curved dorsal fin. Very social and curious — often approaches boats. Commonly seen nearshore.",
  common_dolphin:
    "Look for: distinctive hourglass colour pattern on flanks (yellow/tan forward, grey behind). Often in large fast-moving pods (100+). Energetic leapers.",
  spotted_dolphin:
    "Look for: spots that increase with age (calves are unspotted). Slender build, long beak. Athletic — often seen bow-riding. Warm Atlantic waters.",
  striped_dolphin:
    "Look for: dark stripe running from eye to flipper, and a second stripe from eye to anus. Acrobatic leaper. Warm-temperate and tropical oceans.",
  whitesided_dolphin:
    "Look for: distinctive white and yellow patches on flanks. Robust body. North Atlantic. Often in large pods. Fast swimmers.",
  rissos_dolphin:
    "Look for: blunt rounded head with no beak, heavily scarred grey body that becomes nearly white in older animals. No teeth in upper jaw.",
  pilot_whale:
    "Look for: bulbous rounded forehead, long low sickle-shaped dorsal fin, dark grey/black body. Travels in tight social groups of 10–30.",
  hectors_dolphin:
    "Look for: distinctive rounded black dorsal fin (unlike other dolphins), grey body with white belly. Very small (~1.4 m). Endemic to New Zealand.",

  /* Porpoises */
  harbor_porpoise:
    "Look for: small (1.5 m), dark grey-brown back, lighter flanks. Small triangular dorsal fin. Rounded head with no beak. Quick, rolling surfacings.",
  dalls_porpoise:
    "Look for: stocky black body with white flank patches, small head. Creates a distinctive rooster-tail spray when fast-swimming. North Pacific.",
  vaquita:
    "Look for: dark rings around eyes and dark lip patches on a small grey body. Extremely shy. Gulf of California only. <10 remaining — any sighting is critical.",
};

/**
 * Geographic ranges per species — used to sort/highlight species likely
 * at the user's sighting location. Keys match WIZARD_GROUPS entries.
 * Regions: NAtl = North Atlantic, NPac = North Pacific, Trop = Tropical,
 * South = Southern Hemisphere, Arc = Arctic, Med = Mediterranean,
 * GoM = Gulf of Mexico, NZ = New Zealand, GoCal = Gulf of California.
 */
export const SPECIES_RANGE: Record<string, string[]> = {
  /* Baleen whales */
  right_whale:         ["NAtl"],
  southern_right_whale:["South"],
  humpback:            ["NAtl", "NPac", "South", "Trop"],
  fin_whale:           ["NAtl", "NPac", "Med", "South"],
  blue_whale:          ["NAtl", "NPac", "South"],
  minke_whale:         ["NAtl", "NPac"],
  sei_whale:           ["NAtl", "NPac", "South"],
  gray_whale:          ["NPac"],
  bowhead:             ["Arc"],
  brydes_whale:        ["Trop", "NPac"],
  rices_whale:         ["GoM"],
  omuras_whale:        ["Trop"],
  pygmy_right_whale:   ["South"],
  /* Toothed whales */
  sperm_whale:         ["NAtl", "NPac", "Trop", "South", "Med"],
  beaked_whale:        ["NAtl", "NPac", "South", "Med"],
  narwhal:             ["Arc"],
  beluga:              ["Arc", "NPac"],
  dwarf_sperm_whale:   ["NAtl", "Trop"],
  pygmy_sperm_whale:   ["NAtl", "Trop"],
  /* Dolphins */
  orca:                ["NAtl", "NPac", "South", "Arc"],
  bottlenose_dolphin:  ["NAtl", "NPac", "Trop", "Med"],
  common_dolphin:      ["NAtl", "NPac", "Med"],
  spotted_dolphin:     ["NAtl", "Trop"],
  striped_dolphin:     ["NAtl", "Trop", "Med"],
  whitesided_dolphin:  ["NAtl"],
  rissos_dolphin:      ["NAtl", "NPac", "Med"],
  pilot_whale:         ["NAtl", "NPac", "Med"],
  hectors_dolphin:     ["NZ"],
  /* Porpoises */
  harbor_porpoise:     ["NAtl", "NPac"],
  dalls_porpoise:      ["NPac"],
  vaquita:             ["GoCal"],
};

/** Readable region labels for tooltip/display. */
const REGION_LABELS: Record<string, string> = {
  NAtl: "North Atlantic",
  NPac: "North Pacific",
  Trop: "Tropical",
  South: "Southern Hemisphere",
  Arc: "Arctic",
  Med: "Mediterranean",
  GoM: "Gulf of Mexico",
  NZ: "New Zealand",
  GoCal: "Gulf of California",
};

/**
 * Infer ocean region from lat/lon.
 * Returns region codes matching SPECIES_RANGE keys.
 */
function inferRegion(lat: number, lon: number): string[] {
  const regions: string[] = [];
  // Arctic: > 66°N
  if (lat > 66) regions.push("Arc");
  // Northern Hemisphere ocean basins
  if (lat >= 0 && lat <= 66) {
    if (lon >= -100 && lon <= 0) regions.push("NAtl");
    if (lon >= -180 && lon <= -100) regions.push("NPac");
    if (lon > 0 && lon <= 45) regions.push("NAtl"); // east Atlantic
    if (lon > 100 || lon <= -100) regions.push("NPac"); // west Pacific
  }
  // Mediterranean
  if (lat >= 30 && lat <= 46 && lon >= -6 && lon <= 36) regions.push("Med");
  // Tropical: 23.5°S – 23.5°N
  if (lat >= -23.5 && lat <= 23.5) regions.push("Trop");
  // Gulf of Mexico
  if (lat >= 18 && lat <= 31 && lon >= -98 && lon <= -80) regions.push("GoM");
  // Gulf of California
  if (lat >= 22 && lat <= 32 && lon >= -115 && lon <= -107) regions.push("GoCal");
  // Southern Hemisphere
  if (lat < 0) regions.push("South");
  // New Zealand
  if (lat >= -48 && lat <= -34 && lon >= 166 && lon <= 179) regions.push("NZ");
  // Deduplicate
  return [...new Set(regions)];
}

/** Check if a species is likely present at the given location. */
function speciesLikelyHere(species: string, lat: number, lon: number): boolean {
  const range = SPECIES_RANGE[species];
  if (!range) return true; // unknown range → don't filter out
  const regions = inferRegion(lat, lon);
  return range.some(r => regions.includes(r));
}

/** Friendly labels for species groups. */
export const GROUP_LABEL_OVERRIDES: Record<string, string> = {
  humpback: "Humpback Whale",
  brydes_whale: "Bryde's Whale",
  rices_whale: "Rice's Whale",
  rissos_dolphin: "Risso's Dolphin",
  dalls_porpoise: "Dall's Porpoise",
  hectors_dolphin: "Hector's Dolphin",
  omuras_whale: "Omura's Whale",
  other_dolphin: "Other Dolphins",
  other_porpoise: "Other Porpoises",
  small_sperm_whale: "Small Sperm Whales (Kogia)",
  unid_baleen: "Unidentified Baleen Whale",
  unid_cetacean: "Unidentified Cetacean",
  unid_dolphin: "Unidentified Dolphin",
  unid_rorqual: "Unidentified Rorqual",
  unid_toothed: "Unidentified Toothed Whale",
};

function groupLabel(g: string) {
  return (
    GROUP_LABEL_OVERRIDES[g] ??
    g.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/* ── Types ──────────────────────────────────────────────── */

type WizStep = "start" | "whale-kind" | "result";
type AnimalChoice = "" | "whale" | "dolphin" | "porpoise" | "unsure";
type WhaleChoice = "" | "baleen" | "toothed_whale" | "whale_unsure";

/**
 * `"navigate"` — renders `<Link>` tags to `/report?species=X` (species page).
 * `"callback"` — calls `onSelect(group)` directly (report form inline).
 */
type IDHelperMode =
  | { mode: "navigate" }
  | { mode: "callback"; onSelect: (group: string) => void };

type IDHelperProps = IDHelperMode & {
  /** Optional extra class names on the outer wrapper. */
  className?: string;
  /** Compact styling for embedding inside a form section. */
  compact?: boolean;
  /** Sighting latitude — if provided, species are sorted by geographic likelihood. */
  lat?: number | null;
  /** Sighting longitude — if provided, species are sorted by geographic likelihood. */
  lon?: number | null;
  /** User-uploaded photo data URL — shown as comparison alongside species illustrations. */
  userPhoto?: string | null;
};

/* ── Component ─────────────────────────────────────────── */

export default function IDHelper(props: IDHelperProps) {
  const { compact = false, lat = null, lon = null, userPhoto = null } = props;
  const router = useRouter();
  const [step, setStep] = useState<WizStep>("start");
  const [animal, setAnimal] = useState<AnimalChoice>("");
  const [whaleKind, setWhaleKind] = useState<WhaleChoice>("");
  const [expandedSpecies, setExpandedSpecies] = useState<string | null>(null);
  const [showAnatomy, setShowAnatomy] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTraits, setSelectedTraits] = useState<Set<string>>(new Set());
  const [showTraitFilter, setShowTraitFilter] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  /* ── Region filter ── */
  const [regionFilter, setRegionFilter] = useState<string | null>(
    () => {
      if (lat != null && lon != null) {
        const r = inferRegion(lat, lon);
        return r.length > 0 ? r[0] : null;
      }
      return null;
    },
  );
  const [showAllSpecies, setShowAllSpecies] = useState(false);
  const autoRegions = useMemo(
    () => (lat != null && lon != null ? inferRegion(lat, lon) : []),
    [lat, lon],
  );

  /** When coords are provided the region is locked — user cannot override. */
  const regionLocked = lat != null && lon != null && autoRegions.length > 0;

  /* Keep region in sync when the coords (and thus autoRegions) change */
  useEffect(() => {
    if (regionLocked) {
      setRegionFilter(autoRegions[0]);
      setShowAllSpecies(false);
    }
  }, [regionLocked, autoRegions]);

  /* ── Internal photo upload (navigate mode only) ── */
  const [internalPhoto, setInternalPhoto] = useState<string | null>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const activePhoto = userPhoto ?? internalPhoto;

  const handlePhotoUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setInternalPhoto(dataUrl);
      try { sessionStorage.setItem("idhelper_photo", dataUrl); } catch { /* quota */ }
    };
    reader.readAsDataURL(file);
  }, []);

  const clearInternalPhoto = useCallback(() => {
    setInternalPhoto(null);
    try { sessionStorage.removeItem("idhelper_photo"); } catch { /* noop */ }
    if (photoInputRef.current) photoInputRef.current.value = "";
  }, []);

  function reset() {
    setStep("start");
    setAnimal("");
    setWhaleKind("");
    setExpandedSpecies(null);
    setSearchQuery("");
    setSelectedTraits(new Set());
    setShowTraitFilter(false);
  }

  function pickAnimal(a: AnimalChoice) {
    setAnimal(a);
    setSelectedTraits(new Set());
    if (a === "whale") setStep("whale-kind");
    else setStep("result");
  }

  function pickWhaleKind(k: WhaleChoice) {
    setWhaleKind(k);
    setSelectedTraits(new Set());
    setStep("result");
  }

  function handleSelect(group: string) {
    if (props.mode === "callback") {
      props.onSelect(group);
      reset();
    }
  }

  function toggleTrait(trait: string) {
    setSelectedTraits((prev) => {
      const next = new Set(prev);
      const def = FIELD_TRAITS[trait];
      if (next.has(trait)) {
        next.delete(trait);
      } else {
        // Size is single-select — deselect other sizes
        if (def?.category === "size") {
          for (const t of next) {
            if (FIELD_TRAITS[t]?.category === "size") next.delete(t);
          }
        }
        next.add(trait);
      }
      return next;
    });
  }

  /* Resolve result path */
  const resultKey =
    animal === "whale" ? (whaleKind || "whale_unsure") : animal;
  const rawGroups =
    resultKey === "unsure"
      ? []
      : resultKey === "whale_unsure"
        ? [
            ...WIZARD_GROUPS.baleen,
            ...WIZARD_GROUPS.toothed_whale,
          ]
        : WIZARD_GROUPS[resultKey] ?? [];

  /* Geo-sort: species likely at the sighting location float to top */
  const hasCoords = lat != null && lon != null;
  const likelySet = hasCoords
    ? new Set(rawGroups.filter(g => speciesLikelyHere(g, lat!, lon!)))
    : null;

  /* Region-aware filtering: when a region is selected, filter to species
     that are known in that region. "Show all" overrides the filter. */
  const activeRegions = regionFilter
    ? [regionFilter]
    : autoRegions.length > 0
      ? autoRegions
      : null;

  const regionFilteredGroups = useMemo(() => {
    if (!activeRegions || activeRegions.length === 0) return rawGroups;
    // When locked (coords provided), always filter — no override
    if (!regionLocked && showAllSpecies) return rawGroups;
    return rawGroups.filter((g) => {
      const range = SPECIES_RANGE[g];
      if (!range) return true; // unknown range — keep
      return range.some(r => activeRegions!.includes(r));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawGroups, regionFilter, autoRegions, showAllSpecies, regionLocked]);

  const regionHiddenCount = rawGroups.length - regionFilteredGroups.length;

  /* Available traits in the current species pool (only show relevant pills) */
  const availableTraits = useMemo(() => {
    const s = new Set<string>();
    for (const g of regionFilteredGroups) {
      for (const t of SPECIES_TRAITS[g] ?? []) s.add(t);
    }
    return s;
  }, [regionFilteredGroups]);

  /* Filter by selected observable traits (AND logic) */
  const traitFilteredGroups = useMemo(() => {
    if (selectedTraits.size === 0) return regionFilteredGroups;
    return regionFilteredGroups.filter((g) => {
      const traits = SPECIES_TRAITS[g] ?? [];
      return [...selectedTraits].every((t) => traits.includes(t));
    });
  }, [regionFilteredGroups, selectedTraits]);

  const traitHiddenCount =
    regionFilteredGroups.length - traitFilteredGroups.length;

  const groups = hasCoords
    ? [
        ...traitFilteredGroups.filter(g => likelySet!.has(g)),
        ...traitFilteredGroups.filter(g => !likelySet!.has(g)),
      ]
    : traitFilteredGroups;

  /* Which trait, when removed, unlocks the most species in the current pool */
  const traitBlockers = useMemo(() => {
    if (selectedTraits.size < 2 || traitFilteredGroups.length > 0) return [];
    const candidates: { trait: string; unlocks: number }[] = [];
    for (const t of selectedTraits) {
      const remaining = [...selectedTraits].filter((x) => x !== t);
      const unlocks = regionFilteredGroups.filter((g) => {
        const traits = SPECIES_TRAITS[g] ?? [];
        return remaining.every((r) => traits.includes(r));
      }).length;
      if (unlocks > 0) candidates.push({ trait: t, unlocks });
    }
    return candidates.sort((a, b) => b.unlocks - a.unlocks).slice(0, 2);
  }, [selectedTraits, traitFilteredGroups, regionFilteredGroups]);

  /* Which OTHER wizard-group category best matches the selected traits */
  const altGroupSuggestion = useMemo(() => {
    if (selectedTraits.size === 0 || traitFilteredGroups.length > 0) return null;
    const WIZARD_GROUP_LABELS: Record<string, string> = {
      baleen: "Baleen Whales",
      toothed_whale: "Toothed Whales",
      dolphin: "Dolphins",
      porpoise: "Porpoises",
    };
    const currentKeys = new Set(rawGroups);
    let best: {
      key: string;
      label: string;
      count: number;
      examples: string[];
    } | null = null;
    for (const [key, species] of Object.entries(WIZARD_GROUPS)) {
      if (species.some((s) => currentKeys.has(s))) continue;
      const matches = species.filter((s) => {
        const traits = SPECIES_TRAITS[s] ?? [];
        return [...selectedTraits].every((t) => traits.includes(t));
      });
      if (matches.length > 0 && (!best || matches.length > best.count)) {
        best = {
          key,
          label: WIZARD_GROUP_LABELS[key] ?? key,
          count: matches.length,
          examples: matches.slice(0, 2).map(groupLabel),
        };
      }
    }
    return best;
  }, [selectedTraits, traitFilteredGroups, rawGroups]);

  const catchAll =
    WIZARD_CATCHALL[resultKey] ?? WIZARD_CATCHALL.unsure;

  const stepNum =
    step === "start" ? 1 : step === "whale-kind" ? 2 : 3;

  /* ── All species (flat list for search) ── */
  const allSpecies = useMemo(
    () => Object.values(WIZARD_GROUPS).flat(),
    [],
  );

  /** Filtered species matching the search query. */
  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return allSpecies.filter((g) => {
      const label = groupLabel(g).toLowerCase();
      const tip = (SPECIES_ID_TIPS[g] ?? "").toLowerCase();
      const desc = (SPECIES_DESC[g] ?? "").toLowerCase();
      const range = (SPECIES_RANGE[g] ?? [])
        .map((r) => (REGION_LABELS[r] ?? r).toLowerCase())
        .join(" ");
      return (
        label.includes(q) ||
        g.replace(/_/g, " ").includes(q) ||
        tip.includes(q) ||
        desc.includes(q) ||
        range.includes(q)
      );
    });
  }, [searchQuery, allSpecies]);

  /** Search results filtered by active region. */
  const regionSearchResults = useMemo(() => {
    if (!activeRegions || activeRegions.length === 0) return searchResults;
    if (!regionLocked && showAllSpecies) return searchResults;
    return searchResults.filter((g) => {
      const range = SPECIES_RANGE[g];
      if (!range) return true;
      return range.some((r) => activeRegions!.includes(r));
    });
  }, [searchResults, activeRegions, regionLocked, showAllSpecies]);

  /* ── Species card (compact grid item — click to expand detail below grid) ── */
  function SpeciesCard({ grp }: { grp: string }) {
    const photo = SPECIES_PHOTOS[grp] ?? null;
    const label = groupLabel(grp);
    const tip = SPECIES_ID_TIPS[grp] ?? null;
    const isSelected = expandedSpecies === grp;
    const isLikely = likelySet === null || likelySet.has(grp);
    const range = SPECIES_RANGE[grp];
    const rangeLabel = range?.map(r => REGION_LABELS[r] ?? r).join(", ");

    return (
      <button
        type="button"
        onClick={() => setExpandedSpecies(isSelected ? null : grp)}
        className={`flex w-full items-center gap-2.5 rounded-lg border p-2.5 text-left transition-all ${
          isSelected
            ? "border-ocean-500/50 bg-ocean-900/40 ring-1 ring-ocean-500/30"
            : !isLikely
              ? "border-ocean-800/20 bg-abyss-900/30 opacity-60 hover:opacity-80"
              : "border-ocean-800/30 bg-abyss-900/50 hover:border-ocean-600/40 hover:bg-ocean-900/30"
        }`}
      >
        {photo ? (
          <div className="relative h-10 w-14 shrink-0 overflow-hidden rounded">
            <Image src={`/species/${photo}.jpg`} alt="" fill className="object-cover" sizes="56px" />
          </div>
        ) : (
          <div className="flex h-10 w-14 shrink-0 items-center justify-center rounded bg-ocean-900/40">
            <IconWhale className="h-4 w-4 text-ocean-700" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-xs font-semibold text-slate-200">{label}</p>
            {likelySet && isLikely && (
              <span className="shrink-0 rounded-full bg-teal-500/20 px-1.5 py-px text-[9px] font-medium text-teal-400">
                Likely here
              </span>
            )}
            {likelySet && !isLikely && (
              <span className="shrink-0 rounded-full bg-amber-500/15 px-1.5 py-px text-[9px] font-medium text-amber-500/80">
                Uncommon here
              </span>
            )}
          </div>
          {tip && (
            <p className="mt-0.5 line-clamp-2 text-[10px] leading-snug text-slate-500">
              {tip.replace(/^Look for: /, "")}
            </p>
          )}
          {rangeLabel && (
            <p className="mt-0.5 text-[9px] text-slate-600">
              Range: {rangeLabel}
            </p>
          )}
          {(CONFUSED_WITH[grp]?.length ?? 0) > 0 && (
            <p className="mt-0.5 text-[9px] text-amber-500/70">
              Has look-alikes
            </p>
          )}
        </div>
        <svg
          className={`h-3 w-3 shrink-0 transition-transform ${
            isSelected ? "rotate-90 text-ocean-400" : "text-slate-600"
          }`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    );
  }

  /* ── Expanded species detail panel (renders outside the grid) ── */
  function ExpandedDetail() {
    if (!expandedSpecies) return null;
    const grp = expandedSpecies;
    const photo = SPECIES_PHOTOS[grp] ?? null;
    const label = groupLabel(grp);
    const tip = SPECIES_ID_TIPS[grp] ?? null;
    const desc = SPECIES_DESC[grp] ?? null;

    return (
      <div className="mb-4 overflow-hidden rounded-xl border border-ocean-500/40 bg-ocean-950/40">
        {/* Header bar with collapse */}
        <div className="flex items-center justify-between border-b border-ocean-800/30 px-4 py-2.5">
          <p className="text-sm font-semibold text-slate-200">{label}</p>
          <button
            type="button"
            onClick={() => setExpandedSpecies(null)}
            className="rounded-md px-2 py-1 text-xs text-slate-500 transition hover:bg-ocean-900/40 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>

        <div className="space-y-4 p-4">
          {/* Row 0 (optional): Side-by-side photo comparison */}
          {activePhoto && (
            <div className="rounded-lg border border-ocean-700/30 bg-ocean-950/30 p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ocean-400">
                Compare your photo
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="mb-1 text-center text-[9px] font-medium text-teal-400">Your Photo</p>
                  <div className="relative aspect-[4/3] overflow-hidden rounded-md border border-ocean-700/30 bg-ocean-950/40">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={activePhoto}
                      alt="Your uploaded photo"
                      className="h-full w-full object-contain"
                    />
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-center text-[9px] font-medium text-ocean-400">{label} (reference)</p>
                  <div className="relative aspect-[4/3] overflow-hidden rounded-md border border-ocean-700/30 bg-ocean-950/40">
                    {photo ? (
                      <Image
                        src={`/species/${photo}.jpg`}
                        alt={label}
                        fill
                        className="object-cover"
                        sizes="(max-width: 640px) 50vw, 280px"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <IconWhale className="h-10 w-10 text-ocean-700" />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Row 1: Photo + description side by side */}
          <div className="flex flex-col gap-4 sm:flex-row">
            {/* Photo */}
            {photo ? (
              <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden rounded-lg sm:w-56">
                <Image
                  src={`/species/${photo}.jpg`}
                  alt={label}
                  fill
                  className="object-cover"
                  sizes="(max-width: 640px) 100vw, 224px"
                />
              </div>
            ) : (
              <div className="flex aspect-[4/3] w-full shrink-0 items-center justify-center rounded-lg bg-ocean-900/40 sm:w-56">
                <IconWhale className="h-12 w-12 text-ocean-700" />
              </div>
            )}

            <div className="flex-1 space-y-3">
              {/* Full species description */}
              {desc && (
                <p className="text-xs leading-relaxed text-slate-300">
                  {desc}
                </p>
              )}

              {/* ID tips */}
              {tip && (
                <div className="rounded-md border border-ocean-700/30 bg-ocean-950/30 px-3 py-2">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ocean-400">
                    How to identify
                  </p>
                  <p className="text-[11px] leading-relaxed text-slate-400">
                    {tip}
                  </p>
                </div>
              )}

              {/* Geographic range */}
              {SPECIES_RANGE[grp] && (
                <p className="text-[10px] text-slate-500">
                  <span className="font-medium text-slate-400">Range:</span>{" "}
                  {SPECIES_RANGE[grp].map(r => REGION_LABELS[r] ?? r).join(", ")}
                </p>
              )}
            </div>
          </div>

          {/* Row 1b: Easily mistaken for */}
          {(CONFUSED_WITH[grp]?.length ?? 0) > 0 && (
            <div className="rounded-lg border border-amber-600/20 bg-amber-950/10 p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-amber-400">
                Easily mistaken for
              </p>
              <div className="space-y-2">
                {CONFUSED_WITH[grp].map((pair) => {
                  const pairPhoto = SPECIES_PHOTOS[pair.key] ?? null;
                  const pairLabel = groupLabel(pair.key);
                  return (
                    <button
                      key={pair.key}
                      type="button"
                      onClick={() => setExpandedSpecies(pair.key)}
                      className="flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition hover:bg-amber-900/15"
                    >
                      {/* Mini thumbnail */}
                      <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-md border border-ocean-700/30 bg-ocean-950/40">
                        {pairPhoto ? (
                          <Image
                            src={`/species/${pairPhoto}.jpg`}
                            alt={pairLabel}
                            fill
                            className="object-cover"
                            sizes="40px"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <IconWhale className="h-4 w-4 text-ocean-700" />
                          </div>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <span className="flex items-center gap-1.5">
                          <span className="text-[11px] font-medium text-slate-300">
                            {pairLabel}
                          </span>
                          <span className="shrink-0 rounded-full bg-amber-600/20 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider text-amber-400">
                            Easily mistaken
                          </span>
                        </span>
                        <p className="mt-0.5 text-[10px] leading-snug text-slate-500">
                          {pair.mark}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Row 2: Annotated species illustration — full width */}
          <div className="relative aspect-[3/2] w-full overflow-hidden rounded-lg bg-ocean-950/40">
            <Image
              src={`/wizard/species/${grp}.png`}
              alt={`${label} — annotated identification features`}
              fill
              className="object-contain p-1"
              sizes="(max-width: 640px) 100vw, 600px"
              onError={(e) => {
                /* Fall back to NOAA original if annotated missing */
                const img = e.currentTarget as HTMLImageElement;
                if (!img.src.includes("/noaa/")) {
                  img.src = `/wizard/species/noaa/${grp}.png`;
                } else {
                  (img.parentElement as HTMLElement).style.display = "none";
                }
              }}
            />
            <p className="absolute bottom-1 right-2 text-[8px] text-slate-600">
              Illustration: NOAA Fisheries
            </p>
          </div>

          {/* Row 3 (optional): Reference guide images */}
          {SPECIES_GUIDES[grp] && (
            <div className="space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-ocean-400">
                Reference Guides
              </p>
              {SPECIES_GUIDES[grp].map((guide, i) => (
                <div key={i} className="overflow-hidden rounded-lg border border-ocean-800/30">
                  <p className="bg-ocean-950/60 px-3 py-1.5 text-[10px] font-medium text-slate-400">
                    {guide.caption}
                  </p>
                  <div className="relative aspect-[3/2] w-full bg-ocean-950/40">
                    <Image
                      src={guide.src}
                      alt={guide.alt}
                      fill
                      className="object-contain"
                      sizes="(max-width: 640px) 100vw, 600px"
                    />
                  </div>
                  <p className="bg-ocean-950/60 px-3 py-1 text-[8px] text-slate-600">
                    Source: NOAA Fisheries
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Row 4: Report action button */}
          {props.mode === "navigate" ? (
            <button
              type="button"
              onClick={() => {
                /* Persist user photo so report page can pick it up */
                if (activePhoto) {
                  try { sessionStorage.setItem("idhelper_photo", activePhoto); } catch { /* quota */ }
                }
                router.push(`/report?species=${grp}`);
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-teal-500/40 bg-teal-600/20 px-4 py-2 text-xs font-medium text-teal-300 transition-all hover:bg-teal-600/30"
            >
              <IconWhale className="h-3.5 w-3.5" />
              Report as {label}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => handleSelect(grp)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-teal-500/40 bg-teal-600/20 px-4 py-2 text-xs font-medium text-teal-300 transition-all hover:bg-teal-600/30"
            >
              <IconWhale className="h-3.5 w-3.5" />
              Report as {label}
            </button>
          )}
        </div>
      </div>
    );
  }

  /* ── Catch-all action (link or button) ── */
  function CatchAllAction() {
    const cls =
      "inline-flex items-center gap-1.5 rounded-lg border " +
      "border-amber-600/40 bg-amber-500/10 px-4 py-2 text-xs " +
      "font-medium text-amber-300 transition-all hover:bg-amber-500/20";

    if (props.mode === "navigate") {
      return (
        <button
          type="button"
          onClick={() => {
            if (activePhoto) {
              try { sessionStorage.setItem("idhelper_photo", activePhoto); } catch { /* quota */ }
            }
            router.push(`/report?species=${catchAll.group}`);
          }}
          className={cls}
        >
          <IconWhale className="h-3.5 w-3.5" />
          Report as &ldquo;{catchAll.label}&rdquo;
        </button>
      );
    }
    return (
      <button
        type="button"
        onClick={() => handleSelect(catchAll.group)}
        className={cls}
      >
        <IconWhale className="h-3.5 w-3.5" />
        Select &ldquo;{catchAll.label}&rdquo;
      </button>
    );
  }

  /* ── Back button ── */
  function BackButton({ onClick }: { onClick: () => void }) {
    return (
      <button
        onClick={onClick}
        type="button"
        className="mb-3 flex items-center gap-1 text-xs text-ocean-400 transition hover:text-ocean-300"
      >
        <svg
          className="h-3 w-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Back
      </button>
    );
  }

  /* ── Anatomy primer panel ── single diagram, no tabs ── */
  function AnatomyGuide() {
    return (
      <div className="mb-5 rounded-xl border border-teal-500/30 bg-gradient-to-b from-ocean-950/60 to-ocean-950/40">
        {/* Prominent header — always visible */}
        <button
          type="button"
          onClick={() => setShowAnatomy(!showAnatomy)}
          className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-ocean-900/20"
        >
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-500/20">
              <IconMicroscope className="h-4 w-4 text-teal-400" />
            </div>
            <div>
              <span className="text-sm font-semibold text-teal-300">
                Anatomy Guide
              </span>
              <span className="ml-2 text-[10px] text-slate-500">
                {showAnatomy ? "Click to close" : "Learn the body parts used for identification"}
              </span>
            </div>
          </div>
          <svg
            className={`h-4 w-4 text-teal-400 transition-transform ${showAnatomy ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showAnatomy && (
          <div className="border-t border-ocean-800/30 px-4 pb-4 pt-3">
            {/* Anatomy diagram */}
            <div className="mb-3 overflow-hidden rounded-lg border border-ocean-800/20 bg-ocean-950/40 p-2">
              <div className={`relative ${ANATOMY_DIAGRAM.aspect} w-full`}>
                <Image
                  src={ANATOMY_DIAGRAM.src}
                  alt={ANATOMY_DIAGRAM.alt}
                  fill
                  className="object-contain"
                  sizes="(max-width: 640px) 100vw, 560px"
                  priority
                />
                {/* Labels — diagram is vertically stacked: baleen top, toothed bottom */}
                <span className="absolute left-2 top-1 rounded bg-ocean-950/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-teal-300 backdrop-blur-sm sm:text-xs">
                  Baleen whale
                </span>
                <span className="absolute left-2 top-[50%] rounded bg-ocean-950/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-300 backdrop-blur-sm sm:text-xs">
                  Toothed whale
                </span>
              </div>
              <p className="mt-1.5 text-center text-[8px] text-slate-600">
                {ANATOMY_DIAGRAM.credit}
              </p>
            </div>

            {/* Key terms grid */}
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Key terms
            </p>
            <div className="grid grid-cols-2 gap-x-5 gap-y-2 sm:grid-cols-4">
              {ANATOMY_TERMS.map((t) => (
                <div key={t.term} className="rounded-md bg-ocean-950/30 px-2 py-1.5">
                  <p className="text-[11px] font-semibold text-teal-300">{t.term}</p>
                  <p className="text-[10px] leading-snug text-slate-400">{t.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  /* ── Guidance card sub-component ── */
  function GuidanceCard({ stageKey }: { stageKey: string }) {
    const guidance = STAGE_GUIDANCE[stageKey];
    if (!guidance) return null;

    return (
      <div className="mb-4 rounded-lg border border-ocean-700/30 bg-ocean-950/30 px-4 py-3">
        {/* Stage illustration + optional user photo comparison */}
        <div className="mb-3 flex gap-3">
          {/* User&apos;s photo (if uploaded) */}
          {activePhoto && (
            <div className="relative flex w-1/3 shrink-0 flex-col items-center gap-1.5">
              <p className="text-[9px] font-semibold uppercase tracking-wider text-teal-400">
                Your Photo
              </p>
              <div className="relative aspect-[4/3] w-full overflow-hidden rounded-md border border-ocean-700/30 bg-ocean-950/40">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={activePhoto}
                  alt="Your uploaded photo"
                  className="h-full w-full object-contain"
                />
              </div>
            </div>
          )}
          {/* Stage species comparison illustration */}
          <div className={`w-full overflow-hidden rounded-md bg-ocean-950/40 p-2 ${activePhoto ? "flex-1" : ""}`}>
            <Image
              src={`/wizard/stages/${guidance.imgKey}.png`}
              alt={guidance.title}
              width={1600}
              height={400}
              className="h-auto w-full object-contain"
              sizes="(max-width: 640px) 100vw, 560px"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display =
                  "none";
              }}
            />
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ocean-300">
              {guidance.title}
            </p>
            <ul className="space-y-1">
              {guidance.tips.map((tip, i) => (
                <li
                  key={i}
                  className="text-[11px] leading-relaxed text-slate-400"
                >
                  <span className="mr-1 text-ocean-500">▸</span>
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={
        props.className ??
        (compact
          ? "rounded-xl border border-ocean-800/40 bg-abyss-900/40 p-4"
          : "rounded-2xl border border-ocean-700/30 bg-gradient-to-b " +
            "from-ocean-950/40 to-abyss-900/60 p-6")
      }
    >
      {/* Header + step indicator */}
      <div className={`flex items-center justify-between ${compact ? "mb-4" : "mb-5"}`}>
        <div>
          <h2
            className={`font-bold text-white ${compact ? "text-sm" : "text-lg"}`}
          >
            {compact ? "Not sure what species?" : "What did you see?"}
          </h2>
          <p className="text-xs text-slate-500">
            {compact
              ? "Answer a few quick questions"
              : "Answer a few questions — we\u2019ll help you find the right identification"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {step !== "start" && (
            <button
              onClick={reset}
              type="button"
              className="rounded-md border border-ocean-800/40 px-3 py-1 text-xs text-slate-400 transition hover:bg-ocean-900/30"
            >
              Start over
            </button>
          )}
          {/* Step dots */}
          <div className="flex gap-1.5">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className={`h-1.5 rounded-full transition-all ${
                  n === stepNum
                    ? "w-4 bg-ocean-400"
                    : n < stepNum
                      ? "w-1.5 bg-ocean-600"
                      : "w-1.5 bg-ocean-900"
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Photo upload / compare zone — own upload in navigate mode, or show passed-in photo */}
      {props.mode === "navigate" && !userPhoto && (
        <div className="mb-4">
          <input
            ref={photoInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handlePhotoUpload}
            className="hidden"
          />
          {internalPhoto ? (
            <div className="flex items-center gap-3 rounded-lg border border-teal-700/30 bg-teal-950/20 px-3 py-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={internalPhoto}
                alt="Your photo"
                className="h-12 w-12 shrink-0 rounded-md object-cover"
              />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-teal-300">Your photo loaded</p>
                <p className="text-[10px] text-slate-500">
                  It will appear alongside species illustrations for comparison
                </p>
              </div>
              <button
                type="button"
                onClick={clearInternalPhoto}
                className="shrink-0 rounded-md px-2 py-1 text-[10px] text-slate-500 transition hover:bg-ocean-900/30 hover:text-red-400"
              >
                Remove
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => photoInputRef.current?.click()}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-ocean-700/40 py-2.5 text-xs text-slate-500 transition-colors hover:border-teal-500/40 hover:text-teal-400"
            >
              <IconCamera className="h-3.5 w-3.5" />
              Upload a photo to compare as you identify
            </button>
          )}
        </div>
      )}

      {/* Region filter bar */}
      <div className={`mb-4 rounded-lg border px-3 py-2.5 ${
        regionLocked
          ? "border-teal-700/30 bg-teal-950/15"
          : "border-ocean-800/30 bg-ocean-950/20"
      }`}>
        <div className="flex items-center gap-2">
          <IconPin className={`h-3.5 w-3.5 shrink-0 ${
            regionLocked ? "text-teal-400" : "text-ocean-400"
          }`} />
          <p className="text-[11px] font-medium text-slate-400">
            {regionLocked
              ? <>
                  Region locked to{" "}
                  <span className="text-teal-300">
                    {autoRegions.map(r => REGION_LABELS[r]).join(" / ")}
                  </span>
                  {" "}from your sighting coordinates
                </>
              : autoRegions.length > 0
                ? "Region detected from your location"
                : "Filter species by ocean region"}
          </p>
        </div>
        {!regionLocked && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.entries(REGION_LABELS).map(([code, label]) => {
              const isAuto = autoRegions.includes(code);
              const isActive = regionFilter
                ? regionFilter === code
                : isAuto;
              return (
                <button
                  key={code}
                  type="button"
                  onClick={() => {
                    if (regionFilter === code) {
                      setRegionFilter(null);
                      setShowAllSpecies(false);
                    } else {
                      setRegionFilter(code);
                      setShowAllSpecies(false);
                    }
                  }}
                  className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition-all ${
                    isActive
                      ? "border border-teal-500/50 bg-teal-600/20 text-teal-300"
                      : "border border-ocean-800/40 text-slate-500 hover:border-ocean-600/40 hover:text-slate-300"
                  }`}
                >
                  {label}
                  {isAuto && !regionFilter && (
                    <span className="ml-1 text-[8px] text-teal-500">●</span>
                  )}
                </button>
              );
            })}
            {(regionFilter || autoRegions.length > 0) && (
              <button
                type="button"
                onClick={() => {
                  setRegionFilter(null);
                  setShowAllSpecies(true);
                }}
                className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition-all ${
                  showAllSpecies && !regionFilter
                    ? "border border-amber-500/50 bg-amber-600/15 text-amber-300"
                    : "border border-ocean-800/40 text-slate-500 hover:border-ocean-600/40 hover:text-slate-300"
                }`}
              >
                All regions
              </button>
            )}
          </div>
        )}
      </div>

      {/* Step 1: What type of animal? */}
      {step === "start" && (
        <div>
          {/* Species search — jump directly to a species guide */}
          <div className="mb-4">
            <div className="relative">
              <svg
                className="absolute left-3 top-2.5 h-4 w-4 text-slate-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 103.5 3.5a7.5 7.5 0 0013.15 13.15z"
                />
              </svg>
              <input
                ref={searchRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search species — e.g. humpback, blue whale, orca…"
                className="w-full rounded-lg border border-ocean-800/40 bg-abyss-900/70 py-2 pl-9 pr-8 text-sm text-slate-200 placeholder-slate-600 outline-none ring-ocean-500/30 focus:border-ocean-600/50 focus:ring-2"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery("");
                    setExpandedSpecies(null);
                    searchRef.current?.focus();
                  }}
                  className="absolute right-2.5 top-2.5 text-slate-600 transition hover:text-slate-300"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            {searchQuery && (
              <p className="mt-1.5 text-[11px] text-slate-500">
                {regionSearchResults.length === 0
                  ? "No species match your search"
                  : `${regionSearchResults.length} species match`}
                {regionSearchResults.length < searchResults.length &&
                  ` (${searchResults.length - regionSearchResults.length} outside region)`}
              </p>
            )}
          </div>

          {/* Search results — shown when query is non-empty */}
          {searchQuery.trim() && regionSearchResults.length > 0 && (
            <div className="mb-4">
              <div className="mb-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {regionSearchResults.map((grp) => (
                  <SpeciesCard key={grp} grp={grp} />
                ))}
              </div>
              <ExpandedDetail />
            </div>
          )}

          {/* Normal wizard flow — hidden during active search */}
          {!searchQuery.trim() && (
            <>
          {/* Anatomy primer — collapsible diagram + key terms */}
          <AnatomyGuide />

          {/* Guidance tip card */}
          <GuidanceCard stageKey="start" />

          <div className={`grid gap-3 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
            {(
              [
                {
                  key: "whale" as const,
                  label: "A whale",
                  desc: "Large animal (typically 4–30 m), surfacing to breathe with a visible blow spout. Solitary or in small groups. Includes a few rare smaller toothed whales.",
                  Icon: IconWhale,
                  border: "border-ocean-600/40",
                  hover: "hover:bg-ocean-600/10",
                  accent: "text-ocean-300",
                },
                {
                  key: "dolphin" as const,
                  label: "A dolphin",
                  desc: "Sleek and social (1.5–9 m), often in groups. Curved dorsal fin, beak-like snout. May leap, bow-ride, or approach boats. Includes orca (largest dolphin) and pilot whale.",
                  Icon: IconDolphin,
                  border: "border-teal-600/40",
                  hover: "hover:bg-teal-600/10",
                  accent: "text-teal-300",
                },
                {
                  key: "porpoise" as const,
                  label: "A porpoise",
                  desc: "Small and shy (1.2–2.5 m). Blunt rounded head, no beak. Small triangular fin. Brief rolling surfacings — rarely leaps.",
                  Icon: IconDolphin,
                  border: "border-purple-600/40",
                  hover: "hover:bg-purple-600/10",
                  accent: "text-purple-300",
                },
                {
                  key: "unsure" as const,
                  label: "Not sure",
                  desc: "I saw something but couldn't tell what type. Distant or brief sightings are often impossible to narrow — that's completely fine!",
                  Icon: IconInfo,
                  border: "border-amber-600/40",
                  hover: "hover:bg-amber-600/10",
                  accent: "text-amber-300",
                },
              ] as const
            ).map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => pickAnimal(opt.key)}
                className={`rounded-xl border ${opt.border} p-4 text-left transition-all ${opt.hover}`}
              >
                <opt.Icon
                  className={`mb-2 h-6 w-6 ${opt.accent}`}
                />
                <p className={`text-sm font-semibold ${opt.accent}`}>
                  {opt.label}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                  {opt.desc}
                </p>
              </button>
            ))}
          </div>
            </>
          )}
        </div>
      )}

      {/* Step 2: Whale type */}
      {step === "whale-kind" && (
        <div>
          <BackButton
            onClick={() => {
              setStep("start");
              setAnimal("");
            }}
          />

          {/* ── Baleen vs Toothed visual comparison ── */}
          <div className="mb-5 rounded-xl border border-ocean-700/30 bg-ocean-950/30 p-4">
            <p className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-ocean-300">
              Baleen vs toothed — key differences
            </p>
            <p className="mb-3 text-[11px] text-slate-500">
              Whales split into two fundamental groups. Focus on head shape, blowhole count, and mouth to tell them apart.
            </p>

            {/* User photo — centred above the two columns */}
            {activePhoto && (
              <div className="mb-3 flex flex-col items-center gap-1">
                <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">
                  Your Photo
                </p>
                <div className="relative h-20 w-36 overflow-hidden rounded-lg border border-ocean-700/30 bg-ocean-950/40">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={activePhoto}
                    alt="Your uploaded photo"
                    className="h-full w-full object-contain"
                  />
                </div>
              </div>
            )}

            {/* Two columns: Baleen (teal, left) | Toothed (purple, right) */}
            <div className="grid grid-cols-2 gap-3">
              {/* ── LEFT COLUMN: Baleen ── */}
              <div className="flex flex-col gap-2">
                <p className="text-center text-[10px] font-bold text-teal-300">
                  Baleen whale{" "}
                  <span className="font-normal text-teal-500/60">Mysticeti</span>
                </p>

                {/* Stage illustration — left half (baleen is on the left) */}
                <div className="overflow-hidden rounded-lg border border-teal-600/30 bg-teal-950/20">
                  <Image
                    src="/wizard/stages/stage_whale_kind_comparison.png"
                    alt="Baleen whale — stylised illustration"
                    width={1600}
                    height={400}
                    className="h-auto max-w-none"
                    style={{ width: "200%" }}
                    sizes="(max-width: 640px) 100vw, 560px"
                  />
                </div>

                {/* Anatomy diagram — baleen, pre-tinted teal */}
                <div className="overflow-hidden rounded-lg border border-teal-600/30 bg-teal-950/15">
                  <Image
                    src="/wizard/guides/baleen_anatomy.png"
                    alt="Baleen whale anatomy — double blowhole, baleen plates, ventral pleats"
                    width={1200}
                    height={806}
                    className="h-auto w-full"
                    sizes="(max-width: 640px) 100vw, 560px"
                  />
                </div>

                {/* Distinguishing features */}
                <div className="space-y-1">
                  {BALEEN_CUES.map((c) => (
                    <div
                      key={c.label}
                      className="rounded-md border border-teal-700/20 bg-teal-950/15 px-2.5 py-1.5"
                    >
                      <p className="text-[10px] font-semibold text-teal-300">
                        {c.label}
                      </p>
                      <p className="text-[10px] leading-snug text-slate-400">
                        {c.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── RIGHT COLUMN: Toothed ── */}
              <div className="flex flex-col gap-2">
                <p className="text-center text-[10px] font-bold text-purple-300">
                  Toothed whale{" "}
                  <span className="font-normal text-purple-500/60">Odontoceti</span>
                </p>

                {/* Stage illustration — right half (toothed is on the right) */}
                <div className="overflow-hidden rounded-lg border border-purple-600/30 bg-purple-950/20">
                  <Image
                    src="/wizard/stages/stage_whale_kind_comparison.png"
                    alt="Toothed whale — stylised illustration"
                    width={1600}
                    height={400}
                    className="h-auto max-w-none"
                    style={{ width: "200%", marginLeft: "-100%" }}
                    sizes="(max-width: 640px) 100vw, 560px"
                  />
                </div>

                {/* Anatomy diagram — toothed, pre-tinted purple */}
                <div className="overflow-hidden rounded-lg border border-purple-600/30 bg-purple-950/15">
                  <Image
                    src="/wizard/guides/toothed_anatomy.png"
                    alt="Toothed whale anatomy — single blowhole, teeth, melon, smooth belly"
                    width={1200}
                    height={807}
                    className="h-auto w-full"
                    sizes="(max-width: 640px) 100vw, 560px"
                  />
                </div>

                {/* Distinguishing features */}
                <div className="space-y-1">
                  {TOOTHED_CUES.map((c) => (
                    <div
                      key={c.label}
                      className="rounded-md border border-purple-700/20 bg-purple-950/15 px-2.5 py-1.5"
                    >
                      <p className="text-[10px] font-semibold text-purple-300">
                        {c.label}
                      </p>
                      <p className="text-[10px] leading-snug text-slate-400">
                        {c.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <p className="mt-2 text-center text-[8px] text-slate-600">
              Chris huh, Public Domain, via Wikimedia Commons
            </p>
          </div>

          <p className="mb-3 text-sm font-medium text-slate-300">
            What type of whale?
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {(
              [
                {
                  key: "baleen" as const,
                  label: "Baleen whale",
                  desc: "Two blowholes (wide blow). No teeth — baleen plates hang from upper jaw. Throat grooves (ventral pleats) visible on belly. Broad flat head.",
                  border: "border-teal-600/40",
                  hover: "hover:bg-teal-600/10",
                  accent: "text-teal-300",
                },
                {
                  key: "toothed_whale" as const,
                  label: "Toothed whale",
                  desc: "Single blowhole (forward-angled blow). Visible conical teeth. Smooth belly — no throat grooves. Rounded bulbous head (melon) for echolocation.",
                  border: "border-purple-600/40",
                  hover: "hover:bg-purple-600/10",
                  accent: "text-purple-300",
                },
                {
                  key: "whale_unsure" as const,
                  label: "Not sure",
                  desc: "I saw a large whale but couldn't tell if it was baleen or toothed. Distant sightings often can't distinguish — we'll show all whale species.",
                  border: "border-amber-600/40",
                  hover: "hover:bg-amber-600/10",
                  accent: "text-amber-300",
                },
              ] as const
            ).map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => pickWhaleKind(opt.key)}
                className={`rounded-xl border ${opt.border} p-4 text-left transition-all ${opt.hover}`}
              >
                <p
                  className={`text-sm font-semibold ${opt.accent}`}
                >
                  {opt.label}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                  {opt.desc}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Results */}
      {step === "result" && (
        <div>
          <BackButton
            onClick={() => {
              setSelectedTraits(new Set());
              if (animal === "whale" && whaleKind) {
                setWhaleKind("");
                setStep("whale-kind");
              } else reset();
            }}
          />

          {/* Guidance for this category */}
          {resultKey !== "unsure" && resultKey !== "whale_unsure" && (
            <GuidanceCard stageKey={resultKey} />
          )}

          {/* ── Narrow by field observations ── */}
          {rawGroups.length > 0 && (
            <div className="mb-4 rounded-xl border border-ocean-800/40 bg-ocean-950/30">
              <button
                type="button"
                onClick={() => setShowTraitFilter((v) => !v)}
                className="flex w-full items-center justify-between px-4 py-2.5 text-left transition hover:bg-ocean-900/20"
              >
                <div className="flex items-center gap-2">
                  <svg
                    className="h-4 w-4 text-ocean-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
                    />
                  </svg>
                  <span className="text-xs font-semibold text-slate-300">
                    Narrow by features
                  </span>
                  {selectedTraits.size > 0 && (
                    <span className="rounded-full bg-teal-600/30 px-2 py-0.5 text-[10px] font-medium text-teal-300">
                      {selectedTraits.size} active
                    </span>
                  )}
                </div>
                <svg
                  className={`h-4 w-4 text-slate-500 transition-transform ${
                    showTraitFilter ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>
              {showTraitFilter && (
                <div className="space-y-3 border-t border-ocean-800/30 px-4 pb-4 pt-3">
                  <p className="text-[11px] text-slate-500">
                    Click features you observed &mdash; species that
                    don&apos;t match will be filtered out.
                  </p>
                  {selectedTraits.size > 0 && (
                    <div className="flex items-center justify-between">
                      <p className="text-[11px] text-teal-400">
                        {groups.length} of{" "}
                        {regionFilteredGroups.length} species match
                        {traitHiddenCount > 0 && (
                          <span className="text-slate-500">
                            {" "}&middot; {traitHiddenCount} filtered out
                          </span>
                        )}
                      </p>
                      <button
                        type="button"
                        onClick={() => setSelectedTraits(new Set())}
                        className="text-[10px] text-slate-500 transition hover:text-red-400"
                      >
                        Clear all
                      </button>
                    </div>
                  )}
                  {(
                    ["size", "behavior", "feature", "blow"] as const
                  ).map((cat) => {
                    const traits = Object.entries(FIELD_TRAITS).filter(
                      ([k, d]) =>
                        d.category === cat && availableTraits.has(k),
                    );
                    if (traits.length === 0) return null;
                    return (
                      <div key={cat}>
                        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                          {TRAIT_CATEGORY_LABELS[cat]}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {traits.map(([key, def]) => {
                            const active = selectedTraits.has(key);
                            return (
                              <button
                                key={key}
                                type="button"
                                onClick={() => toggleTrait(key)}
                                className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition-all ${
                                  active
                                    ? "border border-teal-500/60 bg-teal-600/25 text-teal-300"
                                    : "border border-ocean-800/40 text-slate-500 hover:border-ocean-600/40 hover:text-slate-300"
                                }`}
                              >
                                {def.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* No species match all selected traits */}
          {groups.length === 0 &&
            selectedTraits.size > 0 &&
            rawGroups.length > 0 && (
              <div className="mb-4 rounded-xl border border-amber-700/20 bg-amber-950/10 p-4">
                <p className="text-sm font-medium text-amber-300">
                  No species match all selected features
                </p>

                {/* Suggest switching to a different animal category */}
                {altGroupSuggestion && (
                  <div className="mt-2.5 rounded-lg border border-sky-800/25
                    bg-sky-950/25 p-2.5">
                    <p className="text-[11px] leading-relaxed text-sky-300">
                      <span className="font-semibold">
                        {altGroupSuggestion.label}
                      </span>{" "}
                      {altGroupSuggestion.count === 1
                        ? "has 1 species"
                        : `has ${altGroupSuggestion.count} species`}{" "}
                      that match
                      {altGroupSuggestion.examples.length > 0 && (
                        <span className="text-slate-400">
                          {" — "}{altGroupSuggestion.examples.join(", ")}
                        </span>
                      )}
                      . Try going back and selecting a different animal type.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setExpandedSpecies(null);
                        if (
                          altGroupSuggestion.key === "baleen" ||
                          altGroupSuggestion.key === "toothed_whale"
                        ) {
                          setAnimal("whale");
                          setWhaleKind(altGroupSuggestion.key);
                        } else {
                          setAnimal(altGroupSuggestion.key as AnimalChoice);
                          setWhaleKind("");
                        }
                        setStep("result");
                      }}
                      className="mt-2 rounded-md border border-sky-700/40
                        bg-sky-900/25 px-2.5 py-1 text-[10px] font-semibold
                        text-sky-300 transition hover:border-sky-600/50
                        hover:bg-sky-900/35 hover:text-sky-200"
                    >
                      Go to {altGroupSuggestion.label}
                    </button>
                  </div>
                )}

                {/* Suggest removing the single blocking trait */}
                {traitBlockers.length > 0 && (
                  <div className="mt-2.5">
                    <p className="mb-1.5 text-[10px] font-semibold uppercase
                      tracking-wider text-slate-500">
                      Removing one of these would reveal species
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {traitBlockers.map(({ trait, unlocks }) => (
                        <button
                          key={trait}
                          type="button"
                          onClick={() => toggleTrait(trait)}
                          className="flex items-center gap-1.5 rounded-full
                            border border-amber-700/40 bg-amber-950/20 px-2.5
                            py-1 text-[10px] font-medium text-amber-400
                            transition hover:bg-amber-900/30
                            hover:text-amber-300"
                        >
                          <svg
                            className="h-2.5 w-2.5 shrink-0"
                            viewBox="0 0 10 10"
                            fill="currentColor"
                          >
                            <path d="M1.5 1.5 8.5 8.5M8.5 1.5 1.5 8.5"
                              stroke="currentColor" strokeWidth="1.5"
                              strokeLinecap="round"
                            />
                          </svg>
                          <span>
                            {FIELD_TRAITS[trait]?.label}
                          </span>
                          <span className="text-amber-600">
                            → {unlocks}{" "}
                            {unlocks === 1 ? "species" : "species"}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Fallback when no specific hint is available */}
                {!altGroupSuggestion && traitBlockers.length === 0 && (
                  <p className="mt-1.5 text-xs text-slate-500">
                    Try removing some filters to see more species.
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => setSelectedTraits(new Set())}
                  className="mt-2.5 text-xs font-medium text-teal-400
                    transition hover:text-teal-300"
                >
                  Clear all filters
                </button>
              </div>
            )}

          {/* Species grid */}
          {groups.length > 0 && (
            <>
              <p className="mb-1 text-sm font-medium text-slate-300">
                Do any of these match what you saw?
              </p>
              {regionHiddenCount > 0 && !showAllSpecies && (
                <div className="mb-3 flex items-center gap-2 rounded-md border border-teal-700/20 bg-teal-950/15 px-3 py-1.5">
                  <IconPin className="h-3 w-3 shrink-0 text-teal-500" />
                  <p className="flex-1 text-[11px] text-teal-400/80">
                    Showing {groups.length} species found in{" "}
                    <span className="font-medium text-teal-300">
                      {regionFilter
                        ? REGION_LABELS[regionFilter]
                        : autoRegions.map(r => REGION_LABELS[r]).join(" / ")}
                    </span>
                    {" "}&middot; {regionHiddenCount} filtered out
                  </p>
                  {!regionLocked && (
                    <button
                      type="button"
                      onClick={() => setShowAllSpecies(true)}
                      className="shrink-0 text-[10px] font-medium text-ocean-400 transition hover:text-ocean-300"
                    >
                      Show all {rawGroups.length}
                    </button>
                  )}
                </div>
              )}
              {showAllSpecies && regionHiddenCount > 0 && !regionLocked && (
                <div className="mb-3 flex items-center gap-2 rounded-md border border-amber-700/20 bg-amber-950/10 px-3 py-1.5">
                  <p className="flex-1 text-[11px] text-amber-400/80">
                    Showing all {groups.length} species (region filter off)
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowAllSpecies(false)}
                    className="shrink-0 text-[10px] font-medium text-ocean-400 transition hover:text-ocean-300"
                  >
                    Filter by region
                  </button>
                </div>
              )}
              {hasCoords && likelySet && likelySet.size > 0 && likelySet.size < groups.length && !regionFilter && (
                <p className="mb-3 text-[11px] text-slate-500">
                  Sorted by likelihood at your sighting location.
                  Species marked <span className="text-teal-400">Likely here</span> are
                  known in this ocean region.
                </p>
              )}
              {!hasCoords && !regionFilter && (
                <p className="mb-3 text-[11px] text-slate-500">
                  Select a region above or add your sighting location to narrow species.
                </p>
              )}
              <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {groups.map((grp) => (
                  <SpeciesCard key={grp} grp={grp} />
                ))}
              </div>
              {/* Full-width expanded detail panel (outside grid) */}
              <ExpandedDetail />
            </>
          )}

          {/* Catch-all — prominent */}
          <div className="rounded-xl border border-amber-700/30 bg-amber-900/10 p-4">
            <p className="mb-1 text-sm font-semibold text-amber-300">
              {animal === "unsure"
                ? "No problem — your sighting is still valuable"
                : "None of these match?"}
            </p>
            <p className="mb-3 text-xs leading-relaxed text-slate-400">
              {catchAll.desc}
            </p>
            <CatchAllAction />
          </div>
        </div>
      )}
    </div>
  );
}
