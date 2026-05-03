"use client";

import Link from "next/link";
import { useAuth } from "../../contexts/AuthContext";
import { SonarPing } from "../../components/animations";
import ViolationForm from "../../components/ViolationForm";
import { IconShip, IconMap, IconUser } from "../../components/icons/MarineIcons";

export default function ReportVesselPage() {
  const { user, loading } = useAuth();

  return (
    <main className="min-h-screen overflow-y-auto bg-abyss-950 px-4 pb-16 pt-20">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              <IconShip className="mr-2 inline-block h-6 w-6 text-ocean-300" />
              Report Vessel Violation
            </h1>
            <Link
              href="/map"
              className="inline-flex items-center gap-2 rounded-lg border border-ocean-800/30 bg-ocean-500/10 px-4 py-2 text-sm font-semibold text-ocean-300 transition-all hover:border-ocean-500/40 hover:bg-ocean-500/20 hover:text-white"
            >
              <IconMap className="h-4 w-4" />
              View Risk Map
            </Link>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Report vessels observed speeding through active speed zones, entering
            marine protected areas, or suspected of disabling their AIS
            transponders. Reports are reviewed by the community and help improve
            whale–vessel collision risk data.
          </p>
        </div>

        {loading ? (
          <div className="flex flex-col items-center gap-2 py-20">
            <SonarPing size={64} ringCount={3} active />
          </div>
        ) : !user ? (
          <div className="flex flex-col items-center gap-5 rounded-2xl border border-ocean-800/40 bg-abyss-900/60 px-8 py-14 text-center">
            <IconUser className="h-10 w-10 text-slate-500" />
            <div>
              <p className="text-base font-semibold text-slate-200">Sign in to submit a report</p>
              <p className="mt-1.5 text-sm text-slate-500">
                Violation reports are tied to your account so the community can
                verify submissions and build your reputation score.
              </p>
            </div>
            <div className="flex gap-3">
              <Link
                href="/auth?next=/report-vessel"
                className="rounded-xl bg-ocean-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ocean-500"
              >
                Sign in
              </Link>
              <Link
                href="/auth?next=/report-vessel"
                className="rounded-xl border border-ocean-700/40 px-6 py-2.5 text-sm font-semibold text-slate-300 transition-colors hover:border-ocean-500/60 hover:text-white"
              >
                Create account
              </Link>
            </div>
          </div>
        ) : (
          <ViolationForm />
        )}
      </div>
    </main>
  );
}
