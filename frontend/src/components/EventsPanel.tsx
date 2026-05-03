"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import { SonarPing } from "@/components/animations";
import UserAvatar from "@/components/UserAvatar";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
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
  IconCalendar,
  IconGlobe,
  IconWaves,
  IconAnchor,
} from "@/components/icons/MarineIcons";

/* ── Map Locations ─────────────────────────────────────── */

const MAP_LOCATIONS: { label: string; lat: number; lon: number }[] = [
  // US East Coast
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
  // US Southeast & Caribbean
  { label: "Florida Straits", lat: 25.0, lon: -80.5 },
  { label: "Gulf of Mexico", lat: 27.5, lon: -90.0 },
  { label: "Puerto Rico Trench", lat: 19.5, lon: -66.0 },
  // US West Coast
  { label: "Monterey Bay, CA", lat: 36.8, lon: -122.0 },
  { label: "San Francisco Bay, CA", lat: 37.7, lon: -122.5 },
  { label: "Channel Islands, CA", lat: 34.0, lon: -119.7 },
  { label: "Point Reyes, CA", lat: 38.0, lon: -123.0 },
  { label: "San Diego, CA", lat: 32.7, lon: -117.2 },
  { label: "Olympic Coast, WA", lat: 47.5, lon: -124.7 },
  { label: "Puget Sound, WA", lat: 47.6, lon: -122.4 },
  { label: "San Juan Islands, WA", lat: 48.5, lon: -123.1 },
  { label: "Columbia River, OR", lat: 46.2, lon: -124.0 },
  // Alaska
  { label: "Glacier Bay, AK", lat: 58.5, lon: -136.0 },
  { label: "Prince William Sound, AK", lat: 60.7, lon: -147.0 },
  { label: "Kodiak Island, AK", lat: 57.8, lon: -152.4 },
  { label: "Aleutian Islands, AK", lat: 52.0, lon: -174.0 },
  // Hawaii
  { label: "Maui Nui, HI", lat: 20.8, lon: -156.5 },
  { label: "Kailua-Kona, HI", lat: 19.6, lon: -156.0 },
  { label: "North Shore Oahu, HI", lat: 21.6, lon: -158.1 },
  // General areas
  { label: "Georges Bank", lat: 41.3, lon: -67.5 },
  { label: "Norfolk Canyon", lat: 36.9, lon: -74.6 },
  { label: "Hudson Canyon", lat: 39.5, lon: -72.5 },
  { label: "Cordell Bank, CA", lat: 38.0, lon: -123.4 },
];

/* ── Types ──────────────────────────────────────────────── */

interface EventSummary {
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
  my_role: string | null;
  created_at: string;
  vessel_id: number | null;
  vessel_name: string | null;
  vessel_type: string | null;
  cover_url: string | null;
}

interface ExternalEvent {
  id: number;
  title: string;
  description: string | null;
  organizer: string;
  source_url: string | null;
  event_type: string;
  tags: string[];
  start_date: string | null;
  end_date: string | null;
  location_name: string | null;
  lat: number | null;
  lon: number | null;
  is_virtual: boolean;
  is_featured: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

/* ── Style Maps ────────────────────────────────────────── */

const EVENT_TYPE_STYLE: Record<
  string,
  { bg: string; text: string; label: string; Icon: React.FC<{ className?: string }> }
> = {
  whale_watching: { bg: "bg-ocean-500/15", text: "text-ocean-300", label: "Whale Watching", Icon: IconWhale },
  research_expedition: { bg: "bg-purple-500/15", text: "text-purple-300", label: "Research Expedition", Icon: IconMicroscope },
  citizen_science: { bg: "bg-emerald-500/15", text: "text-emerald-300", label: "Citizen Science", Icon: IconEye },
  cleanup: { bg: "bg-teal-500/15", text: "text-teal-300", label: "Cleanup", Icon: IconStar },
  educational: { bg: "bg-amber-500/15", text: "text-amber-300", label: "Educational", Icon: IconClipboard },
  other: { bg: "bg-slate-500/15", text: "text-slate-300", label: "Other", Icon: IconPin },
};

const STATUS_STYLE: Record<string, { bg: string; dot: string; text: string; label: string }> = {
  upcoming: { bg: "bg-blue-500/10", dot: "bg-blue-400", text: "text-blue-300", label: "Upcoming" },
  active: { bg: "bg-emerald-500/10", dot: "bg-emerald-400", text: "text-emerald-300", label: "Active" },
  completed: { bg: "bg-slate-500/10", dot: "bg-slate-400", text: "text-slate-300", label: "Completed" },
  cancelled: { bg: "bg-red-500/10", dot: "bg-red-400", text: "text-red-300", label: "Cancelled" },
};

const EXT_TYPE_STYLE: Record<
  string,
  { bg: string; text: string; label: string; Icon: React.FC<{ className?: string }> }
> = {
  workshop: { bg: "bg-amber-500/15", text: "text-amber-300", label: "Workshop", Icon: IconClipboard },
  webinar: { bg: "bg-purple-500/15", text: "text-purple-300", label: "Webinar", Icon: IconEye },
  public_comment: { bg: "bg-rose-500/15", text: "text-rose-300", label: "Public Comment", Icon: IconClipboard },
  conference: { bg: "bg-cyan-500/15", text: "text-cyan-300", label: "Conference", Icon: IconUsers },
  education: { bg: "bg-amber-500/15", text: "text-amber-300", label: "Education", Icon: IconClipboard },
  research: { bg: "bg-purple-500/15", text: "text-purple-300", label: "Research", Icon: IconMicroscope },
  cleanup: { bg: "bg-teal-500/15", text: "text-teal-300", label: "Cleanup", Icon: IconStar },
  other: { bg: "bg-slate-500/15", text: "text-slate-300", label: "Event", Icon: IconPin },
};

type StatusFilter = "all" | "upcoming" | "active" | "completed" | "cancelled";
type TypeFilter = "all" | string;
type ViewMode = "browse" | "mine";
type EventsViewTab = "community" | "featured";

/* ── Create Modal ──────────────────────────────────────── */

function CreateEventModal({
  open,
  onClose,
  onCreated,
  token,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (ev: EventSummary) => void;
  token: string | null;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [eventType, setEventType] = useState("whale_watching");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [locationIdx, setLocationIdx] = useState<number | -1>(-1);
  const [locationSearch, setLocationSearch] = useState("");
  const [locationOpen, setLocationOpen] = useState(false);
  const [isPublic, setIsPublic] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVesselId, setSelectedVesselId] = useState<string>("");
  const [userVessels, setUserVessels] = useState<
    { id: number; vessel_name: string; vessel_type: string }[]
  >([]);

  /* Fetch user's vessels for linking */
  useEffect(() => {
    if (!open || !token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/vessels`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUserVessels(data.vessels ?? []);
          if (data.active_vessel_id) {
            setSelectedVesselId(String(data.active_vessel_id));
          }
        }
      } catch {
        /* ignore */
      }
    })();
  }, [open, token]);

  const filteredLocations = MAP_LOCATIONS.filter((l) =>
    l.label.toLowerCase().includes(locationSearch.toLowerCase()),
  );
  const selectedLocation = locationIdx >= 0 ? MAP_LOCATIONS[locationIdx] : null;

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
        is_public: isPublic,
      };
      if (startDate) body.start_date = startDate;
      if (endDate) body.end_date = endDate;
      if (selectedLocation) {
        body.location_name = selectedLocation.label;
        body.lat = selectedLocation.lat;
        body.lon = selectedLocation.lon;
      }
      if (selectedVesselId) {
        body.vessel_id = Number(selectedVesselId);
      }

      const res = await fetch(`${API_BASE}/api/v1/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail || `Error ${res.status}`);
      }
      const created = await res.json();
      onCreated(created);
      onClose();
      // Reset
      setTitle("");
      setDescription("");
      setEventType("whale_watching");
      setStartDate("");
      setEndDate("");
      setLocationIdx(-1);
      setLocationSearch("");
      setIsPublic(true);
      setSelectedVesselId("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create event");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-abyss-950/80 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="glass-panel-strong mx-4 w-full max-w-lg space-y-4 rounded-2xl p-6"
      >
        <h2 className="text-lg font-bold text-white">Create Event</h2>

        {error && (
          <div className="rounded-lg bg-red-500/15 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">Title *</label>
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
          <label className="mb-1 block text-xs font-medium text-slate-400">Description</label>
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
            <label className="mb-1 block text-xs font-medium text-slate-400">Type</label>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            >
              {Object.entries(EVENT_TYPE_STYLE).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>
          <div className="relative">
            <label className="mb-1 block text-xs font-medium text-slate-400">Location</label>
            <button
              type="button"
              onClick={() => setLocationOpen(!locationOpen)}
              className="flex w-full items-center justify-between rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-left text-sm text-white focus:border-ocean-500 focus:outline-none"
            >
              <span className={selectedLocation ? "text-white" : "text-slate-500"}>
                {selectedLocation ? selectedLocation.label : "Select location…"}
              </span>
              <svg className={`h-4 w-4 text-slate-500 transition-transform ${locationOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            {locationOpen && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-hidden rounded-lg border border-ocean-800/50 bg-abyss-900 shadow-xl">
                <div className="border-b border-ocean-800/30 p-2">
                  <input
                    autoFocus
                    value={locationSearch}
                    onChange={(e) => setLocationSearch(e.target.value)}
                    placeholder="Search locations…"
                    className="w-full rounded-md border border-ocean-800/40 bg-abyss-950/60 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
                  />
                </div>
                <div className="max-h-44 overflow-y-auto">
                  {selectedLocation && (
                    <button
                      type="button"
                      onClick={() => { setLocationIdx(-1); setLocationSearch(""); setLocationOpen(false); }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-500 transition hover:bg-ocean-800/20"
                    >
                      ✕ Clear selection
                    </button>
                  )}
                  {filteredLocations.length === 0 ? (
                    <p className="px-3 py-4 text-center text-xs text-slate-500">No matching locations</p>
                  ) : (
                    filteredLocations.map((loc) => {
                      const idx = MAP_LOCATIONS.indexOf(loc);
                      return (
                        <button
                          type="button"
                          key={idx}
                          onClick={() => { setLocationIdx(idx); setLocationSearch(""); setLocationOpen(false); }}
                          className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition hover:bg-ocean-800/20 ${
                            locationIdx === idx ? "bg-ocean-600/15 text-ocean-300" : "text-white"
                          }`}
                        >
                          <IconPin className="h-3 w-3 flex-shrink-0 text-ocean-500" />
                          {loc.label}
                          <span className="ml-auto text-[10px] text-slate-600">
                            {loc.lat.toFixed(1)}°, {loc.lon.toFixed(1)}°
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Vessel selector */}
        {userVessels.length > 0 && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">
              <div className="flex items-center gap-1.5">
                <IconAnchor className="h-3.5 w-3.5 text-ocean-400" />
                Link Vessel
              </div>
            </label>
            <select
              value={selectedVesselId}
              onChange={(e) => setSelectedVesselId(e.target.value)}
              className="w-full rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
            >
              <option value="">No vessel</option>
              {userVessels.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.vessel_name} ({v.vessel_type})
                </option>
              ))}
            </select>
            <p className="mt-1 text-[10px] text-slate-500">
              All sighting reports through this event will automatically use this vessel.
            </p>
          </div>
        )}

        <div className="rounded-lg border border-ocean-800/30 bg-abyss-900/40 p-3">
          <label className="flex items-start gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="mt-0.5 rounded border-ocean-700 bg-abyss-900"
            />
            <div>
              <span className="font-medium text-white">
                {isPublic ? "Public event" : "Private / Invite only"}
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
            {submitting ? "Creating…" : "Create Event"}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ── Event Card ────────────────────────────────────────── */

function EventCard({ event }: { event: EventSummary }) {
  const typeStyle = EVENT_TYPE_STYLE[event.event_type] ?? EVENT_TYPE_STYLE.other;
  const statusStyle = STATUS_STYLE[event.status] ?? STATUS_STYLE.upcoming;
  const TypeIcon = typeStyle.Icon;

  const fmtDate = (d: string | null) =>
    d ? new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null;

  return (
    <Link
      href={`/events/${event.id}`}
      className="glass-panel group flex flex-col overflow-hidden rounded-2xl border border-ocean-800/30 transition-all hover:border-ocean-600/40 hover:shadow-ocean-sm"
    >
      {/* Cover photo */}
      <div className="relative h-32 w-full flex-shrink-0 overflow-hidden bg-gradient-to-br from-ocean-900/60 to-abyss-800/80">
        {event.cover_url ? (
          <Image
            src={`${API_BASE}${event.cover_url}`}
            alt={event.title}
            fill
            unoptimized
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <TypeIcon className={`h-10 w-10 ${typeStyle.text} opacity-30`} />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/70 to-transparent" />
        {/* Status badge on photo */}
        <span className={`absolute top-2 right-2 flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium backdrop-blur-sm ${statusStyle.bg} ${statusStyle.text}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
          {statusStyle.label}
        </span>
        {/* Type chip on photo */}
        <span className={`absolute bottom-2 left-3 rounded-full px-2 py-0.5 text-[10px] font-medium backdrop-blur-sm ${typeStyle.bg} ${typeStyle.text}`}>
          {typeStyle.label}
        </span>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-3 p-5">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-bold text-white group-hover:text-ocean-300 transition-colors line-clamp-1">
          {event.title}
        </h3>
      </div>
      {!event.is_public && (
        <div className="flex items-center gap-1 text-xs text-amber-400/80">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
          </svg>
          Invite only
        </div>
      )}

      {/* Description */}
      {event.description && (
        <p className="text-xs leading-relaxed text-slate-400 line-clamp-2">
          {event.description}
        </p>
      )}

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        {event.location_name && (
          <span className="flex items-center gap-1">
            <IconPin className="h-3.5 w-3.5" />
            {event.location_name}
          </span>
        )}
        {event.start_date && (
          <span className="flex items-center gap-1">
            <IconCalendar className="h-3.5 w-3.5" />
            {fmtDate(event.start_date)}
            {event.end_date && event.end_date !== event.start_date && ` – ${fmtDate(event.end_date)}`}
          </span>
        )}
      </div>

      {/* Footer stats */}
      <div className="flex items-center justify-between border-t border-ocean-800/20 pt-3">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-xs text-slate-400">
            <IconUsers className="h-3.5 w-3.5 text-ocean-400" />
            {event.member_count} {event.member_count === 1 ? "member" : "members"}
          </span>
          <span className="flex items-center gap-1 text-xs text-slate-400">
            <IconCamera className="h-3.5 w-3.5 text-bioluminescent-400" />
            {event.sighting_count} {event.sighting_count === 1 ? "interaction" : "interactions"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <UserAvatar
            displayName={event.creator_name}
            avatarUrl={event.creator_avatar_url}
            size={20}
          />
          <span className="text-xs text-slate-500">{event.creator_name}</span>
        </div>
      </div>

      {/* My role badge */}
      {event.my_role && (
        <div className="flex items-center gap-1 text-xs text-ocean-400">
          <IconCheck className="h-3 w-3" />
          You&apos;re {event.my_role === "creator" ? "the organiser" : `a ${event.my_role}`}
        </div>
      )}
      </div>
    </Link>
  );
}

/* ── External Event Card ───────────────────────────────── */

function ExternalEventCard({ event }: { event: ExternalEvent }) {
  const typeStyle = EXT_TYPE_STYLE[event.event_type] ?? EXT_TYPE_STYLE.other;
  const TypeIcon = typeStyle.Icon;

  const fmtDate = (d: string | null) =>
    d ? new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null;

  const isPast = event.end_date
    ? new Date(event.end_date) < new Date()
    : event.start_date
      ? new Date(event.start_date) < new Date()
      : false;

  const Wrapper = event.source_url ? "a" : "div";
  const linkProps = event.source_url
    ? { href: event.source_url, target: "_blank", rel: "noopener noreferrer" }
    : {};

  return (
    <Wrapper
      {...linkProps}
      className={`glass-panel group relative flex flex-col gap-3 rounded-2xl border p-5 transition-all ${
        event.is_featured
          ? "border-amber-500/30 hover:border-amber-400/50 hover:shadow-[0_0_20px_rgba(245,158,11,0.08)]"
          : "border-ocean-800/30 hover:border-ocean-600/40 hover:shadow-ocean-sm"
      } ${isPast ? "opacity-60" : ""}`}
    >
      {/* Featured badge */}
      {event.is_featured && (
        <div className="absolute -top-2.5 right-4 rounded-full bg-gradient-to-r from-amber-600 to-amber-500 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm">
          ★ Featured
        </div>
      )}

      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${typeStyle.bg}`}>
            <TypeIcon className={`h-5 w-5 ${typeStyle.text}`} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white group-hover:text-ocean-300 transition-colors line-clamp-1">
              {event.title}
            </h3>
            <span className={`text-xs ${typeStyle.text}`}>{typeStyle.label}</span>
          </div>
        </div>
        {/* External badge */}
        <span className="flex items-center gap-1 rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-[10px] font-medium text-indigo-300">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
          </svg>
          External
        </span>
      </div>

      {/* Description */}
      {event.description && (
        <p className="text-xs leading-relaxed text-slate-400 line-clamp-2">
          {event.description}
        </p>
      )}

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        {event.location_name && (
          <span className="flex items-center gap-1">
            {event.is_virtual ? <IconGlobe className="h-3.5 w-3.5" /> : <IconPin className="h-3.5 w-3.5" />}
            {event.location_name}
          </span>
        )}
        {event.start_date && (
          <span className="flex items-center gap-1">
            <IconCalendar className="h-3.5 w-3.5" />
            {fmtDate(event.start_date)}
            {event.end_date && event.end_date !== event.start_date && ` – ${fmtDate(event.end_date)}`}
          </span>
        )}
      </div>

      {/* Tags + organizer footer */}
      <div className="flex items-center justify-between border-t border-ocean-800/20 pt-3">
        <div className="flex flex-wrap gap-1.5">
          {event.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-ocean-500/10 px-2 py-0.5 text-[10px] font-medium text-ocean-400"
            >
              {tag.replace(/_/g, " ")}
            </span>
          ))}
        </div>
        <span className="text-xs font-medium text-slate-500">
          {event.organizer}
        </span>
      </div>

      {/* External link hint */}
      {event.source_url && (
        <div className="flex items-center gap-1 text-xs text-indigo-400/70">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
          </svg>
          Visit event page →
        </div>
      )}
    </Wrapper>
  );
}

/* ── Events Panel ──────────────────────────────────────── */

export default function EventsPanel() {
  const { user, token } = useAuth();
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("browse");
  const [createOpen, setCreateOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [eventsViewTab, setEventsViewTab] = useState<EventsViewTab>("community");
  const limit = 24;

  /* ── External events state ─────────────────────────────── */
  const [externalEvents, setExternalEvents] = useState<ExternalEvent[]>([]);
  const [extLoading, setExtLoading] = useState(true);

  const fetchExternalEvents = useCallback(async () => {
    setExtLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/external-events?limit=50&offset=0`
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setExternalEvents(data.events ?? []);
    } catch {
      setExternalEvents([]);
    } finally {
      setExtLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchExternalEvents();
  }, [fetchExternalEvents]);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(page * limit));
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (typeFilter !== "all") params.set("event_type", typeFilter);

      const isMine = viewMode === "mine" && token;
      const url = isMine
        ? `${API_BASE}/api/v1/events/mine?${params}`
        : `${API_BASE}/api/v1/events?${params}`;

      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;

      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setEvents(data.events ?? []);
      setTotal(data.total ?? 0);
    } catch {
      setEvents([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, typeFilter, viewMode, token]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Reset page on filter change
  useEffect(() => {
    setPage(0);
  }, [statusFilter, typeFilter, viewMode]);

  const totalPages = Math.ceil(total / limit);

  /* ── Client-side date filter ───────────────────────────── */
  const filteredEvents = events.filter((ev) => {
    if (dateFrom && ev.start_date && ev.start_date < dateFrom) return false;
    if (dateTo && ev.start_date && ev.start_date > dateTo + "T23:59:59") return false;
    return true;
  });

  /* ── Filter external events by date too ────────────────── */
  const filteredExternal = externalEvents.filter((ev) => {
    if (dateFrom && ev.start_date && ev.start_date < dateFrom) return false;
    if (dateTo && ev.start_date && ev.start_date > dateTo + "T23:59:59") return false;
    return true;
  });

  return (
    <>
      {/* Header row with create button */}
      <div className="mb-6 flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Organise whale watching trips, research expeditions, and
          citizen science surveys. Group interactions together and
          collaborate with other observers.
        </p>
        {user && (
          <button
            onClick={() => setCreateOpen(true)}
            className="flex-shrink-0 rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-5 py-2.5 text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400 hover:shadow-ocean-md"
          >
            + New Event
          </button>
        )}
      </div>

      {/* Top-level tabs: Community vs Featured/External */}
      <div className="mb-5 flex items-center gap-1 border-b border-ocean-800/20">
        <button
          onClick={() => { setEventsViewTab("community"); setPage(0); }}
          className={`flex items-center gap-1.5 rounded-t-lg px-5 py-2.5 text-sm font-medium transition-all ${
            eventsViewTab === "community"
              ? "border-b-2 border-ocean-400 text-ocean-300"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          <IconUsers className="h-4 w-4" />
          Community Events
        </button>
        <button
          onClick={() => { setEventsViewTab("featured"); setPage(0); }}
          className={`flex items-center gap-1.5 rounded-t-lg px-5 py-2.5 text-sm font-medium transition-all ${
            eventsViewTab === "featured"
              ? "border-b-2 border-amber-400 text-amber-300"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          <IconAnchor className="h-4 w-4" />
          Featured & External
          {filteredExternal.length > 0 && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-400">
              {filteredExternal.length}
            </span>
          )}
        </button>
      </div>

      {/* Filters bar — shown for community tab */}
      {eventsViewTab === "community" && (
      <div className="glass-panel mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-ocean-800/30 px-4 py-3">
        {/* View mode toggle */}
        {user && (
          <div className="flex rounded-lg border border-ocean-800/30 p-0.5">
            {(["browse", "mine"] as ViewMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-all ${
                  viewMode === m
                    ? "bg-ocean-500/20 text-ocean-300"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {m === "browse" ? "Browse All" : "My Events"}
              </button>
            ))}
          </div>
        )}

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-1.5 text-xs text-white focus:border-ocean-500 focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="upcoming">Upcoming</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>

        {/* Type filter */}
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
          className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-3 py-1.5 text-xs text-white focus:border-ocean-500 focus:outline-none"
        >
          <option value="all">All Types</option>
          {Object.entries(EVENT_TYPE_STYLE).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>

        {/* Date range */}
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(0); }}
            className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-2.5 py-[5px] text-xs text-white focus:border-ocean-500 focus:outline-none [color-scheme:dark]"
            title="From date"
          />
          <span className="text-[10px] text-slate-600">–</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(0); }}
            className="rounded-lg border border-ocean-800/50 bg-abyss-900/60 px-2.5 py-[5px] text-xs text-white focus:border-ocean-500 focus:outline-none [color-scheme:dark]"
            title="To date"
          />
          {(dateFrom || dateTo) && (
            <button
              onClick={() => { setDateFrom(""); setDateTo(""); setPage(0); }}
              className="rounded-md px-1.5 py-1 text-xs text-slate-500 transition hover:text-red-400"
              title="Clear dates"
            >
              ✕
            </button>
          )}
        </div>

        <span className="ml-auto text-xs text-slate-500">
          {filteredEvents.length}{filteredEvents.length !== total ? ` / ${total}` : ""} event{total !== 1 ? "s" : ""}
        </span>
      </div>
      )}

      {/* ── Featured / External tab content ───────────────── */}
      {eventsViewTab === "featured" && (
        <div>
          {extLoading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-24">
              <SonarPing size={56} ringCount={3} active />
              <span className="text-sm text-ocean-400/60">Loading events…</span>
            </div>
          ) : filteredExternal.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-4 py-24">
              <IconAnchor className="h-16 w-16 text-ocean-800/50" />
              <p className="text-sm text-slate-500">
                No featured or external events right now.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredExternal.map((ev) => (
                <ExternalEventCard key={`ext-${ev.id}`} event={ev} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Community tab content ─────────────────────────── */}
      {eventsViewTab === "community" && (loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <SonarPing size={56} ringCount={3} active />
          <span className="text-sm text-ocean-400/60">Loading events…</span>
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-24">
          <IconUsers className="h-16 w-16 text-ocean-800/50" />
          <p className="text-sm text-slate-500">
            {viewMode === "mine"
              ? "You haven't joined or created any events yet."
              : "No events found. Be the first to create one!"}
          </p>
          {user && viewMode !== "mine" && (
            <button
              onClick={() => setCreateOpen(true)}
              className="rounded-lg bg-ocean-600/20 px-4 py-2 text-sm font-medium text-ocean-300 transition hover:bg-ocean-500/30"
            >
              Create Event
            </button>
          )}
          {!user && (
            <Link
              href="/auth"
              className="rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-5 py-2 text-sm font-semibold text-white shadow-ocean-sm transition hover:from-ocean-500 hover:to-ocean-400"
            >
              Sign in to create events
            </Link>
          )}
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-24">
          <p className="text-sm text-slate-500">
            No events match the selected date range.
          </p>
          <button
            onClick={() => { setDateFrom(""); setDateTo(""); }}
            className="text-xs text-ocean-400 underline"
          >
            Clear date filter
          </button>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredEvents.map((ev) => (
              <EventCard key={ev.id} event={ev} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-ocean-800/30 px-3 py-1.5 text-xs text-slate-400 transition hover:border-ocean-600/40 hover:text-white disabled:opacity-30"
              >
                ← Prev
              </button>
              <span className="text-xs text-slate-500">
                Page {page + 1} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-ocean-800/30 px-3 py-1.5 text-xs text-slate-400 transition hover:border-ocean-600/40 hover:text-white disabled:opacity-30"
              >
                Next →
              </button>
            </div>
          )}
        </>
      ))}

      {/* Create modal */}
      <CreateEventModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(ev) => {
          setEvents((prev) => [ev, ...prev]);
          setTotal((t) => t + 1);
        }}
        token={token}
      />
    </>
  );
}
