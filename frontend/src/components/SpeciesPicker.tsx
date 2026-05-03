"use client";

import { useState, useRef, useMemo, useCallback, useEffect } from "react";
import Image from "next/image";
import { API_BASE } from "@/lib/config";
import {
  IconWhale,
  IconWarning,
  IconCamera,
  IconMicrophone,
} from "@/components/icons/MarineIcons";

/* ── Types ───────────────────────────────────────────────── */

export interface SpeciesSelection {
  /** species_group or scientific_name key sent to backend */
  value: string;
  /** Human-readable display label */
  label: string;
  /** Taxonomic rank of the selection */
  rank: "order" | "suborder" | "family" | "genus" | "species";
  /** Family name (empty for higher ranks) */
  family: string;
  /** Scientific name of the selected taxon */
  scientificName: string;
}

interface CrosswalkRow {
  scientific_name: string;
  common_name: string;
  species_group: string;
  taxonomic_rank: string;
  family: string;
  is_baleen: boolean;
}

interface TreeNode {
  key: string;
  label: string;
  scientificName: string;
  rank: "order" | "suborder" | "family" | "species";
  family: string;
  isBaleen: boolean;
  /** species_group value to set when selected */
  selectValue: string;
  photo: string | null;
  desc: string | null;
  children: TreeNode[];
  speciesCount: number;
}

/* ── ML model coverage sets ──────────────────────────────── */

const PHOTO_CLASSIFIABLE = new Set([
  "right_whale", "humpback", "fin_whale", "blue_whale",
  "minke_whale", "sei_whale", "orca",
]);
const AUDIO_CLASSIFIABLE = new Set([
  "right_whale", "humpback", "fin_whale", "blue_whale",
  "sperm_whale", "minke_whale", "sei_whale", "orca",
]);
const SDM_MODELLED = new Set([
  "right_whale", "humpback", "fin_whale", "blue_whale",
  "sperm_whale", "minke_whale",
]);
const ISDM_MODELLED = new Set([
  "humpback", "fin_whale", "blue_whale", "sperm_whale",
]);

/* ── Photo + description lookup ──────────────────────────── */

export const SPECIES_PHOTOS: Record<string, string> = {
  right_whale: "right_whale",
  southern_right_whale: "right_whale",
  humpback: "humpback_whale",
  fin_whale: "fin_whale",
  blue_whale: "blue_whale",
  sperm_whale: "sperm_whale",
  minke_whale: "minke_whale",
  sei_whale: "sei_whale",
  orca: "orca",
  gray_whale: "gray_whale",
  bowhead: "bowhead",
  brydes_whale: "brydes_whale",
  bottlenose_dolphin: "bottlenose_dolphin",
  common_dolphin: "common_dolphin",
  spotted_dolphin: "spotted_dolphin",
  striped_dolphin: "striped_dolphin",
  whitesided_dolphin: "whitesided_dolphin",
  rissos_dolphin: "rissos_dolphin",
  pilot_whale: "pilot_whale",
  beluga: "beluga",
  beaked_whale: "beaked_whale",
  harbor_porpoise: "harbor_porpoise",
  dalls_porpoise: "dalls_porpoise",
  vaquita: "vaquita",
  dwarf_sperm_whale: "dwarf_sperm_whales",
  pygmy_sperm_whale: "dwarf_sperm_whales",
  small_sperm_whale: "dwarf_sperm_whales",
};

export const SPECIES_DESC: Record<string, string> = {
  right_whale: "Stocky, dark body with no dorsal fin. White callosities on the head. V-shaped blow. Critically endangered (~350 remaining).",
  southern_right_whale: "Large, rotund. Callosities on head. No dorsal fin. Southern Hemisphere counterpart of the North Atlantic right whale.",
  humpback: "Long pectoral fins, knobby head. Unique black-and-white fluke pattern. Known for breaching and complex songs.",
  fin_whale: "Second-largest animal on Earth. Asymmetric jaw colouring (white on right). Tall, columnar blow. Fast swimmer.",
  blue_whale: "Largest animal ever. Mottled blue-grey skin, tiny dorsal fin set far back. U-shaped head. Endangered.",
  sperm_whale: "Massive square head (~1/3 of body). Wrinkled skin, left-angled blow. Deep diver. Largest toothed predator.",
  minke_whale: "Smallest rorqual (7–10 m). Pointed snout, white flipper bands. Curious — often approaches boats.",
  sei_whale: "Sleek, dark grey. Single prominent ridge on head. Tall sickle dorsal fin. One of the fastest whales.",
  orca: "Black and white with tall dorsal fin. Saddle patch behind dorsal. Travels in tight family pods.",
  gray_whale: "Mottled grey with barnacles and whale lice. No dorsal fin — low dorsal hump followed by knuckles. Heart-shaped blow.",
  bowhead: "Massive triangular head (~40% of body). No dorsal fin. Thick blubber layer. Arctic specialist.",
  brydes_whale: "Three parallel ridges on head (unique among rorquals). Tropical, does not migrate to polar waters.",
  omuras_whale: "Recently described (2003). Small rorqual with asymmetric jaw like fin whale. Tropical waters. Rarely observed.",
  rices_whale: "Critically endangered Gulf of Mexico endemic (~50 remaining). Formerly classified as Bryde's whale. Described 2021.",
  pygmy_right_whale: "Smallest baleen whale (~6 m). Arched jawline. Southern Hemisphere only. Rarely seen — few confirmed sightings.",
  pygmy_sperm_whale: "Small, shark-like profile. Bracket-shaped mark behind eye ('false gill'). Slow, often seen floating at the surface.",
  dwarf_sperm_whale: "Smallest whale species (~2.7 m). Similar to pygmy sperm whale but smaller with taller dorsal fin. Deep water.",
  beaked_whale: "Elongated beak, small dorsal fin set far back. Deep diver. Rarely seen — often scarred from conspecific teeth.",
  bottlenose_dolphin: "Robust grey dolphin with a short, stubby beak. Very social. Commonly seen nearshore.",
  common_dolphin: "Hourglass colour pattern on flanks (yellow/tan and grey). Often in large fast-moving pods.",
  spotted_dolphin: "Born unspotted; develops increasing spots with age. Athletic, often seen bow-riding.",
  striped_dolphin: "Dark lateral stripe from eye to flipper. Acrobatic leaper. Warm-temperate and tropical oceans.",
  whitesided_dolphin: "White and yellow lateral patches. Robust body. North Atlantic. Forms large pods.",
  rissos_dolphin: "Blunt head, no beak. Heavily scarred grey body that whitens with age. Deep-water squid specialist.",
  pilot_whale: "Bulbous head, sickle-shaped dorsal fin. Dark grey/black. Travels in tight social groups.",
  hectors_dolphin: "One of the world's smallest dolphins. Rounded black dorsal fin. Endemic to New Zealand. Critically endangered.",
  other_dolphin: "Unidentified or less common dolphin species. Many oceanic dolphins are difficult to distinguish at sea.",
  beluga: "All-white adult. Rounded head with flexible neck. No dorsal fin. Arctic and subarctic waters.",
  narwhal: "Male has a long spiral tusk (elongated canine). Mottled grey. Arctic specialist. Travels in groups along ice edges.",
  harbor_porpoise: "Small, shy. Rounded head with no beak. Small triangular dorsal fin. Coastal waters.",
  dalls_porpoise: "Stocky black-and-white body. Creates a rooster-tail spray when swimming fast. North Pacific.",
  vaquita: "World's rarest marine mammal (<10 remaining). Dark eye rings and lip patches. Gulf of California endemic.",
  other_porpoise: "Unidentified or less common porpoise species. Small, shy cetaceans with brief surfacings.",
};

const FAMILY_DESC: Record<string, string> = {
  Balaenidae: "Right whales and bowhead. Stocky, slow-moving filter feeders with no dorsal fin.",
  Balaenopteridae: "Rorquals: the largest baleen whale family. Throat grooves expand during lunge feeding.",
  Eschrichtiidae: "Gray whale family. Longest mammalian migration. Unique bottom-feeding behaviour.",
  Neobalaenidae: "Pygmy right whale. Smallest, most cryptic baleen whale. Southern Hemisphere only.",
  Delphinidae: "Oceanic dolphins: largest and most diverse cetacean family (35+ species).",
  Phocoenidae: "Porpoises: small, stocky cetaceans with spade-shaped teeth. Generally shy.",
  Physeteridae: "Sperm whale: largest toothed predator. Dives to 2,000+ m depth.",
  Kogiidae: "Pygmy and dwarf sperm whales. Small, deep-diving, rarely seen alive.",
  Ziphiidae: "Beaked whales: most species-rich cetacean family. Extreme deep-divers.",
  Monodontidae: "Narwhals and belugas. Arctic specialists with no dorsal fin.",
  Iniidae: "River dolphins: freshwater dolphins of South America.",
  Platanistidae: "South Asian river dolphins. Nearly blind, navigate by echolocation.",
  Pontoporiidae: "Franciscana: small coastal dolphin of South America.",
};

const FAMILY_PHOTOS: Record<string, string> = {
  Balaenidae: "right_whale",
  Balaenopteridae: "humpback_whale",
  Eschrichtiidae: "gray_whale",
  Neobalaenidae: "bowhead",
  Delphinidae: "orca",
  Phocoenidae: "harbor_porpoise",
  Physeteridae: "sperm_whale",
  Kogiidae: "dwarf_sperm_whales",
  Ziphiidae: "beaked_whale",
  Monodontidae: "beluga",
};

/* ── Baleen families ─────────────────────────────────────── */

const BALEEN_FAMILIES = new Set([
  "Balaenidae", "Balaenopteridae", "Eschrichtiidae", "Neobalaenidae",
]);

/* ── Fallback flat list ──────────────────────────────────── */

interface FlatOption {
  value: string;
  label: string;
  family: string;
  rank: "order" | "suborder" | "family" | "genus" | "species";
  scientificName: string;
}

const FALLBACK_FLAT: FlatOption[] = [
  { value: "", label: "Not sure / Unknown", family: "", rank: "order", scientificName: "Cetacea" },
  { value: "right_whale", label: "Right Whale (Eubalaena glacialis)", family: "Balaenidae", rank: "species", scientificName: "Eubalaena glacialis" },
  { value: "humpback", label: "Humpback Whale (Megaptera novaeangliae)", family: "Balaenopteridae", rank: "species", scientificName: "Megaptera novaeangliae" },
  { value: "fin_whale", label: "Fin Whale (Balaenoptera physalus)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera physalus" },
  { value: "blue_whale", label: "Blue Whale (Balaenoptera musculus)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera musculus" },
  { value: "sperm_whale", label: "Sperm Whale (Physeter macrocephalus)", family: "Physeteridae", rank: "species", scientificName: "Physeter macrocephalus" },
  { value: "minke_whale", label: "Minke Whale (Balaenoptera acutorostrata)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera acutorostrata" },
  { value: "sei_whale", label: "Sei Whale (Balaenoptera borealis)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera borealis" },
  { value: "orca", label: "Killer Whale (Orcinus orca)", family: "Delphinidae", rank: "species", scientificName: "Orcinus orca" },
  { value: "gray_whale", label: "Gray Whale (Eschrichtius robustus)", family: "Eschrichtiidae", rank: "species", scientificName: "Eschrichtius robustus" },
  { value: "bowhead", label: "Bowhead Whale (Balaena mysticetus)", family: "Balaenidae", rank: "species", scientificName: "Balaena mysticetus" },
  { value: "brydes_whale", label: "Bryde's Whale (Balaenoptera edeni)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera edeni" },
  { value: "omuras_whale", label: "Omura's Whale (Balaenoptera omurai)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera omurai" },
  { value: "rices_whale", label: "Rice's Whale (Balaenoptera ricei)", family: "Balaenopteridae", rank: "species", scientificName: "Balaenoptera ricei" },
  { value: "bottlenose_dolphin", label: "Bottlenose Dolphin (Tursiops truncatus)", family: "Delphinidae", rank: "species", scientificName: "Tursiops truncatus" },
  { value: "common_dolphin", label: "Common Dolphin (Delphinus delphis)", family: "Delphinidae", rank: "species", scientificName: "Delphinus delphis" },
  { value: "spotted_dolphin", label: "Spotted Dolphin (Stenella frontalis)", family: "Delphinidae", rank: "species", scientificName: "Stenella frontalis" },
  { value: "striped_dolphin", label: "Striped Dolphin (Stenella coeruleoalba)", family: "Delphinidae", rank: "species", scientificName: "Stenella coeruleoalba" },
  { value: "whitesided_dolphin", label: "White-sided Dolphin (Lagenorhynchus acutus)", family: "Delphinidae", rank: "species", scientificName: "Lagenorhynchus acutus" },
  { value: "rissos_dolphin", label: "Risso's Dolphin (Grampus griseus)", family: "Delphinidae", rank: "species", scientificName: "Grampus griseus" },
  { value: "pilot_whale", label: "Pilot Whale (Globicephala melas)", family: "Delphinidae", rank: "species", scientificName: "Globicephala melas" },
  { value: "harbor_porpoise", label: "Harbor Porpoise (Phocoena phocoena)", family: "Phocoenidae", rank: "species", scientificName: "Phocoena phocoena" },
  { value: "dalls_porpoise", label: "Dall's Porpoise (Phocoenoides dalli)", family: "Phocoenidae", rank: "species", scientificName: "Phocoenoides dalli" },
  { value: "vaquita", label: "Vaquita (Phocoena sinus)", family: "Phocoenidae", rank: "species", scientificName: "Phocoena sinus" },
  { value: "beluga", label: "Beluga (Delphinapterus leucas)", family: "Monodontidae", rank: "species", scientificName: "Delphinapterus leucas" },
  { value: "narwhal", label: "Narwhal (Monodon monoceros)", family: "Monodontidae", rank: "species", scientificName: "Monodon monoceros" },
  { value: "beaked_whale", label: "Beaked Whale (Ziphius cavirostris)", family: "Ziphiidae", rank: "species", scientificName: "Ziphius cavirostris" },
  { value: "dwarf_sperm_whale", label: "Dwarf Sperm Whale (Kogia sima)", family: "Kogiidae", rank: "species", scientificName: "Kogia sima" },
  { value: "pygmy_sperm_whale", label: "Pygmy Sperm Whale (Kogia breviceps)", family: "Kogiidae", rank: "species", scientificName: "Kogia breviceps" },
  { value: "pygmy_right_whale", label: "Pygmy Right Whale (Caperea marginata)", family: "Neobalaenidae", rank: "species", scientificName: "Caperea marginata" },
  { value: "southern_right_whale", label: "Southern Right Whale (Eubalaena australis)", family: "Balaenidae", rank: "species", scientificName: "Eubalaena australis" },
  { value: "hectors_dolphin", label: "Hector's Dolphin (Cephalorhynchus hectori)", family: "Delphinidae", rank: "species", scientificName: "Cephalorhynchus hectori" },
  { value: "other_dolphin", label: "Other Dolphin", family: "Delphinidae", rank: "species", scientificName: "" },
  { value: "other_porpoise", label: "Other Porpoise", family: "Phocoenidae", rank: "species", scientificName: "" },
  { value: "unid_cetacean", label: "Unknown Cetacean", family: "", rank: "order", scientificName: "Cetacea" },
  { value: "unid_baleen", label: "Unidentified Baleen Whale", family: "", rank: "suborder", scientificName: "Mysticeti" },
  { value: "unid_toothed", label: "Unidentified Toothed Whale", family: "", rank: "suborder", scientificName: "Odontoceti" },
  { value: "unid_dolphin", label: "Unidentified Dolphin", family: "Delphinidae", rank: "family", scientificName: "Delphinidae" },
  { value: "unid_rorqual", label: "Unidentified Rorqual", family: "Balaenopteridae", rank: "family", scientificName: "Balaenopteridae" },
];

/** Look up species selection metadata by group key. */
export function lookupSpeciesGroup(
  group: string,
): { rank: string; scientificName: string } | null {
  const entry = FALLBACK_FLAT.find((o) => o.value === group);
  if (!entry) return null;
  return { rank: entry.rank, scientificName: entry.scientificName };
}

/* ── Tree building from crosswalk ────────────────────────── */

function buildTree(rows: CrosswalkRow[]): TreeNode {
  // Group by rank
  const byRank = (r: string) => rows.filter((row) => row.taxonomic_rank === r);
  const suborders = byRank("suborder");
  const families = byRank("family");
  const species = byRank("species");

  // Group species by family
  const speciesByFamily = new Map<string, CrosswalkRow[]>();
  for (const sp of species) {
    const fam = sp.family || "Unknown";
    if (!speciesByFamily.has(fam)) speciesByFamily.set(fam, []);
    speciesByFamily.get(fam)!.push(sp);
  }

  // Deduplicate species by species_group (keep first / most common name)
  function dedupeSpecies(spp: CrosswalkRow[]): CrosswalkRow[] {
    const seen = new Map<string, CrosswalkRow>();
    for (const sp of spp) {
      const key = sp.species_group;
      if (!seen.has(key)) seen.set(key, sp);
    }
    return Array.from(seen.values());
  }

  // Build species nodes
  function makeSpeciesNode(sp: CrosswalkRow): TreeNode {
    const grp = sp.species_group;
    return {
      key: `sp-${sp.scientific_name}`,
      label: sp.common_name,
      scientificName: sp.scientific_name,
      rank: "species",
      family: sp.family,
      isBaleen: sp.is_baleen,
      selectValue: grp,
      photo: SPECIES_PHOTOS[grp] ?? null,
      desc: SPECIES_DESC[grp] ?? null,
      children: [],
      speciesCount: 1,
    };
  }

  // Build family nodes
  function makeFamilyNode(fam: string, familyRow: CrosswalkRow | undefined): TreeNode {
    const spp = dedupeSpecies(speciesByFamily.get(fam) ?? []);
    spp.sort((a, b) => a.common_name.localeCompare(b.common_name));
    const children = spp.map(makeSpeciesNode);
    return {
      key: `fam-${fam}`,
      label: fam,
      scientificName: fam,
      rank: "family",
      family: fam,
      isBaleen: BALEEN_FAMILIES.has(fam),
      selectValue: familyRow?.species_group ?? fam.toLowerCase(),
      photo: FAMILY_PHOTOS[fam] ?? null,
      desc: FAMILY_DESC[fam] ?? null,
      children,
      speciesCount: children.length,
    };
  }

  // Build suborder nodes
  const familyRows = new Map(families.map((f) => [f.family || f.common_name, f]));
  const allFamilyNames = new Set([
    ...families.map((f) => f.family || f.scientific_name),
    ...species.map((s) => s.family).filter(Boolean),
  ]);

  // Partition families into suborders
  const baleenFams = new Set<string>();
  const toothedFams = new Set<string>();
  for (const fam of allFamilyNames) {
    if (BALEEN_FAMILIES.has(fam)) baleenFams.add(fam);
    else toothedFams.add(fam);
  }

  function makeSuborderNode(
    label: string,
    scientificName: string,
    isBaleen: boolean,
    suborderRow: CrosswalkRow | undefined,
    fams: Set<string>,
  ): TreeNode {
    const sortedFams = Array.from(fams).sort();
    const children = sortedFams.map((f) => makeFamilyNode(f, familyRows.get(f)));
    return {
      key: `sub-${scientificName}`,
      label,
      scientificName,
      rank: "suborder",
      family: "",
      isBaleen,
      selectValue: suborderRow?.species_group ?? (isBaleen ? "unid_baleen" : "unid_toothed"),
      photo: null,
      desc: isBaleen
        ? "Baleen whales: filter feeders with baleen plates instead of teeth."
        : "Toothed whales: echolocating predators including dolphins and porpoises.",
      children,
      speciesCount: children.reduce((n, c) => n + c.speciesCount, 0),
    };
  }

  const mysticeti = suborders.find((s) => s.scientific_name === "Mysticeti");
  const odontoceti = suborders.find((s) => s.scientific_name === "Odontoceti");

  return {
    key: "order-Cetacea",
    label: "Cetacea",
    scientificName: "Cetacea",
    rank: "order",
    family: "",
    isBaleen: false,
    selectValue: "unid_cetacean",
    photo: null,
    desc: "All whales, dolphins, and porpoises.",
    children: [
      makeSuborderNode("Baleen Whales", "Mysticeti", true, mysticeti, baleenFams),
      makeSuborderNode("Toothed Whales", "Odontoceti", false, odontoceti, toothedFams),
    ],
    speciesCount: species.length,
  };
}

/* ── Flat list from crosswalk ────────────────────────────── */

function buildFlatList(rows: CrosswalkRow[]): FlatOption[] {
  // Include all ranks: families + species (deduped by species_group)
  const result: FlatOption[] = [
    { value: "", label: "Not sure / Unknown", family: "", rank: "order", scientificName: "Cetacea" },
  ];

  // Add suborders
  for (const row of rows.filter((r) => r.taxonomic_rank === "suborder")) {
    result.push({
      value: row.species_group,
      label: `${row.common_name} (${row.scientific_name})`,
      family: "",
      rank: "suborder",
      scientificName: row.scientific_name,
    });
  }

  // Add families
  for (const row of rows.filter((r) => r.taxonomic_rank === "family")) {
    result.push({
      value: row.species_group,
      label: `${row.common_name} — ${row.family}`,
      family: row.family,
      rank: "family",
      scientificName: row.scientific_name,
    });
  }

  // Add species (deduped by species_group)
  const seen = new Set<string>();
  for (const row of rows.filter((r) => r.taxonomic_rank === "species")) {
    const key = row.species_group;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push({
      value: key,
      label: `${row.common_name} (${row.scientific_name})`,
      family: row.family,
      rank: "species",
      scientificName: row.scientific_name,
    });
  }

  result.sort((a, b) => {
    if (!a.value) return -1;
    if (!b.value) return 1;
    const rankOrder = { order: 0, suborder: 1, family: 2, genus: 3, species: 4 };
    const ra = rankOrder[a.rank] ?? 9;
    const rb = rankOrder[b.rank] ?? 9;
    if (ra !== rb) return ra - rb;
    return a.label.localeCompare(b.label);
  });

  return result;
}

/* ── Rank labels & badges ────────────────────────────────── */

const RANK_BADGE: Record<string, { label: string; className: string }> = {
  order: { label: "Order", className: "bg-slate-700/50 text-slate-400" },
  suborder: { label: "Suborder", className: "bg-indigo-900/40 text-indigo-400" },
  family: { label: "Family", className: "bg-teal-900/40 text-teal-400" },
  genus: { label: "Genus", className: "bg-cyan-900/40 text-cyan-400" },
  species: { label: "Species", className: "bg-purple-900/40 text-purple-300" },
};

/* ── Chevron icon ────────────────────────────────────────── */

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

/* ── Tree row component ──────────────────────────────────── */

function TreeRow({
  node,
  depth,
  expanded,
  onToggle,
  onSelect,
  selectedValue,
  searchQuery,
}: {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (key: string) => void;
  onSelect: (node: TreeNode) => void;
  selectedValue: string;
  searchQuery: string;
}) {
  const isExpanded = expanded.has(node.key);
  const hasChildren = node.children.length > 0;
  const isSelected = node.selectValue === selectedValue;
  const photo = node.photo;

  // Highlight matching text
  function highlight(text: string) {
    if (!searchQuery) return text;
    const idx = text.toLowerCase().indexOf(searchQuery.toLowerCase());
    if (idx === -1) return text;
    return (
      <>
        {text.slice(0, idx)}
        <span className="bg-ocean-500/30 text-ocean-200">{text.slice(idx, idx + searchQuery.length)}</span>
        {text.slice(idx + searchQuery.length)}
      </>
    );
  }

  return (
    <>
      <div
        className={`flex items-center gap-1.5 border-b border-ocean-900/20 transition-colors ${
          isSelected ? "bg-purple-600/20" : "hover:bg-abyss-800/80"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {/* Expand/collapse toggle */}
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onToggle(node.key); }}
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded transition hover:bg-ocean-700/30"
          >
            <ChevronRight className={`h-3 w-3 text-slate-500 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
          </button>
        ) : (
          <span className="w-5 shrink-0" />
        )}

        {/* Select button (the row itself) */}
        <button
          type="button"
          onClick={() => onSelect(node)}
          className="flex min-w-0 flex-1 items-center gap-2 py-1.5 pr-2 text-left"
        >
          {/* Photo thumbnail */}
          {photo ? (
            <div className="relative h-7 w-10 shrink-0 overflow-hidden rounded">
              <Image src={`/species/${photo}.jpg`} alt="" fill className="object-cover" sizes="40px" />
            </div>
          ) : node.rank === "species" ? (
            <div className="flex h-7 w-10 shrink-0 items-center justify-center rounded bg-ocean-900/30">
              <IconWhale className="h-3.5 w-3.5 text-ocean-700" />
            </div>
          ) : null}

          {/* Labels */}
          <div className="min-w-0 flex-1">
            <span className={`block truncate text-[13px] font-medium ${
              isSelected ? "text-purple-300" : "text-slate-200"
            }`}>
              {highlight(node.label)}
            </span>
            {node.rank !== "order" && (
              <span className="block truncate text-[10px] italic text-slate-600">
                {highlight(node.scientificName)}
                {node.rank !== "species" && node.speciesCount > 0 && (
                  <span className="ml-1 not-italic text-slate-700">
                    ({node.speciesCount} species)
                  </span>
                )}
              </span>
            )}
          </div>

          {/* Rank badge */}
          {node.rank !== "species" && (
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
              RANK_BADGE[node.rank]?.className ?? ""
            }`}>
              {RANK_BADGE[node.rank]?.label ?? node.rank}
            </span>
          )}

          {/* Coverage dots (species only) */}
          {node.rank === "species" && node.selectValue && (
            <div className="flex items-center gap-1 shrink-0">
              {SDM_MODELLED.has(node.selectValue) && (
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" title="SDM modelled" />
              )}
              {PHOTO_CLASSIFIABLE.has(node.selectValue) && (
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" title="Photo classifiable" />
              )}
              {AUDIO_CLASSIFIABLE.has(node.selectValue) && (
                <span className="h-1.5 w-1.5 rounded-full bg-violet-400" title="Audio classifiable" />
              )}
            </div>
          )}
        </button>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && node.children.map((child) => (
        <TreeRow
          key={child.key}
          node={child}
          depth={depth + 1}
          expanded={expanded}
          onToggle={onToggle}
          onSelect={onSelect}
          selectedValue={selectedValue}
          searchQuery={searchQuery}
        />
      ))}
    </>
  );
}

/* ── Main SpeciesPicker component ────────────────────────── */

export default function SpeciesPicker({
  value,
  onChange,
  open,
  onOpenChange,
  onLightbox,
}: {
  value: string;
  onChange: (sel: SpeciesSelection) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onLightbox: (photo: string | null) => void;
}) {
  const dropRef = useRef<HTMLDivElement>(null);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<"search" | "tree">("search");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [flatList, setFlatList] = useState<FlatOption[]>(FALLBACK_FLAT);
  const [tree, setTree] = useState<TreeNode | null>(null);
  const [crosswalkLoaded, setCrosswalkLoaded] = useState(false);

  /* Fetch crosswalk → build both flat list and tree */
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/species/crosswalk`);
        if (!res.ok) return;
        const json = await res.json();
        const rows: CrosswalkRow[] = (json.data ?? json).map(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (r: any) => ({
            scientific_name: r.scientific_name ?? "",
            common_name: r.common_name ?? "",
            species_group: r.species_group ?? "",
            taxonomic_rank: r.taxonomic_rank ?? "",
            family: r.family ?? "",
            is_baleen: r.is_baleen ?? false,
          }),
        );
        setFlatList(buildFlatList(rows));
        setTree(buildTree(rows));
        setCrosswalkLoaded(true);
      } catch {
        /* fallback to hardcoded */
      }
    })();
  }, []);

  /* Close on outside click */
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
        onOpenChange(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onOpenChange]);

  /* Auto-expand tree branches matching search */
  useEffect(() => {
    if (!tree || !search.trim()) return;
    const q = search.toLowerCase();
    const toExpand = new Set<string>();

    function walk(node: TreeNode, ancestors: string[]): boolean {
      const selfMatch =
        node.label.toLowerCase().includes(q) ||
        node.scientificName.toLowerCase().includes(q);
      let childMatch = false;
      for (const child of node.children) {
        if (walk(child, [...ancestors, node.key])) childMatch = true;
      }
      if (selfMatch || childMatch) {
        for (const a of ancestors) toExpand.add(a);
        toExpand.add(node.key);
        return true;
      }
      return false;
    }

    walk(tree, []);
    setExpanded(toExpand);
  }, [search, tree]);

  /* Filtered flat list */
  const filteredFlat = useMemo(() => {
    if (!search.trim()) return flatList;
    const q = search.toLowerCase();
    return flatList.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.value.toLowerCase().includes(q) ||
        s.family.toLowerCase().includes(q) ||
        s.scientificName.toLowerCase().includes(q),
    );
  }, [flatList, search]);

  /* Count visible tree nodes for empty state */
  const treeMatchCount = useMemo(() => {
    if (!tree || !search.trim()) return tree ? 999 : 0;
    const q = search.toLowerCase();
    function count(node: TreeNode): number {
      const selfMatch =
        node.label.toLowerCase().includes(q) ||
        node.scientificName.toLowerCase().includes(q);
      const childCounts = node.children.reduce((n, c) => n + count(c), 0);
      return (selfMatch ? 1 : 0) + childCounts;
    }
    return count(tree);
  }, [tree, search]);

  /* Find label for currently selected value */
  const selectedLabel = useMemo(() => {
    if (!value) return "Not sure / Unknown";
    const flat = flatList.find((s) => s.value === value);
    if (flat) return flat.label;
    return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }, [value, flatList]);

  const selectedRank = useMemo(() => {
    if (!value) return "order" as const;
    const flat = flatList.find((s) => s.value === value);
    return (flat?.rank ?? "species") as SpeciesSelection["rank"];
  }, [value, flatList]);

  /* Toggle a tree node */
  const toggleNode = useCallback((key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  /* Handle selection */
  const handleSelect = useCallback(
    (opt: { value: string; label: string; rank: string; family: string; scientificName: string }) => {
      onChange({
        value: opt.value,
        label: opt.label,
        rank: opt.rank as SpeciesSelection["rank"],
        family: opt.family,
        scientificName: opt.scientificName,
      });
      onOpenChange(false);
      setSearch("");
    },
    [onChange, onOpenChange],
  );

  const handleTreeSelect = useCallback(
    (node: TreeNode) => {
      handleSelect({
        value: node.selectValue,
        label: node.rank === "species"
          ? `${node.label} (${node.scientificName})`
          : node.label,
        rank: node.rank,
        family: node.family,
        scientificName: node.scientificName,
      });
    },
    [handleSelect],
  );

  /* Filter tree nodes to only show matches */
  function shouldShowNode(node: TreeNode, q: string): boolean {
    if (!q) return true;
    const ql = q.toLowerCase();
    if (
      node.label.toLowerCase().includes(ql) ||
      node.scientificName.toLowerCase().includes(ql)
    ) return true;
    return node.children.some((c) => shouldShowNode(c, q));
  }

  /* Preview data for current selection */
  const preview = value ? {
    photo: SPECIES_PHOTOS[value] ?? null,
    desc: SPECIES_DESC[value] ?? FAMILY_DESC[flatList.find((f) => f.value === value)?.family ?? ""] ?? null,
  } : null;

  const hasPhoto = PHOTO_CLASSIFIABLE.has(value);
  const hasAudio = AUDIO_CLASSIFIABLE.has(value);
  const hasSdm = SDM_MODELLED.has(value);
  const hasIsdm = ISDM_MODELLED.has(value);
  const noModels = value ? !hasPhoto && !hasAudio && !hasSdm : false;

  return (
    <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
        <IconWhale className="mr-1.5 inline h-4 w-4" /> Species
      </h3>
      <p className="mb-4 text-xs text-slate-500">
        Optional — your best guess at any taxonomic level. Our models will also
        classify from uploaded media.
      </p>

      {/* Dropdown trigger */}
      <div ref={dropRef} className="relative">
        <button
          type="button"
          onClick={() => onOpenChange(!open)}
          className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left text-sm transition-colors ${
            value
              ? "border-purple-500/50 bg-purple-600/20 text-purple-300"
              : "border-ocean-800 text-slate-400 hover:bg-abyss-800"
          }`}
        >
          <span className="min-w-0 flex-1 truncate">
            {selectedLabel}
            {value && selectedRank !== "species" && (
              <span className={`ml-2 inline-block rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
                RANK_BADGE[selectedRank]?.className ?? ""
              }`}>
                {RANK_BADGE[selectedRank]?.label}
              </span>
            )}
          </span>
          <svg
            className={`ml-2 h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Dropdown panel */}
        {open && (
          <div className="absolute z-30 mt-1 max-h-[480px] w-full overflow-hidden rounded-xl border border-ocean-700 bg-abyss-900 shadow-2xl">
            {/* Header: search + mode toggle */}
            <div className="flex items-center gap-2 border-b border-ocean-800/50 p-2">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={mode === "search" ? "Type to search species, family…" : "Filter tree…"}
                className="min-w-0 flex-1 rounded-md border border-ocean-800 bg-abyss-800 px-3 py-1.5 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                autoFocus
              />
              <button
                type="button"
                onClick={() => {
                  setMode((m) => (m === "search" ? "tree" : "search"));
                  if (!expanded.size && tree) {
                    // Auto-expand suborders in tree mode
                    setExpanded(new Set(tree.children.map((c) => c.key)));
                  }
                }}
                className={`flex h-8 items-center gap-1 rounded-md border px-2 text-[11px] font-medium transition ${
                  mode === "tree"
                    ? "border-teal-600/50 bg-teal-600/20 text-teal-300"
                    : "border-ocean-800 text-slate-500 hover:bg-abyss-800"
                }`}
                title={mode === "search" ? "Switch to tree view" : "Switch to search view"}
              >
                {mode === "tree" ? (
                  <>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                    List
                  </>
                ) : (
                  <>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                    Tree
                  </>
                )}
              </button>
            </div>

            {/* Can't identify? Quick-pick catch-alls */}
            {mode === "search" && !search && (
              <div className="border-b border-ocean-800/30 px-2.5 py-2">
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                  Can&apos;t identify the species?
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { value: "unid_cetacean", label: "Unknown cetacean", rank: "order" as const, family: "", scientificName: "Cetacea" },
                    { value: "unid_baleen", label: "Baleen whale", rank: "suborder" as const, family: "", scientificName: "Mysticeti" },
                    { value: "unid_toothed", label: "Toothed whale", rank: "suborder" as const, family: "", scientificName: "Odontoceti" },
                    { value: "unid_dolphin", label: "Dolphin (unsure)", rank: "family" as const, family: "Delphinidae", scientificName: "Delphinidae" },
                    { value: "other_porpoise", label: "Porpoise (unsure)", rank: "family" as const, family: "Phocoenidae", scientificName: "Phocoenidae" },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => handleSelect(opt)}
                      className="rounded-full border border-amber-700/30 bg-amber-900/10 px-2.5 py-1 text-[10px] font-medium text-amber-400/90 transition-all hover:bg-amber-700/20"
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <p className="mt-1.5 text-[10px] text-slate-600">
                  Or{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setMode("tree");
                      if (!expanded.size && tree) {
                        setExpanded(new Set(tree.children.map((c) => c.key)));
                      }
                    }}
                    className="text-teal-500 underline decoration-teal-700 underline-offset-2"
                  >
                    browse the full tree
                  </button>{" "}
                  to find your species.
                </p>
              </div>
            )}

            {/* Content area */}
            <div className="max-h-[360px] overflow-y-auto">
              {mode === "search" ? (
                /* ── Search / flat list ── */
                <ul>
                  {filteredFlat.length === 0 ? (
                    <li className="px-3 py-4 text-center text-xs text-slate-500">
                      No matching taxa
                    </li>
                  ) : (
                    filteredFlat.map((sp) => {
                      const photo = SPECIES_PHOTOS[sp.value] ?? (sp.rank === "family" ? FAMILY_PHOTOS[sp.family] : null);
                      const isSelected = value === sp.value;
                      return (
                        <li key={sp.value || "_unknown"} className="border-b border-ocean-900/20 last:border-0">
                          <button
                            type="button"
                            onClick={() => handleSelect({
                              value: sp.value,
                              label: sp.label,
                              rank: sp.rank,
                              family: sp.family,
                              scientificName: sp.scientificName,
                            })}
                            className={`flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors ${
                              isSelected ? "bg-purple-600/20" : "hover:bg-abyss-800"
                            }`}
                          >
                            {/* Photo thumbnail */}
                            {photo ? (
                              <div className="relative h-8 w-11 shrink-0 overflow-hidden rounded">
                                <Image src={`/species/${photo}.jpg`} alt="" fill className="object-cover" sizes="44px" />
                              </div>
                            ) : sp.value ? (
                              <div className="flex h-8 w-11 shrink-0 items-center justify-center rounded bg-ocean-900/40">
                                <IconWhale className="h-3.5 w-3.5 text-ocean-700" />
                              </div>
                            ) : null}

                            {/* Labels */}
                            <div className="min-w-0 flex-1">
                              <span className={`block truncate text-sm font-medium ${
                                isSelected ? "text-purple-300" : "text-slate-200"
                              }`}>
                                {sp.label}
                              </span>
                              {sp.family && sp.rank === "species" && (
                                <span className="text-[10px] text-slate-600">{sp.family}</span>
                              )}
                            </div>

                            {/* Rank badge for non-species */}
                            {sp.rank !== "species" && sp.value && (
                              <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
                                RANK_BADGE[sp.rank]?.className ?? ""
                              }`}>
                                {RANK_BADGE[sp.rank]?.label}
                              </span>
                            )}

                            {/* Coverage dots (species only) */}
                            {sp.rank === "species" && sp.value && (
                              <div className="flex items-center gap-1 shrink-0">
                                {SDM_MODELLED.has(sp.value) && (
                                  <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" title="SDM modelled" />
                                )}
                                {PHOTO_CLASSIFIABLE.has(sp.value) && (
                                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" title="Photo classifiable" />
                                )}
                                {AUDIO_CLASSIFIABLE.has(sp.value) && (
                                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400" title="Audio classifiable" />
                                )}
                              </div>
                            )}
                          </button>
                        </li>
                      );
                    })
                  )}
                </ul>
              ) : (
                /* ── Tree view ── */
                tree ? (
                  <div>
                    {/* "Not sure" option at top */}
                    <button
                      type="button"
                      onClick={() => handleSelect({ value: "", label: "Not sure / Unknown", rank: "order", family: "", scientificName: "Cetacea" })}
                      className={`flex w-full items-center gap-2 border-b border-ocean-900/30 px-3 py-2 text-left text-sm transition-colors ${
                        !value ? "bg-purple-600/20 text-purple-300" : "text-slate-400 hover:bg-abyss-800"
                      }`}
                    >
                      Not sure / Unknown
                    </button>

                    {/* Tree nodes */}
                    {tree.children
                      .filter((c) => shouldShowNode(c, search))
                      .map((suborder) => (
                        <TreeRow
                          key={suborder.key}
                          node={suborder}
                          depth={0}
                          expanded={expanded}
                          onToggle={toggleNode}
                          onSelect={handleTreeSelect}
                          selectedValue={value}
                          searchQuery={search}
                        />
                      ))}

                    {search && treeMatchCount === 0 && (
                      <p className="px-3 py-4 text-center text-xs text-slate-500">
                        No matching taxa in tree
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="px-3 py-4 text-center text-xs text-slate-500">Loading taxonomy…</p>
                )
              )}
            </div>

            {/* Footer legend */}
            <div className="flex items-center gap-3 border-t border-ocean-800/40 px-3 py-1.5">
              <span className="flex items-center gap-1 text-[9px] text-slate-600">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" /> SDM
              </span>
              <span className="flex items-center gap-1 text-[9px] text-slate-600">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Photo
              </span>
              <span className="flex items-center gap-1 text-[9px] text-slate-600">
                <span className="h-1.5 w-1.5 rounded-full bg-violet-400" /> Audio
              </span>
              <span className="ml-auto text-[9px] text-slate-700">
                {crosswalkLoaded ? `${flatList.length - 1} taxa` : `${FALLBACK_FLAT.length - 1} species`}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Preview card */}
      {value && (
        <div className="mt-3 space-y-2">
          {/* Rank context (when non-species selected) */}
          {selectedRank !== "species" && (
            <div className="flex items-start gap-2 rounded-lg border border-indigo-600/30 bg-indigo-500/[0.06] px-3 py-2">
              <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" />
              </svg>
              <p className="text-[11px] leading-relaxed text-indigo-300/90">
                {selectedRank === "family"
                  ? "You selected a family-level identification. This is perfectly fine if you aren't sure of the exact species — it still helps us narrow down the sighting."
                  : selectedRank === "suborder"
                  ? "You selected a broad group (suborder). You can always refine later if you get a better look or our classifiers identify the species."
                  : "You selected a very broad category. Consider narrowing it down in the tree view if possible."
                }
              </p>
            </div>
          )}

          {/* Photo + description */}
          {preview && (preview.photo || preview.desc) && (
            <div className="flex items-start gap-3 rounded-lg border border-ocean-700/40 bg-ocean-500/[0.05] px-3 py-2.5">
              {preview.photo ? (
                <button
                  type="button"
                  onClick={() => onLightbox(preview.photo)}
                  className="group relative h-16 w-24 shrink-0 overflow-hidden rounded-md transition hover:ring-2 hover:ring-ocean-500/50"
                >
                  <Image
                    src={`/species/${preview.photo}.jpg`}
                    alt={selectedLabel}
                    fill
                    className="object-cover transition group-hover:scale-105"
                    sizes="96px"
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition group-hover:bg-black/30">
                    <svg className="h-5 w-5 text-white opacity-0 transition group-hover:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16zM11 8v6M8 11h6" />
                    </svg>
                  </div>
                  <div className="absolute inset-0 rounded-md ring-1 ring-inset ring-white/10" />
                </button>
              ) : (
                <div className="flex h-16 w-24 shrink-0 items-center justify-center rounded-md border border-ocean-800/30 bg-ocean-900/30">
                  <IconWhale className="h-6 w-6 text-ocean-700" />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-ocean-300">
                  {selectedLabel}
                </p>
                {preview.desc && (
                  <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">
                    {preview.desc}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Coverage warnings */}
          {noModels && selectedRank === "species" && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-600/30 bg-amber-500/[0.06] px-3 py-2">
              <IconWarning className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
              <p className="text-[11px] leading-relaxed text-amber-300/90">
                This species is not covered by our classification or distribution
                models. Your sighting is still valuable — it will be stored and
                contribute to the community record.
              </p>
            </div>
          )}
          {!noModels && selectedRank === "species" && (!hasPhoto || !hasAudio || !hasSdm) && (
            <div className="flex flex-wrap gap-1.5">
              {!hasPhoto && (
                <span className="inline-flex items-center gap-1 rounded-full border border-slate-700/40 bg-slate-800/30 px-2 py-0.5 text-[10px] text-slate-500">
                  <IconCamera className="h-2.5 w-2.5" /> No photo classifier
                </span>
              )}
              {!hasAudio && (
                <span className="inline-flex items-center gap-1 rounded-full border border-slate-700/40 bg-slate-800/30 px-2 py-0.5 text-[10px] text-slate-500">
                  <IconMicrophone className="h-2.5 w-2.5" /> No audio classifier
                </span>
              )}
              {!hasSdm && (
                <span className="inline-flex items-center gap-1 rounded-full border border-slate-700/40 bg-slate-800/30 px-2 py-0.5 text-[10px] text-slate-500">
                  <IconWhale className="h-2.5 w-2.5" /> No distribution model
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
