"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { SectionHeading } from "../_field";

const EventsPanel = dynamic(() => import("@/components/EventsPanel"), {
  ssr: false,
  loading: () => (
    <div className="flex h-48 items-center justify-center text-xs text-ocean-400/70">
      Loading expeditions…
    </div>
  ),
});

export default function PrototypeEventsPage() {
  return (
    <div className="min-h-screen bg-abyss-950 text-slate-200">
      <div className="mx-auto max-w-7xl px-6 pb-24 pt-10 sm:px-10">
        <Link
          href="/community"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-ocean-300 transition-colors hover:text-bioluminescent-400"
        >
          ← Back to the field station
        </Link>

        <div className="mt-8">
          <SectionHeading
            eyebrow="The expedition board"
            title="Survey events & expeditions"
            hint="Join a community survey, run your own, or browse what's afoot on the water"
          />
        </div>

        <div className="mt-10">
          <EventsPanel />
        </div>
      </div>
    </div>
  );
}
