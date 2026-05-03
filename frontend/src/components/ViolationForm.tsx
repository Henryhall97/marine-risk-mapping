
"use client";
import React, { useState, useRef, useCallback } from "react";
import {
  IconBolt,
  IconSatellite,
  IconShield,
  IconWhale,
  IconBeach,
  IconAlert,
  IconCheck,
  IconCamera,
} from "./icons/MarineIcons";

interface ViolationFormProps {
  onSubmit?: () => void;
}

const VIOLATION_TYPES = [
  { value: "speeding", label: "Speeding in speed zone", Icon: IconBolt },
  { value: "ais_off", label: "AIS off / not transmitting", Icon: IconSatellite },
  { value: "mpa_entry", label: "Entering marine protected area", Icon: IconShield },
  { value: "bia_entry", label: "Entering biologically important area", Icon: IconWhale },
  { value: "critical_habitat", label: "Entering critical habitat", Icon: IconBeach },
  { value: "other", label: "Other violation", Icon: IconAlert },
];

const VESSEL_TYPES = [
  "Unknown",
  "Cargo",
  "Tanker",
  "Passenger",
  "Fishing",
  "Tug / Tow",
  "Recreational",
  "Military",
  "Other",
];

const INPUT =
  "w-full rounded-lg border border-ocean-700/50 bg-abyss-900 px-3 py-2 text-sm " +
  "text-slate-200 placeholder-slate-500 outline-none transition " +
  "focus:border-ocean-400 focus:ring-1 focus:ring-ocean-400";

const SECTION_LABEL = "text-xs font-bold uppercase tracking-widest text-ocean-400 mb-4";

export const ViolationForm: React.FC<ViolationFormProps> = ({ onSubmit }) => {
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [incidentTime, setIncidentTime] = useState("");
  const [violationType, setViolationType] = useState(VIOLATION_TYPES[0].value);
  const [vesselMmsi, setVesselMmsi] = useState("");
  const [vesselName, setVesselName] = useState("");
  const [vesselType, setVesselType] = useState(VESSEL_TYPES[0]);
  const [estimatedSpeed, setEstimatedSpeed] = useState("");
  const [description, setDescription] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [photoFiles, setPhotoFiles] = useState<File[]>([]);
  const [photoPreviews, setPhotoPreviews] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const addFiles = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files).filter(f => f.type.startsWith("image/") || f.type.startsWith("video/"));
    if (!arr.length) return;
    setPhotoFiles(prev => [...prev, ...arr].slice(0, 5));
    arr.forEach(f => {
      const reader = new FileReader();
      reader.onload = e => setPhotoPreviews(prev => [...prev, e.target?.result as string].slice(0, 5));
      reader.readAsDataURL(f);
    });
  }, []);

  const removeFile = (idx: number) => {
    setPhotoFiles(prev => prev.filter((_, i) => i !== idx));
    setPhotoPreviews(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      let resp: Response;
      if (photoFiles.length > 0) {
        const fd = new FormData();
        fd.append("lat", lat);
        fd.append("lon", lon);
        fd.append("violation_type", violationType);
        fd.append("description", description);
        if (evidenceUrl) fd.append("evidence_url", evidenceUrl);
        photoFiles.forEach(f => fd.append("photos", f));
        resp = await fetch("/api/v1/violations", { method: "POST", body: fd });
      } else {
        resp = await fetch("/api/v1/violations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lat: parseFloat(lat),
            lon: parseFloat(lon),
            violation_type: violationType,
            description,
            evidence_url: evidenceUrl || undefined,
          }),
        });
      }
      if (!resp.ok) throw new Error("Submission failed");
      setSuccess(true);
      if (onSubmit) onSubmit();
    } catch (err: unknown) {
      setError((err as Error).message || "Error submitting report");
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="glass-panel-strong rounded-2xl border border-ocean-700/40 p-10 text-center shadow-xl">
        <div className="mb-4 flex justify-center">
          <IconCheck className="h-14 w-14 text-bioluminescent-400" />
        </div>
        <h3 className="mb-2 text-xl font-bold text-bioluminescent-400">Report submitted</h3>
        <p className="text-sm text-slate-400">
          Thank you. Your report has been logged and will be reviewed by the community.
        </p>
        <button
          className="mt-6 rounded-lg bg-ocean-500/20 px-5 py-2 text-sm font-semibold text-ocean-300 hover:bg-ocean-500/30 transition"
          onClick={() => setSuccess(false)}
        >
          Submit another
        </button>
      </div>
    );
  }

  return (
    <form className="space-y-8" onSubmit={handleSubmit}>

      {/* ── Violation type ── */}
      <section className="glass-panel-strong rounded-2xl border border-ocean-700/40 p-6 shadow-lg">
        <p className={SECTION_LABEL}>Violation type</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {VIOLATION_TYPES.map(({ value, label, Icon }) => (
            <label
              key={value}
              className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition ${
                violationType === value
                  ? "border-ocean-400 bg-ocean-500/15 text-slate-100"
                  : "border-ocean-700/40 bg-abyss-900/50 text-slate-400 hover:border-ocean-600/60 hover:text-slate-200"
              }`}
            >
              <input
                type="radio"
                name="violation_type"
                value={value}
                checked={violationType === value}
                onChange={() => setViolationType(value)}
                className="accent-ocean-400"
              />
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </label>
          ))}
        </div>
      </section>

      {/* ── Location & time ── */}
      <section className="glass-panel-strong rounded-2xl border border-ocean-700/40 p-6 shadow-lg">
        <p className={SECTION_LABEL}>Location &amp; time</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-400">Latitude</label>
            <input
              type="number"
              className={INPUT}
              value={lat}
              onChange={e => setLat(e.target.value)}
              required
              step="any"
              min="-90"
              max="90"
              placeholder="e.g. 36.123"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-400">Longitude</label>
            <input
              type="number"
              className={INPUT}
              value={lon}
              onChange={e => setLon(e.target.value)}
              required
              step="any"
              min="-180"
              max="180"
              placeholder="e.g. -122.456"
            />
          </div>
        </div>
        <div className="mt-4">
          <label className="mb-1.5 block text-xs font-semibold text-slate-400">
            Date &amp; time of incident
          </label>
          <input
            type="datetime-local"
            className={INPUT}
            value={incidentTime}
            onChange={e => setIncidentTime(e.target.value)}
          />
        </div>
      </section>

      {/* ── Vessel details ── */}
      <section className="glass-panel-strong rounded-2xl border border-ocean-700/40 p-6 shadow-lg">
        <p className={SECTION_LABEL}>Vessel details <span className="normal-case font-normal text-slate-500">(if known)</span></p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-400">Vessel name</label>
            <input
              type="text"
              className={INPUT}
              value={vesselName}
              onChange={e => setVesselName(e.target.value)}
              placeholder="e.g. MV Atlantic Star"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-400">MMSI / AIS ID</label>
            <input
              type="text"
              className={INPUT}
              value={vesselMmsi}
              onChange={e => setVesselMmsi(e.target.value)}
              placeholder="9-digit number"
              maxLength={9}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-400">Vessel type</label>
            <select
              className={INPUT}
              value={vesselType}
              onChange={e => setVesselType(e.target.value)}
            >
              {VESSEL_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-400">Estimated speed (knots)</label>
            <input
              type="number"
              className={INPUT}
              value={estimatedSpeed}
              onChange={e => setEstimatedSpeed(e.target.value)}
              placeholder="e.g. 14"
              min="0"
              max="50"
              step="0.5"
            />
          </div>
        </div>
      </section>

      {/* ── Description ── */}
      <section className="glass-panel-strong rounded-2xl border border-ocean-700/40 p-6 shadow-lg">
        <p className={SECTION_LABEL}>Description</p>
        <textarea
          className={INPUT}
          value={description}
          onChange={e => setDescription(e.target.value)}
          required
          rows={4}
          placeholder="Describe what you observed — zone, vessel behaviour, wildlife nearby, AIS status, etc."
        />
      </section>

      {/* ── Evidence ── */}
      <section className="glass-panel-strong rounded-2xl border border-ocean-700/40 p-6 shadow-lg">
        <p className={SECTION_LABEL}>Evidence <span className="normal-case font-normal text-slate-500">(optional)</span></p>

        {/* Drag-and-drop upload zone */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload photos or videos"
          className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition cursor-pointer ${
            dragOver
              ? "border-ocean-400 bg-ocean-500/10"
              : "border-ocean-700/50 bg-abyss-900/40 hover:border-ocean-500/70 hover:bg-ocean-500/5"
          }`}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={e => e.key === "Enter" && fileInputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
        >
          <IconCamera className="mb-3 h-8 w-8 text-ocean-400" />
          <p className="text-sm font-semibold text-slate-300">Drop photos or videos here</p>
          <p className="mt-1 text-xs text-slate-500">or click to browse · JPG, PNG, MP4 · max 5 files</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            multiple
            className="hidden"
            onChange={e => { if (e.target.files) addFiles(e.target.files); }}
          />
        </div>

        {/* Thumbnails */}
        {photoPreviews.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3">
            {photoPreviews.map((src, i) => (
              <div key={i} className="relative h-20 w-20 overflow-hidden rounded-lg border border-ocean-700/50">
                {photoFiles[i]?.type.startsWith("video/") ? (
                  <div className="flex h-full w-full items-center justify-center bg-abyss-900">
                    <IconCamera className="h-6 w-6 text-slate-500" />
                  </div>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={src} alt={`evidence-${i}`} className="h-full w-full object-cover" />
                )}
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/70 text-xs text-white hover:bg-red-700/80"
                  aria-label="Remove"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3 w-3">
                    <path strokeLinecap="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* URL fallback */}
        <div className="mt-5">
          <label className="mb-1.5 block text-xs font-semibold text-slate-400">Or link to AIS track / external evidence</label>
          <input
            type="url"
            className={INPUT}
            value={evidenceUrl}
            onChange={e => setEvidenceUrl(e.target.value)}
            placeholder="https://marinetraffic.com/... or image link"
          />
          <p className="mt-2 text-xs text-slate-500">
            AIS screenshots from MarineTraffic or VesselFinder are especially useful.
          </p>
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-700/40 bg-red-950/40 px-4 py-3">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
          </svg>
          <p className="flex-1 text-sm text-red-300">{error}</p>
          <button
            type="button"
            onClick={() => setError("")}
            aria-label="Dismiss error"
            className="shrink-0 text-red-500 transition-colors hover:text-red-300"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-xl bg-gradient-to-r from-ocean-600 to-ocean-400 py-3 font-bold text-white shadow-ocean-md transition hover:from-ocean-500 hover:to-ocean-300 disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Submit Violation Report"}
      </button>
    </form>
  );
};

export default ViolationForm;
