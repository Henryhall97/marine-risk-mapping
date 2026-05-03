"use client";

import { API_BASE } from "@/lib/config";
import { SonarPing } from "@/components/animations";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Fragment, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  IconWhale,
  IconMicroscope,
  IconGlobe,
  IconShield,
  IconWarning,
  IconRobot,
  IconCamera,
  IconMicrophone,
  IconChart,
  IconShip,
  IconInfo,
} from "@/components/icons/MarineIcons";
import IDHelper, { GROUP_LABEL_OVERRIDES } from "@/components/IDHelper";

/* ── Types ──────────────────────────────────────────────── */

interface CrosswalkEntry {
  scientific_name: string;
  common_name: string | null;
  species_group: string | null;
  nisi_species: string | null;
  strike_species: string | null;
  taxonomic_rank: string | null;
  family: string | null;
  is_baleen: boolean | null;
  conservation_priority: string | null;
  aphia_id: number | null;
  worms_lsid: string | null;
}

interface TaxonNode {
  key: string;
  label: string;
  scientificName: string;
  rank: "order" | "suborder" | "family" | "genus" | "species";
  description: string;
  photo: string | null;
  collagePhotos?: string[];
  conservation: string | null;
  isBaleen: boolean | null;
  aphiaId: number | null;
  modelCoverage: {
    isdm: boolean;
    sdm: boolean;
    audio: boolean;
    photo: boolean;
  };
  children: TaxonNode[];
  speciesCount: number;
  entries: CrosswalkEntry[];
  isCatchAll?: boolean;
}

/* ── Static data ────────────────────────────────────────── */

const SPECIES_PHOTOS: Record<string, string> = {
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
};

const FAMILY_PHOTOS: Record<string, string[]> = {
  Balaenidae: ["right_whale", "bowhead"],
  Balaenopteridae: [
    "blue_whale",
    "humpback_whale",
    "fin_whale",
    "minke_whale",
  ],
  Eschrichtiidae: ["gray_whale"],
  Delphinidae: [
    "orca",
    "bottlenose_dolphin",
    "common_dolphin",
    "spotted_dolphin",
  ],
  Phocoenidae: ["harbor_porpoise", "dalls_porpoise", "vaquita"],
  Physeteridae: ["sperm_whale"],
  Kogiidae: ["dwarf_sperm_whales"],
  Ziphiidae: ["beaked_whale"],
  Monodontidae: ["beluga"],
};

const SUBORDER_PHOTOS: Record<string, string[]> = {
  Mysticeti: ["humpback_whale", "blue_whale", "right_whale", "gray_whale"],
  Odontoceti: ["sperm_whale", "orca", "bottlenose_dolphin", "beluga"],
};

const FAMILY_DESCRIPTIONS: Record<string, string> = {
  Balaenidae:
    "Right whales and bowhead. Stocky, slow-moving filter feeders " +
    "with no dorsal fin, arched jaw, and long baleen plates. Among " +
    "the most endangered large whales due to historical whaling and " +
    "ongoing ship-strike and entanglement threats.",
  Balaenopteridae:
    "Rorquals: the largest family of baleen whales, distinguished " +
    "by throat grooves that expand during lunge feeding. Includes " +
    "the blue whale (largest animal ever), fin, humpback, sei, " +
    "Bryde's, and minke whales.",
  Eschrichtiidae:
    "A monotypic family containing only the gray whale. Known for " +
    "the longest mammalian migration (up to 22,000 km round-trip) " +
    "between Arctic feeding grounds and Mexican breeding lagoons. " +
    "Unique bottom-feeding behaviour, scooping sediment for amphipods.",
  Neobalaenidae:
    "Pygmy right whale: the smallest and most cryptic baleen whale. " +
    "Rarely observed at sea, known mainly from strandings in the " +
    "Southern Hemisphere. Phylogenetically distinct from other " +
    "living baleen whales.",
  Delphinidae:
    "Oceanic dolphins: the largest and most diverse cetacean family " +
    "with over 35 species. Highly social, fast-swimming, and found " +
    "in all oceans. Includes orcas (killer whales), bottlenose " +
    "dolphins, and pilot whales.",
  Phocoenidae:
    "Porpoises: small, stocky cetaceans with spade-shaped teeth " +
    "(vs. conical in dolphins). Generally shy and solitary. " +
    "Includes the critically endangered vaquita, with fewer " +
    "than 10 individuals remaining.",
  Physeteridae:
    "Sperm whales: the largest toothed predator on Earth, diving " +
    "to over 2,000 m depth to hunt giant squid. Highly social " +
    "matrilineal groups with complex click-based communication. " +
    "The only living member of this family.",
  Kogiidae:
    "Pygmy and dwarf sperm whales: small, deep-diving toothed " +
    "whales superficially resembling sharks. Rarely seen alive; " +
    "most knowledge comes from strandings. They eject a dark " +
    "reddish-brown ink when threatened.",
  Ziphiidae:
    "Beaked whales: the most species-rich cetacean family (over " +
    "20 species), yet among the least known mammals. Extreme " +
    "deep-divers, with Cuvier's beaked whale holding the mammalian " +
    "dive record at 2,992 m. Highly sensitive to naval sonar.",
  Monodontidae:
    "Narwhals and belugas: Arctic specialists with no dorsal fin. " +
    "Belugas are the 'canaries of the sea' with exceptional vocal " +
    "range. Narwhals possess the iconic spiralled tusk, actually " +
    "an elongated upper canine tooth.",
  Platanistidae:
    "South Asian river dolphins: functionally blind, navigating " +
    "murky river waters entirely by echolocation. One of the most " +
    "endangered cetacean families, threatened by dams, pollution, " +
    "and bycatch in the Ganges and Indus river systems.",
  Pontoporiidae:
    "Franciscana (La Plata dolphin): the smallest South American " +
    "cetacean and the only river dolphin regularly found in " +
    "saltwater. Extremely long, narrow beak relative to body size. " +
    "Vulnerable due to gillnet bycatch.",
  Iniidae:
    "Amazon river dolphins (boto): the largest river dolphins, " +
    "with distinctive pink colouration that intensifies with age. " +
    "Flexible necks allow navigation through flooded forests. " +
    "Important in Amazonian folklore and mythology.",
  Lipotidae:
    "Baiji (Yangtze river dolphin): the first cetacean driven " +
    "to functional extinction in modern times, declared likely " +
    "extinct in 2007. A sobering conservation lesson about " +
    "irreversible habitat destruction.",
};

const SUBORDER_DESCRIPTIONS: Record<string, string> = {
  Mysticeti:
    "Baleen whales filter enormous volumes of water through " +
    "keratinous baleen plates to capture krill, copepods, and " +
    "small fish. They include the largest animals to have ever " +
    "lived. 4 families, around 15 species.",
  Odontoceti:
    "Toothed whales use echolocation to hunt individual prey. " +
    "The most diverse cetacean suborder, ranging from 1.5 m " +
    "porpoises to 18 m sperm whales. 10 families, around 75 species.",
};

const SPECIES_DESCRIPTIONS: Record<string, string> = {
  right_whale:
    "North Atlantic right whale. Critically endangered with around " +
    "350 individuals remaining. Slow-moving and coastal, making " +
    "them highly vulnerable to ship strikes and entanglement.",
  humpback:
    "Famous for complex songs and acrobatic breaching. Populations " +
    "have partially recovered from whaling but face ongoing threats " +
    "from vessel traffic and fishing gear.",
  fin_whale:
    "Second-largest animal on Earth (up to 26 m). Unusually fast " +
    "for its size, often called the 'greyhound of the sea'. " +
    "Distinctive asymmetric jaw colouration.",
  blue_whale:
    "The largest animal ever known, reaching 30 m and 190 tonnes. " +
    "Heart the size of a small car. Endangered, with only " +
    "10,000-25,000 remaining worldwide.",
  sperm_whale:
    "Deepest-diving mammal, reaching depths over 2,000 m. The " +
    "largest brain of any animal. Complex social structures with " +
    "cultural transmission of foraging dialects.",
  minke_whale:
    "Smallest of the rorquals at 7-10 m. Curious and often " +
    "approaches boats. Relatively abundant, but vulnerable to " +
    "bycatch and climate-driven prey shifts.",
  sei_whale:
    "One of the fastest cetaceans, capable of short bursts up to " +
    "50 km/h. Endangered, with a preference for deep offshore " +
    "waters that makes population estimates difficult.",
  orca:
    "Apex predator found in every ocean. Distinct ecotypes " +
    "specialise on different prey (fish, seals, whales). Complex " +
    "matrilineal social structure with culturally transmitted " +
    "hunting techniques.",
  gray_whale:
    "Unique bottom-feeding baleen whale. Undertakes the longest " +
    "known mammalian migration. Eastern Pacific population " +
    "recovered; western Pacific critically endangered " +
    "(around 300 individuals).",
  bowhead:
    "Arctic specialist with the thickest blubber and longest " +
    "baleen of any whale. Lifespan exceeds 200 years, making it " +
    "the longest-lived mammal. Population recovering from whaling.",
  bottlenose_dolphin:
    "Perhaps the most studied cetacean. Highly intelligent with " +
    "documented tool use, self-recognition, and complex social " +
    "alliances. Found in coastal and offshore waters worldwide.",
  common_dolphin:
    "Gregarious and fast-moving, forming pods of hundreds to " +
    "thousands. Two species (short-beaked and long-beaked) with " +
    "a distinctive hourglass colour pattern.",
  harbor_porpoise:
    "Small, shy coastal cetacean. One of the most commonly " +
    "encountered cetaceans in the Northern Hemisphere, but highly " +
    "vulnerable to bycatch in gillnets.",
  pilot_whale:
    "Long-finned and short-finned species. Highly social, forming " +
    "tight pods. The second-most commonly mass-stranded cetacean " +
    "after sperm whales, likely due to strong social bonds.",
  beluga:
    "The 'white whale' of Arctic waters. Exceptional vocal range " +
    "earned it the nickname 'canary of the sea'. Flexible neck " +
    "allows unique head movements among cetaceans.",
  beaked_whale:
    "Mysterious deep-divers; some species known only from " +
    "strandings. Extremely sensitive to anthropogenic noise, " +
    "particularly military sonar. Cuvier's beaked whale holds " +
    "the dive depth record.",
  brydes_whale:
    "Tropical rorqual that does not migrate to polar waters. " +
    "Three described forms (ordinary, pygmy, and Eden's whale). " +
    "Lunge feeds on schooling fish near the surface.",
  rissos_dolphin:
    "Recognizable by extensive scarring from squid suckers and " +
    "intraspecific tooth rakes. Adults become nearly white with " +
    "age. Deep-water species specialising on cephalopods.",
  spotted_dolphin:
    "Atlantic and pantropical species. Born unspotted; develops " +
    "increasing spots with age. Fast swimmers often seen " +
    "bow-riding. Historically impacted by tuna purse-seine bycatch.",
  striped_dolphin:
    "One of the most abundant dolphins globally. Distinctive " +
    "lateral stripe pattern. Known for acrobatic leaps. Found " +
    "in warm-temperate and tropical waters worldwide.",
  whitesided_dolphin:
    "Robust, fast-swimming North Atlantic species. Forms large " +
    "pods and often associates with other cetaceans. Important " +
    "indicator of productive oceanic frontal zones.",
  dalls_porpoise:
    "One of the fastest small cetaceans, creating a distinctive " +
    "'rooster tail' spray when swimming at speed. Stocky build " +
    "with bold black-and-white colouration. North Pacific endemic.",
  vaquita:
    "The world's rarest marine mammal. Critically endangered with " +
    "fewer than 10 individuals. Endemic to the northern Gulf of " +
    "California. Primary threat: illegal gillnet fishing for totoaba.",
  dwarf_sperm_whale:
    "Small, rarely-seen deep-diver. Shark-like false gill slit " +
    "marking behind the eye. Ejects reddish ink cloud when " +
    "threatened. Most knowledge comes from strandings.",
  pygmy_sperm_whale:
    "Slightly larger than the dwarf sperm whale but similarly " +
    "elusive. Square head profile. Among the most commonly " +
    "stranded cetaceans despite being rarely observed at sea.",
  hectors_dolphin:
    "Smallest oceanic dolphin (up to 1.4 m). Endemic to New " +
    "Zealand. Critically endangered Māui subspecies has fewer " +
    "than 60 individuals. Distinctive rounded dorsal fin.",
  narwhal:
    "The 'unicorn of the sea'. Males bear a spiralled tusk up " +
    "to 3 m long — actually an elongated canine tooth. Arctic " +
    "specialist, highly sensitive to climate change and sea " +
    "ice loss.",
  omuras_whale:
    "One of the most recently described whale species (2003). " +
    "Tropical rorqual previously confused with Bryde's whale. " +
    "Rare and poorly known, with fewer than 100 confirmed " +
    "sightings worldwide.",
  rices_whale:
    "Critically endangered Gulf of Mexico endemic, described " +
    "as a new species in 2021 (formerly Gulf of Mexico Bryde's " +
    "whale). Estimated population of fewer than 100. Threatened " +
    "by vessel strikes, oil spills, and seismic surveys.",
  southern_right_whale:
    "Southern Hemisphere counterpart to the North Atlantic right " +
    "whale. Populations recovering after whaling, with around " +
    "15,000 individuals. Found around South America, southern " +
    "Africa, and Australasia.",
  pygmy_right_whale:
    "The smallest and most enigmatic baleen whale. Rarely observed " +
    "alive, known mainly from strandings in the Southern " +
    "Hemisphere. Phylogenetically distinct — the sole living " +
    "member of family Neobalaenidae.",
  other_dolphin:
    "Dolphins not assigned to a named focus group. Includes 27 " +
    "species across multiple genera — from spinner and Clymene " +
    "dolphins to river dolphins and Commerson's dolphin. Select " +
    "this when you've identified a dolphin but it doesn't match " +
    "the named groups above.",
  other_porpoise:
    "Porpoise species outside the named groups. Includes finless " +
    "porpoises, spectacled porpoise, and Burmeister's porpoise. " +
    "Generally small and shy, most easily confused with one " +
    "another in the field.",
  small_sperm_whale:
    "Pygmy and dwarf sperm whales (genus Kogia). Use this when " +
    "you spotted a small, square-headed whale with a shark-like " +
    "appearance but couldn't tell whether it was the pygmy or " +
    "dwarf species — they're extremely difficult to distinguish.",
  unid_baleen:
    "Use when you saw a baleen whale (filter feeder, usually " +
    "large) but couldn't identify the species. Common at " +
    "distance when only the blow or dorsal profile is visible.",
  unid_cetacean:
    "Use when you saw a whale or dolphin but couldn't tell " +
    "whether it was baleen or toothed. Perfectly valid — " +
    "distant or brief sightings often can't be narrowed " +
    "down further.",
  unid_dolphin:
    "Use when you saw a dolphin but couldn't narrow it to a " +
    "specific group. Small, fast-moving dolphins at distance " +
    "are often impossible to identify beyond 'dolphin'.",
  unid_rorqual:
    "Use when you saw a rorqual (family Balaenopteridae — " +
    "blue, fin, humpback, sei, Bryde's, or minke whale) but " +
    "couldn't determine which species. Rorquals share similar " +
    "body plans and are easy to confuse at distance.",
  unid_toothed:
    "Use when you saw a toothed whale (dolphin, porpoise, " +
    "sperm whale, or beaked whale) but couldn't identify it " +
    "further. Toothed whales range from 1.5 m porpoises to " +
    "18 m sperm whales.",
};

const MODEL_COVERAGE: Record<
  string,
  { isdm: boolean; sdm: boolean; audio: boolean; photo: boolean }
> = {
  right_whale: { isdm: false, sdm: true, audio: true, photo: true },
  humpback: { isdm: true, sdm: true, audio: true, photo: true },
  fin_whale: { isdm: true, sdm: true, audio: true, photo: true },
  blue_whale: { isdm: true, sdm: true, audio: true, photo: true },
  sperm_whale: { isdm: true, sdm: true, audio: true, photo: false },
  minke_whale: { isdm: false, sdm: true, audio: true, photo: true },
  sei_whale: { isdm: false, sdm: false, audio: true, photo: true },
  orca: { isdm: false, sdm: false, audio: true, photo: true },
};

const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border-red-500/30",
  high: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  moderate: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  low: "bg-slate-500/15 text-slate-400 border-slate-500/30",
  unknown: "bg-slate-600/15 text-slate-500 border-slate-600/30",
};

/* ── Helpers ────────────────────────────────────────────── */

/**
 * Derive photo filename stem from a scientific name.
 * "Balaenoptera musculus" → "balaenoptera_musculus"
 */
function scientificPhoto(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "_");
}

function groupLabel(g: string) {
  return g.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function priorityBadge(p: string | null) {
  const key = p ?? "unknown";
  const cls = PRIORITY_COLORS[key] ?? PRIORITY_COLORS.unknown;
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}
    >
      {key}
    </span>
  );
}

/* ── Photo components ──────────────────────────────────── */

function PhotoThumbnail({
  photo,
  collage,
  alt,
  size = "md",
}: {
  photo: string | null;
  collage?: string[];
  alt: string;
  size?: "sm" | "md" | "lg";
}) {
  const dims =
    size === "sm"
      ? "h-10 w-10"
      : size === "lg"
        ? "h-14 w-20"
        : "h-12 w-12";

  if (photo) {
    return (
      <div
        className={`relative ${dims} shrink-0 overflow-hidden rounded-lg`}
      >
        <Image
          src={`/species/${photo}.jpg`}
          alt={alt}
          fill
          className="object-cover"
          sizes="96px"
        />
        <div className="absolute inset-0 rounded-lg ring-1 ring-inset ring-white/10" />
      </div>
    );
  }

  if (collage && collage.length > 0) {
    return (
      <div
        className={`relative ${dims} shrink-0 grid grid-cols-2 grid-rows-2 gap-px overflow-hidden rounded-lg ring-1 ring-inset ring-white/10`}
      >
        {collage.slice(0, 4).map((p) => (
          <div key={p} className="relative overflow-hidden">
            <Image
              src={`/species/${p}.jpg`}
              alt=""
              fill
              className="object-cover"
              sizes="48px"
            />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div
      className={`${dims} shrink-0 rounded-lg bg-gradient-to-br from-ocean-600/20 to-teal-600/20`}
    />
  );
}

function PhotoBanner({
  photo,
  collage,
  label,
  sublabel,
}: {
  photo: string | null;
  collage?: string[];
  label: string;
  sublabel?: string;
}) {
  const hasVisual = photo || (collage && collage.length > 0);
  if (!hasVisual) return null;

  return (
    <div className="relative h-48 w-full overflow-hidden bg-abyss-950 sm:h-56">
      {photo ? (
        <Image
          src={`/species/${photo}.jpg`}
          alt={label}
          fill
          className="object-contain"
          sizes="(max-width:768px) 100vw, 900px"
        />
      ) : (
        <div className="flex h-full w-full">
          {collage!.slice(0, 4).map((p) => (
            <div key={p} className="relative flex-1">
              <Image
                src={`/species/${p}.jpg`}
                alt=""
                fill
                className="object-contain"
                sizes="25vw"
              />
            </div>
          ))}
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-abyss-900 to-transparent" />
      <div className="absolute bottom-3 left-5 right-5">
        <p className="text-lg font-bold text-white drop-shadow-lg">
          {label}
        </p>
        {sublabel && (
          <p className="text-xs text-slate-300/80">{sublabel}</p>
        )}
      </div>
    </div>
  );
}



/* ── Build taxonomy tree from flat crosswalk ─────────────── */

function buildTree(rows: CrosswalkEntry[]): TaxonNode {
  const familyMap = new Map<string, Map<string, CrosswalkEntry[]>>();

  for (const r of rows) {
    const fam = r.family ?? "Unknown";
    if (!familyMap.has(fam)) familyMap.set(fam, new Map());
    const groupMap = familyMap.get(fam)!;
    const grp = r.species_group ?? "ungrouped";
    if (!groupMap.has(grp)) groupMap.set(grp, []);
    groupMap.get(grp)!.push(r);
  }

  const baleenFamilies = new Set<string>();
  const toothedFamilies = new Set<string>();
  for (const [fam, groupMap] of familyMap) {
    for (const entries of groupMap.values()) {
      for (const e of entries) {
        if (e.is_baleen === true) baleenFamilies.add(fam);
        else if (e.is_baleen === false) toothedFamilies.add(fam);
      }
    }
  }

  function buildFamilyNode(
    family: string,
    groupMap: Map<string, CrosswalkEntry[]>,
  ): TaxonNode {
    const allEntries = [...groupMap.values()].flat();
    const speciesEntries = allEntries.filter(
      (e) => e.taxonomic_rank === "species",
    );

    const PRIO_ORDER: Record<string, number> = {
      critical: 0,
      high: 1,
      moderate: 2,
      low: 3,
      unknown: 4,
    };
    const sortedGroups = [...groupMap.entries()].sort(
      ([, a], [, b]) => {
        const pa =
          PRIO_ORDER[a[0].conservation_priority ?? "unknown"] ?? 4;
        const pb =
          PRIO_ORDER[b[0].conservation_priority ?? "unknown"] ?? 4;
        if (pa !== pb) return pa - pb;
        return (a[0].common_name ?? "").localeCompare(
          b[0].common_name ?? "",
        );
      },
    );

    const children: TaxonNode[] = sortedGroups.map(
      ([grp, entries]) => {
        const lead = entries[0];
        /* Prefer scientific-name photo, fall back to old species_group map */
        const sciPhoto = scientificPhoto(lead.scientific_name);
        const photoKey = sciPhoto || SPECIES_PHOTOS[grp] || null;
        /* Collage: if group has multiple species, show up to 4 */
        const speciesInGroup = entries.filter(
          (e) => e.taxonomic_rank === "species",
        );
        const collage =
          speciesInGroup.length > 1
            ? speciesInGroup
                .slice(0, 4)
                .map((e) => scientificPhoto(e.scientific_name))
            : undefined;
        return {
          key: grp,
          label:
            GROUP_LABEL_OVERRIDES[grp] ??
            (lead.common_name
              ? groupLabel(grp)
              : lead.scientific_name),
          scientificName: lead.scientific_name,
          rank: "species" as const,
          isCatchAll:
            grp.startsWith("unid_") ||
            grp.startsWith("other_"),
          description: SPECIES_DESCRIPTIONS[grp] ?? "",
          photo: photoKey,
          collagePhotos: collage,
          conservation: lead.conservation_priority,
          isBaleen: lead.is_baleen,
          aphiaId: lead.aphia_id ?? null,
          modelCoverage: MODEL_COVERAGE[grp] ?? {
            isdm: false,
            sdm: false,
            audio: false,
            photo: false,
          },
          children: [],
          speciesCount: entries.filter(
            (e) => e.taxonomic_rank === "species",
          ).length,
          entries,
        };
      },
    );

    /* Family photo: try scientific-name photo for the family itself,
       else build a collage from representative species entries,
       with old FAMILY_PHOTOS as final fallback */
    const famPhoto = scientificPhoto(family);
    const famSpecies = speciesEntries.slice(0, 4).map(
      (e) => scientificPhoto(e.scientific_name),
    );
    const legacyPhotos = FAMILY_PHOTOS[family];
    const familyCollage =
      famSpecies.length > 1
        ? famSpecies
        : legacyPhotos && legacyPhotos.length > 1
          ? legacyPhotos
          : undefined;
    const familySinglePhoto =
      famPhoto || (legacyPhotos?.length === 1 ? legacyPhotos[0] : null);

    return {
      key: `fam-${family}`,
      label: family,
      scientificName: family,
      rank: "family",
      description: FAMILY_DESCRIPTIONS[family] ?? "",
      photo: familyCollage ? null : familySinglePhoto,
      collagePhotos: familyCollage,
      conservation: null,
      isBaleen: baleenFamilies.has(family)
        ? true
        : toothedFamilies.has(family)
          ? false
          : null,
      aphiaId: null,
      modelCoverage: {
        isdm: false,
        sdm: false,
        audio: false,
        photo: false,
      },
      children,
      speciesCount: speciesEntries.length,
      entries: allEntries,
    };
  }

  function buildSuborderNode(
    name: string,
    isBaleen: boolean,
    families: [string, Map<string, CrosswalkEntry[]>][],
  ): TaxonNode {
    const children = families
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fam, gm]) => buildFamilyNode(fam, gm));

    const allEntries = children.flatMap((c) => c.entries);
    const speciesCount = allEntries.filter(
      (e) => e.taxonomic_rank === "species",
    ).length;
    /* Suborder photo: try scientific-name photo, else collage from
       representative species, with old SUBORDER_PHOTOS as fallback */
    const subPhoto = scientificPhoto(name);
    const subSpecies = allEntries
      .filter((e) => e.taxonomic_rank === "species")
      .slice(0, 4)
      .map((e) => scientificPhoto(e.scientific_name));
    const legacySubPhotos = SUBORDER_PHOTOS[name];
    const suborderCollage =
      subSpecies.length > 1
        ? subSpecies
        : legacySubPhotos ?? undefined;

    return {
      key: `sub-${name}`,
      label: name,
      scientificName: name,
      rank: "suborder",
      description: SUBORDER_DESCRIPTIONS[name] ?? "",
      photo: suborderCollage ? null : subPhoto,
      collagePhotos: suborderCollage,
      conservation: null,
      isBaleen: isBaleen,
      aphiaId: null,
      modelCoverage: {
        isdm: false,
        sdm: false,
        audio: false,
        photo: false,
      },
      children,
      speciesCount,
      entries: allEntries,
    };
  }

  const baleenEntries: [string, Map<string, CrosswalkEntry[]>][] = [];
  const toothedEntries: [string, Map<string, CrosswalkEntry[]>][] = [];
  const unknownEntries: [string, Map<string, CrosswalkEntry[]>][] = [];

  for (const [fam, groupMap] of familyMap) {
    if (baleenFamilies.has(fam)) baleenEntries.push([fam, groupMap]);
    else if (toothedFamilies.has(fam))
      toothedEntries.push([fam, groupMap]);
    else unknownEntries.push([fam, groupMap]);
  }

  const suborderChildren: TaxonNode[] = [];
  if (baleenEntries.length > 0) {
    suborderChildren.push(
      buildSuborderNode("Mysticeti", true, baleenEntries),
    );
  }
  if (toothedEntries.length > 0 || unknownEntries.length > 0) {
    suborderChildren.push(
      buildSuborderNode("Odontoceti", false, [
        ...toothedEntries,
        ...unknownEntries,
      ]),
    );
  }

  return {
    key: "order-Cetacea",
    label: "Cetacea",
    scientificName: "Cetacea",
    rank: "order",
    description:
      "Marine mammals comprising baleen whales and toothed whales. " +
      "Around 90 living species across 14 families, found in every " +
      "ocean from the tropics to the poles.",
    photo: null,
    collagePhotos: [
      "humpback_whale",
      "sperm_whale",
      "orca",
      "bottlenose_dolphin",
    ],
    conservation: null,
    isBaleen: null,
    aphiaId: null,
    modelCoverage: {
      isdm: false,
      sdm: false,
      audio: false,
      photo: false,
    },
    children: suborderChildren,
    speciesCount: rows.filter((e) => e.taxonomic_rank === "species")
      .length,
    entries: rows,
  };
}

/* ── Tree rendering ──────────────────────────────────────── */

const RANK_STYLES: Record<
  string,
  { border: string; bg: string; accent: string; line: string }
> = {
  order: {
    border: "border-ocean-500/40",
    bg: "bg-ocean-500/[0.07]",
    accent: "text-ocean-300",
    line: "bg-ocean-500/30",
  },
  suborder: {
    border: "border-teal-600/40",
    bg: "bg-teal-600/[0.06]",
    accent: "text-teal-300",
    line: "bg-teal-600/25",
  },
  family: {
    border: "border-cyan-700/35",
    bg: "bg-cyan-700/[0.05]",
    accent: "text-cyan-300",
    line: "bg-cyan-700/25",
  },
  genus: {
    border: "border-indigo-700/30",
    bg: "bg-indigo-700/[0.04]",
    accent: "text-indigo-300",
    line: "bg-indigo-700/20",
  },
  species: {
    border: "border-ocean-800/30",
    bg: "bg-abyss-900/40",
    accent: "text-slate-200",
    line: "bg-ocean-800/25",
  },
};

const RANK_LABELS: Record<string, string> = {
  order: "Order",
  suborder: "Suborder",
  family: "Family",
  genus: "Genus",
  species: "Species group",
};

const CHILD_NOUN: Record<string, string> = {
  order: "suborders",
  suborder: "families",
  family: "groups",
  genus: "species",
  species: "entries",
};

function TreeNode({
  node,
  depth,
  search,
  expandedNodes,
  toggleNode,
  isLast,
}: {
  node: TaxonNode;
  depth: number;
  search: string;
  expandedNodes: Set<string>;
  toggleNode: (key: string) => void;
  isLast: boolean;
}) {
  const isExpanded = expandedNodes.has(node.key);
  const hasChildren = node.children.length > 0;
  const isLeaf = node.rank === "species" || node.rank === "genus";
  const style = RANK_STYLES[node.rank] ?? RANK_STYLES.species;

  /* Search filtering */
  const q = search.toLowerCase();
  const matchesSelf = q
    ? node.label.toLowerCase().includes(q) ||
      node.scientificName.toLowerCase().includes(q) ||
      node.entries.some(
        (e) =>
          e.scientific_name.toLowerCase().includes(q) ||
          (e.common_name ?? "").toLowerCase().includes(q) ||
          (e.family ?? "").toLowerCase().includes(q) ||
          (e.nisi_species ?? "").toLowerCase().includes(q) ||
          (e.strike_species ?? "").toLowerCase().includes(q),
      )
    : true;

  function anyDescendantMatches(n: TaxonNode): boolean {
    if (!q) return true;
    for (const child of n.children) {
      if (
        child.label.toLowerCase().includes(q) ||
        child.scientificName.toLowerCase().includes(q) ||
        child.entries.some(
          (e) =>
            e.scientific_name.toLowerCase().includes(q) ||
            (e.common_name ?? "").toLowerCase().includes(q),
        )
      )
        return true;
      if (anyDescendantMatches(child)) return true;
    }
    return false;
  }

  if (q && !matchesSelf && !anyDescendantMatches(node)) return null;

  return (
    <div className="relative">
      {/* Vertical trunk line from parent */}
      {depth > 0 && !isLast && (
        <div
          className={`absolute bottom-0 top-0 w-px ${style.line}`}
          style={{ left: `${(depth - 1) * 28 + 13}px` }}
        />
      )}

      <div style={{ paddingLeft: depth > 0 ? `${depth * 28}px` : 0 }}>
        {/* Horizontal branch connector */}
        {depth > 0 && (
          <div
            className="flex items-center"
            style={{ marginLeft: "-15px", width: "15px" }}
          >
            <div className={`h-px flex-1 ${style.line}`} />
          </div>
        )}

        {/* Node card */}
        <div
          className={`overflow-hidden rounded-xl border ${style.border} ${style.bg} transition-all duration-200`}
        >
          {/* Clickable header */}
          <button
            onClick={() => toggleNode(node.key)}
            className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
          >
            <PhotoThumbnail
              photo={node.photo}
              collage={node.collagePhotos}
              alt={node.label}
              size={depth < 2 ? "lg" : "md"}
            />

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`font-bold ${style.accent} ${
                    depth === 0
                      ? "text-lg"
                      : depth === 1
                        ? "text-base"
                        : "text-sm"
                  }`}
                >
                  {node.label}
                </span>
                {node.rank !== "species" && (
                  <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                    {RANK_LABELS[node.rank]}
                  </span>
                )}
                {node.conservation && priorityBadge(node.conservation)}
                {node.isBaleen === true && (
                  <span className="text-[10px] font-semibold text-teal-400/80">
                    Baleen
                  </span>
                )}
                {node.isBaleen === false && (
                  <span className="text-[10px] font-semibold text-purple-400/80">
                    Toothed
                  </span>
                )}
                {node.isCatchAll && (
                  <span className="rounded border border-amber-600/30 bg-amber-700/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-400/90">
                    Broad ID
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
                {node.scientificName !== node.label && (
                  <span className="font-mono text-xs italic text-slate-500">
                    {node.scientificName}
                  </span>
                )}
                <span className="text-[11px] text-slate-600">
                  {node.speciesCount > 0 &&
                    `${node.speciesCount} species`}
                  {hasChildren &&
                    ` / ${node.children.length} ${CHILD_NOUN[node.rank] ?? "children"}`}
                </span>
              </div>
            </div>

            {/* Model badges (desktop only) */}
            {isLeaf && (
              <div className="hidden items-center gap-1 sm:flex">
                {node.modelCoverage.isdm && (
                  <span className="rounded-full bg-amber-500/30 px-1.5 py-0.5 text-[9px] font-medium text-amber-400">
                    ISDM
                  </span>
                )}
                {node.modelCoverage.sdm && (
                  <span className="rounded-full bg-cyan-500/30 px-1.5 py-0.5 text-[9px] font-medium text-cyan-400">
                    SDM
                  </span>
                )}
                {node.modelCoverage.audio && (
                  <span className="rounded-full bg-violet-500/30 px-1.5 py-0.5 text-[9px] font-medium text-violet-400">
                    Audio
                  </span>
                )}
                {node.modelCoverage.photo && (
                  <span className="rounded-full bg-emerald-500/30 px-1.5 py-0.5 text-[9px] font-medium text-emerald-400">
                    Photo
                  </span>
                )}
              </div>
            )}

            {/* Chevron */}
            <svg
              className={`h-4 w-4 shrink-0 text-slate-600 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          {/* Expanded content */}
          {isExpanded && (
            <div className="border-t border-white/5">
              {/* Banner photo */}
              <PhotoBanner
                photo={node.photo}
                collage={node.collagePhotos}
                label={node.label}
                sublabel={`${RANK_LABELS[node.rank]}${node.speciesCount > 0 ? ` / ${node.speciesCount} species` : ""}`}
              />

              {/* Description */}
              {node.description && (
                <div className="px-5 py-3">
                  <p className="text-sm leading-relaxed text-slate-400">
                    {node.description}
                  </p>
                </div>
              )}

              {/* Species-level crosswalk table */}
              {isLeaf && node.entries.length > 0 && (
                <div className="px-3 pb-3">
                  <table className="w-full text-left text-[11px]">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-slate-600">
                        <th className="px-3 py-2">
                          Scientific Name
                        </th>
                        <th className="px-3 py-2">Common Name</th>
                        <th className="hidden px-3 py-2 sm:table-cell">
                          Rank
                        </th>
                        <th className="px-3 py-2">ISDM</th>
                        <th className="px-3 py-2">Strike DB</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const rankOrd: Record<string, number> = {
                          species: 0,
                          genus: 1,
                          family: 2,
                          suborder: 3,
                          order: 4,
                        };
                        const sorted = [...node.entries].sort(
                          (a, b) => {
                            const ra =
                              rankOrd[
                                a.taxonomic_rank ?? ""
                              ] ?? 5;
                            const rb =
                              rankOrd[
                                b.taxonomic_rank ?? ""
                              ] ?? 5;
                            if (ra !== rb) return ra - rb;
                            return a.scientific_name.localeCompare(
                              b.scientific_name,
                            );
                          },
                        );
                        const hasSpecies = sorted.some(
                          (e) =>
                            e.taxonomic_rank === "species",
                        );
                        let dividered = false;
                        return sorted.map((r) => {
                          const isHigher =
                            r.taxonomic_rank !== "species";
                          const needDivider =
                            isHigher &&
                            hasSpecies &&
                            !dividered;
                          if (needDivider) dividered = true;
                          const dimmed =
                            isHigher && hasSpecies;
                          return (
                            <Fragment
                              key={r.scientific_name}
                            >
                              {needDivider && (
                                <tr>
                                  <td
                                    colSpan={5}
                                    className="px-3 pb-1 pt-3 text-[10px] uppercase tracking-wider text-slate-600/70"
                                  >
                                    Higher-level taxa
                                  </td>
                                </tr>
                              )}
                              <tr
                                className={`border-t border-ocean-900/30 transition-colors hover:bg-ocean-900/20${
                                  dimmed
                                    ? " opacity-50"
                                    : ""
                                }`}
                              >
                                <td className="px-3 py-1.5">
                                  <span className="font-mono italic text-slate-300">
                                    {r.scientific_name}
                                  </span>
                                  {r.aphia_id && (
                                    <a
                                      href={`https://www.marinespecies.org/aphia.php?p=taxdetails&id=${r.aphia_id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="ml-1.5 text-[9px] text-ocean-500 hover:text-ocean-400"
                                      title={`WoRMS AphiaID: ${r.aphia_id}`}
                                    >
                                      WoRMS
                                    </a>
                                  )}
                                </td>
                                <td className="px-3 py-1.5 text-slate-200">
                                  {r.common_name ?? (
                                    <span className="text-slate-700">
                                      --
                                    </span>
                                  )}
                                </td>
                                <td className="hidden px-3 py-1.5 sm:table-cell">
                                  <span
                                    className={`rounded px-1.5 py-0.5 text-[10px]${
                                      dimmed
                                        ? " bg-indigo-900/30 text-indigo-400/70"
                                        : " bg-ocean-900/40 text-slate-500"
                                    }`}
                                  >
                                    {r.taxonomic_rank ??
                                      "--"}
                                  </span>
                                </td>
                                <td className="px-3 py-1.5 text-amber-400/80">
                                  {r.nisi_species ?? (
                                    <span className="text-slate-700">
                                      --
                                    </span>
                                  )}
                                </td>
                                <td className="px-3 py-1.5 text-rose-400/80">
                                  {r.strike_species ?? (
                                    <span className="text-slate-700">
                                      --
                                    </span>
                                  )}
                                </td>
                              </tr>
                            </Fragment>
                          );
                        });
                      })()}
                    </tbody>
                  </table>

                  {/* Mobile model badges */}
                  {(node.modelCoverage.isdm ||
                    node.modelCoverage.sdm ||
                    node.modelCoverage.audio ||
                    node.modelCoverage.photo) && (
                    <div className="mt-3 flex flex-wrap gap-2 px-3 sm:hidden">
                      {node.modelCoverage.isdm && (
                        <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                          ISDM model
                        </span>
                      )}
                      {node.modelCoverage.sdm && (
                        <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-[10px] font-medium text-cyan-400">
                          SDM model
                        </span>
                      )}
                      {node.modelCoverage.audio && (
                        <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-medium text-violet-400">
                          Audio classifier
                        </span>
                      )}
                      {node.modelCoverage.photo && (
                        <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                          Photo classifier
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Children */}
              {hasChildren && (
                <div className="space-y-2 px-2 pb-3 pt-1">
                  {node.children.map((child, i) => (
                    <TreeNode
                      key={child.key}
                      node={child}
                      depth={depth + 1}
                      search={search}
                      expandedNodes={expandedNodes}
                      toggleNode={toggleNode}
                      isLast={i === node.children.length - 1}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Data-source cards ──────────────────────────────────── */

const DATA_SOURCES = [
  {
    key: "obis",
    label: "OBIS (Scientific)",
    column: "scientific_name",
    description:
      "Ocean Biodiversity Information System. Full binomial Latin " +
      "names at species, genus, family, or suborder level. The " +
      "primary key in our crosswalk.",
    Icon: IconGlobe,
    accent: "text-cyan-400",
  },
  {
    key: "nisi",
    label: "Nisi ISDM",
    column: "nisi_species",
    description:
      "Nisi et al. (2024) Integrated Species Distribution Model. " +
      "Short English names (Blue, Fin, Humpback, Sperm) for the " +
      "4 modelled whale species.",
    Icon: IconMicroscope,
    accent: "text-amber-400",
  },
  {
    key: "nmfs",
    label: "NMFS Strikes",
    column: "strike_species",
    description:
      "NOAA National Marine Fisheries Service ship strike records. " +
      "Lowercase short names (right, finback, humpback, blue, " +
      "unknown) parsed from NOAA PDFs.",
    Icon: IconWarning,
    accent: "text-rose-400",
  },
];

/* ── Page ───────────────────────────────────────────────── */

function SpeciesCrosswalkPageInner() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<CrosswalkEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(
    new Set(["order-Cetacea"]),
  );

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/species/crosswalk`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setRows(json.data ?? []);
      } catch (e: unknown) {
        setError(
          e instanceof Error ? e.message : "Failed to load",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const tree = useMemo(
    () => (rows.length > 0 ? buildTree(rows) : null),
    [rows],
  );

  const toggleNode = useCallback((key: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const allKeys = useMemo(() => {
    if (!tree) return new Set<string>();
    const keys = new Set<string>();
    function collect(n: TaxonNode) {
      keys.add(n.key);
      n.children.forEach(collect);
    }
    collect(tree);
    return keys;
  }, [tree]);

  const allExpanded = expandedNodes.size >= allKeys.size;

  function expandAll() {
    setExpandedNodes(new Set(allKeys));
  }
  function collapseAll() {
    setExpandedNodes(new Set(["order-Cetacea"]));
  }

  useEffect(() => {
    if (search.trim() && tree) {
      setExpandedNodes(new Set(allKeys));
    }
  }, [search, allKeys, tree]);

  const speciesCount = rows.filter(
    (r) => r.taxonomic_rank === "species",
  ).length;
  const familyCount = new Set(
    rows.map((r) => r.family).filter(Boolean),
  ).size;
  const baleenCount = rows.filter(
    (r) => r.is_baleen === true && r.taxonomic_rank === "species",
  ).length;
  const toothedCount = rows.filter(
    (r) => r.is_baleen === false && r.taxonomic_rank === "species",
  ).length;

  return (
    <main className="min-h-screen bg-abyss-950 px-4 pb-20 pt-24">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-10 text-center">
          <div className="mb-4 flex items-center justify-center gap-3">
            <Image
              src="/whale_watch_logo.png"
              alt="Whale Watch"
              width={60}
              height={40}
              className="h-10 w-[60px] object-contain opacity-60"
            />
            <h1 className="font-display text-4xl font-extrabold tracking-tight text-white">
              Species{" "}
              <span className="bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">
                Identification Guide
              </span>
            </h1>
          </div>
          <p className="mx-auto max-w-2xl text-sm leading-relaxed text-slate-400">
            Not sure what you saw? Answer a few questions below and
            we&apos;ll help you find the right category. Or browse the
            full taxonomy to explore all 138 tracked cetacean taxa.
          </p>
        </div>

        {/* Stats bar */}
        {!loading && !error && (
          <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              {
                label: "Species",
                value: speciesCount,
                accent: "text-white",
              },
              {
                label: "Families",
                value: familyCount,
                accent: "text-cyan-400",
              },
              {
                label: "Baleen species",
                value: baleenCount,
                accent: "text-teal-400",
              },
              {
                label: "Toothed species",
                value: toothedCount,
                accent: "text-purple-400",
              },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-ocean-800/30 bg-abyss-900/60 px-4 py-3 text-center"
              >
                <p
                  className={`text-2xl font-extrabold ${s.accent}`}
                >
                  {s.value}
                </p>
                <p className="text-[11px] text-slate-500">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* ID Helper — guided identification */}
        {!loading && !error && <IDHelper mode="navigate" />}

        {/* Species group explainer */}
        <div className="mb-8 rounded-xl border border-ocean-800/30 bg-gradient-to-r from-abyss-900/60 to-ocean-950/40 p-5">
          <div className="flex items-start gap-3">
            <IconInfo className="mt-0.5 h-5 w-5 shrink-0 text-ocean-400" />
            <div>
              <h3 className="mb-2 text-sm font-bold text-white">
                How species groups work
              </h3>
              <p className="mb-2 text-xs leading-relaxed text-slate-400">
                Species are organised into{" "}
                <span className="font-medium text-slate-300">
                  groups
                </span>{" "}
                based on what observers can realistically identify
                at sea. Some groups map to a single species (like
                Blue Whale), while others encompass many species
                when field identification is difficult (like
                Beaked Whales — 24 species that look nearly
                identical at the surface).
              </p>
              <p className="mb-3 text-xs leading-relaxed text-slate-400">
                Groups labelled{" "}
                <span className="rounded border border-amber-600/30 bg-amber-700/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-400/90">
                  Broad ID
                </span>{" "}
                are catch-all categories for sightings that
                couldn&apos;t be narrowed down further — these are
                the right choice when you&apos;re unsure of the
                exact species.
              </p>
              <Link
                href="/report"
                className="inline-flex items-center gap-1.5 rounded-md border border-teal-700/40 bg-teal-500/10 px-3 py-1.5 text-[11px] font-medium text-teal-300 transition-all hover:bg-teal-500/20"
              >
                <IconWhale className="h-3.5 w-3.5" />
                Report an interaction
              </Link>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-sm flex-1">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search species, family, group..."
              className="w-full rounded-lg border border-ocean-800/40 bg-abyss-900/70 px-4 py-2 pl-9 text-sm text-slate-200 placeholder-slate-600 outline-none ring-ocean-500/30 focus:border-ocean-700/60 focus:ring-2"
            />
            <svg
              className="absolute left-3 top-2.5 h-4 w-4 text-slate-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 103.5 3.5a7.5 7.5 0 0013.15 13.15z"
              />
            </svg>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={allExpanded ? collapseAll : expandAll}
              className="rounded-md border border-ocean-800/30 px-3 py-1.5 text-xs font-medium text-slate-400 transition-all hover:bg-ocean-900/30"
            >
              {allExpanded ? "Collapse all" : "Expand all"}
            </button>
            <span className="text-xs text-slate-600">
              {rows.length} entries
            </span>
          </div>
        </div>

        {/* Loading / Error */}
        {loading && (
          <div className="flex flex-col items-center gap-3 py-20">
            <SonarPing size={56} ringCount={3} active />
            <span className="text-sm text-ocean-400/60">
              Loading taxonomy...
            </span>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center">
            <IconWarning className="mx-auto mb-2 h-6 w-6 text-red-400" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Taxonomy tree */}
        {!loading && !error && tree && (
          <div className="space-y-2">
            <TreeNode
              node={tree}
              depth={0}
              search={search}
              expandedNodes={expandedNodes}
              toggleNode={toggleNode}
              isLast
            />
          </div>
        )}

        {/* Data-source cards */}
        <div className="mt-16 mb-8 grid gap-4 sm:grid-cols-3">
          {DATA_SOURCES.map((ds) => (
            <div
              key={ds.key}
              className="rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-5"
            >
              <div className="mb-2 flex items-center gap-2">
                <ds.Icon className={`h-5 w-5 ${ds.accent}`} />
                <h3 className={`text-sm font-bold ${ds.accent}`}>
                  {ds.label}
                </h3>
              </div>
              <p className="mb-2 text-xs leading-relaxed text-slate-400">
                {ds.description}
              </p>
              <p className="text-[10px] text-slate-600">
                Column:{" "}
                <code className="rounded bg-ocean-900/40 px-1.5 py-0.5 text-slate-400">
                  {ds.column}
                </code>
              </p>
            </div>
          ))}
        </div>

        {/* ── Model Species Coverage ── */}
        {!loading && !error && rows.length > 0 && (
          <div className="mt-16">
            <h2 className="mb-6 text-center font-display text-2xl font-extrabold tracking-tight text-white">
              Model{" "}
              <span className="bg-gradient-to-r from-ocean-400 to-bioluminescent-400 bg-clip-text text-transparent">
                Species Coverage
              </span>
            </h2>
            <p className="mx-auto mb-8 max-w-3xl text-center text-sm leading-relaxed text-slate-400">
              Different models are trained on different species subsets
              depending on available training data, the scientific
              question being answered, and practical constraints of each
              data source.
            </p>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {/* ISDM */}
              <div className="group relative overflow-hidden rounded-xl border border-amber-700/30 bg-abyss-900/60 p-5">
                <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-amber-600 to-yellow-500 opacity-60" />
                <div className="mb-3 flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-amber-600/30 to-yellow-600/30">
                    <IconRobot className="h-4 w-4 text-amber-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Expert Model
                    </h3>
                    <p className="text-[10px] text-amber-400/70">
                      Nisi et al. 2024, 4 species
                    </p>
                  </div>
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {[
                    "Blue whale",
                    "Fin whale",
                    "Humpback whale",
                    "Sperm whale",
                  ].map((s) => (
                    <span
                      key={s}
                      className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300"
                    >
                      {s}
                    </span>
                  ))}
                </div>
                <p className="text-xs leading-relaxed text-slate-400">
                  Integrated Species Distribution Models trained on the
                  Nisi et al. global risk grid using 7 environmental
                  covariates. Limited to 4 species with sufficient global
                  distribution data.
                </p>
              </div>

              {/* SDM */}
              <div className="group relative overflow-hidden rounded-xl border border-cyan-700/30 bg-abyss-900/60 p-5">
                <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-cyan-600 to-teal-500 opacity-60" />
                <div className="mb-3 flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-600/30 to-teal-600/30">
                    <IconChart className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      SDM -- OBIS Sighting Models
                    </h3>
                    <p className="text-[10px] text-cyan-400/70">
                      XGBoost spatial CV, 7 species
                    </p>
                  </div>
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {[
                    "Any cetacean",
                    "Right whale",
                    "Humpback",
                    "Fin whale",
                    "Blue whale",
                    "Sperm whale",
                    "Minke whale",
                  ].map((s) => (
                    <span
                      key={s}
                      className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300"
                    >
                      {s}
                    </span>
                  ))}
                </div>
                <p className="text-xs leading-relaxed text-slate-400">
                  Species Distribution Models trained on OBIS cetacean
                  sighting data. Spatial block cross-validation prevents
                  spatial leakage. Traffic features excluded to avoid
                  detection bias.
                </p>
              </div>

              {/* Audio */}
              <div className="group relative overflow-hidden rounded-xl border border-violet-700/30 bg-abyss-900/60 p-5">
                <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-violet-600 to-purple-500 opacity-60" />
                <div className="mb-3 flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600/30 to-purple-600/30">
                    <IconMicrophone className="h-4 w-4 text-violet-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Audio Classifier
                    </h3>
                    <p className="text-[10px] text-violet-400/70">
                      XGBoost + CNN, 8 species
                    </p>
                  </div>
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {[
                    "Right whale",
                    "Humpback",
                    "Fin whale",
                    "Blue whale",
                    "Sperm whale",
                    "Minke whale",
                    "Sei whale",
                    "Killer whale",
                  ].map((s) => (
                    <span
                      key={s}
                      className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-300"
                    >
                      {s}
                    </span>
                  ))}
                </div>
                <p className="text-xs leading-relaxed text-slate-400">
                  Classifies whale species from underwater audio. Two
                  backends: XGBoost on 64 acoustic features (97.9%) and
                  CNN on mel spectrograms (99.3%).
                </p>
              </div>

              {/* Photo */}
              <div className="group relative overflow-hidden rounded-xl border border-emerald-700/30 bg-abyss-900/60 p-5">
                <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-emerald-600 to-green-500 opacity-60" />
                <div className="mb-3 flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-600/30 to-green-600/30">
                    <IconCamera className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Photo Classifier
                    </h3>
                    <p className="text-[10px] text-emerald-400/70">
                      EfficientNet-B4, 7+1 classes
                    </p>
                  </div>
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {[
                    "Right whale",
                    "Humpback",
                    "Fin whale",
                    "Blue whale",
                    "Minke whale",
                    "Sei whale",
                    "Killer whale",
                    "Other cetacean",
                  ].map((s) => (
                    <span
                      key={s}
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                        s === "Other cetacean"
                          ? "border-slate-500/20 bg-slate-500/10 italic text-slate-400"
                          : "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                      }`}
                    >
                      {s}
                    </span>
                  ))}
                </div>
                <p className="text-xs leading-relaxed text-slate-400">
                  Classifies whale species from surface photographs. No
                  sperm whale coverage (absent from Happywhale dataset).
                  Audio fills that gap.
                </p>
              </div>

              {/* Survey-Based Risk */}
              <div className="group relative overflow-hidden rounded-xl border border-blue-700/30 bg-abyss-900/60 p-5">
                <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-blue-600 to-sky-500 opacity-60" />
                <div className="mb-3 flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600/30 to-sky-600/30">
                    <IconShield className="h-4 w-4 text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Survey-Based Risk
                    </h3>
                    <p className="text-[10px] text-blue-400/70">
                      7 sub-scores, all cetaceans
                    </p>
                  </div>
                </div>
                <p className="text-xs leading-relaxed text-slate-400">
                  The composite risk model is species-agnostic. It scores
                  collision risk for all cetaceans combined using 7
                  weighted sub-scores: traffic, cetacean presence,
                  proximity, strike history, habitat, protection gap, and
                  reference risk.
                </p>
              </div>

              {/* Strike Risk */}
              <div className="group relative overflow-hidden rounded-xl border border-rose-700/30 bg-abyss-900/60 p-5">
                <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-rose-600 to-pink-500 opacity-60" />
                <div className="mb-3 flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-rose-600/30 to-pink-600/30">
                    <IconShip className="h-4 w-4 text-rose-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Strike Risk Model
                    </h3>
                    <p className="text-[10px] text-rose-400/70">
                      Experimental, all species
                    </p>
                  </div>
                </div>
                <p className="text-xs leading-relaxed text-slate-400">
                  Binary classifier predicting strike probability per H3
                  cell. Currently parked due to extreme class imbalance
                  (67 positives in 1.8M cells). Species mapped via the
                  crosswalk strike_species column.
                </p>
              </div>
            </div>

            {/* Coverage matrix */}
            <div className="mt-8 overflow-x-auto rounded-xl border border-ocean-800/30 bg-abyss-900/50">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr className="border-b border-ocean-800/30 text-[10px] uppercase tracking-wider text-slate-600">
                    <th className="px-4 py-3">Species</th>
                    <th className="px-3 py-3 text-center">ISDM</th>
                    <th className="px-3 py-3 text-center">SDM</th>
                    <th className="px-3 py-3 text-center">Audio</th>
                    <th className="px-3 py-3 text-center">Photo</th>
                    <th className="px-3 py-3 text-center">Risk</th>
                    <th className="px-3 py-3 text-center">Strike</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    {
                      name: "North Atlantic Right Whale",
                      img: "right_whale",
                      isdm: false,
                      sdm: true,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Humpback Whale",
                      img: "humpback_whale",
                      isdm: true,
                      sdm: true,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Fin Whale",
                      img: "fin_whale",
                      isdm: true,
                      sdm: true,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Blue Whale",
                      img: "blue_whale",
                      isdm: true,
                      sdm: true,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Sperm Whale",
                      img: "sperm_whale",
                      isdm: true,
                      sdm: true,
                      audio: true,
                      photoM: false,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Minke Whale",
                      img: "minke_whale",
                      isdm: false,
                      sdm: true,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Sei Whale",
                      img: "sei_whale",
                      isdm: false,
                      sdm: false,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Killer Whale",
                      img: "orca",
                      isdm: false,
                      sdm: false,
                      audio: true,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                    {
                      name: "Other Cetaceans",
                      img: null,
                      isdm: false,
                      sdm: false,
                      audio: false,
                      photoM: true,
                      risk: true,
                      strike: true,
                    },
                  ].map((s) => (
                    <tr
                      key={s.name}
                      className="border-t border-ocean-900/30 transition-colors hover:bg-ocean-900/20"
                    >
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          {s.img ? (
                            <div className="relative h-7 w-10 shrink-0 overflow-hidden rounded">
                              <Image
                                src={`/species/${s.img}.jpg`}
                                alt={s.name}
                                fill
                                className="object-cover"
                                sizes="40px"
                              />
                            </div>
                          ) : (
                            <div className="h-7 w-10 shrink-0 rounded bg-ocean-800/30" />
                          )}
                          <span className="font-medium text-slate-200">
                            {s.name}
                          </span>
                        </div>
                      </td>
                      {(
                        [
                          "isdm",
                          "sdm",
                          "audio",
                          "photoM",
                          "risk",
                          "strike",
                        ] as const
                      ).map((col) => (
                        <td
                          key={col}
                          className="px-3 py-2 text-center"
                        >
                          {s[col] ? (
                            <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
                          ) : (
                            <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-800" />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Methodology */}
        {!loading && !error && rows.length > 0 && (
          <div className="mt-12 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-8 text-center">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-widest text-slate-500">
              Methodology
            </h3>
            <p className="mx-auto max-w-3xl text-sm leading-relaxed text-slate-400">
              The crosswalk bridges three naming systems:{" "}
              <span className="text-cyan-400">OBIS</span> scientific
              names (our primary key),{" "}
              <span className="text-amber-400">Nisi ISDM</span> short
              English names for the 4 modelled species, and{" "}
              <span className="text-rose-400">NMFS strike records</span>{" "}
              which use lowercase short names parsed from NOAA PDFs.
              Higher taxonomic ranks (genus, family, suborder, order) are
              included to capture sighting records identified only to a
              coarser level.
            </p>
            <p className="mx-auto mt-3 max-w-2xl text-xs text-slate-500">
              All taxa include WoRMS AphiaIDs for interoperability with
              OBIS and other marine biodiversity databases. Conservation
              priority follows ESA/IUCN status: critical = endangered
              with imminent extinction risk, high = endangered/vulnerable,
              moderate = species of concern, low = least concern.
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-xs text-slate-600">
              <span>{rows.length} total entries</span>
              <span className="text-slate-700">/</span>
              <span>{speciesCount} species-level</span>
              <span className="text-slate-700">/</span>
              <span>{familyCount} families</span>
              <span className="text-slate-700">/</span>
              <span>
                {
                  rows.filter((r) => r.nisi_species).length
                }{" "}
                with ISDM mapping
              </span>
              <span className="text-slate-700">/</span>
              <span>
                {
                  rows.filter((r) => r.strike_species).length
                }{" "}
                with strike mapping
              </span>
            </div>
            <div className="mt-4">
              <Link
                href="/map"
                className="inline-flex items-center gap-1.5 rounded-lg border border-ocean-700/40 bg-ocean-500/10 px-4 py-2 text-xs font-medium text-ocean-300 transition-all hover:bg-ocean-500/20"
              >
                <IconShield className="h-3.5 w-3.5" />
                View species on the Risk Map
              </Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function SpeciesCrosswalkPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-abyss-950 text-slate-100 flex items-center justify-center">
          <div className="text-slate-400">Loading...</div>
        </main>
      }
    >
      <SpeciesCrosswalkPageInner />
    </Suspense>
  );
}
