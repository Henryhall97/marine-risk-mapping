"use client";

import { Suspense } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useAuth } from "@/contexts/AuthContext";
import { useSearchParams } from "next/navigation";
import { SonarPing } from "@/components/animations";
import { IconWhale, IconMap, IconUser } from "@/components/icons/MarineIcons";

// SightingForm doesn't need WebGL, but lazy-load to keep the
// report page bundle small when navigating from the map.
const SightingForm = dynamic(
  () => import("@/components/SightingForm"),
  {
    ssr: false,
    loading: () => (
      <div className="flex flex-col items-center gap-2 py-20">
        <SonarPing size={72} ringCount={3} active />
        <span className="text-xs text-ocean-400/70">Loading form…</span>
      </div>
    ),
  },
);

function ReportPageInner() {
  const { user, loading } = useAuth();
  const searchParams = useSearchParams();
  const eventId = searchParams.get("event_id") ?? undefined;
  const vesselId = searchParams.get("vessel_id") ?? undefined;
  const initialSpecies = searchParams.get("species") ?? undefined;

  return (
    <>
      <main className="min-h-screen overflow-y-auto bg-abyss-950 px-4 pb-12 pt-20">
        {/* Header */}
        <div className="mx-auto mb-8 max-w-3xl">
          <div className="flex items-center justify-between">
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
              <IconWhale className="h-5 w-5" /> Report a Whale Interaction
            </h1>
            <Link
              href="/map"
              className="flex items-center gap-1.5 rounded-lg border border-ocean-800/30 bg-ocean-500/10 px-4 py-2 text-sm font-semibold text-ocean-300 transition-all hover:border-ocean-500/40 hover:bg-ocean-500/20 hover:text-white"
            >
              <IconMap className="h-4 w-4" />
              View Risk Map
            </Link>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Help improve whale–vessel collision risk models by reporting your
            observations. Upload a photo or audio recording and our AI will
            classify the species automatically. Location-aware risk context is
            returned for every report.
          </p>
        </div>

        {loading ? (
          <div className="flex flex-col items-center gap-2 py-20">
            <SonarPing size={64} ringCount={3} active />
          </div>
        ) : !user ? (
          <div className="mx-auto max-w-3xl">
            <div className="flex flex-col items-center gap-5 rounded-2xl border border-ocean-800/40 bg-abyss-900/60 px-8 py-14 text-center">
              <IconUser className="h-10 w-10 text-slate-500" />
              <div>
                <p className="text-base font-semibold text-slate-200">Sign in to submit a report</p>
                <p className="mt-1.5 text-sm text-slate-500">
                  Community reports are tied to your account so the community can
                  verify sightings and build your reputation score.
                </p>
              </div>
              <div className="flex gap-3">
                <Link
                  href="/auth?next=/report"
                  className="rounded-xl bg-ocean-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ocean-500"
                >
                  Sign in
                </Link>
                <Link
                  href="/auth?next=/report"
                  className="rounded-xl border border-ocean-700/40 px-6 py-2.5 text-sm font-semibold text-slate-300 transition-colors hover:border-ocean-500/60 hover:text-white"
                >
                  Create account
                </Link>
              </div>
            </div>
          </div>
        ) : (
          <SightingForm
            key={`${eventId ?? ""}_${vesselId ?? ""}_${initialSpecies ?? ""}`}
            eventId={eventId}
            vesselId={vesselId}
            initialSpecies={initialSpecies}
          />
        )}
      </main>
    </>
  );
}

export default function ReportPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-abyss-950 text-slate-100 flex items-center justify-center">
          <div className="text-slate-400">Loading…</div>
        </main>
      }
    >
      <ReportPageInner />
    </Suspense>
  );
}
