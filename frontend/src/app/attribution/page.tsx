"use client";

import Link from "next/link";
import Nav from "@/components/Nav";

const US_GOV_SOURCES = [
  {
    name: "MarineCadastre AIS Vessel Traffic",
    url: "https://marinecadastre.gov/",
    org: "Bureau of Ocean Energy Management (BOEM) / NOAA",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Ship Strike Records",
    url: "https://www.fisheries.noaa.gov/inport/item/23127",
    org: "NOAA Fisheries",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Marine Protected Areas Inventory",
    url: "https://marineprotectedareas.noaa.gov/",
    org: "NOAA National MPA Center",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Seasonal Management Areas",
    url: "https://www.fisheries.noaa.gov/",
    org: "NOAA Fisheries, 50 CFR § 224.105",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Biologically Important Areas (CetMap)",
    url: "https://cetsound.noaa.gov/biologically-important-areas",
    org: "NOAA Fisheries",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Critical Habitat Designations",
    url: "https://www.fisheries.noaa.gov/",
    org: "NMFS / NOAA Fisheries",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Shipping Lanes & TSS",
    url: "https://nauticalcharts.noaa.gov/",
    org: "NOAA Office of Coast Survey",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Right Whale Slow Zones / DMAs",
    url: "https://www.fisheries.noaa.gov/",
    org: "NOAA Fisheries",
    license: "Public Domain (US Gov)",
  },
  {
    name: "Sea Surface Temperature (OISST v2.1)",
    url: "https://www.ncei.noaa.gov/products/optimum-interpolation-sst",
    org: "NOAA National Centers for Environmental Information",
    license: "Public Domain (US Gov)",
  },
];

export default function AttributionPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-gradient-to-b from-abyss-950 to-abyss-900 px-4 pt-20 pb-16 text-slate-300">
        <div className="mx-auto max-w-4xl">
          <h1 className="mb-2 text-3xl font-bold text-white">
            Data Sources &amp; Attribution
          </h1>
          <p className="mb-10 text-sm text-slate-400">
            WhaleWatch uses publicly available scientific datasets. We are
            grateful to the organisations below for making their data
            accessible. See our full{" "}
            <Link
              href="https://github.com/henryhall/marine_risk_mapping/blob/main/CREDITS.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ocean-400 underline hover:text-ocean-300"
            >
              CREDITS.md
            </Link>{" "}
            for detailed license information.
          </p>

          {/* ── Copernicus (mandatory) ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              E.U. Copernicus Marine Service
            </h2>
            <p className="mb-4 text-sm leading-relaxed">
              Ocean covariate data (mixed layer depth, sea level anomaly,
              and primary production) is provided by the Copernicus Marine
              Service. This study has been conducted using E.U. Copernicus
              Marine Service Information.{" "}
              <a
                href="https://marine.copernicus.eu/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-ocean-400 underline hover:text-ocean-300"
              >
                https://marine.copernicus.eu/
              </a>
            </p>
            <div className="text-xs text-slate-500">
              <p>
                Global Ocean Physics Reanalysis —{" "}
                <a
                  href="https://doi.org/10.48670/moi-00021"
                  className="underline"
                >
                  doi:10.48670/moi-00021
                </a>
              </p>
              <p>
                Global Ocean Biogeochemistry Hindcast —{" "}
                <a
                  href="https://doi.org/10.48670/moi-00019"
                  className="underline"
                >
                  doi:10.48670/moi-00019
                </a>
              </p>
            </div>
          </section>

          {/* ── CMIP6 (mandatory) ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              CMIP6 Climate Projections
            </h2>
            <p className="mb-4 text-sm leading-relaxed">
              Climate-projected ocean covariates are derived from CMIP6
              model outputs (SSP2-4.5 and SSP5-8.5 scenarios, 2030s–2080s)
              distributed via the Copernicus Climate Data Store (
              <a
                href="https://doi.org/10.24381/cds.c866074c"
                className="text-ocean-400 underline"
              >
                doi:10.24381/cds.c866074c
              </a>
              ) under CC-BY 4.0.
            </p>
            <p className="mb-4 text-xs leading-relaxed text-slate-400">
              We acknowledge the World Climate Research Programme, which,
              through its Working Group on Coupled Modelling, coordinated
              and promoted CMIP6. We thank the climate modelling groups for
              producing and making available their model output, the Earth
              System Grid Federation (ESGF) for archiving the data and
              providing access, and the multiple funding agencies who
              support CMIP6 and ESGF.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-ocean-800/30 text-left text-slate-400">
                    <th className="py-1 pr-4">Model</th>
                    <th className="py-1">Institution</th>
                  </tr>
                </thead>
                <tbody className="text-slate-500">
                  {[
                    ["IPSL-CM6A-LR", "Institut Pierre-Simon Laplace, France"],
                    ["MPI-ESM1-2-LR", "Max Planck Institute for Meteorology, Germany"],
                    ["UKESM1-0-LL", "Met Office Hadley Centre / NERC, UK"],
                    ["GFDL-ESM4", "NOAA Geophysical Fluid Dynamics Lab, USA"],
                    ["NorESM2-LM", "NorESM Climate Modelling Consortium, Norway"],
                  ].map(([model, inst]) => (
                    <tr key={model} className="border-b border-ocean-800/10">
                      <td className="py-1 pr-4 font-mono">{model}</td>
                      <td className="py-1">{inst}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── OBIS ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              OBIS Cetacean Sightings
            </h2>
            <p className="text-sm leading-relaxed">
              OBIS (2024). Ocean Biodiversity Information System.
              Intergovernmental Oceanographic Commission of UNESCO.{" "}
              <a
                href="https://obis.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-ocean-400 underline hover:text-ocean-300"
              >
                www.obis.org
              </a>
              . Accessed 2024.
            </p>
          </section>

          {/* ── GEBCO ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              GEBCO Bathymetry
            </h2>
            <p className="text-sm leading-relaxed">
              GEBCO Compilation Group (2023). GEBCO 2023 Grid.{" "}
              <a
                href="https://doi.org/10.5285/f98b053b-0cbc-6c23-e053-6c86abc0af7b"
                className="text-ocean-400 underline"
              >
                doi:10.5285/f98b053b-0cbc-6c23-e053-6c86abc0af7b
              </a>
            </p>
          </section>

          {/* ── US Government sources ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              US Government Data (Public Domain)
            </h2>
            <p className="mb-4 text-xs text-slate-400">
              Works produced by the US Federal Government are in the
              public domain under 17 U.S.C. § 105.
            </p>
            <div className="space-y-2">
              {US_GOV_SOURCES.map((s) => (
                <div key={s.name} className="flex items-start gap-2 text-xs">
                  <span className="mt-0.5 text-ocean-500">●</span>
                  <div>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-slate-300 underline decoration-ocean-700/40 hover:text-ocean-300"
                    >
                      {s.name}
                    </a>
                    <span className="text-slate-500"> — {s.org}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Nisi ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              Nisi et al. 2024 — Global Whale-Ship Collision Risk
            </h2>
            <p className="text-sm leading-relaxed">
              Nisi, A.C., Becker, E.A., Pinsky, M.L., &amp; Palumbi, S.R.
              (2024). Ship collision risk threatens whales across the
              world&apos;s oceans. <em>Science</em>, 386(6724), 870–875.{" "}
              <a
                href="https://doi.org/10.1126/science.adp1950"
                className="text-ocean-400 underline"
              >
                doi:10.1126/science.adp1950
              </a>
            </p>
          </section>

          {/* ── Map tiles ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              Map Tiles
            </h2>
            <p className="text-sm leading-relaxed">
              © <a href="https://carto.com/" className="text-ocean-400 underline">CARTO</a>{" "}
              Dark Matter basemap · Map data © <a href="https://www.openstreetmap.org/copyright" className="text-ocean-400 underline">OpenStreetMap</a>{" "}
              contributors.
            </p>
          </section>

          {/* ── 3D models ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              3D Whale Models
            </h2>
            <p className="text-sm leading-relaxed">
              3D whale models by{" "}
              <a
                href="https://sketchfab.com/Nestaeric"
                target="_blank"
                rel="noopener noreferrer"
                className="text-ocean-400 underline"
              >
                Nestaeric
              </a>{" "}
              on Sketchfab. Blue whale, humpback whale, sperm whale, and
              killer whale models used under the Sketchfab download
              license.
            </p>
          </section>

          {/* ── NOAA Species Illustrations ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              Species Illustrations
            </h2>
            <p className="mb-3 text-sm leading-relaxed">
              Cetacean species illustrations in the identification wizard are
              sourced from{" "}
              <a
                href="https://www.fisheries.noaa.gov/species-directory/marine-mammals"
                target="_blank"
                rel="noopener noreferrer"
                className="text-ocean-400 underline hover:text-ocean-300"
              >
                NOAA Fisheries Species Directory
              </a>
              . These illustrations are used for educational and conservation
              purposes on this non-commercial platform.
            </p>
            <div className="space-y-2 text-xs text-slate-400">
              <p>
                <span className="font-medium text-slate-300">
                  General credit:
                </span>{" "}
                NOAA Fisheries
              </p>
              <p>
                <span className="font-medium text-slate-300">
                  Select illustrations:
                </span>{" "}
                Jack Hornady / NOAA Fisheries (Dall&apos;s porpoise,
                Atlantic spotted dolphin)
              </p>
              <p>
                <span className="font-medium text-slate-300">
                  NARW infographics:
                </span>{" "}
                NOAA Fisheries Office of Protected Resources — identification
                features, common behaviors, and right whale vs. humpback
                comparison guides
              </p>
              <p className="text-slate-500">
                NOAA Fisheries grants permission to use graphics on a
                case-by-case basis. Permission has been requested for these
                illustrations. Graphics are not redistributed outside this
                platform.
              </p>
            </div>
          </section>

          {/* ── Wikimedia Commons ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              Wikimedia Commons
            </h2>
            <p className="mb-3 text-sm leading-relaxed">
              Cetacean anatomy diagrams in the identification wizard are
              sourced from Wikimedia Commons and used under their respective
              Creative Commons licenses.
            </p>
            <div className="space-y-2 text-xs text-slate-400">
              <p>
                <span className="font-medium text-slate-300">
                  Dolphin Anatomy Diagram:
                </span>{" "}
                by WikipedianProlific &amp; Wilfredor,{" "}
                <a
                  href="https://creativecommons.org/licenses/by-sa/4.0/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400 underline"
                >
                  CC BY-SA 4.0
                </a>
                , via{" "}
                <a
                  href="https://commons.wikimedia.org/wiki/File:Dolphin_Anatomy.svg"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400 underline"
                >
                  Wikimedia Commons
                </a>
              </p>
              <p>
                <span className="font-medium text-slate-300">
                  Orca Anatomy Diagram:
                </span>{" "}
                by Petruss,{" "}
                <a
                  href="https://creativecommons.org/publicdomain/zero/1.0/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400 underline"
                >
                  CC0 (public domain)
                </a>
                , via{" "}
                <a
                  href="https://commons.wikimedia.org/wiki/File:Orca_anatomy.svg"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400 underline"
                >
                  Wikimedia Commons
                </a>
              </p>
              <p>
                <span className="font-medium text-slate-300">
                  Baleen vs Toothed Whale Comparison:
                </span>{" "}
                by Chris huh, translated from Italian to English,{" "}
                <a
                  href="https://creativecommons.org/publicdomain/zero/1.0/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400 underline"
                >
                  Public Domain
                </a>
                , via{" "}
                <a
                  href="https://commons.wikimedia.org/wiki/File:Toothed_Whale_and_Baleen_Whale_Physical_Characteristics_it.svg"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ocean-400 underline"
                >
                  Wikimedia Commons
                </a>
              </p>
            </div>
          </section>

          {/* ── Audio & Photo training data ── */}
          <section className="mb-10 rounded-xl border border-ocean-700/30 bg-ocean-900/20 p-6">
            <h2 className="mb-3 text-lg font-semibold text-ocean-400">
              ML Training Data
            </h2>
            <div className="space-y-3 text-sm leading-relaxed">
              <p>
                <strong className="text-slate-300">Whale audio:</strong>{" "}
                Watkins Marine Mammal Sound Database (WHOI) + Zenodo
                CC-BY 4.0 datasets (
                <a
                  href="https://doi.org/10.5281/zenodo.3624145"
                  className="text-ocean-400 underline"
                >
                  3624145
                </a>
                ,{" "}
                <a
                  href="https://doi.org/10.5281/zenodo.13880107"
                  className="text-ocean-400 underline"
                >
                  13880107
                </a>
                ,{" "}
                <a
                  href="https://doi.org/10.5281/zenodo.10719537"
                  className="text-ocean-400 underline"
                >
                  10719537
                </a>
                ).
              </p>
              <p>
                <strong className="text-slate-300">Whale photos:</strong>{" "}
                Happywhale Kaggle dataset — used under
                competition/academic/non-commercial terms. Images are not
                redistributed.
              </p>
            </div>
          </section>

          <p className="text-center text-xs text-slate-500">
            See{" "}
            <Link
              href="https://github.com/henryhall/marine_risk_mapping/blob/main/CREDITS.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ocean-400 underline"
            >
              CREDITS.md
            </Link>{" "}
            for detailed license terms, DOIs, and compliance notes.
          </p>
        </div>
      </main>
    </>
  );
}
