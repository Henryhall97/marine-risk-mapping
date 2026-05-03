"use client";

import { useState, useRef, useMemo, type ChangeEvent } from "react";
import Image from "next/image";
import dynamic from "next/dynamic";
import { API_BASE } from "@/lib/config";
import { IconMusic, IconMicrophone } from "@/components/icons/MarineIcons";
import { SPECIES_PHOTOS, SPECIES_ID_TIPS } from "@/components/IDHelper";

const AudioWaveform = dynamic(
  () => import("@/components/AudioWaveform"),
  { ssr: false },
);

/* ── Confused-species pairs (acoustic context) ──────────────
   Key species the model tends to confuse, plus the auditory
   distinction.  Mirrors the PhotoClassifier pattern.
   ──────────────────────────────────────────────────────── */

interface LookAlike {
  species: string;
  photoKey: string;
  distinction: string;
}

const LOOK_ALIKES: Record<string, LookAlike[]> = {
  right_whale: [
    { species: "humpback_whale", photoKey: "humpback", distinction: "Humpback calls are complex songs lasting minutes; right whale up-calls are short (~1 s) sweeping tones." },
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin whale 20 Hz pulses are regular, low, and brief; right whale calls sweep upward in frequency." },
  ],
  humpback_whale: [
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin whale produces repetitive 20 Hz pulses; humpback song has varied phrases with frequency modulation." },
    { species: "minke_whale", photoKey: "minke_whale", distinction: "Minke boings are mechanical and repetitive; humpback song has complex melodic phrases." },
  ],
  fin_whale: [
    { species: "blue_whale", photoKey: "blue_whale", distinction: "Blue whale calls are extremely low (10–25 Hz) and long; fin whale 20 Hz pulses are shorter and more regular." },
    { species: "humpback_whale", photoKey: "humpback", distinction: "Humpback has complex song phrases; fin whale produces simple repetitive 20 Hz pulses." },
  ],
  blue_whale: [
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin whale pulses are around 20 Hz and brief; blue whale calls are very low infrasound (10–25 Hz) with longer duration." },
    { species: "sei_whale", photoKey: "sei_whale", distinction: "Sei whale calls are higher-frequency downward sweeps; blue whale infrasound is below human hearing." },
  ],
  minke_whale: [
    { species: "humpback_whale", photoKey: "humpback", distinction: "Humpback has varied melodic songs; minke produces distinctive mechanical boings and pulse trains." },
  ],
  sei_whale: [
    { species: "fin_whale", photoKey: "fin_whale", distinction: "Fin whale produces low 20 Hz pulses; sei whale calls are higher-frequency paired downward sweeps." },
    { species: "blue_whale", photoKey: "blue_whale", distinction: "Blue whale is very low infrasound; sei whale calls are audibly higher-frequency." },
  ],
  killer_whale: [
    { species: "sperm_whale", photoKey: "sperm_whale", distinction: "Sperm whale produces echolocation clicks in rhythmic codas; orca calls are tonal whistles and pulsed calls." },
  ],
  sperm_whale: [
    { species: "killer_whale", photoKey: "orca", distinction: "Orca produces tonal whistles and pulsed calls; sperm whale clicks are sharp broadband pulses in rhythmic patterns." },
  ],
};

/* Map audio model species keys → SPECIES_PHOTOS keys */
const MODEL_PHOTO_KEY: Record<string, string> = {
  right_whale: "right_whale",
  humpback_whale: "humpback",
  fin_whale: "fin_whale",
  blue_whale: "blue_whale",
  sperm_whale: "sperm_whale",
  minke_whale: "minke_whale",
  sei_whale: "sei_whale",
  killer_whale: "orca",
};

/* ── Types ───────────────────────────────────────────────── */

interface SegmentPrediction {
  segment_idx: number;
  start_sec: number;
  end_sec: number;
  predicted_species: string;
  confidence: number;
  probabilities: Record<string, number>;
}

interface AudioResult {
  dominant_species: string;
  dominant_confidence?: number;
  n_segments: number;
  segments: SegmentPrediction[];
}

/* ── Species colour map for segment timeline ─────────────── */

const SPECIES_COLORS: Record<string, string> = {
  right_whale: "bg-red-500",
  humpback_whale: "bg-green-500",
  fin_whale: "bg-amber-600",
  blue_whale: "bg-ocean-500",
  sperm_whale: "bg-slate-400",
  minke_whale: "bg-teal-500",
  sei_whale: "bg-purple-500",
  killer_whale: "bg-orange-500",
};

/* ── Component ───────────────────────────────────────────── */

export default function AudioClassifier() {
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<AudioResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showAllSpecies, setShowAllSpecies] = useState(false);
  const [expandedSeg, setExpandedSeg] = useState<number | null>(null);
  const [showSegmentDetail, setShowSegmentDetail] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function applyFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
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

  async function handleClassify() {
    if (!file) return;
    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch(`${API_BASE}/api/v1/audio/classify`, {
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
    setResult(null);
    setError(null);
    setShowAllSpecies(false);
    setExpandedSeg(null);
    setShowSegmentDetail(false);
  }

  /* ── Aggregate segment species counts ── */
  const speciesCounts = result
    ? result.segments.reduce(
        (acc, s) => {
          acc[s.predicted_species] = (acc[s.predicted_species] || 0) + 1;
          return acc;
        },
        {} as Record<string, number>,
      )
    : {};
  const sortedSpecies = Object.entries(speciesCounts).sort(
    ([, a], [, b]) => b - a,
  );

  /* Aggregate species probabilities: mean probability across all segments */
  const aggregateProbs = useMemo(() => {
    if (!result) return [];
    const sums: Record<string, number> = {};
    for (const seg of result.segments) {
      if (!seg.probabilities) continue;
      for (const [sp, p] of Object.entries(seg.probabilities)) {
        sums[sp] = (sums[sp] || 0) + p;
      }
    }
    const n = result.segments.length || 1;
    return Object.entries(sums)
      .map(([sp, total]) => [sp, total / n] as [string, number])
      .sort(([, a], [, b]) => b - a);
  }, [result]);

  /* Object URL for local waveform playback */
  const audioUrl = useMemo(
    () => (file ? URL.createObjectURL(file) : null),
    [file],
  );

  /* Compute dominant confidence: average confidence of segments
     matching the dominant species, or fall back to the API value */
  const dominantConfidence = result
    ? (result.dominant_confidence ??
        (() => {
          const domSegs = result.segments.filter(
            (s) => s.predicted_species === result.dominant_species,
          );
          return domSegs.length
            ? domSegs.reduce((sum, s) => sum + s.confidence, 0) / domSegs.length
            : 0;
        })())
    : 0;

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
            ? "border-teal-400/60 bg-ocean-900/20"
            : file
            ? "border-teal-500/30 bg-abyss-900/60"
            : "border-ocean-800 hover:border-teal-500/50 hover:bg-abyss-800/50"
        }`}
      >
        {file ? (
          <div className="space-y-2">
            <IconMusic className="mx-auto h-8 w-8 text-teal-400" />
            <p className="text-sm font-medium text-slate-200">{file.name}</p>
            <p className="text-xs text-slate-500">
              {(file.size / 1_048_576).toFixed(1)} MB
            </p>
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
            <IconMicrophone className="mx-auto mb-3 h-10 w-10 text-slate-400" />
            <p className="text-sm font-medium text-slate-300">
              Drop an audio recording or click to browse
            </p>
            <p className="mt-2 text-xs text-slate-500">
              WAV, FLAC, MP3, AIF · Max 100 MB
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="audio/wav,audio/x-wav,audio/flac,audio/mpeg,audio/aiff,audio/x-aiff"
          onChange={handleFile}
          className="hidden"
        />
      </div>

      {/* Classify button */}
      {file && !result && (
        <button
          onClick={handleClassify}
          disabled={submitting}
          className="w-full rounded-xl bg-teal-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Analysing audio…
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
          {/* Dominant prediction */}
          <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <div className="flex items-center gap-4">
              {/* Species photo */}
              {(() => {
                const photoKey = MODEL_PHOTO_KEY[result.dominant_species];
                const photoSrc = photoKey
                  ? SPECIES_PHOTOS[photoKey]
                  : null;
                return photoSrc ? (
                  <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-abyss-800">
                    <Image
                      src={`/species/${photoSrc}.jpg`}
                      alt={result.dominant_species}
                      fill
                      className="object-cover"
                      sizes="64px"
                    />
                  </div>
                ) : null;
              })()}
              <div className="rounded-lg bg-teal-600/20 px-4 py-3 text-center">
                <p className="text-2xl font-bold text-teal-300">
                  {Math.round(dominantConfidence * 100)}%
                </p>
                <p className="text-[10px] text-slate-400">confidence</p>
              </div>
              <div>
                <p className="text-lg font-bold capitalize text-white">
                  {result.dominant_species.replace(/_/g, " ")}
                </p>
                <p className="text-xs text-slate-500">
                  {result.n_segments} segments · 4s windows · 2s hop
                </p>
              </div>
            </div>
          </div>

          {/* Runner-up detections — aggregate probabilities + segment counts */}
          {aggregateProbs.length > 1 && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Runner-up Predictions
              </h4>
              <div className="space-y-2.5">
                {aggregateProbs.slice(1, 3).map(([sp, avgP], i) => {
                  const topP = aggregateProbs[0][1];
                  const gap = topP - avgP;
                  const isClose = gap < 0.15;
                  const segCount = speciesCounts[sp] ?? 0;
                  const photoKey = MODEL_PHOTO_KEY[sp];
                  const photoSrc = photoKey
                    ? SPECIES_PHOTOS[photoKey]
                    : null;
                  return (
                    <div key={sp}>
                      <div className="flex items-center gap-2">
                        <span className="w-5 text-xs font-medium text-slate-500">
                          {i + 2}.
                        </span>
                        {photoSrc && (
                          <div className="relative h-7 w-7 shrink-0 overflow-hidden rounded bg-abyss-800">
                            <Image
                              src={`/species/${photoSrc}.jpg`}
                              alt={sp}
                              fill
                              className="object-cover"
                              sizes="28px"
                            />
                          </div>
                        )}
                        <span
                          className={`w-28 truncate text-xs ${
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
                              isClose ? "bg-amber-500" : "bg-teal-500/60"
                            }`}
                            style={{ width: `${Math.round(avgP * 100)}%` }}
                          />
                        </div>
                        <span
                          className={`w-10 text-right text-xs ${
                            isClose
                              ? "font-semibold text-amber-300"
                              : "text-slate-400"
                          }`}
                        >
                          {Math.round(avgP * 100)}%
                        </span>
                        {segCount > 0 && (
                          <span className="w-14 text-right text-[10px] text-slate-500">
                            {segCount}/{result.n_segments} seg
                          </span>
                        )}
                      </div>
                      {isClose && (
                        <p className="ml-7 mt-0.5 text-[10px] text-amber-400/70">
                          Close margin — only {Math.round(gap * 100)}pp
                          behind top pick
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* Collapsible remaining species */}
              {aggregateProbs.length > 3 && (
                <div className="mt-3 border-t border-ocean-800/30 pt-3">
                  <button
                    type="button"
                    onClick={() => setShowAllSpecies((v) => !v)}
                    className="flex w-full items-center gap-1.5 text-xs text-teal-400 transition-colors hover:text-teal-300"
                  >
                    <svg
                      className={`h-3 w-3 transition-transform ${
                        showAllSpecies ? "rotate-90" : ""
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
                    {showAllSpecies ? "Hide" : "Show"} remaining{" "}
                    {aggregateProbs.length - 3} species
                  </button>
                  {showAllSpecies && (
                    <div className="mt-2 space-y-1.5">
                      {aggregateProbs.slice(3).map(([sp, avgP]) => {
                        const segCount = speciesCounts[sp] ?? 0;
                        return (
                          <div key={sp} className="flex items-center gap-2">
                            <span className="w-32 truncate text-xs text-slate-400">
                              {sp.replace(/_/g, " ")}
                            </span>
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
                              <div
                                className="h-full rounded-full bg-slate-500 transition-all"
                                style={{
                                  width: `${Math.round(avgP * 100)}%`,
                                }}
                              />
                            </div>
                            <span className="w-10 text-right text-xs text-slate-400">
                              {Math.round(avgP * 100)}%
                            </span>
                            {segCount > 0 && (
                              <span className="w-14 text-right text-[10px] text-slate-500">
                                {segCount}/{result.n_segments} seg
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Similar species comparison (acoustic look-alikes) */}
          {(() => {
            const predicted = result.dominant_species;
            const alikes = LOOK_ALIKES[predicted] ?? [];
            if (alikes.length === 0) return null;
            const predPhotoKey = MODEL_PHOTO_KEY[predicted];
            const predPhotoSrc = predPhotoKey
              ? SPECIES_PHOTOS[predPhotoKey]
              : null;
            const predTip =
              SPECIES_ID_TIPS[predPhotoKey ?? ""] ??
              SPECIES_ID_TIPS[predicted] ??
              null;
            return (
              <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Compare with Similar Species
                </h4>
                <p className="mb-4 text-[11px] text-slate-500">
                  These species produce sounds that can be confused with
                  the prediction. Check the distinguishing acoustic features.
                </p>

                {/* Predicted species card */}
                <div className="mb-4 rounded-lg border border-teal-400/30 bg-ocean-900/30 p-3">
                  <div className="flex gap-3">
                    {predPhotoSrc && (
                      <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-abyss-800">
                        <Image
                          src={`/species/${predPhotoSrc}.jpg`}
                          alt={predicted}
                          fill
                          className="object-cover"
                          sizes="64px"
                        />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold capitalize text-teal-400">
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
                    const laPhotoSrc =
                      SPECIES_PHOTOS[la.photoKey] ?? la.photoKey;
                    return (
                      <div
                        key={la.species}
                        className="rounded-lg border border-ocean-800/40 bg-abyss-800/40 p-3"
                      >
                        <div className="flex gap-3">
                          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-abyss-800">
                            <Image
                              src={`/species/${laPhotoSrc}.jpg`}
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

          {/* Segment timeline + per-segment detail */}
          <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Segment Timeline
              </h4>
              <button
                type="button"
                onClick={() => {
                  setShowSegmentDetail((v) => !v);
                  if (showSegmentDetail) setExpandedSeg(null);
                }}
                className="text-[10px] text-teal-400 transition-colors hover:text-teal-300"
              >
                {showSegmentDetail ? "Hide" : "Show"} per-segment detail
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {result.segments.map((seg) => {
                const isExpanded = expandedSeg === seg.segment_idx;
                return (
                  <button
                    key={seg.segment_idx}
                    type="button"
                    onClick={() => {
                      if (!showSegmentDetail) setShowSegmentDetail(true);
                      setExpandedSeg(isExpanded ? null : seg.segment_idx);
                    }}
                    title={`${seg.start_sec}–${seg.end_sec}s: ${seg.predicted_species.replace(/_/g, " ")} (${Math.round(seg.confidence * 100)}%)`}
                    className={`h-6 w-6 rounded-sm transition-all ${
                      SPECIES_COLORS[seg.predicted_species] ?? "bg-slate-600"
                    } ${isExpanded ? "ring-2 ring-teal-400 ring-offset-1 ring-offset-abyss-900" : "hover:ring-1 hover:ring-slate-500"}`}
                    style={{ opacity: 0.5 + seg.confidence * 0.5 }}
                  />
                );
              })}
            </div>
            <div className="mt-3 flex flex-wrap gap-3">
              {sortedSpecies.map(([sp]) => (
                <div key={sp} className="flex items-center gap-1.5 text-[10px] text-slate-400">
                  <div
                    className={`h-2.5 w-2.5 rounded-sm ${SPECIES_COLORS[sp] ?? "bg-slate-600"}`}
                  />
                  {sp.replace(/_/g, " ")}
                </div>
              ))}
            </div>

            {/* Per-segment detail list */}
            {showSegmentDetail && (
              <div className="mt-4 space-y-2 border-t border-ocean-800/30 pt-4">
                {result.segments.map((seg) => {
                  const isExpanded = expandedSeg === seg.segment_idx;
                  const sortedProbs = seg.probabilities
                    ? Object.entries(seg.probabilities).sort(
                        ([, a], [, b]) => b - a,
                      )
                    : [];
                  return (
                    <div key={seg.segment_idx}>
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedSeg(
                            isExpanded ? null : seg.segment_idx,
                          )
                        }
                        className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors ${
                          isExpanded
                            ? "bg-ocean-900/40"
                            : "hover:bg-abyss-800/50"
                        }`}
                      >
                        <div
                          className={`h-4 w-4 shrink-0 rounded-sm ${
                            SPECIES_COLORS[seg.predicted_species] ??
                            "bg-slate-600"
                          }`}
                          style={{
                            opacity: 0.5 + seg.confidence * 0.5,
                          }}
                        />
                        <span className="w-16 text-[11px] tabular-nums text-slate-500">
                          {seg.start_sec.toFixed(1)}–{seg.end_sec.toFixed(1)}s
                        </span>
                        <span className="flex-1 truncate text-xs font-medium capitalize text-slate-300">
                          {seg.predicted_species.replace(/_/g, " ")}
                        </span>
                        <span className="text-xs tabular-nums text-teal-400">
                          {Math.round(seg.confidence * 100)}%
                        </span>
                        <svg
                          className={`h-3 w-3 shrink-0 text-slate-500 transition-transform ${
                            isExpanded ? "rotate-90" : ""
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
                      </button>
                      {/* Expanded: top-3 probabilities for this segment */}
                      {isExpanded && sortedProbs.length > 0 && (
                        <div className="ml-6 mt-1.5 mb-1 space-y-1.5 rounded-lg bg-abyss-800/40 p-3">
                          {sortedProbs.slice(0, 3).map(([sp, p], j) => {
                            const pct = Math.round(p * 100);
                            const photoKey = MODEL_PHOTO_KEY[sp];
                            const photoSrc = photoKey
                              ? SPECIES_PHOTOS[photoKey]
                              : null;
                            const isTop = j === 0;
                            return (
                              <div
                                key={sp}
                                className="flex items-center gap-2"
                              >
                                <span className="w-4 text-[10px] font-medium text-slate-500">
                                  {j + 1}.
                                </span>
                                {photoSrc && (
                                  <div className="relative h-5 w-5 shrink-0 overflow-hidden rounded bg-abyss-800">
                                    <Image
                                      src={`/species/${photoSrc}.jpg`}
                                      alt={sp}
                                      fill
                                      className="object-cover"
                                      sizes="20px"
                                    />
                                  </div>
                                )}
                                <span
                                  className={`w-24 truncate text-[11px] capitalize ${
                                    isTop
                                      ? "font-semibold text-teal-400"
                                      : "text-slate-400"
                                  }`}
                                >
                                  {sp.replace(/_/g, " ")}
                                </span>
                                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-700">
                                  <div
                                    className={`h-full rounded-full transition-all ${
                                      isTop
                                        ? "bg-teal-500"
                                        : "bg-slate-500"
                                    }`}
                                    style={{
                                      width: `${pct}%`,
                                    }}
                                  />
                                </div>
                                <span
                                  className={`w-8 text-right text-[10px] tabular-nums ${
                                    isTop
                                      ? "font-semibold text-teal-400"
                                      : "text-slate-500"
                                  }`}
                                >
                                  {pct}%
                                </span>
                              </div>
                            );
                          })}
                          {sortedProbs.length > 3 && (
                            <p className="text-[10px] text-slate-600">
                              +{sortedProbs.length - 3} more species
                              below 1%
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Waveform playback */}
          {audioUrl && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <AudioWaveform
                src={audioUrl}
                label="Audio Waveform"
                height={80}
                color="#1e3a5f"
                progressColor="#2dd4bf"
              />
            </div>
          )}

          {/* Try again */}
          <button
            onClick={handleReset}
            className="w-full rounded-xl border border-ocean-800 px-6 py-3 text-sm font-semibold text-slate-200 transition-colors hover:bg-abyss-800"
          >
            Classify Another Recording
          </button>
        </div>
      )}
    </div>
  );
}
