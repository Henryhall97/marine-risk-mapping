"use client";

import dynamic from "next/dynamic";

// SightingForm doesn't need WebGL, but lazy-load to keep the
// report page bundle small when navigating from the map.
const SightingForm = dynamic(
  () => import("@/components/SightingForm"),
  {
    ssr: false,
    loading: () => (
      <div className="flex justify-center py-20">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-400 border-t-transparent" />
      </div>
    ),
  },
);

export default function ReportPage() {
  return (
    <>
      <main className="min-h-screen overflow-y-auto bg-abyss-950 px-4 pb-12 pt-20">
        {/* Header */}
        <div className="mx-auto mb-8 max-w-3xl">
          <h1 className="text-2xl font-bold tracking-tight">
            🐋 Report a Whale Sighting
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Help improve whale–vessel collision risk models by reporting your
            observations. Upload a photo or audio recording and our AI will
            classify the species automatically. Location-aware risk context is
            returned for every report.
          </p>
        </div>

        <SightingForm />
      </main>
    </>
  );
}
