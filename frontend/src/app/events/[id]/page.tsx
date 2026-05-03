"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import { SonarPing } from "@/components/animations";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  IconUsers,
  IconStar,
  IconWhale,
  IconEye,
  IconCamera,
  IconPin,
  IconClipboard,
  IconCheck,
  IconMicroscope,
  IconThumbUp,
  IconWarning,
  IconMusic,
  IconCalendar,
  IconComment,
  IconChart,
  IconAnchor,
} from "@/components/icons/MarineIcons";

/* ── Map Locations ─────────────────────────────────────── */

const MAP_LOCATIONS: { label: string; lat: number; lon: number }[] = [
  { label: "Cape Cod Bay, MA", lat: 41.85, lon: -70.2 },
  { label: "Stellwagen Bank, MA", lat: 42.35, lon: -70.35 },
  { label: "Great South Channel, MA", lat: 41.2, lon: -69.0 },
  { label: "Gulf of Maine", lat: 43.5, lon: -68.0 },
  { label: "Bay of Fundy", lat: 44.8, lon: -66.5 },
  { label: "Narragansett Bay, RI", lat: 41.55, lon: -71.35 },
  { label: "Long Island Sound, NY", lat: 41.1, lon: -72.8 },
  { label: "New York Bight", lat: 40.3, lon: -73.7 },
  { label: "Delaware Bay, DE", lat: 38.9, lon: -75.1 },
  { label: "Chesapeake Bay, VA", lat: 37.5, lon: -76.1 },
  { label: "Cape Hatteras, NC", lat: 35.2, lon: -75.5 },
  { label: "Charleston, SC", lat: 32.7, lon: -79.9 },
  { label: "Florida Straits", lat: 25.0, lon: -80.5 },
  { label: "Gulf of Mexico", lat: 27.5, lon: -90.0 },
  { label: "Puerto Rico Trench", lat: 19.5, lon: -66.0 },
  { label: "Monterey Bay, CA", lat: 36.8, lon: -122.0 },
  { label: "San Francisco Bay, CA", lat: 37.7, lon: -122.5 },
  { label: "Channel Islands, CA", lat: 34.0, lon: -119.7 },
  { label: "Point Reyes, CA", lat: 38.0, lon: -123.0 },
  { label: "San Diego, CA", lat: 32.7, lon: -117.2 },
  { label: "Olympic Coast, WA", lat: 47.5, lon: -124.7 },
  { label: "Puget Sound, WA", lat: 47.6, lon: -122.4 },
  { label: "San Juan Islands, WA", lat: 48.5, lon: -123.1 },
  { label: "Columbia River, OR", lat: 46.2, lon: -124.0 },
  { label: "Glacier Bay, AK", lat: 58.5, lon: -136.0 },
  { label: "Prince William Sound, AK", lat: 60.7, lon: -147.0 },
  { label: "Kodiak Island, AK", lat: 57.8, lon: -152.4 },
  { label: "Aleutian Islands, AK", lat: 52.0, lon: -174.0 },
  { label: "Maui Nui, HI", lat: 20.8, lon: -156.5 },
  { label: "Kailua-Kona, HI", lat: 19.6, lon: -156.0 },
  { label: "North Shore Oahu, HI", lat: 21.6, lon: -158.1 },
  { label: "Georges Bank", lat: 41.3, lon: -67.5 },
  { label: "Norfolk Canyon", lat: 36.9, lon: -74.6 },
  { label: "Hudson Canyon", lat: 39.5, lon: -72.5 },
  { label: "Cordell Bank, CA", lat: 38.0, lon: -123.4 },
];

/* ── Types ──────────────────────────────────────────────── */

interface EventMember {
  user_id: number;
  display_name: string;
  role: string;
  joined_at: string;
  reputation_tier: string | null;
  avatar_url: string | null;
}

interface EventDetail {
  id: string;
  title: string;
  description: string | null;
  event_type: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  lat: number | null;
  lon: number | null;
  location_name: string | null;
  is_public: boolean;
  invite_code: string | null;
  creator_id: number;
  creator_name: string;
  creator_avatar_url: string | null;
  creator_tier: string | null;
  member_count: number;
  sighting_count: number;
  created_at: string;
  updated_at: string | null;
  cover_url: string | null;
  members: EventMember[];
  vessel_id: number | null;
  vessel_name: string | null;
  vessel_type: string | null;
}

interface EventSighting {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  species_guess: string | null;
  model_species: string | null;
  model_confidence: number | null;
  risk_category: string | null;
  risk_score: number | null;
  verification_status: string;
  community_agree: number;
  community_disagree: number;
  has_photo: boolean;
  has_audio: boolean;
  submitter_name: string | null;
  submitter_id: number | null;
  submitter_tier: string | null;
  submitter_avatar: string | null;
}

interface EventComment {
  id: number;
  event_id: string;
  user_id: number;
  display_name: string | null;
  reputation_tier: string | null;
  avatar_url: string | null;
  body: string;
  created_at: string;
  updated_at: string | null;
}

interface SpeciesCount {
  species: string;
  count: number;
}

interface GalleryPhoto {
  id: number;
  event_id: string;
  user_id: number;
  url: string;
  caption: string | null;
  created_at: string | null;
  uploader_name: string | null;
  uploader_avatar_url: string | null;
  uploader_tier: string | null;
}

interface EventStats {
  total_sightings: number;
  unique_species: number;
  species_breakdown: SpeciesCount[];
  unique_contributors: number;
  top_contributors: {
    user_id: number;
    display_name: string;
    avatar_filename?: string;
    reputation_tier?: string;
    count: number;
  }[];
  verified_count: number;
  has_photo_count: number;
  has_audio_count: number;
  highest_risk_score: number | null;
  highest_risk_category: string | null;
  avg_risk_score: number | null;
  date_range_start: string | null;
  date_range_end: string | null;
  interaction_types: { type: string; count: number }[];
}

/* ── Style Maps ────────────────────────────────────────── */

const EVENT_TYPE_META: Record<
  string,
  { label: string; Icon: React.FC<{ className?: string }> }
> = {
  whale_watching: { label: "Whale Watching", Icon: IconWhale },
  research_expedition: { label: "Research Expedition", Icon: IconMicroscope },
  citizen_science: { label: "Citizen Science", Icon: IconEye },
  cleanup: { label: "Cleanup", Icon: IconStar },
  educational: { label: "Educational", Icon: IconClipboard },
  other: { label: "Other", Icon: IconPin },
};

const STATUS_STYLE: Record<
  string,
  { bg: string; dot: string; text: string; label: string }
> = {
  upcoming: {
    bg: "bg-blue-500/10",
    dot: "bg-blue-400",
    text: "text-blue-300",
    label: "Upcoming",
  },
  active: {
    bg: "bg-emerald-500/10",
    dot: "bg-emerald-400",
    text: "text-emerald-300",
    label: "Active",
  },
  completed: {
    bg: "bg-slate-500/10",
    dot: "bg-slate-400",
    text: "text-slate-300",
    label: "Completed",
  },
  cancelled: {
    bg: "bg-red-500/10",
    dot: "bg-red-400",
    text: "text-red-300",
    label: "Cancelled",
  },
};

const ROLE_STYLE: Record<string, { bg: string; text: string }> = {
  creator: { bg: "bg-amber-500/15", text: "text-amber-300" },
  organizer: { bg: "bg-purple-500/15", text: "text-purple-300" },
  member: { bg: "bg-ocean-500/15", text: "text-ocean-300" },
};

const RISK_STYLE: Record<string, string> = {
  critical: "bg-red-500/15 text-red-300",
  high: "bg-orange-500/15 text-orange-300",
  medium: "bg-yellow-500/15 text-yellow-300",
  low: "bg-green-500/15 text-green-300",
};

const SPECIES_COLOR: Record<string, string> = {
  humpback_whale: "bg-ocean-400",
  blue_whale: "bg-blue-400",
  right_whale: "bg-slate-400",
  fin_whale: "bg-indigo-400",
  sperm_whale: "bg-purple-400",
  killer_whale: "bg-slate-600",
  minke_whale: "bg-teal-400",
  sei_whale: "bg-cyan-400",
  gray_whale: "bg-zinc-400",
};

const INTERACTION_LABELS: Record<string, string> = {
  passive_observation: "Passive Observation",
  vessel_approach: "Vessel Approach",
  near_miss: "Near Miss",
  strike: "Strike",
  entanglement: "Entanglement",
  stranding: "Stranding",
  acoustic_detection: "Acoustic Detection",
  other: "Other",
};

/* ── Link Sighting Modal ──────────────────────────────── */

function LinkSightingModal({
  open,
  onClose,
  onLinked,
  eventId,
  token,
}: {
  open: boolean;
  onClose: () => void;
  onLinked: () => void;
  eventId: string;
  token: string | null;
}) {
  const [submissions, setSubmissions] = useState<
    {
      id: string;
      species_guess: string | null;
      model_species: string | null;
      created_at: string;
    }[]
  >([]);
  const [loadingSubs, setLoadingSubs] = useState(false);

  useEffect(() => {
    if (!open || !token) return;
    setLoadingSubs(true);
    fetch(`${API_BASE}/api/v1/submissions/mine?limit=100`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => setSubmissions(d.submissions ?? []))
      .catch(() => setSubmissions([]))
      .finally(() => setLoadingSubs(false));
  }, [open, token]);

  if (!open) return null;

  const handleLink = async (subId: string) => {
    if (!token) return;
    const res = await fetch(
      `${API_BASE}/api/v1/events/${eventId}/sightings/${subId}`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` } },
    );
    if (res.ok) {
      onLinked();
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/80 backdrop-blur-sm">
      <div className="glass-panel-strong mx-4 w-full max-w-lg rounded-2xl p-6">
        <h2 className="mb-4 text-lg font-bold text-white">Link an Interaction</h2>
        <p className="mb-4 text-xs text-slate-400">
          Select one of your interactions to link it to this event.
        </p>

        {loadingSubs ? (
          <div className="flex justify-center py-8">
            <SonarPing size={40} ringCount={2} active />
          </div>
        ) : submissions.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            No interactions found. Submit an interaction first!
          </p>
        ) : (
          <div className="max-h-72 space-y-2 overflow-y-auto">
            {submissions.map((s) => (
              <button
                key={s.id}
                onClick={() => handleLink(s.id)}
                className="flex w-full items-center justify-between rounded-lg border border-ocean-800/30 px-3 py-2 text-left text-sm transition hover:border-ocean-600/40 hover:bg-ocean-900/30"
              >
                <div>
                  <span className="font-medium text-white">
                    {s.model_species ?? s.species_guess ?? "Unknown species"}
                  </span>
                  <span className="ml-2 text-xs text-slate-500">
                    {new Date(s.created_at).toLocaleDateString()}
                  </span>
                </div>
                <span className="text-xs text-ocean-400">Link →</span>
              </button>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-400 transition hover:text-white"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Edit Event Modal ──────────────────────────────────── */

function EditEventModal({
  open,
  onClose,
  onSaved,
  event,
  token,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  event: EventDetail;
  token: string | null;
}) {
  const [title, setTitle] = useState(event.title);
  const [description, setDescription] = useState(
    event.description ?? "",
  );
  const [eventType, setEventType] = useState(event.event_type);
  const [status, setStatus] = useState(event.status);
  const [startDate, setStartDate] = useState(
    event.start_date?.slice(0, 10) ?? "",
  );
  const [endDate, setEndDate] = useState(
    event.end_date?.slice(0, 10) ?? "",
  );
  const [locationIdx, setLocationIdx] = useState<number>(() => {
    if (!event.location_name) return -1;
    return MAP_LOCATIONS.findIndex(
      (l) => l.label === event.location_name,
    );
  });
  const [locationSearch, setLocationSearch] = useState("");
  const [locationOpen, setLocationOpen] = useState(false);
  const [isPublic, setIsPublic] = useState(event.is_public);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Re-sync form when event changes while modal is closed */
  useEffect(() => {
    if (!open) return;
    setTitle(event.title);
    setDescription(event.description ?? "");
    setEventType(event.event_type);
    setStatus(event.status);
    setStartDate(event.start_date?.slice(0, 10) ?? "");
    setEndDate(event.end_date?.slice(0, 10) ?? "");
    setLocationIdx(
      event.location_name
        ? MAP_LOCATIONS.findIndex(
            (l) => l.label === event.location_name,
          )
        : -1,
    );
    setIsPublic(event.is_public);
    setError(null);
  }, [open, event]);

  const filteredLocations = MAP_LOCATIONS.filter((l) =>
    l.label.toLowerCase().includes(locationSearch.toLowerCase()),
  );
  const selectedLocation =
    locationIdx >= 0 ? MAP_LOCATIONS[locationIdx] : null;

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        title: title.trim(),
        description: description.trim() || null,
        event_type: eventType,
        status,
        is_public: isPublic,
        start_date: startDate || null,
        end_date: endDate || null,
      };
      if (selectedLocation) {
        body.location_name = selectedLocation.label;
        body.lat = selectedLocation.lat;
        body.lon = selectedLocation.lon;
      } else {
        body.location_name = null;
        body.lat = null;
        body.lon = null;
      }

      const res = await fetch(
        `${API_BASE}/api/v1/events/${event.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        },
      );
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(
          d?.detail || `Error ${res.status}`,
        );
      }
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to update event",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/80 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="glass-panel-strong mx-4 max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-2xl p-6"
      >
        <h2 className="text-lg font-bold text-white">
          Edit Event
        </h2>

        {error && (
          <div className="rounded-lg bg-red-500/15 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">
            Title *
          </label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            minLength={3}
            maxLength={200}
            className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
            placeholder="e.g. Monterey Bay Research Trip"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            maxLength={2000}
            className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
            placeholder="What's the event about?"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Type
            </label>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            >
              {Object.entries(EVENT_TYPE_META).map(
                ([k, v]) => (
                  <option key={k} value={k}>
                    {v.label}
                  </option>
                ),
              )}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            >
              {Object.entries(STATUS_STYLE).map(
                ([k, v]) => (
                  <option key={k} value={k}>
                    {v.label}
                  </option>
                ),
              )}
            </select>
          </div>
        </div>

        {/* Location dropdown */}
        <div className="relative">
          <label className="mb-1 block text-xs font-medium text-slate-400">
            Location
          </label>
          <button
            type="button"
            onClick={() => setLocationOpen(!locationOpen)}
            className="flex w-full items-center justify-between rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-left text-sm text-white focus:border-ocean-500 focus:outline-none"
          >
            <span
              className={
                selectedLocation
                  ? "text-white"
                  : "text-slate-500"
              }
            >
              {selectedLocation
                ? selectedLocation.label
                : "Select location…"}
            </span>
            <svg
              className={`h-4 w-4 text-slate-500 transition-transform ${locationOpen ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 8.25l-7.5 7.5-7.5-7.5"
              />
            </svg>
          </button>
          {locationOpen && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-hidden rounded-lg border border-ocean-800/50 bg-abyss-900 shadow-xl">
              <div className="border-b border-ocean-800/30 p-2">
                <input
                  autoFocus
                  value={locationSearch}
                  onChange={(e) =>
                    setLocationSearch(e.target.value)
                  }
                  placeholder="Search locations…"
                  className="w-full rounded-md border border-ocean-800/40 bg-abyss-950/60 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
                />
              </div>
              <div className="max-h-44 overflow-y-auto">
                {selectedLocation && (
                  <button
                    type="button"
                    onClick={() => {
                      setLocationIdx(-1);
                      setLocationSearch("");
                      setLocationOpen(false);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-500 transition hover:bg-ocean-800/20"
                  >
                    ✕ Clear selection
                  </button>
                )}
                {filteredLocations.length === 0 ? (
                  <p className="px-3 py-4 text-center text-xs text-slate-500">
                    No matching locations
                  </p>
                ) : (
                  filteredLocations.map((loc) => {
                    const idx = MAP_LOCATIONS.indexOf(loc);
                    return (
                      <button
                        type="button"
                        key={idx}
                        onClick={() => {
                          setLocationIdx(idx);
                          setLocationSearch("");
                          setLocationOpen(false);
                        }}
                        className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition hover:bg-ocean-800/20 ${
                          locationIdx === idx
                            ? "bg-ocean-600/15 text-ocean-300"
                            : "text-white"
                        }`}
                      >
                        <IconPin className="h-3 w-3 flex-shrink-0 text-ocean-500" />
                        {loc.label}
                        <span className="ml-auto text-[10px] text-slate-600">
                          {loc.lat.toFixed(1)}°,{" "}
                          {loc.lon.toFixed(1)}°
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="rounded-lg border border-ocean-800/30 bg-abyss-900/40 p-3">
          <label className="flex items-start gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) =>
                setIsPublic(e.target.checked)
              }
              className="mt-0.5 rounded border-ocean-700 bg-abyss-900"
            />
            <div>
              <span className="font-medium text-white">
                {isPublic
                  ? "Public event"
                  : "Private / Invite only"}
              </span>
              <p className="mt-0.5 text-xs text-slate-500">
                {isPublic
                  ? "Visible to all users. Anyone can browse and join."
                  : "Only visible to members. Others must use an invite link to join."}
              </p>
            </div>
          </label>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-400 transition hover:text-white"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !title.trim()}
            className="rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-5 py-2 text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400 disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ── Event Summary Card ───────────────────────────────── */

function EventSummaryCard({ stats }: { stats: EventStats }) {
  if (stats.total_sightings === 0) {
    return (
      <div className="glass-panel rounded-2xl border border-ocean-800/30 p-6">
        <h2 className="mb-3 flex items-center gap-2 text-base font-bold text-white">
          <IconChart className="h-4 w-4 text-ocean-400" />
          Event Summary
        </h2>
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <IconWhale className="h-12 w-12 text-ocean-800/40" />
          <p className="text-sm text-slate-500">
            No interactions yet — be the first to report one!
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl border border-ocean-800/30 p-6">
      <h2 className="mb-4 flex items-center gap-2 text-base font-bold text-white">
        <IconChart className="h-4 w-4 text-ocean-400" />
        Event Summary
      </h2>

      {/* Top-line stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl bg-ocean-500/10 p-3 text-center">
          <span className="block text-2xl font-black text-ocean-300">
            {stats.total_sightings}
          </span>
          <span className="text-xs text-slate-400">Interactions</span>
        </div>
        <div className="rounded-xl bg-bioluminescent-500/10 p-3 text-center">
          <span className="block text-2xl font-black text-bioluminescent-300">
            {stats.unique_species}
          </span>
          <span className="text-xs text-slate-400">Species Spotted</span>
        </div>
        <div className="rounded-xl bg-purple-500/10 p-3 text-center">
          <span className="block text-2xl font-black text-purple-300">
            {stats.unique_contributors}
          </span>
          <span className="text-xs text-slate-400">Contributors</span>
        </div>
        <div className="rounded-xl bg-emerald-500/10 p-3 text-center">
          <span className="block text-2xl font-black text-emerald-300">
            {stats.verified_count}
          </span>
          <span className="text-xs text-slate-400">Verified</span>
        </div>
      </div>

      {/* Species breakdown */}
      {stats.species_breakdown.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Species Spotted
          </h3>
          <div className="space-y-2">
            {stats.species_breakdown.map((sp) => {
              const dotColor = SPECIES_COLOR[sp.species] ?? "bg-ocean-500";
              const pct = Math.round(
                (sp.count / stats.total_sightings) * 100,
              );
              return (
                <div key={sp.species} className="flex items-center gap-3">
                  <span className={`inline-block h-3 w-3 rounded-full ${dotColor}`} />
                  <div className="flex-1">
                    <div className="flex items-baseline justify-between">
                      <span className="text-sm font-medium text-white">
                        {sp.species.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-slate-400">
                        {sp.count} ({pct}%)
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-abyss-800">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-ocean-500 to-bioluminescent-400 transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Risk + media stats row */}
      <div className="mt-5 flex flex-wrap gap-3">
        {stats.has_photo_count > 0 && (
          <div className="flex items-center gap-1.5 rounded-full bg-abyss-900/50 px-3 py-1 text-xs text-slate-300">
            <IconCamera className="h-3.5 w-3.5 text-bioluminescent-400" />
            {stats.has_photo_count} photos
          </div>
        )}
        {stats.has_audio_count > 0 && (
          <div className="flex items-center gap-1.5 rounded-full bg-abyss-900/50 px-3 py-1 text-xs text-slate-300">
            <IconMusic className="h-3.5 w-3.5 text-ocean-400" />
            {stats.has_audio_count} recordings
          </div>
        )}
        {stats.avg_risk_score != null && (
          <div className="flex items-center gap-1.5 rounded-full bg-abyss-900/50 px-3 py-1 text-xs text-slate-300">
            <IconWarning className="h-3.5 w-3.5 text-amber-400" />
            Avg risk: {(stats.avg_risk_score * 100).toFixed(0)}%
          </div>
        )}
        {stats.highest_risk_category && (
          <div
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs ${RISK_STYLE[stats.highest_risk_category] ?? "text-slate-300"}`}
          >
            Peak: {stats.highest_risk_category}
          </div>
        )}
      </div>

      {/* Interaction types */}
      {stats.interaction_types.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Interaction Types
          </h3>
          <div className="flex flex-wrap gap-2">
            {stats.interaction_types.map((it) => (
              <span
                key={it.type}
                className="rounded-full bg-abyss-900/60 px-3 py-1 text-xs text-slate-300"
              >
                {INTERACTION_LABELS[it.type] ?? it.type} ×{it.count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Date range */}
      {stats.date_range_start && (
        <div className="mt-4 flex items-center gap-1.5 text-xs text-slate-500">
          <IconCalendar className="h-3.5 w-3.5 text-slate-400" />
          {new Date(stats.date_range_start).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          })}
          {stats.date_range_end &&
            stats.date_range_end !== stats.date_range_start && (
              <>
                {" – "}
                {new Date(stats.date_range_end).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </>
            )}
        </div>
      )}

      {/* Top contributors */}
      {stats.top_contributors.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Top Contributors
          </h3>
          <div className="flex flex-wrap gap-2">
            {stats.top_contributors.slice(0, 5).map((c) => (
              <Link
                key={c.user_id}
                href={`/users/${c.user_id}`}
                className="flex items-center gap-1.5 rounded-full bg-abyss-900/50 px-2.5 py-1 transition-colors hover:bg-ocean-900/30"
              >
                <UserAvatar
                  displayName={c.display_name ?? "User"}
                  avatarUrl={
                    c.avatar_filename
                      ? `/api/v1/media/avatar/${c.user_id}`
                      : null
                  }
                  size={18}
                />
                <span className="text-xs text-slate-300">
                  {c.display_name}
                </span>
                <span className="text-xs text-ocean-400">×{c.count}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Comment Section ──────────────────────────────────── */

function CommentSection({
  eventId,
  token,
  user,
}: {
  eventId: string;
  token: string | null;
  user: { id: number; display_name?: string; avatar_url?: string | null } | null;
}) {
  const [comments, setComments] = useState<EventComment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editBody, setEditBody] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchComments = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/comments?limit=200`,
      );
      if (!res.ok) return;
      const data = await res.json();
      setComments(data.comments ?? []);
      setTotal(data.total ?? 0);
    } catch {
      /* swallow */
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  const handlePost = async () => {
    if (!token || !body.trim()) return;
    setSending(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/comments`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ body: body.trim() }),
        },
      );
      if (res.ok) {
        setBody("");
        await fetchComments();
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } finally {
      setSending(false);
    }
  };

  const handleEdit = async (commentId: number) => {
    if (!token || !editBody.trim()) return;
    const res = await fetch(
      `${API_BASE}/api/v1/events/${eventId}/comments/${commentId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ body: editBody.trim() }),
      },
    );
    if (res.ok) {
      setEditingId(null);
      setEditBody("");
      await fetchComments();
    }
  };

  const handleDelete = async (commentId: number) => {
    if (!token || !confirm("Delete this comment?")) return;
    const res = await fetch(
      `${API_BASE}/api/v1/events/${eventId}/comments/${commentId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    if (res.ok) await fetchComments();
  };

  const fmtTime = (d: string) =>
    new Date(d).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });

  return (
    <div className="glass-panel rounded-2xl border border-ocean-800/30 p-6">
      <h2 className="mb-4 flex items-center gap-2 text-base font-bold text-white">
        <IconComment className="h-4 w-4 text-ocean-400" />
        Discussion
        {total > 0 && (
          <span className="text-xs font-normal text-slate-500">
            ({total})
          </span>
        )}
      </h2>

      {loading ? (
        <div className="flex justify-center py-6">
          <SonarPing size={36} ringCount={2} active />
        </div>
      ) : comments.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          No comments yet — start the conversation!
        </p>
      ) : (
        <div className="max-h-96 space-y-4 overflow-y-auto pr-1">
          {comments.map((c) => {
            const isAuthor = user && c.user_id === user.id;
            const isEditing = editingId === c.id;

            return (
              <div
                key={c.id}
                className="-mx-2 group flex gap-3 rounded-lg border border-transparent p-2 transition hover:border-ocean-800/20 hover:bg-abyss-900/30"
              >
                <UserAvatar
                  displayName={c.display_name ?? "User"}
                  avatarUrl={c.avatar_url}
                  size={32}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <Link
                      href={user && c.user_id === user.id ? "/profile" : `/users/${c.user_id}`}
                      className="text-sm font-semibold text-white transition-colors hover:text-ocean-300"
                    >
                      {c.display_name ?? "User"}
                    </Link>
                    {c.reputation_tier && (
                      <span className="text-xs text-slate-500">
                        {c.reputation_tier}
                      </span>
                    )}
                    <span className="text-xs text-slate-600">
                      {fmtTime(c.created_at)}
                    </span>
                    {c.updated_at && (
                      <span className="text-xs italic text-slate-600">
                        (edited)
                      </span>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="mt-1">
                      <textarea
                        value={editBody}
                        onChange={(e) => setEditBody(e.target.value)}
                        className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
                        rows={2}
                      />
                      <div className="mt-1 flex gap-2">
                        <button
                          onClick={() => handleEdit(c.id)}
                          className="rounded-md bg-ocean-600/30 px-2.5 py-1 text-xs text-ocean-300 hover:bg-ocean-500/40"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => {
                            setEditingId(null);
                            setEditBody("");
                          }}
                          className="rounded-md px-2.5 py-1 text-xs text-slate-400 hover:text-white"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-0.5 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
                      {c.body}
                    </p>
                  )}

                  {isAuthor && !isEditing && (
                    <div className="mt-1 flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        onClick={() => {
                          setEditingId(c.id);
                          setEditBody(c.body);
                        }}
                        className="text-xs text-slate-500 hover:text-ocean-400"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(c.id)}
                        className="text-xs text-slate-500 hover:text-red-400"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Compose area */}
      {user ? (
        <div className="mt-4 flex gap-3">
          <UserAvatar
            displayName={user.display_name ?? "You"}
            avatarUrl={user.avatar_url ?? null}
            size={32}
          />
          <div className="flex-1">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write a comment…"
              maxLength={2000}
              rows={2}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
            />
            <div className="mt-1 flex items-center justify-between">
              <span className="text-xs text-slate-600">
                {body.length}/2000
              </span>
              <button
                onClick={handlePost}
                disabled={!body.trim() || sending}
                className="rounded-lg bg-ocean-600/30 px-4 py-1.5 text-xs font-medium text-ocean-300 transition hover:bg-ocean-500/40 disabled:opacity-30"
              >
                {sending ? "Posting…" : "Post"}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-ocean-800/20 bg-abyss-900/40 p-3 text-center text-sm text-slate-500">
          <Link href="/auth" className="text-ocean-400 underline">
            Sign in
          </Link>{" "}
          to join the discussion.
        </div>
      )}
    </div>
  );
}

/* ── Cover Photo Upload ───────────────────────────────── */

function CoverPhoto({
  eventId,
  coverUrl,
  canEdit,
  token,
  onUploaded,
}: {
  eventId: string;
  coverUrl: string | null;
  canEdit: boolean;
  token: string | null;
  onUploaded: () => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("image", file);
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/cover`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        },
      );
      if (res.ok) {
        onUploaded();
      } else {
        const body = await res.json().catch(() => null);
        setUploadError(
          body?.detail ?? `Upload failed (${res.status})`,
        );
      }
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : "Upload failed",
      );
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const imgSrc = coverUrl
    ? `${API_BASE}/api/v1/events/${eventId}/cover`
    : null;

  return (
    <div className="relative z-20 overflow-hidden rounded-2xl border border-ocean-800/30">
      {imgSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imgSrc}
          alt="Event cover"
          className="h-48 w-full object-cover sm:h-56"
        />
      ) : canEdit ? (
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="flex h-48 w-full items-center justify-center bg-gradient-to-br from-ocean-900/40 via-abyss-950 to-ocean-900/20 transition hover:from-ocean-800/40 hover:via-abyss-900 sm:h-56"
        >
          <div className="text-center">
            <IconCamera className="mx-auto h-10 w-10 text-ocean-800/60" />
            <p className="mt-2 text-xs text-slate-400">
              Click to add a cover photo
            </p>
          </div>
        </button>
      ) : (
        <div className="flex h-48 items-center justify-center bg-gradient-to-br from-ocean-900/40 via-abyss-950 to-ocean-900/20 sm:h-56">
          <div className="text-center">
            <IconCamera className="mx-auto h-10 w-10 text-ocean-800/40" />
          </div>
        </div>
      )}
      {/* Gradient overlay for text readability */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-abyss-950/80 via-transparent to-abyss-950/20" />

      {/* Upload error toast */}
      {uploadError && (
        <div className="absolute left-3 top-3 z-30 max-w-xs rounded-lg bg-red-500/90 px-3 py-1.5 text-xs font-medium text-white shadow-lg backdrop-blur-sm">
          {uploadError}
        </div>
      )}

      {canEdit && imgSrc && (
        <>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="absolute bottom-3 right-3 z-30 flex items-center gap-1.5 rounded-lg bg-abyss-950/70 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm transition hover:bg-abyss-900/90 disabled:opacity-50"
          >
            <IconCamera className="h-3.5 w-3.5" />
            {uploading ? "Uploading…" : "Change Cover"}
          </button>
        </>
      )}
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleUpload}
        className="sr-only"
      />
    </div>
  );
}

/* ── Main Page ─────────────────────────────────────────── */

export default function EventDetailPage() {
  const params = useParams();
  const router = useRouter();
  const eventId = params.id as string;
  const { user, token } = useAuth();

  const [event, setEvent] = useState<EventDetail | null>(null);
  const [sightings, setSightings] = useState<EventSighting[]>([]);
  const [sightingTotal, setSightingTotal] = useState(0);
  const [stats, setStats] = useState<EventStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [joining, setJoining] = useState(false);
  const [tab, setTab] = useState<"sightings" | "gallery" | "members">("sightings");

  /* ── Gallery state ──────────────────────────────── */
  const [gallery, setGallery] = useState<GalleryPhoto[]>([]);
  const [galleryTotal, setGalleryTotal] = useState(0);
  const [galleryUploading, setGalleryUploading] = useState(false);
  const [lightbox, setLightbox] = useState<GalleryPhoto | null>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

  const isMember = event?.members?.some((m) => m.user_id === user?.id);
  const isCreator = event?.creator_id === user?.id;
  const myRole = event?.members?.find(
    (m) => m.user_id === user?.id,
  )?.role;
  const canEditCover = myRole === "creator" || myRole === "organizer";

  const fetchEvent = useCallback(async () => {
    try {
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}`,
        { headers },
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setEvent(data);
    } catch {
      setEvent(null);
    } finally {
      setLoading(false);
    }
  }, [eventId, token]);

  const fetchSightings = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/sightings?limit=100`,
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setSightings(data.sightings ?? []);
      setSightingTotal(data.total ?? 0);
    } catch {
      setSightings([]);
    }
  }, [eventId]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/stats`,
      );
      if (!res.ok) return;
      setStats(await res.json());
    } catch {
      /* swallow */
    }
  }, [eventId]);

  const fetchGallery = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/gallery?limit=200`,
      );
      if (!res.ok) return;
      const data = await res.json();
      setGallery(data.photos ?? []);
      setGalleryTotal(data.total ?? 0);
    } catch {
      /* swallow */
    }
  }, [eventId]);

  const handleGalleryUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setGalleryUploading(true);
    try {
      const form = new FormData();
      form.append("image", file);
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/gallery`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        },
      );
      if (res.ok) await fetchGallery();
    } finally {
      setGalleryUploading(false);
      if (galleryInputRef.current) galleryInputRef.current.value = "";
    }
  };

  const handleDeletePhoto = async (photoId: number) => {
    if (!token || !confirm("Delete this photo?")) return;
    await fetch(
      `${API_BASE}/api/v1/events/${eventId}/gallery/${photoId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    setLightbox(null);
    await fetchGallery();
  };

  useEffect(() => {
    fetchEvent();
    fetchSightings();
    fetchStats();
    fetchGallery();
  }, [fetchEvent, fetchSightings, fetchStats, fetchGallery]);

  const handleJoin = async () => {
    if (!token) return;
    setJoining(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/events/${eventId}/join`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (res.ok) await fetchEvent();
    } finally {
      setJoining(false);
    }
  };

  const handleLeave = async () => {
    if (!token) return;
    await fetch(`${API_BASE}/api/v1/events/${eventId}/leave`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    await fetchEvent();
  };

  const handleDelete = async () => {
    if (!token || !confirm("Delete this event? This cannot be undone."))
      return;
    const res = await fetch(`${API_BASE}/api/v1/events/${eventId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) router.push("/community?tab=events");
  };

  const copyInvite = () => {
    if (!event?.invite_code) return;
    const url = `${window.location.origin}/events/join/${event.invite_code}`;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fmtDate = (d: string | null) =>
    d
      ? new Date(d).toLocaleDateString("en-US", {
          month: "long",
          day: "numeric",
          year: "numeric",
        })
      : null;

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-abyss-950 pt-20">
        <SonarPing size={56} ringCount={3} active />
      </main>
    );
  }

  if (!event) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-abyss-950 pt-20">
        <IconWarning className="h-12 w-12 text-red-400/50" />
        <p className="text-sm text-slate-400">Event not found.</p>
        <Link
          href="/community?tab=events"
          className="text-sm text-ocean-400 underline"
        >
          ← Back to events
        </Link>
      </main>
    );
  }

  const typeMeta =
    EVENT_TYPE_META[event.event_type] ?? EVENT_TYPE_META.other;
  const statusStyle =
    STATUS_STYLE[event.status] ?? STATUS_STYLE.upcoming;
  const TypeIcon = typeMeta.Icon;

  return (
    <main className="min-h-screen bg-abyss-950 pb-16 pt-24">
      <div className="mx-auto max-w-4xl px-4 sm:px-6">
        {/* Breadcrumb */}
        <Link
          href="/community?tab=events"
          className="mb-4 inline-flex items-center gap-1 text-xs text-slate-500 transition hover:text-ocean-400"
        >
          ← Back to events
        </Link>

        {/* Cover photo */}
        <div className="mb-2">
          <CoverPhoto
            eventId={eventId}
            coverUrl={event.cover_url}
            canEdit={canEditCover}
            token={token}
            onUploaded={fetchEvent}
          />
        </div>

        {/* Title section */}
        <div className="glass-panel relative z-10 rounded-2xl border border-ocean-800/30 p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-ocean-500/15">
                <TypeIcon className="h-6 w-6 text-ocean-300" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white sm:text-2xl">
                  {event.title}
                </h1>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                  <span>{typeMeta.label}</span>
                  <span className="text-slate-600">·</span>
                  <span
                    className={`flex items-center gap-1 ${statusStyle.text}`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`}
                    />
                    {statusStyle.label}
                  </span>
                  <span className="text-slate-600">·</span>
                  {event.is_public ? (
                    <span className="flex items-center gap-1 text-slate-400">
                      <IconEye className="h-3 w-3" /> Public
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-amber-400">
                      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                      </svg>
                      Invite Only
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              {!isMember && user && event.status !== "cancelled" && (
                event.is_public ? (
                  <button
                    onClick={handleJoin}
                    disabled={joining}
                    className="rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-4 py-2 text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400 disabled:opacity-50"
                  >
                    {joining ? "Joining…" : "Join Event"}
                  </button>
                ) : (
                  <span className="flex items-center gap-1.5 rounded-lg border border-amber-800/30 bg-amber-500/10 px-4 py-2 text-sm font-medium text-amber-300">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                    Invite Only
                  </span>
                )
              )}
              {isMember && !isCreator && (
                <button
                  onClick={handleLeave}
                  className="rounded-lg border border-red-800/30 px-3 py-1.5 text-xs text-red-400 transition hover:bg-red-500/10"
                >
                  Leave
                </button>
              )}
              {canEditCover && (
                <button
                  onClick={() => setEditOpen(true)}
                  className="rounded-lg border border-ocean-800/30 px-3 py-1.5 text-xs text-ocean-400 transition hover:border-ocean-600/40 hover:bg-ocean-900/30"
                >
                  Edit
                </button>
              )}
              {isCreator && (
                <button
                  onClick={handleDelete}
                  className="rounded-lg border border-red-800/30 px-3 py-1.5 text-xs text-red-400 transition hover:bg-red-500/10"
                >
                  Delete
                </button>
              )}
            </div>
          </div>

          {/* Description */}
          {event.description && (
            <p className="mt-4 text-sm leading-relaxed text-slate-300">
              {event.description}
            </p>
          )}

          {/* Meta grid */}
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {event.location_name && (
              <div className="rounded-lg bg-abyss-900/50 px-3 py-2">
                <span className="block text-xs text-slate-500">
                  Location
                </span>
                <span className="flex items-center gap-1 text-sm text-white">
                  <IconPin className="h-3.5 w-3.5 text-ocean-400" />
                  {event.location_name}
                </span>
              </div>
            )}
            {event.start_date && (
              <div className="rounded-lg bg-abyss-900/50 px-3 py-2 sm:col-span-2">
                <span className="block text-xs text-slate-500">Date</span>
                <div className="mt-1 flex items-center gap-3">
                  {/* Calendar icon block */}
                  <div className="flex h-10 w-10 flex-col items-center justify-center rounded-lg border border-ocean-800/30 bg-ocean-500/10">
                    <span className="text-[9px] font-bold uppercase leading-none text-ocean-400">
                      {new Date(event.start_date).toLocaleDateString("en-US", { month: "short" })}
                    </span>
                    <span className="text-sm font-black leading-tight text-white">
                      {new Date(event.start_date).getDate()}
                    </span>
                  </div>
                  <div>
                    <span className="block text-sm font-medium text-white">
                      {new Date(event.start_date).toLocaleDateString("en-US", {
                        weekday: "long",
                        month: "long",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                    {event.end_date && event.end_date !== event.start_date && (
                      <span className="mt-0.5 flex items-center gap-1 text-xs text-slate-400">
                        <span className="text-slate-600">→</span>
                        {new Date(event.end_date).toLocaleDateString("en-US", {
                          weekday: "long",
                          month: "long",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
            <div className="rounded-lg bg-abyss-900/50 px-3 py-2">
              <span className="block text-xs text-slate-500">
                Members
              </span>
              <span className="flex items-center gap-1 text-sm text-white">
                <IconUsers className="h-3.5 w-3.5 text-ocean-400" />
                {event.member_count}
              </span>
            </div>
            <div className="rounded-lg bg-abyss-900/50 px-3 py-2">
              <span className="block text-xs text-slate-500">
                Interactions
              </span>
              <span className="flex items-center gap-1 text-sm text-white">
                <IconCamera className="h-3.5 w-3.5 text-bioluminescent-400" />
                {event.sighting_count}
              </span>
            </div>
            {event.vessel_name && (
              <div className="rounded-lg bg-abyss-900/50 px-3 py-2">
                <span className="block text-xs text-slate-500">
                  Vessel
                </span>
                <Link
                  href={`/boat/${event.vessel_id}`}
                  className="flex items-center gap-1 text-sm text-ocean-300 transition hover:text-ocean-200"
                >
                  <IconAnchor className="h-3.5 w-3.5 text-ocean-400" />
                  {event.vessel_name}
                  <span className="text-[10px] text-slate-500">({event.vessel_type})</span>
                </Link>
              </div>
            )}
          </div>

          {/* Organiser + invite + report button */}
          <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-ocean-800/20 pt-4">
            <Link
              href={event.creator_id === user?.id ? "/profile" : `/users/${event.creator_id}`}
              className="flex items-center gap-2 rounded-lg transition hover:bg-abyss-900/40 -m-1 p-1"
            >
              <UserAvatar
                displayName={event.creator_name}
                avatarUrl={event.creator_avatar_url}
                size={28}
              />
              <div>
                <span className="text-xs text-slate-500">
                  Organised by
                </span>
                <span className="block text-sm font-medium text-white group-hover:text-ocean-300">
                  {event.creator_name}
                </span>
              </div>
            </Link>

            <div className="ml-auto flex items-center gap-2">
              {myRole && (
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_STYLE[myRole]?.bg ?? ""} ${ROLE_STYLE[myRole]?.text ?? ""}`}
                >
                  {myRole === "creator" ? "Organiser" : myRole}
                </span>
              )}
              {(isMember || isCreator) && event.invite_code && (
                <button
                  onClick={copyInvite}
                  className="flex items-center gap-1.5 rounded-lg border border-ocean-800/30 px-3 py-1.5 text-xs text-ocean-400 transition hover:border-ocean-600/40 hover:bg-ocean-900/30"
                >
                  {copied ? (
                    <>
                      <IconCheck className="h-3.5 w-3.5" /> Copied!
                    </>
                  ) : (
                    <>
                      <IconClipboard className="h-3.5 w-3.5" /> Share
                      Invite
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Interaction CTA banner */}
        {isMember && event.status !== "cancelled" && event.status !== "completed" && (
          <div className="mt-4 overflow-hidden rounded-2xl border border-ocean-700/30 bg-gradient-to-r from-ocean-900/60 via-abyss-900/80 to-bioluminescent-900/40">
            <div className="flex flex-col items-center gap-4 px-6 py-5 sm:flex-row">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-ocean-500/15">
                <IconWhale className="h-7 w-7 text-ocean-300" />
              </div>
              <div className="flex-1 text-center sm:text-left">
                <h3 className="text-sm font-bold text-white">
                  Contribute to this event
                </h3>
                <p className="mt-0.5 text-xs text-slate-400">
                  Report a new whale interaction or link one you&apos;ve already submitted.
                </p>
              </div>
              <div className="flex shrink-0 gap-3">
                <Link
                  href={`/report?event_id=${event.id}${event.vessel_id ? `&vessel_id=${event.vessel_id}` : ""}`}
                  className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-bioluminescent-600 to-bioluminescent-500 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-bioluminescent-600/20 transition-all hover:from-bioluminescent-500 hover:to-bioluminescent-400 hover:shadow-bioluminescent-500/30"
                >
                  <IconCamera className="h-4 w-4" />
                  Report New Interaction
                </Link>
                <button
                  onClick={() => setLinkOpen(true)}
                  className="flex items-center gap-2 rounded-xl border border-ocean-600/40 bg-ocean-600/15 px-5 py-2.5 text-sm font-bold text-ocean-300 transition-all hover:border-ocean-500/50 hover:bg-ocean-500/25"
                >
                  <IconClipboard className="h-4 w-4" />
                  Link Existing
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Summary stats */}
        {stats && (
          <div className="mt-6">
            <EventSummaryCard stats={stats} />
          </div>
        )}

        {/* Tabs */}
        <div className="mb-4 mt-6 flex items-center gap-1 border-b border-ocean-800/20 pb-2">
          {(["sightings", "gallery", "members"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-t-lg px-4 py-2 text-sm font-medium transition-all ${
                tab === t
                  ? "border-b-2 border-ocean-400 text-ocean-300"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {t === "sightings"
                ? `Interactions (${sightingTotal})`
                : t === "gallery"
                  ? `Gallery (${galleryTotal})`
                  : `Members (${event.member_count})`}
            </button>
          ))}

          {isMember && tab === "gallery" && (
            <>
              <button
                onClick={() => galleryInputRef.current?.click()}
                disabled={galleryUploading}
                className="ml-auto rounded-lg bg-ocean-600/20 px-3 py-1.5 text-xs font-medium text-ocean-300 transition hover:bg-ocean-500/30 disabled:opacity-50"
              >
                {galleryUploading ? "Uploading…" : "+ Add Photo"}
              </button>
              <input
                ref={galleryInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleGalleryUpload}
                className="hidden"
              />
            </>
          )}
        </div>

        {/* Tab content */}
        {tab === "sightings" && (
          <div className="space-y-3">
            {sightings.length === 0 ? (
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-ocean-800/30 py-16">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-ocean-500/10">
                  <IconWhale className="h-8 w-8 text-ocean-700/60" />
                </div>
                <div className="text-center">
                  <p className="text-base font-semibold text-slate-400">
                    No interactions yet
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    Be the first to report a whale sighting for this event!
                  </p>
                </div>
                {isMember && (
                  <div className="mt-2 flex gap-3">
                    <Link
                      href={`/report?event_id=${event.id}${event.vessel_id ? `&vessel_id=${event.vessel_id}` : ""}`}
                      className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-bioluminescent-600 to-bioluminescent-500 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-bioluminescent-600/20 transition-all hover:from-bioluminescent-500 hover:to-bioluminescent-400"
                    >
                      <IconCamera className="h-4 w-4" />
                      Report Interaction
                    </Link>
                    <button
                      onClick={() => setLinkOpen(true)}
                      className="flex items-center gap-2 rounded-xl border border-ocean-600/40 bg-ocean-600/15 px-5 py-2.5 text-sm font-bold text-ocean-300 transition-all hover:border-ocean-500/50 hover:bg-ocean-500/25"
                    >
                      <IconClipboard className="h-4 w-4" />
                      Link Existing
                    </button>
                  </div>
                )}
              </div>
            ) : (
              sightings.map((s) => (
                <Link
                  key={s.id}
                  href={`/submissions/${s.id}`}
                  className="glass-panel flex items-center gap-4 rounded-xl border border-ocean-800/30 p-4 transition hover:border-ocean-600/40"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-abyss-900/60">
                    {s.has_photo ? (
                      <IconCamera className="h-5 w-5 text-bioluminescent-400" />
                    ) : s.has_audio ? (
                      <IconWhale className="h-5 w-5 text-ocean-400" />
                    ) : (
                      <IconEye className="h-5 w-5 text-slate-500" />
                    )}
                  </div>
                  <div className="flex-1">
                    <span className="block text-sm font-medium text-white">
                      {s.model_species ??
                        s.species_guess ??
                        "Unknown species"}
                    </span>
                    <span className="text-xs text-slate-500">
                      {new Date(s.created_at).toLocaleDateString()} · by{" "}
                      {s.submitter_id ? (
                        <Link
                          href={s.submitter_id === user?.id ? "/profile" : `/users/${s.submitter_id}`}
                          className="text-slate-400 transition-colors hover:text-ocean-300"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {s.submitter_name ?? "Anonymous"}
                        </Link>
                      ) : (
                        (s.submitter_name ?? "Anonymous")
                      )}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="flex items-center gap-0.5">
                      <IconThumbUp className="h-3 w-3" />{" "}
                      {s.community_agree}
                    </span>
                    {s.risk_category && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${RISK_STYLE[s.risk_category] ?? ""}`}
                      >
                        {s.risk_category}
                      </span>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        )}

        {/* Gallery tab */}
        {tab === "gallery" && (
          <div>
            {gallery.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-16">
                <IconCamera className="h-12 w-12 text-ocean-800/40" />
                <p className="text-sm text-slate-500">
                  No photos yet — be the first to share one!
                </p>
                {isMember && (
                  <button
                    onClick={() => galleryInputRef.current?.click()}
                    disabled={galleryUploading}
                    className="rounded-lg bg-ocean-600/20 px-4 py-2 text-sm text-ocean-300 transition hover:bg-ocean-500/30"
                  >
                    Upload Photo
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {gallery.map((photo) => (
                  <button
                    key={photo.id}
                    onClick={() => setLightbox(photo)}
                    className="group relative aspect-square overflow-hidden rounded-xl border border-ocean-800/30 transition-all hover:border-ocean-600/40 hover:shadow-ocean-sm"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`${API_BASE}${photo.url}`}
                      alt={photo.caption ?? "Event photo"}
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      loading="lazy"
                    />
                    <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-abyss-950/60 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                    {photo.caption && (
                      <div className="absolute bottom-0 left-0 right-0 p-2 opacity-0 transition-opacity group-hover:opacity-100">
                        <p className="line-clamp-2 text-xs text-white/90">
                          {photo.caption}
                        </p>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Lightbox */}
            {lightbox && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/90 backdrop-blur-sm"
                onClick={() => setLightbox(null)}
              >
                <div
                  className="relative mx-4 max-h-[85vh] max-w-4xl overflow-hidden rounded-2xl border border-ocean-800/30 bg-abyss-950/95"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`${API_BASE}${lightbox.url}`}
                    alt={lightbox.caption ?? "Event photo"}
                    className="max-h-[70vh] w-full object-contain"
                  />
                  <div className="flex items-center gap-3 border-t border-ocean-800/20 px-4 py-3">
                    {lightbox.uploader_avatar_url || lightbox.uploader_name ? (
                      <UserAvatar
                        displayName={lightbox.uploader_name ?? "User"}
                        avatarUrl={lightbox.uploader_avatar_url}
                        size={24}
                      />
                    ) : null}
                    <div className="min-w-0 flex-1">
                      {lightbox.uploader_name && (
                        <Link
                          href={`/users/${lightbox.user_id}`}
                          className="text-xs font-medium text-white transition-colors hover:text-ocean-300"
                        >
                          {lightbox.uploader_name}
                        </Link>
                      )}
                      {lightbox.caption && (
                        <p className="mt-0.5 text-xs text-slate-400">
                          {lightbox.caption}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {lightbox.created_at && (
                        <span className="text-xs text-slate-500">
                          {new Date(lightbox.created_at).toLocaleDateString()}
                        </span>
                      )}
                      {user &&
                        (lightbox.user_id === user.id ||
                          myRole === "creator" ||
                          myRole === "organizer") && (
                          <button
                            onClick={() => handleDeletePhoto(lightbox.id)}
                            className="rounded-lg border border-red-800/30 px-2.5 py-1 text-xs text-red-400 transition hover:bg-red-500/10"
                          >
                            Delete
                          </button>
                        )}
                    </div>
                  </div>
                  {/* Close button */}
                  <button
                    onClick={() => setLightbox(null)}
                    className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-abyss-950/70 text-white backdrop-blur-sm transition hover:bg-abyss-900/90"
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "members" && (
          <div className="space-y-2">
            {event.members.map((m) => {
              const roleStyle = ROLE_STYLE[m.role] ?? ROLE_STYLE.member;
              const isOwnProfile = m.user_id === user?.id;
              const profileHref = isOwnProfile
                ? "/profile"
                : `/users/${m.user_id}`;
              return (
                <Link
                  key={m.user_id}
                  href={profileHref}
                  className="glass-panel flex items-center gap-3 rounded-xl border border-ocean-800/30 p-4 transition-all hover:border-ocean-600/40"
                >
                  <UserAvatar
                    displayName={m.display_name}
                    avatarUrl={m.avatar_url}
                    size={36}
                  />
                  <div className="flex-1">
                    <span className="block text-sm font-medium text-white">
                      {m.display_name}
                    </span>
                    <span className="text-xs text-slate-500">
                      Joined{" "}
                      {new Date(m.joined_at).toLocaleDateString()}
                    </span>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${roleStyle.bg} ${roleStyle.text}`}
                  >
                    {m.role === "creator" ? "Organiser" : m.role}
                  </span>
                  {m.reputation_tier && (
                    <span className="text-xs text-slate-500">
                      {m.reputation_tier}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        )}

        {/* Comments */}
        <div className="mt-6">
          <CommentSection
            eventId={eventId}
            token={token}
            user={user}
          />
        </div>
      </div>

      {/* Link sighting modal */}
      <LinkSightingModal
        open={linkOpen}
        onClose={() => setLinkOpen(false)}
        onLinked={() => {
          fetchSightings();
          fetchStats();
        }}
        eventId={eventId}
        token={token}
      />

      {/* Edit event modal */}
      {event && canEditCover && (
        <EditEventModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            fetchEvent();
            fetchStats();
          }}
          event={event}
          token={token}
        />
      )}
    </main>
  );
}
