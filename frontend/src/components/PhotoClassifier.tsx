"use client";

import { useState, useRef, type ChangeEvent } from "react";
import Image from "next/image";
import { API_BASE } from "@/lib/config";
import { IconCamera, IconPin } from "@/components/icons/MarineIcons";
import { SPECIES_PHOTOS, SPECIES_ID_TIPS } from "@/components/IDHelper";

/* ── Confused-species pairs ─────────────────────────────────
   For each model species, the 2–3 most commonly confused
   look-alikes, with the key distinguishing field mark.
   Sources: model confusion matrix + field guide literature.
   ─────────────────────────────────────────────────────── */

interface LookAlike {
  species: string;
  photoKey: string;
  distinction: string;
}

const LOOK_ALIKES: Record<string, LookAlike[]> = {
  right_whale: [
    { species: "bowhead", photoKey: "bowhead", distinction: "Bowhead has no callosities and a white chin patch; right whale has rough white callosities on head." },
    { species: "humpback_whale", photoKey: "humpback_whale", distinction: "Humpback has long white pectoral fins and knobby tubercles; right whale has no dorsal fin." },
  ],
  humpback_whale: [
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin whale has a tall sickle dorsal and rarely shows flukes; humpback lifts broad patterned flukes high." },
    { species: "minke_whale", photoKey: "minke_whale", distinction: "Minke is much smaller (7–10 m) with a pointed snout; humpback has knobby head tubercles and very long flippers." },
  ],
  fin_whale: [
    { species: "blue_whale", photoKey: "blue_whale", distinction: "Blue is mottled blue-grey with tiny dorsal far back; fin has asymmetric jaw (right side white) and taller dorsal." },
    { species: "sei_whale", photoKey: "sei_whale", distinction: "Sei has a single head ridge and surfaces at a shallow angle; fin has asymmetric jaw colouring (white right lower jaw)." },
    { species: "humpback_whale", photoKey: "humpback_whale", distinction: "Humpback has long pectoral fins and knobby head; fin whale is sleeker with a pointed rostrum." },
  ],
  blue_whale: [
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin has asymmetric jaw (right side white) and taller dorsal fin; blue has U-shaped head and mottled blue-grey skin." },
    { species: "sei_whale", photoKey: "sei_whale", distinction: "Sei is smaller (15–18 m) with a taller dorsal; blue is the largest animal ever (up to 30 m), tiny dorsal far back." },
  ],
  minke_whale: [
    { species: "sei_whale", photoKey: "sei_whale", distinction: "Sei is much larger (15–18 m) and lacks white flipper bands; minke has distinctive white bands on flippers." },
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin is much larger (18–25 m) with asymmetric jaw; minke is small (7–10 m) with a pointed triangular snout." },
  ],
  sei_whale: [
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin has asymmetric jaw colouring; sei has a single central head ridge (vs fin’s more prominent ridge)." },
    { species: "blue_whale", photoKey: "blue_whale", distinction: "Blue is much larger with mottled blue-grey colouring; sei is uniformly dark grey." },
    { species: "minke_whale", photoKey: "minke_whale", distinction: "Minke is smaller (7–10 m) with white flipper bands; sei is larger with no flipper markings." },
  ],
  killer_whale: [
    { species: "dalls_porpoise", photoKey: "dalls_porpoise", distinction: "Dall’s porpoise has white flank patches but is much smaller (2 m) with a small triangular dorsal." },
    { species: "pilot_whale", photoKey: "pilot_whale", distinction: "Pilot whale is all dark with a rounded melon head; orca has striking black-and-white pattern and tall dorsal." },
  ],
  other_cetacean: [],
};

/* Map model species keys to photo keys for the prediction species */
const MODEL_PHOTO_KEY: Record<string, string> = {
  right_whale: "right_whale",
  humpback_whale: "humpback_whale",
  fin_whale: "fin_whale",
  blue_whale: "blue_whale",
  minke_whale: "minke_whale",
  sei_whale: "sei_whale",
  killer_whale: "orca",
  other_cetacean: "",
};

/* ── Types ───────────────────────────────────────────────── */

interface PhotoClassification {
  predicted_species: string;
  confidence: number;
  probabilities: Record<string, number>;
}

interface PhotoRiskContext {
  h3_cell: number;
  cell_lat: number;
  cell_lon: number;
  risk_score: number | null;
  risk_category: string | null;
  traffic_score: number | null;
  cetacean_score: number | null;
}

interface PhotoResult {
  classification: PhotoClassification;
  risk_context: PhotoRiskContext | null;
  gps_source: string | null;
}

/* ── Helpers ─────────────────────────────────────────────── */

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const hue = Math.round(120 - value * 120);
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 text-xs text-slate-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${pct}%`,
            backgroundColor: `hsl(${hue}, 80%, 50%)`,
          }}
        />
      </div>
      <span className="w-10 text-right text-xs text-slate-300">{pct}%</span>
    </div>
  );
}

function SpeciesBar({
  species,
  prob,
  isTop,
}: {
  species: string;
  prob: number;
  isTop: boolean;
}) {
  const pct = Math.round(prob * 100);
  return (
    <div className="flex items-center gap-2">
      <span
        className={`w-32 truncate text-xs ${isTop ? "font-semibold text-bioluminescent-400" : "text-slate-400"}`}
      >
        {species.replace(/_/g, " ")}
      </span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
        <div
          className={`h-full rounded-full transition-all ${isTop ? "bg-ocean-500" : "bg-slate-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span
        className={`w-10 text-right text-xs ${isTop ? "font-semibold text-bioluminescent-400" : "text-slate-300"}`}
      >
        {pct}%
      </span>
    </div>
  );
}

/* ── Component ───────────────────────────────────────────── */

export default function PhotoClassifier() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<PhotoResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showAllProbs, setShowAllProbs] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function applyFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
    if (f) {
      const reader = new FileReader();
      reader.onload = () => setPreview(reader.result as string);
      reader.readAsDataURL(f);
    } else {
      setPreview(null);
    }
  }

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    applyFile(e.target.files?.[0] ?? null);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (result) return;
    applyFile(e.dataTransfer.files[0] ?? null);
  }

  function handleGeolocate() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(6));
        setLon(pos.coords.longitude.toFixed(6));
      },
      (err) => setError(`Geolocation error: ${err.message}`),
      { enableHighAccuracy: true },
    );
  }

  async function handleClassify() {
    if (!file) return;
    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file);
      if (lat) form.append("lat", lat);
      if (lon) form.append("lon", lon);

      const res = await fetch(`${API_BASE}/api/v1/photo/classify`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Server error ${res.status}`);
      }

      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Classification failed");
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setLat("");
    setLon("");
    setShowAllProbs(false);
  }

  const sortedProbs = result
    ? Object.entries(result.classification.probabilities).sort(([, a], [, b]) => b - a)
    : [];

  return (
    <div className="space-y-6">
      {/* Upload area */}
      <div
        onClick={() => !result && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!result) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`group cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
          dragOver
            ? "border-bioluminescent-500/60 bg-ocean-900/20"
            : preview
            ? "border-blue-500/30 bg-abyss-900/60"
            : "border-ocean-800 hover:border-blue-500/50 hover:bg-abyss-800/50"
        }`}
      >
        {preview ? (
          <div className="space-y-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={preview}
              alt="Upload preview"
              className="mx-auto max-h-64 rounded-xl object-contain shadow-lg"
            />
            <p className="text-xs text-slate-400">{file?.name}</p>
            {!result && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleReset();
                }}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Remove
              </button>
            )}
          </div>
        ) : (
          <>
            <IconCamera className="mb-3 h-10 w-10 text-slate-400" />
            <p className="text-sm font-medium text-slate-300">
              Drop a whale photo or click to browse
            </p>
            <p className="mt-2 text-xs text-slate-500">
              JPG, PNG, WEBP · Max 20 MB
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/tiff"
          onChange={handleFile}
          className="hidden"
        />
      </div>

      {/* GPS (optional) */}
      {file && !result && (
        <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <IconPin className="h-3.5 w-3.5" /> Location (optional)
            </h4>
            <button
              type="button"
              onClick={handleGeolocate}
              className="rounded-lg border border-blue-600/40 bg-ocean-600/20 px-3 py-1 text-xs font-medium text-bioluminescent-400 transition-colors hover:bg-ocean-600/30"
            >
              Use GPS
            </button>
          </div>
          <p className="mb-3 text-[11px] text-slate-500">
            Provide coordinates to get H3 collision risk context alongside the
            species prediction. EXIF GPS is also extracted automatically.
          </p>
          <div className="flex gap-3">
            <input
              type="number"
              step="any"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              placeholder="Latitude"
              className="flex-1 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-ocean-500 focus:outline-none"
            />
            <input
              type="number"
              step="any"
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              placeholder="Longitude"
              className="flex-1 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-ocean-500 focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Classify button */}
      {file && !result && (
        <button
          onClick={handleClassify}
          disabled={submitting}
          className="w-full rounded-xl bg-ocean-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-ocean-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Classifying…
            </span>
          ) : (
            "Classify Species"
          )}
        </button>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-700/40 bg-red-950/40 px-4 py-3">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
          </svg>
          <p className="flex-1 text-sm text-red-300">{error}</p>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
            className="shrink-0 text-red-500 transition-colors hover:text-red-300"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-5">
          {/* Top prediction */}
          <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-ocean-600/20 px-4 py-3 text-center">
                <p className="text-2xl font-bold text-bioluminescent-400">
                  {Math.round(result.classification.confidence * 100)}%
                </p>
                <p className="text-[10px] text-slate-400">confidence</p>
              </div>
              <div>
                <p className="text-lg font-bold capitalize text-white">
                  {result.classification.predicted_species.replace(/_/g, " ")}
                </p>
                <p className="text-xs text-slate-500">
                  EfficientNet-B4 · 8 species classes
                </p>
              </div>
            </div>
          </div>

          {/* Runner-up predictions & full breakdown */}
          {sortedProbs.length > 1 && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Runner-up Predictions
              </h4>
              <div className="space-y-2.5">
                {sortedProbs.slice(1, 3).map(([sp, p], i) => {
                  const gap = sortedProbs[0][1] - p;
                  const isClose = gap < 0.15;
                  return (
                    <div key={sp}>
                      <div className="flex items-center gap-2">
                        <span className="w-5 text-xs font-medium text-slate-500">
                          {i + 2}.
                        </span>
                        <span
                          className={`w-32 truncate text-xs ${
                            isClose
                              ? "font-semibold text-amber-300"
                              : "font-medium text-slate-300"
                          }`}
                        >
                          {sp.replace(/_/g, " ")}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
                          <div
                            className={`h-full rounded-full transition-all ${
                              isClose ? "bg-amber-500" : "bg-slate-500"
                            }`}
                            style={{ width: `${Math.round(p * 100)}%` }}
                          />
                        </div>
                        <span
                          className={`w-10 text-right text-xs ${
                            isClose
                              ? "font-semibold text-amber-300"
                              : "text-slate-400"
                          }`}
                        >
                          {Math.round(p * 100)}%
                        </span>
                      </div>
                      {isClose && (
                        <p className="ml-7 mt-0.5 text-[10px] text-amber-400/70">
                          Close margin — only {Math.round(gap * 100)}pp behind
                          top pick
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* Collapsible remaining species */}
              {sortedProbs.length > 3 && (
                <div className="mt-3 border-t border-ocean-800/30 pt-3">
                  <button
                    type="button"
                    onClick={() => setShowAllProbs((v) => !v)}
                    className="flex w-full items-center gap-1.5 text-xs text-ocean-400 transition-colors hover:text-ocean-300"
                  >
                    <svg
                      className={`h-3 w-3 transition-transform ${
                        showAllProbs ? "rotate-90" : ""
                      }`}
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        fillRule="evenodd"
                        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {showAllProbs ? "Hide" : "Show"} remaining{" "}
                    {sortedProbs.length - 3} species
                  </button>
                  {showAllProbs && (
                    <div className="mt-2 space-y-1.5">
                      {sortedProbs.slice(3).map(([sp, p]) => (
                        <SpeciesBar
                          key={sp}
                          species={sp}
                          prob={p}
                          isTop={false}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Similar species comparison */}
          {(() => {
            const predicted = result.classification.predicted_species;
            const alikes = LOOK_ALIKES[predicted] ?? [];
            if (alikes.length === 0) return null;
            const predPhotoKey = MODEL_PHOTO_KEY[predicted];
            const predTip = SPECIES_ID_TIPS[predPhotoKey] ?? SPECIES_ID_TIPS[predicted] ?? null;
            return (
              <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Compare with Similar Species
                </h4>
                <p className="mb-4 text-[11px] text-slate-500">
                  Check these commonly confused look-alikes against your photo.
                </p>

                {/* Predicted species card */}
                <div className="mb-4 rounded-lg border border-bioluminescent-400/30 bg-ocean-900/30 p-3">
                  <div className="flex gap-3">
                    {predPhotoKey && (
                      <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-abyss-800">
                        <Image
                          src={`/species/${predPhotoKey}.jpg`}
                          alt={predicted}
                          fill
                          className="object-cover"
                          sizes="64px"
                        />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold capitalize text-bioluminescent-400">
                        {predicted.replace(/_/g, " ")}
                        <span className="ml-2 text-[10px] font-normal text-slate-500">
                          Model prediction
                        </span>
                      </p>
                      {predTip && (
                        <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-400">
                          {predTip}
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Look-alike cards */}
                <div className="space-y-3">
                  {alikes.map((la) => {
                    const laPhotoKey =
                      SPECIES_PHOTOS[la.species] ?? la.photoKey;
                    return (
                      <div
                        key={la.species}
                        className="rounded-lg border border-ocean-800/40 bg-abyss-800/40 p-3"
                      >
                        <div className="flex gap-3">
                          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-abyss-800">
                            <Image
                              src={`/species/${laPhotoKey}.jpg`}
                              alt={la.species}
                              fill
                              className="object-cover"
                              sizes="64px"
                            />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="flex items-center gap-2 text-xs font-medium capitalize text-slate-200">
                              {la.species.replace(/_/g, " ")}
                              <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-amber-400">
                                Easily mistaken
                              </span>
                            </p>
                            <p className="mt-1 text-[11px] leading-relaxed text-amber-300/80">
                              {la.distinction}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}

          {/* Risk context */}
          {result.risk_context && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                H3 Cell Risk Context
              </h4>
              {result.risk_context.risk_category && (
                <p className="mb-3 text-sm">
                  Category:{" "}
                  <strong className="text-white">
                    {result.risk_context.risk_category}
                  </strong>
                </p>
              )}
              <div className="space-y-2">
                <ScoreBar
                  label="Overall"
                  value={result.risk_context.risk_score}
                />
                <ScoreBar
                  label="Traffic"
                  value={result.risk_context.traffic_score}
                />
                <ScoreBar
                  label="Cetacean"
                  value={result.risk_context.cetacean_score}
                />
              </div>
            </div>
          )}

          {/* Try again */}
          <button
            onClick={handleReset}
            className="w-full rounded-xl border border-ocean-800 px-6 py-3 text-sm font-semibold text-slate-200 transition-colors hover:bg-abyss-800"
          >
            Classify Another Photo
          </button>
        </div>
      )}
    </div>
  );
}
