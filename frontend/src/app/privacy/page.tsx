"use client";

import Link from "next/link";
import { IconShield } from "@/components/icons/MarineIcons";

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
        <div className="mb-8 flex items-center gap-3">
          <IconShield className="h-8 w-8 text-bioluminescent-400" />
          <h1 className="text-3xl font-bold text-white">Privacy Policy</h1>
        </div>
        <p className="mb-6 text-sm text-slate-400">
          Last updated: March 2026
        </p>

        <div className="space-y-8 text-sm leading-relaxed text-slate-300">
          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              1. What Data We Collect
            </h2>
            <p>
              When you submit a sighting report, we collect the information you
              provide, including:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-slate-400">
              <li>
                <strong className="text-slate-300">Location data</strong> — GPS
                coordinates (from your device, manual entry, or map selection)
              </li>
              <li>
                <strong className="text-slate-300">Species identification</strong>{" "}
                — your species guess, confidence level, and AI model predictions
              </li>
              <li>
                <strong className="text-slate-300">Observation details</strong>{" "}
                — group size, behaviour, life stage, sea conditions, distance to
                animal, visibility, and observation platform
              </li>
              <li>
                <strong className="text-slate-300">Media</strong> — photographs
                and audio recordings you upload
              </li>
              <li>
                <strong className="text-slate-300">Account information</strong>{" "}
                — display name and email (if you create an account)
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              2. How We Use Your Data
            </h2>
            <ul className="list-inside list-disc space-y-1 text-slate-400">
              <li>
                <strong className="text-slate-300">
                  Marine conservation research
                </strong>{" "}
                — your sighting data helps scientists understand whale
                distribution, vessel collision risk, and habitat use
              </li>
              <li>
                <strong className="text-slate-300">
                  Scientific data sharing (OBIS)
                </strong>{" "}
                — verified sightings may be exported in Darwin Core Archive
                format and shared with the Ocean Biodiversity Information System
                (OBIS) for global marine research
              </li>
              <li>
                <strong className="text-slate-300">
                  AI model improvement
                </strong>{" "}
                — submitted photos and audio may be used to improve species
                classification accuracy
              </li>
              <li>
                <strong className="text-slate-300">Community engagement</strong>{" "}
                — sightings shared publicly help other observers and citizen
                scientists
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              3. Privacy Levels
            </h2>
            <p className="mb-2">
              You control how your sighting is shared when submitting a report:
            </p>
            <div className="space-y-3">
              <div className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 p-3">
                <p className="font-semibold text-teal-300">Private</p>
                <p className="text-slate-400">
                  Your sighting is recorded for scientific research only. It is
                  not visible on the community feed. Your name is never
                  associated publicly.
                </p>
              </div>
              <div className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 p-3">
                <p className="font-semibold text-teal-300">
                  Anonymous (Community, No Name)
                </p>
                <p className="text-slate-400">
                  Your sighting appears on the community feed but without your
                  name or profile. Other users can see the species, location,
                  and observation details, but not who submitted it.
                </p>
              </div>
              <div className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 p-3">
                <p className="font-semibold text-teal-300">
                  Public (Community with Name)
                </p>
                <p className="text-slate-400">
                  Your sighting appears on the community feed with your display
                  name and profile. This helps build your reputation as a
                  citizen scientist and allows other observers to recognise
                  your contributions.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              4. Location Data
            </h2>
            <p>
              GPS coordinates are essential for marine research. Location data
              is:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-slate-400">
              <li>
                Mapped to H3 hexagonal grid cells (~1.2 km resolution) for
                spatial analysis
              </li>
              <li>
                Used to compute collision risk scores and generate safety
                advisories
              </li>
              <li>
                Included in OBIS exports for verified sightings (coordinates are
                always shared with scientific databases, regardless of privacy
                level, as they are essential for conservation research)
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              5. Data Retention
            </h2>
            <p>
              Sighting data is retained indefinitely for long-term ecological
              monitoring. You may request deletion of your account and personal
              information (name, email), but anonymised sighting records will be
              preserved for research continuity.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              6. Third-Party Sharing
            </h2>
            <p>
              We share data only with scientific research organisations and
              databases:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-slate-400">
              <li>
                <strong className="text-slate-300">OBIS</strong> — Ocean
                Biodiversity Information System (verified sightings only)
              </li>
              <li>
                <strong className="text-slate-300">NOAA</strong> — Relevant
                strike or stranding reports may be forwarded to regional
                authorities
              </li>
            </ul>
            <p className="mt-2">
              We do not sell personal data to commercial entities.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              7. Your Rights
            </h2>
            <ul className="list-inside list-disc space-y-1 text-slate-400">
              <li>Change your privacy level on any submission at any time</li>
              <li>Delete your account and personal information</li>
              <li>Export your submission data</li>
              <li>
                Opt out of community features while continuing to contribute to
                research
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-white">
              8. Contact
            </h2>
            <p>
              For privacy inquiries or data requests, contact the project
              maintainers through the repository&apos;s issue tracker.
            </p>
          </section>

          <section className="rounded-lg border border-ocean-600/30 bg-ocean-500/10 p-4">
            <p className="text-xs text-slate-400">
              By submitting sighting reports, you agree to this privacy policy
              and consent to your observation data being used for marine
              conservation research. All data handling follows the{" "}
              <strong className="text-slate-300">CC-BY 4.0</strong> licence for
              scientific data sharing.
            </p>
          </section>
        </div>

        <div className="mt-8">
          <Link
            href="/report"
            className="inline-flex items-center gap-2 rounded-lg bg-ocean-600 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-500"
          >
            Back to Report Form
          </Link>
        </div>
      </main>
  );
}
