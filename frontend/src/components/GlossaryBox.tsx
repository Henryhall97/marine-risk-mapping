"use client";

import { type ReactNode, useState } from "react";
import { IconInfo } from "@/components/icons/MarineIcons";

export interface GlossaryTerm {
  term: string;
  definition: ReactNode;
}

/** Reusable definitions shared across insights pages. */
export const GLOSSARY: Record<string, GlossaryTerm> = {
  cell: {
    term: "What is a “cell”?",
    definition: (
      <>
        The coast is divided into a grid of{" "}
        <strong className="text-slate-200">H3 hexagons ≈ 1.2 km across</strong>{" "}
        (~4.7 km² each). Every score, count and map dot on this page refers to
        one of these cells, so &ldquo;111 cells&rdquo; ≈ 520 km² of ocean — the
        mini-maps show exactly where they sit.
      </>
    ),
  },
  riskScore: {
    term: "What does a risk score mean?",
    definition: (
      <>
        Risk is a{" "}
        <strong className="text-slate-200">
          0–100% relative ranking
        </strong>
        , not a probability of a strike. A cell at{" "}
        <strong className="text-slate-200">75%</strong> sits in the{" "}
        <strong className="text-slate-200">top quartile</strong> of collision
        risk across all assessed US waters; 50% is the median. It blends vessel
        traffic, whale presence, strike history and protection into one score.
      </>
    ),
  },
  protectionGap: {
    term: "What is the protection gap?",
    definition: (
      <>
        How <em>exposed</em> a cell is to regulation. A high protection gap
        (near 100%) means high-risk water with{" "}
        <strong className="text-slate-200">
          no active speed rule or protected-area coverage
        </strong>
        ; a low gap means it already falls inside an SMA, slow zone or MPA.
      </>
    ),
  },
  whaleProb: {
    term: "What is whale probability?",
    definition: (
      <>
        The modelled likelihood that{" "}
        <strong className="text-slate-200">any whale</strong> is present, from
        the ISDM+SDM habitat ensemble. It is a habitat-suitability score
        (0–100%), highest along feeding grounds and migratory corridors.
      </>
    ),
  },
};

/**
 * A compact "How to read this page" box that grounds the abstract numbers.
 * Collapsible so it doesn't dominate the page on repeat visits.
 */
export default function GlossaryBox({
  terms,
  defaultOpen = true,
}: {
  terms: GlossaryTerm[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mb-8 rounded-2xl border border-ocean-800/40 bg-ocean-950/20 p-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <IconInfo className="h-4 w-4 text-ocean-400" />
          How to read this page
        </span>
        <span className="text-xs text-slate-500">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {terms.map((t) => (
            <div key={t.term}>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ocean-400">
                {t.term}
              </dt>
              <dd className="mt-1 text-xs leading-relaxed text-slate-400">
                {t.definition}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
