"use client";

import { useState, useRef, useMemo, type ChangeEvent } from "react";
import dynamic from "next/dynamic";
import { API_BASE } from "@/lib/config";

const AudioWaveform = dynamic(
  () => import("@/components/AudioWaveform"),
  { ssr: false },
);

/* ── Types ───────────────────────────────────────────────── */

interface SegmentPrediction {
  segment_idx: number;
  start_sec: number;
  end_sec: number;
  predicted_species: string;
  confidence: number;
}

interface AudioResult {
  dominant_species: string;
  dominant_confidence?: number;
  n_segments: number;
  segments: SegmentPrediction[];
  risk_context: {
    h3_cell: number;
    risk_score: number | null;
    risk_category: string | null;
    traffic_score: number | null;
    cetacean_score: number | null;
    strike_score: number | null;
    habitat_score: number | null;
    proximity_score: number | null;
    protection_gap: number | null;
    reference_risk_score: number | null;
  } | null;
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
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<AudioResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setResult(null);
    setError(null);
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
    if (!lat || !lon) {
      setError("Location is required for audio classification.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file);
      form.append("lat", lat);
      form.append("lon", lon);

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
    setLat("");
    setLon("");
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
        className={`group cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
          file
            ? "border-teal-500/30 bg-abyss-900/60"
            : "border-ocean-800 hover:border-teal-500/50 hover:bg-abyss-800/50"
        }`}
      >
        {file ? (
          <div className="space-y-2">
            <div className="text-4xl">🎵</div>
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
            <div className="mb-3 text-5xl">🎙️</div>
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

      {/* GPS (required for audio) */}
      {file && !result && (
        <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              📍 Location (required)
            </h4>
            <button
              type="button"
              onClick={handleGeolocate}
              className="rounded-lg border border-teal-600/40 bg-teal-600/20 px-3 py-1 text-xs font-medium text-teal-300 transition-colors hover:bg-teal-600/30"
            >
              Use GPS
            </button>
          </div>
          <p className="mb-3 text-[11px] text-slate-500">
            Audio files have no EXIF GPS — coordinates are required for H3 risk
            enrichment.
          </p>
          <div className="flex gap-3">
            <input
              type="number"
              step="any"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              placeholder="Latitude"
              className="flex-1 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-teal-500 focus:outline-none"
            />
            <input
              type="number"
              step="any"
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              placeholder="Longitude"
              className="flex-1 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-teal-500 focus:outline-none"
            />
          </div>
        </div>
      )}

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
        <div className="rounded-lg border border-red-600/50 bg-red-900/30 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-5">
          {/* Dominant prediction */}
          <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <div className="flex items-center gap-4">
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

          {/* Species breakdown across segments */}
          {sortedSpecies.length > 0 && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Species Detections by Segment
              </h4>
              <div className="space-y-2">
                {sortedSpecies.map(([sp, count]) => {
                  const pct = Math.round((count / result.n_segments) * 100);
                  return (
                    <div key={sp} className="flex items-center gap-2">
                      <span className="w-32 truncate text-xs text-slate-400">
                        {sp.replace(/_/g, " ")}
                      </span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
                        <div
                          className="h-full rounded-full bg-teal-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="w-16 text-right text-xs text-slate-300">
                        {count}/{result.n_segments}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Segment timeline */}
          <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Segment Timeline
            </h4>
            <div className="flex flex-wrap gap-1">
              {result.segments.map((seg) => (
                <div
                  key={seg.segment_idx}
                  title={`${seg.start_sec}–${seg.end_sec}s: ${seg.predicted_species.replace(/_/g, " ")} (${Math.round(seg.confidence * 100)}%)`}
                  className={`h-6 w-6 rounded-sm ${SPECIES_COLORS[seg.predicted_species] ?? "bg-slate-600"}`}
                  style={{ opacity: 0.5 + seg.confidence * 0.5 }}
                />
              ))}
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
                <ScoreBar
                  label="Proximity"
                  value={result.risk_context.proximity_score}
                />
                <ScoreBar
                  label="Strike"
                  value={result.risk_context.strike_score}
                />
                <ScoreBar
                  label="Habitat"
                  value={result.risk_context.habitat_score}
                />
                <ScoreBar
                  label="Protection"
                  value={result.risk_context.protection_gap}
                />
                <ScoreBar
                  label="Reference"
                  value={result.risk_context.reference_risk_score}
                />
              </div>
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
