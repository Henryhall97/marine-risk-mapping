"use client";

import { useState, useRef, useMemo, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";

const LocationPin = dynamic(() => import("@/components/LocationPin"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[200px] items-center justify-center rounded-xl border border-ocean-800 bg-abyss-900 text-xs text-slate-500">
      Loading map…
    </div>
  ),
});

const AudioWaveform = dynamic(() => import("@/components/AudioWaveform"), {
  ssr: false,
});

/* ── Constants ───────────────────────────────────────────── */

const SPECIES_OPTIONS = [
  { value: "", label: "Not sure / Unknown" },
  { value: "right_whale", label: "Right Whale" },
  { value: "humpback_whale", label: "Humpback Whale" },
  { value: "fin_whale", label: "Fin Whale" },
  { value: "blue_whale", label: "Blue Whale" },
  { value: "sperm_whale", label: "Sperm Whale" },
  { value: "minke_whale", label: "Minke Whale" },
  { value: "sei_whale", label: "Sei Whale" },
  { value: "killer_whale", label: "Killer Whale" },
  { value: "other", label: "Other Cetacean" },
];

const INTERACTION_TYPES = [
  { value: "passive_observation", label: "🔭 Passive Observation", desc: "Observed from a safe distance" },
  { value: "vessel_approach", label: "🚢 Vessel Approach", desc: "Whale approached or was approached by vessel" },
  { value: "near_miss", label: "⚠️ Near Miss", desc: "Close encounter, no contact" },
  { value: "strike", label: "💥 Strike", desc: "Known or suspected vessel collision" },
  { value: "entanglement", label: "🪢 Entanglement", desc: "Whale tangled in fishing gear or debris" },
  { value: "stranding", label: "🏖️ Stranding", desc: "Whale found on shore or in shallow water" },
  { value: "acoustic_detection", label: "🎙️ Acoustic Detection", desc: "Heard but not visually confirmed" },
  { value: "other", label: "📝 Other", desc: "Doesn't fit other categories" },
];

/* ── Types ───────────────────────────────────────────────── */

interface SightingResult {
  sighting_id: string;
  timestamp: string;
  location: {
    lat: number;
    lon: number;
    h3_cell: number | null;
    gps_source: string | null;
  } | null;
  user_input: {
    species_guess: string | null;
    description: string | null;
    interaction_type: string | null;
  };
  photo_classification: {
    predicted_species: string;
    confidence: number;
    probabilities: Record<string, number>;
  } | null;
  audio_classification: {
    dominant_species: string;
    n_segments: number;
  } | null;
  species_assessment: {
    model_species: string;
    model_confidence: number;
    source: string;
    user_agrees: boolean | null;
  } | null;
  risk_summary: {
    h3_cell: number;
    risk_score: number | null;
    risk_category: string | null;
    traffic_score: number | null;
    cetacean_score: number | null;
    proximity_score: number | null;
    strike_score: number | null;
    habitat_score: number | null;
    protection_gap: number | null;
    reference_risk_score: number | null;
  } | null;
  advisory: {
    level: string;
    message: string;
    authority?: {
      name: string;
      office: string;
      phone: string;
      stranding: string;
      stranding_phone: string;
      email: string;
    } | null;
  } | null;
  submission_id: string | null;
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
      <span className="w-10 text-right text-xs text-slate-300">
        {pct}%
      </span>
    </div>
  );
}

function AdvisoryBanner({ level, message }: { level: string; message: string }) {
  const colors: Record<string, string> = {
    low: "border-green-600/50 bg-green-900/30 text-green-300",
    moderate: "border-yellow-600/50 bg-yellow-900/30 text-yellow-300",
    high: "border-orange-600/50 bg-orange-900/30 text-orange-300",
    critical: "border-red-600/50 bg-red-900/30 text-red-300",
  };
  return (
    <div className={`rounded-lg border px-4 py-3 ${colors[level] ?? colors.moderate}`}>
      <p className="text-xs font-semibold uppercase tracking-wider opacity-70">
        {level} Risk Advisory
      </p>
      <p className="mt-1 text-sm">{message}</p>
    </div>
  );
}

/* ── Main Form ───────────────────────────────────────────── */

export default function SightingForm() {
  const { authHeader, user } = useAuth();

  /* ── Form state ── */
  const [speciesGuess, setSpeciesGuess] = useState("");
  const [interaction, setInteraction] = useState("passive_observation");
  const [description, setDescription] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [sharePublicly, setSharePublicly] = useState(true);

  /* ── Submission state ── */
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SightingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const photoInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);

  /* ── Handlers ── */

  function handlePhoto(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setPhoto(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setPhotoPreview(reader.result as string);
      reader.readAsDataURL(file);
    } else {
      setPhotoPreview(null);
    }
  }

  function handleAudio(e: ChangeEvent<HTMLInputElement>) {
    setAudio(e.target.files?.[0] ?? null);
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

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!lat || !lon) {
      setError("Location is required — use GPS or enter coordinates manually.");
      return;
    }

    setSubmitting(true);
    try {
      const form = new FormData();
      form.append("lat", lat);
      form.append("lon", lon);
      form.append("share_publicly", sharePublicly ? "true" : "false");
      if (speciesGuess) form.append("species_guess", speciesGuess);
      if (description) form.append("description", description);
      if (interaction) form.append("interaction_type", interaction);
      if (photo) form.append("image", photo);
      if (audio) form.append("audio", audio);

      const headers: Record<string, string> = {};
      if (authHeader) headers["Authorization"] = authHeader;

      const res = await fetch(`${API_BASE}/api/v1/sightings/report`, {
        method: "POST",
        headers,
        body: form,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(
          body?.detail ?? `Server error ${res.status}`,
        );
      }

      const data: SightingResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setSpeciesGuess("");
    setInteraction("passive_observation");
    setDescription("");
    setLat("");
    setLon("");
    setPhoto(null);
    setAudio(null);
    setPhotoPreview(null);
    setResult(null);
    setError(null);
    setSharePublicly(true);
  }

  /* Object URL for local audio playback in the result view */
  const audioUrl = useMemo(
    () => (audio ? URL.createObjectURL(audio) : null),
    [audio],
  );

  /* ── Render ── */
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* ── Result view ── */}
      {result ? (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-bold">Sighting Submitted ✓</h2>
              <p className="mt-1 text-sm text-slate-400">
                ID: {result.sighting_id.slice(0, 8)}… ·{" "}
                {new Date(result.timestamp).toLocaleString()}
              </p>
              {result.submission_id && (
                <Link
                  href={`/submissions/${result.submission_id}`}
                  className="mt-1 inline-block text-xs text-bioluminescent-400 hover:underline"
                >
                  View full submission →
                </Link>
              )}
            </div>
            <button
              onClick={handleReset}
              className="rounded-lg border border-ocean-800 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-abyss-800"
            >
              New Report
            </button>
          </div>

          {/* Advisory */}
          {result.advisory && (
            <AdvisoryBanner
              level={result.advisory.level}
              message={result.advisory.message}
            />
          )}

          {/* Regional authority contact */}
          {result.advisory?.authority && (() => {
            const auth = result.advisory!.authority!;
            const itype = result.user_input.interaction_type;
            const isStrike = itype === "strike";
            const isEntanglement = itype === "entanglement";
            const isStranding = itype === "stranding";
            const isUrgent = isStrike || isEntanglement || isStranding;

            // Interaction-specific guidance
            const guidance: Record<string, { icon: string; heading: string; body: string; primaryPhone: string }> = {
              strike: {
                icon: "🚨",
                heading: "Report Ship Strike Immediately",
                body: `Call ${auth.name} now. Provide vessel name, location, speed, and whale condition. Do not move the vessel until instructed.`,
                primaryPhone: auth.phone,
              },
              entanglement: {
                icon: "🪢",
                heading: "Report Entanglement — Do NOT Intervene",
                body: `Contact the stranding network. Stay 100+ yards away, note the whale's location and condition, and keep visual contact until responders arrive.`,
                primaryPhone: auth.stranding_phone,
              },
              stranding: {
                icon: "🏖️",
                heading: "Report Stranding to Stranding Network",
                body: `Call the stranding hotline. Do not touch, push, or pour water on the animal. Note the exact location and keep bystanders at a safe distance.`,
                primaryPhone: auth.stranding_phone,
              },
              near_miss: {
                icon: "⚠️",
                heading: "Near-Miss Event — Report & Slow Down",
                body: "Reduce speed to ≤10 knots immediately. Report this near-miss to help map collision risk hotspots.",
                primaryPhone: auth.phone,
              },
            };

            const g = itype ? guidance[itype] : null;

            return (
              <section className={`rounded-xl border p-4 ${
                isUrgent
                  ? "border-red-700/50 bg-red-950/20"
                  : "border-ocean-800/40 bg-abyss-900/50"
              }`}>
                {/* Context-specific guidance */}
                {g && (
                  <div className={`mb-3 rounded-lg px-3 py-2.5 ${
                    isUrgent ? "bg-red-900/30" : "bg-ocean-900/30"
                  }`}>
                    <p className={`text-sm font-bold ${
                      isUrgent ? "text-red-300" : "text-ocean-300"
                    }`}>
                      {g.icon} {g.heading}
                    </p>
                    <p className="mt-1 text-xs text-slate-300">
                      {g.body}
                    </p>
                    <a
                      href={`tel:${g.primaryPhone}`}
                      className={`mt-2 inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                        isUrgent
                          ? "bg-red-600 text-white hover:bg-red-500"
                          : "bg-ocean-600 text-white hover:bg-ocean-500"
                      }`}
                    >
                      📞 Call {g.primaryPhone}
                    </a>
                  </div>
                )}

                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  🏛️ {auth.name}
                </h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-sm font-medium text-white">
                      {auth.office}
                    </p>
                    {auth.email && (
                      <a
                        href={`mailto:${auth.email}`}
                        className="text-xs text-bioluminescent-400 hover:underline"
                      >
                        {auth.email}
                      </a>
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-slate-300">
                      📞 Incidents & strikes:{" "}
                      <a
                        href={`tel:${auth.phone}`}
                        className="font-medium text-bioluminescent-400 hover:underline"
                      >
                        {auth.phone}
                      </a>
                    </p>
                    {auth.stranding_phone !== auth.phone && (
                      <p className="text-xs text-slate-300">
                        🆘 Strandings & entanglement:{" "}
                        <a
                          href={`tel:${auth.stranding_phone}`}
                          className="font-medium text-bioluminescent-400 hover:underline"
                        >
                          {auth.stranding_phone}
                        </a>
                      </p>
                    )}
                  </div>
                </div>
              </section>
            );
          })()}

          {/* Species assessment */}
          {result.species_assessment && (
            <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                Species Assessment
              </h3>
              <div className="flex items-center gap-4">
                <div className="rounded-lg bg-ocean-600/20 px-4 py-3 text-center">
                  <p className="text-2xl font-bold text-bioluminescent-400">
                    {Math.round(result.species_assessment.model_confidence * 100)}%
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">confidence</p>
                </div>
                <div>
                  <p className="text-lg font-semibold">
                    {result.species_assessment.model_species.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-slate-400">
                    Source: {result.species_assessment.source}
                    {result.species_assessment.user_agrees === true && " · matches your guess ✓"}
                    {result.species_assessment.user_agrees === false && " · differs from your guess"}
                  </p>
                </div>
              </div>
            </section>
          )}

          {/* Submitted media + location map */}
          {(photoPreview || audio || result.location) && (
            <div className="grid gap-4 md:grid-cols-2">
              {/* Uploaded photo */}
              {photoPreview && (
                <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-4">
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    📷 Submitted Photo
                  </h3>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={photoPreview}
                    alt="Submitted whale photo"
                    className="max-h-64 w-full rounded-lg object-contain"
                  />
                </div>
              )}

              {/* Uploaded audio */}
              {audio && audioUrl && (
                <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-4">
                  <AudioWaveform
                    src={audioUrl}
                    label="🎙️ Submitted Audio"
                    height={96}
                    color="#1e3a5f"
                    progressColor="#22d3ee"
                  />
                  <p className="mt-2 text-xs text-slate-500">
                    {audio.name} · {(audio.size / 1_048_576).toFixed(1)} MB
                  </p>
                </div>
              )}

              {/* Location mini-map */}
              {result.location && (
                <div className={`${!photoPreview && !audio ? "md:col-span-2" : ""}`}>
                  <LocationPin
                    lat={result.location.lat}
                    lon={result.location.lon}
                    label={
                      result.species_assessment?.model_species?.replace(/_/g, " ")
                    }
                    height={200}
                    zoom={5}
                  />
                  <p className="mt-2 text-xs text-slate-500">
                    📍 {result.location.lat.toFixed(4)}°, {result.location.lon.toFixed(4)}°
                    {result.location.h3_cell && ` · H3 ${result.location.h3_cell}`}
                    {result.location.gps_source && ` · via ${result.location.gps_source}`}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Photo + Audio results side by side */}
          <div className="grid gap-4 md:grid-cols-2">
            {result.photo_classification && (
              <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                  📷 Photo Classification
                </h3>
                <p className="text-sm">
                  <strong className="text-slate-200">
                    {result.photo_classification.predicted_species.replace(/_/g, " ")}
                  </strong>{" "}
                  ({Math.round(result.photo_classification.confidence * 100)}%)
                </p>
                {Object.keys(result.photo_classification.probabilities).length > 0 && (
                  <div className="mt-3 space-y-1">
                    {Object.entries(result.photo_classification.probabilities)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 5)
                      .map(([sp, p]) => (
                        <div key={sp} className="flex items-center gap-2 text-xs">
                          <span className="w-28 text-slate-400">
                            {sp.replace(/_/g, " ")}
                          </span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-700">
                            <div
                              className="h-full rounded-full bg-ocean-500"
                              style={{ width: `${Math.round(p * 100)}%` }}
                            />
                          </div>
                          <span className="w-8 text-right text-slate-300">
                            {Math.round(p * 100)}%
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </section>
            )}

            {result.audio_classification && (
              <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                  🎙️ Audio Classification
                </h3>
                <p className="text-sm">
                  Dominant:{" "}
                  <strong className="text-slate-200">
                    {result.audio_classification.dominant_species.replace(/_/g, " ")}
                  </strong>
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {result.audio_classification.n_segments} segments analysed
                </p>
              </section>
            )}
          </div>

          {/* Risk summary */}
          {result.risk_summary && (
            <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                Risk Context
              </h3>
              {result.risk_summary.risk_category && (
                <p className="mb-3 text-sm text-slate-300">
                  Category:{" "}
                  <strong className="text-white">
                    {result.risk_summary.risk_category}
                  </strong>
                </p>
              )}
              <div className="space-y-2">
                <ScoreBar label="Overall" value={result.risk_summary.risk_score} />
                <ScoreBar label="Traffic" value={result.risk_summary.traffic_score} />
                <ScoreBar label="Cetacean" value={result.risk_summary.cetacean_score} />
                <ScoreBar label="Proximity" value={result.risk_summary.proximity_score} />
                <ScoreBar label="Strike" value={result.risk_summary.strike_score} />
                <ScoreBar label="Habitat" value={result.risk_summary.habitat_score} />
                <ScoreBar label="Protection Gap" value={result.risk_summary.protection_gap} />
                <ScoreBar label="Reference" value={result.risk_summary.reference_risk_score} />
              </div>
            </section>
          )}
        </div>
      ) : (
        /* ── Form view ── */
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* ── Location ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              📍 Location
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Required — use your device GPS or enter coordinates manually.
            </p>

            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-xs text-slate-400">
                  Latitude
                </label>
                <input
                  type="number"
                  step="any"
                  min={-90}
                  max={90}
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  placeholder="e.g. 41.3829"
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
                />
              </div>
              <div className="flex-1">
                <label className="mb-1 block text-xs text-slate-400">
                  Longitude
                </label>
                <input
                  type="number"
                  step="any"
                  min={-180}
                  max={180}
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                  placeholder="e.g. -71.0580"
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
                />
              </div>
              <button
                type="button"
                onClick={handleGeolocate}
                className="rounded-lg border border-blue-600/40 bg-ocean-600/20 px-4 py-2 text-sm font-medium text-bioluminescent-400 transition-colors hover:bg-ocean-600/30"
              >
                📡 Use GPS
              </button>
            </div>

            {/* Live map preview when coordinates are entered */}
            {lat && lon && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon)) &&
             parseFloat(lat) >= -90 && parseFloat(lat) <= 90 &&
             parseFloat(lon) >= -180 && parseFloat(lon) <= 180 && (
              <div className="mt-4">
                <LocationPin
                  lat={parseFloat(lat)}
                  lon={parseFloat(lon)}
                  height={220}
                  zoom={5}
                  interactive
                />
              </div>
            )}
          </section>

          {/* ── Species guess ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              🐋 Species
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Optional — your best guess. Our models will also classify from
              uploaded media.
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {SPECIES_OPTIONS.map((sp) => (
                <button
                  key={sp.value}
                  type="button"
                  onClick={() => setSpeciesGuess(sp.value)}
                  className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                    speciesGuess === sp.value
                      ? "border-purple-500/50 bg-purple-600/30 text-purple-300"
                      : "border-ocean-800 text-slate-400 hover:bg-abyss-800"
                  }`}
                >
                  {sp.label}
                </button>
              ))}
            </div>
          </section>

          {/* ── Interaction type ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              🔄 Interaction Type
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              What kind of encounter did you observe?
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {INTERACTION_TYPES.map((it) => (
                <button
                  key={it.value}
                  type="button"
                  onClick={() => setInteraction(it.value)}
                  className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                    interaction === it.value
                      ? "border-teal-500/50 bg-teal-600/30 text-teal-300"
                      : "border-ocean-800 text-slate-400 hover:bg-abyss-800"
                  }`}
                >
                  <span className="text-sm font-medium">{it.label}</span>
                  <p className="mt-0.5 text-xs opacity-60">{it.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* ── Media uploads ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              📎 Media
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Optional — upload a photo and/or audio recording for AI species
              classification.
            </p>

            <div className="grid gap-4 md:grid-cols-2">
              {/* Photo upload */}
              <div
                onClick={() => photoInputRef.current?.click()}
                className="group cursor-pointer rounded-lg border-2 border-dashed border-ocean-800 p-6 text-center transition-colors hover:border-blue-500/50 hover:bg-abyss-800/50"
              >
                {photoPreview ? (
                  <div className="space-y-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={photoPreview}
                      alt="Preview"
                      className="mx-auto max-h-40 rounded-lg object-contain"
                    />
                    <p className="text-xs text-slate-400">{photo?.name}</p>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setPhoto(null);
                        setPhotoPreview(null);
                      }}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="mb-2 text-3xl">📷</div>
                    <p className="text-sm font-medium text-slate-300">
                      Upload Photo
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      JPG, PNG, WEBP · Max 20 MB
                    </p>
                  </>
                )}
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/tiff"
                  onChange={handlePhoto}
                  className="hidden"
                />
              </div>

              {/* Audio upload */}
              <div
                onClick={() => audioInputRef.current?.click()}
                className="group cursor-pointer rounded-lg border-2 border-dashed border-ocean-800 p-6 text-center transition-colors hover:border-blue-500/50 hover:bg-abyss-800/50"
              >
                {audio ? (
                  <div className="space-y-2">
                    <div className="text-3xl">🎵</div>
                    <p className="text-xs text-slate-400">{audio.name}</p>
                    <p className="text-xs text-slate-500">
                      {(audio.size / 1_048_576).toFixed(1)} MB
                    </p>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setAudio(null);
                      }}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="mb-2 text-3xl">🎙️</div>
                    <p className="text-sm font-medium text-slate-300">
                      Upload Audio
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      WAV, FLAC, MP3, AIF · Max 100 MB
                    </p>
                  </>
                )}
                <input
                  ref={audioInputRef}
                  type="file"
                  accept="audio/wav,audio/x-wav,audio/flac,audio/mpeg,audio/aiff,audio/x-aiff"
                  onChange={handleAudio}
                  className="hidden"
                />
              </div>
            </div>
          </section>

          {/* ── Description ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              📝 Description
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Optional — any additional details about the sighting.
            </p>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder="Number of animals, behaviour, sea state, weather…"
              className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-slate-200 placeholder-gray-600 focus:border-ocean-500 focus:outline-none focus:ring-1 focus:ring-ocean-500"
            />
            <p className="mt-1 text-right text-xs text-slate-600">
              {description.length} / 2000
            </p>
          </section>

          {/* ── Share with community ── */}
          {user && (
            <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <label className="flex cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  checked={sharePublicly}
                  onChange={(e) => setSharePublicly(e.target.checked)}
                  className="h-5 w-5 rounded border-ocean-800 bg-abyss-800 text-ocean-500 focus:ring-ocean-500"
                />
                <div>
                  <span className="text-sm font-medium text-slate-200">
                    🌊 Share with community
                  </span>
                  <p className="text-xs text-slate-500">
                    Make this sighting visible on the community feed. You can
                    change this later from your submissions page.
                  </p>
                </div>
              </label>
            </section>
          )}

          {!user && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <p className="text-sm text-slate-400">
                💡{" "}
                <Link
                  href="/login"
                  className="text-bioluminescent-400 underline hover:text-bioluminescent-300"
                >
                  Log in
                </Link>{" "}
                to save your sighting and share it with the community.
              </p>
            </div>
          )}

          {/* ── Error ── */}
          {error && (
            <div className="rounded-lg border border-red-600/50 bg-red-900/30 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {/* ── Submit ── */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-ocean-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-ocean-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Submitting…
              </span>
            ) : (
              "Submit Sighting Report"
            )}
          </button>
        </form>
      )}
    </div>
  );
}
