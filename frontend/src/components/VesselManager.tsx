"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import {
  IconAnchor,
  IconCheck,
  IconRefresh,
  IconShip,
} from "@/components/icons/MarineIcons";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

/* ── Types ──────────────────────────────────────────────── */

export interface Vessel {
  id: number;
  vessel_name: string;
  vessel_type: string;
  description: string | null;
  length_m: number | null;
  beam_m: number | null;
  draft_m: number | null;
  hull_material: string | null;
  propulsion: string | null;
  typical_speed_knots: number | null;
  home_port: string | null;
  flag_state: string | null;
  registration_number: string | null;
  mmsi: string | null;
  imo: string | null;
  call_sign: string | null;
  is_active: boolean;
  profile_photo_url: string | null;
  cover_photo_url: string | null;
  created_at: string;
}

interface VesselListResponse {
  vessels: Vessel[];
  active_vessel_id: number | null;
}

/* ── Constants ──────────────────────────────────────────── */

const VESSEL_TYPES: Record<string, string> = {
  sailing_yacht: "Sailing Yacht",
  motorboat: "Motorboat",
  kayak_canoe: "Kayak / Canoe",
  research_vessel: "Research Vessel",
  whale_watch_boat: "Whale Watch Boat",
  fishing_vessel: "Fishing Vessel",
  cargo_ship: "Cargo Ship",
  tanker: "Tanker",
  ferry_passenger: "Ferry / Passenger",
  tug_workboat: "Tug / Workboat",
  coast_guard: "Coast Guard",
  other: "Other",
};

const HULL_MATERIALS: Record<string, string> = {
  fiberglass: "Fiberglass",
  aluminum: "Aluminium",
  steel: "Steel",
  wood: "Wood",
  carbon_composite: "Carbon Composite",
  inflatable: "Inflatable",
  other: "Other",
};

const PROPULSION_TYPES: Record<string, string> = {
  sail: "Sail",
  outboard: "Outboard Motor",
  inboard_diesel: "Inboard Diesel",
  inboard_gas: "Inboard Gas",
  electric: "Electric",
  paddle: "Paddle",
  jet: "Jet Drive",
  other: "Other",
};

/* ── Component ──────────────────────────────────────────── */

export default function VesselManager() {
  const { authHeader } = useAuth();
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  /* Form state */
  const [name, setName] = useState("");
  const [type, setType] = useState("sailing_yacht");
  const [description, setDescription] = useState("");
  const [length, setLength] = useState("");
  const [beam, setBeam] = useState("");
  const [draft, setDraft] = useState("");
  const [hull, setHull] = useState("");
  const [propulsion, setPropulsion] = useState("");
  const [speed, setSpeed] = useState("");
  const [homePort, setHomePort] = useState("");
  const [flagState, setFlagState] = useState("");
  const [regNumber, setRegNumber] = useState("");
  const [mmsi, setMmsi] = useState("");
  const [imo, setImo] = useState("");
  const [callSign, setCallSign] = useState("");
  const [saving, setSaving] = useState(false);

  const resetForm = useCallback(() => {
    setName("");
    setType("sailing_yacht");
    setDescription("");
    setLength("");
    setBeam("");
    setDraft("");
    setHull("");
    setPropulsion("");
    setSpeed("");
    setHomePort("");
    setFlagState("");
    setRegNumber("");
    setMmsi("");
    setImo("");
    setCallSign("");
    setEditingId(null);
    setShowForm(false);
  }, []);

  /* Fetch vessels */
  const fetchVessels = useCallback(async () => {
    if (!authHeader) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/v1/vessels`, {
        headers: { Authorization: authHeader },
      });
      if (!res.ok) return;
      const data: VesselListResponse = await res.json();
      setVessels(data.vessels);
      setActiveId(data.active_vessel_id);
    } finally {
      setLoading(false);
    }
  }, [authHeader]);

  useEffect(() => {
    fetchVessels();
  }, [fetchVessels]);

  /* Pre-fill form for editing */
  const startEdit = (v: Vessel) => {
    setEditingId(v.id);
    setName(v.vessel_name);
    setType(v.vessel_type);
    setDescription(v.description ?? "");
    setLength(v.length_m?.toString() ?? "");
    setBeam(v.beam_m?.toString() ?? "");
    setDraft(v.draft_m?.toString() ?? "");
    setHull(v.hull_material ?? "");
    setPropulsion(v.propulsion ?? "");
    setSpeed(v.typical_speed_knots?.toString() ?? "");
    setHomePort(v.home_port ?? "");
    setFlagState(v.flag_state ?? "");
    setRegNumber(v.registration_number ?? "");
    setMmsi(v.mmsi ?? "");
    setImo(v.imo ?? "");
    setCallSign(v.call_sign ?? "");
    setShowForm(true);
  };

  /* Save (create or update) */
  const handleSave = async () => {
    if (!authHeader || !name.trim()) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        vessel_name: name.trim(),
        vessel_type: type,
      };
      if (description.trim()) body.description = description.trim();
      if (length) body.length_m = parseFloat(length);
      if (beam) body.beam_m = parseFloat(beam);
      if (draft) body.draft_m = parseFloat(draft);
      if (hull) body.hull_material = hull;
      if (propulsion) body.propulsion = propulsion;
      if (speed) body.typical_speed_knots = parseFloat(speed);
      if (homePort) body.home_port = homePort;
      if (flagState) body.flag_state = flagState;
      if (regNumber) body.registration_number = regNumber;
      if (mmsi) body.mmsi = mmsi;
      if (imo) body.imo = imo;
      if (callSign) body.call_sign = callSign;

      const url = editingId
        ? `${API_BASE}/api/v1/vessels/${editingId}`
        : `${API_BASE}/api/v1/vessels`;
      const method = editingId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: authHeader,
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        resetForm();
        await fetchVessels();
      }
    } finally {
      setSaving(false);
    }
  };

  /* Delete */
  const handleDelete = async (id: number) => {
    if (!authHeader) return;
    if (!confirm("Delete this vessel profile?")) return;
    await fetch(`${API_BASE}/api/v1/vessels/${id}`, {
      method: "DELETE",
      headers: { Authorization: authHeader },
    });
    await fetchVessels();
  };

  /* Activate / deactivate */
  const handleActivate = async (id: number) => {
    if (!authHeader) return;
    if (id === activeId) {
      /* Deactivate (shore mode) */
      await fetch(`${API_BASE}/api/v1/vessels/deactivate`, {
        method: "POST",
        headers: { Authorization: authHeader },
      });
    } else {
      await fetch(`${API_BASE}/api/v1/vessels/${id}/activate`, {
        method: "POST",
        headers: { Authorization: authHeader },
      });
    }
    await fetchVessels();
  };

  if (loading && vessels.length === 0) {
    return (
      <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/60 py-6 text-center text-sm text-slate-500">
        Loading vessels…
      </div>
    );
  }

  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
          <IconAnchor className="h-5 w-5 text-ocean-400" />
          My Vessels
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchVessels}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-abyss-800 hover:text-white"
            title="Refresh"
          >
            <IconRefresh className="h-4 w-4" />
          </button>
          {!showForm && (
            <button
              onClick={() => {
                resetForm();
                setShowForm(true);
              }}
              className="rounded-lg bg-ocean-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-ocean-500"
            >
              + Add Vessel
            </button>
          )}
        </div>
      </div>

      {/* Add / Edit form */}
      {showForm && (
        <div className="mb-4 rounded-xl border border-ocean-700 bg-abyss-900/80 p-4">
          <h3 className="mb-3 text-sm font-semibold text-white">
            {editingId ? "Edit Vessel" : "Register a Vessel"}
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {/* Name */}
            <div className="sm:col-span-2 lg:col-span-3">
              <label className="mb-1 block text-xs text-slate-400">
                Vessel Name *
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. SV Wanderer"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>

            {/* Description */}
            <div className="sm:col-span-2 lg:col-span-3">
              <label className="mb-1 block text-xs text-slate-400">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Tell us about your boat..."
                rows={2}
                maxLength={2000}
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500 resize-none"
              />
            </div>

            {/* Type */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Vessel Type *
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white"
              >
                {Object.entries(VESSEL_TYPES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            {/* Dimensions */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Length (m)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={length}
                onChange={(e) => setLength(e.target.value)}
                placeholder="12.5"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Beam (m)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={beam}
                onChange={(e) => setBeam(e.target.value)}
                placeholder="4.2"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Draft (m)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="1.8"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>

            {/* Hull + Propulsion */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Hull Material
              </label>
              <select
                value={hull}
                onChange={(e) => setHull(e.target.value)}
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white"
              >
                <option value="">—</option>
                {Object.entries(HULL_MATERIALS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Propulsion
              </label>
              <select
                value={propulsion}
                onChange={(e) => setPropulsion(e.target.value)}
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white"
              >
                <option value="">—</option>
                {Object.entries(PROPULSION_TYPES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Typical Speed (kn)
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={speed}
                onChange={(e) => setSpeed(e.target.value)}
                placeholder="7"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>

            {/* Location + registration */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Home Port
              </label>
              <input
                value={homePort}
                onChange={(e) => setHomePort(e.target.value)}
                placeholder="e.g. Monterey, CA"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Flag State
              </label>
              <input
                value={flagState}
                onChange={(e) => setFlagState(e.target.value)}
                placeholder="e.g. USA"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Registration No.
              </label>
              <input
                value={regNumber}
                onChange={(e) => setRegNumber(e.target.value)}
                placeholder="e.g. CA 1234 AB"
                className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
              />
            </div>

            {/* Maritime IDs */}
            <details className="sm:col-span-2 lg:col-span-3">
              <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-300">
                Maritime identifiers (MMSI, IMO, Call Sign)
              </summary>
              <div className="mt-2 grid gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    MMSI
                  </label>
                  <input
                    value={mmsi}
                    onChange={(e) => setMmsi(e.target.value)}
                    placeholder="9-digit"
                    className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    IMO Number
                  </label>
                  <input
                    value={imo}
                    onChange={(e) => setImo(e.target.value)}
                    placeholder="7-digit"
                    className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Call Sign
                  </label>
                  <input
                    value={callSign}
                    onChange={(e) => setCallSign(e.target.value)}
                    placeholder="e.g. WDB1234"
                    className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
                  />
                </div>
              </div>
            </details>
          </div>

          {/* Form actions */}
          <div className="mt-4 flex items-center justify-end gap-2">
            <button
              onClick={resetForm}
              className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !name.trim()}
              className="rounded-lg bg-ocean-600 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-500 disabled:opacity-50"
            >
              {saving ? "Saving…" : editingId ? "Update" : "Add Vessel"}
            </button>
          </div>
        </div>
      )}

      {/* Vessel cards */}
      {vessels.length === 0 && !showForm ? (
        <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 py-10 text-center">
          <IconAnchor className="mx-auto mb-2 h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-400">No vessels registered yet.</p>
          <p className="mt-1 text-xs text-slate-500">
            Add your boat so its details are automatically linked to every
            sighting you report.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-3 rounded-lg bg-ocean-600 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-500"
          >
            + Register Your First Vessel
          </button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {vessels.map((v) => (
            <div
              key={v.id}
              className={`group relative flex flex-col overflow-hidden rounded-xl border transition-all ${
                v.id === activeId
                  ? "border-ocean-500 bg-ocean-500/5 shadow-ocean-sm"
                  : "border-ocean-800/40 bg-abyss-900/70 hover:border-ocean-700"
              }`}
            >
              {/* Photo banner */}
              <Link href={`/boat/${v.id}`} className="relative block h-32 w-full flex-shrink-0 overflow-hidden bg-gradient-to-br from-ocean-900/60 to-abyss-800/80">
                {v.profile_photo_url ? (
                  <Image
                    src={`${API_BASE}${v.profile_photo_url}`}
                    alt={v.vessel_name}
                    fill
                    unoptimized
                    className="object-cover transition-transform duration-300 group-hover:scale-105"
                    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center">
                    <IconShip className="h-10 w-10 text-ocean-400/30" />
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/60 to-transparent" />
                {/* Vessel type chip on photo */}
                <span className="absolute bottom-2 left-2 rounded-full bg-black/50 px-2 py-0.5 text-[10px] font-medium text-white/80 backdrop-blur-sm">
                  {VESSEL_TYPES[v.vessel_type] ?? v.vessel_type}
                </span>
              </Link>

              {/* Active badge */}
              {v.id === activeId && (
                <span className="absolute top-2 right-2 z-10 flex items-center gap-1 rounded-full bg-ocean-600 px-2 py-0.5 text-[10px] font-semibold text-white shadow">
                  <IconCheck className="h-3 w-3" /> Active
                </span>
              )}

              {/* Content */}
              <div className="flex flex-1 flex-col gap-2 p-4">
                {/* Name */}
                <div>
                  <h3 className="text-sm font-bold text-white">
                    {v.vessel_name}
                  </h3>
                  {v.description && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">
                      {v.description}
                    </p>
                  )}
                </div>

                {/* Quick specs */}
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                  {v.length_m && <span>{v.length_m}m</span>}
                  {v.propulsion && (
                    <span>{PROPULSION_TYPES[v.propulsion] ?? v.propulsion}</span>
                  )}
                  {v.home_port && <span>{v.home_port}</span>}
                </div>

                {/* Actions */}
                <div className="mt-auto flex items-center gap-2 border-t border-ocean-800/20 pt-2">
                  <button
                    onClick={() => handleActivate(v.id)}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      v.id === activeId
                        ? "bg-slate-700/50 text-slate-300 hover:bg-slate-700"
                        : "bg-ocean-600/20 text-ocean-400 hover:bg-ocean-600/40"
                    }`}
                  >
                    {v.id === activeId ? "Deactivate" : "Set Active"}
                  </button>
                  <Link
                    href={`/boat/${v.id}`}
                    className="rounded-md px-2.5 py-1 text-xs text-ocean-400/70 hover:bg-ocean-600/10 hover:text-ocean-300"
                  >
                    <IconShip className="inline h-3 w-3 mr-0.5" />
                    Profile
                  </Link>
                  <button
                    onClick={() => startEdit(v)}
                    className="rounded-md px-2.5 py-1 text-xs text-slate-400 hover:bg-abyss-800 hover:text-white"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(v.id)}
                    className="ml-auto rounded-md px-2.5 py-1 text-xs text-red-400/60 hover:bg-red-500/10 hover:text-red-400"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Hint */}
      {vessels.length > 0 && activeId && (
        <p className="mt-2 text-xs text-slate-500">
          Your active vessel is automatically linked when you submit a sighting
          report.
        </p>
      )}
    </div>
  );
}
