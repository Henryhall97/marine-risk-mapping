"use client";

import dynamic from "next/dynamic";

// Deck.gl + MapLibre require browser APIs — disable SSR.
const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-screen items-center justify-center bg-abyss-950">
      <div className="text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-400 border-t-transparent" />
        <p className="mt-3 text-sm text-slate-400">Loading map…</p>
      </div>
    </div>
  ),
});

export default function MapPage() {
  return (
    <>
      <MapView />
    </>
  );
}
