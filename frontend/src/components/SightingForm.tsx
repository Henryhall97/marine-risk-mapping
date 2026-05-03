"use client";

import { useState, useRef, useMemo, useCallback, useEffect, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import dynamic from "next/dynamic";
import exifr from "exifr";
import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import CelebrationOverlay from "@/components/CelebrationOverlay";
import SpeciesPicker, { SPECIES_DESC, lookupSpeciesGroup } from "@/components/SpeciesPicker";
import IDHelper from "@/components/IDHelper";
import {
  IconTelescope,
  IconShip,
  IconWarning,
  IconExplosion,
  IconKnot,
  IconBeach,
  IconMicrophone,
  IconPencil,
  IconAlert,
  IconBuilding,
  IconCamera,
  IconPin,
  IconSatellite,
  IconWhale,
  IconRefresh,
  IconPaperclip,
  IconMusic,
  IconWaves,
  IconLightbulb,
  IconCalendar,
  IconAnchor,
  IconEye,
  IconShield,
} from "@/components/icons/MarineIcons";

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

const BEHAVIOR_OPTIONS = [
  { value: "", label: "Not observed" },
  { value: "feeding", label: "Feeding" },
  { value: "traveling", label: "Traveling" },
  { value: "resting", label: "Resting / Logging" },
  { value: "socializing", label: "Socializing" },
  { value: "mating", label: "Mating" },
  { value: "breaching", label: "Breaching" },
  { value: "other", label: "Other" },
];

const LIFE_STAGE_OPTIONS = [
  { value: "", label: "Unknown" },
  { value: "adult", label: "Adult" },
  { value: "juvenile", label: "Juvenile" },
  { value: "calf", label: "Calf" },
];

const PLATFORM_OPTIONS = [
  { value: "", label: "Not specified" },
  { value: "vessel", label: "Vessel / Boat" },
  { value: "shore", label: "Shore / Land" },
  { value: "aircraft", label: "Aircraft" },
  { value: "drone", label: "Drone" },
  { value: "kayak", label: "Kayak / Paddleboard" },
  { value: "diving", label: "Diving / Snorkeling" },
  { value: "other", label: "Other" },
];

const INTERACTION_TYPES = [
  { value: "passive_observation", label: "Passive Observation", desc: "Observed from a safe distance", Icon: IconTelescope },
  { value: "vessel_approach", label: "Vessel Approach", desc: "Whale approached or was approached by vessel", Icon: IconShip },
  { value: "near_miss", label: "Near Miss", desc: "Close encounter, no contact", Icon: IconWarning },
  { value: "strike", label: "Strike", desc: "Known or suspected vessel collision", Icon: IconExplosion },
  { value: "entanglement", label: "Entanglement", desc: "Whale tangled in fishing gear or debris", Icon: IconKnot },
  { value: "stranding", label: "Stranding", desc: "Whale found on shore or in shallow water", Icon: IconBeach },
  { value: "acoustic_detection", label: "Acoustic Detection", desc: "Heard but not visually confirmed", Icon: IconMicrophone },
  { value: "other", label: "Other", desc: "Doesn't fit other categories", Icon: IconPencil },
];

const BEAUFORT_LABELS = [
  "Calm (glassy)",
  "Calm (rippled)",
  "Smooth (wavelets)",
  "Slight",
  "Moderate",
  "Rough",
  "Very rough",
  "High",
  "Very high",
  "Phenomenal",
  "Storm",
  "Violent storm",
  "Hurricane force",
];

function windSpeedToBeaufort(kmh: number): number {
  if (kmh < 1) return 0;
  if (kmh <= 5) return 1;
  if (kmh <= 11) return 2;
  if (kmh <= 19) return 3;
  if (kmh <= 28) return 4;
  if (kmh <= 38) return 5;
  if (kmh <= 49) return 6;
  if (kmh <= 61) return 7;
  if (kmh <= 74) return 8;
  if (kmh <= 88) return 9;
  if (kmh <= 102) return 10;
  if (kmh <= 117) return 11;
  return 12;
}

function radiationToGlare(directRad: number): string | null {
  if (directRad >= 600) return "severe";
  if (directRad >= 350) return "moderate";
  if (directRad >= 100) return "slight";
  return "none";
}

const GLARE_LABELS: Record<string, string> = {
  none: "None",
  slight: "Slight",
  moderate: "Moderate",
  severe: "Severe",
};

/* ── Types ───────────────────────────────────────────────── */

interface SightingResult {
  sighting_id: string;
  timestamp: string;
  location: {
    lat: number;
    lon: number;
    h3_cell: number | null;
    gps_source: string | null;
    is_ocean: boolean | null;
    in_risk_coverage: boolean;
    location_warnings: string[];
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
    model_rank: string | null;
    user_rank: string | null;
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

export default function SightingForm({
  eventId,
  vesselId: vesselIdProp,
  initialSpecies,
}: {
  eventId?: string;
  vesselId?: string;
  initialSpecies?: string;
}) {
  const { authHeader, user } = useAuth();

  /* ── Form state ── */
  const [speciesGuess, setSpeciesGuess] = useState(
    initialSpecies ?? "",
  );
  const [wizardOpen, setWizardOpen] = useState(!initialSpecies);
  const [submittedRank, setSubmittedRank] = useState<string>("");
  const [submittedScientificName, setSubmittedScientificName] = useState("");
  const [groupSize, setGroupSize] = useState("");
  const [interaction, setInteraction] = useState("passive_observation");
  const [description, setDescription] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [sharePublicly, setSharePublicly] = useState(true);

  /* ── Biological fields ── */
  const [sightingDatetime, setSightingDatetime] = useState("");
  const [behavior, setBehavior] = useState("");
  const [lifeStage, setLifeStage] = useState("");
  const [calfPresent, setCalfPresent] = useState<boolean | null>(null);
  const [seaState, setSeaState] = useState("");
  const [observationPlatform, setObservationPlatform] = useState("");

  /* ── Weather suggestions ── */
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [suggestedBeaufort, setSuggestedBeaufort] = useState<number | null>(null);
  const [suggestedVisibility, setSuggestedVisibility] = useState<number | null>(null);
  const [suggestedGlare, setSuggestedGlare] = useState<string | null>(null);
  const [weatherWindKmh, setWeatherWindKmh] = useState<number | null>(null);
  const [weatherSource, setWeatherSource] = useState<string>("");

  /* ── Photo EXIF metadata ── */
  const [exifLat, setExifLat] = useState<number | null>(null);
  const [exifLon, setExifLon] = useState<number | null>(null);
  const [exifDatetime, setExifDatetime] = useState<string | null>(null);
  const [exifLoading, setExifLoading] = useState(false);

  /* ── Enhanced fields ── */
  const [confidenceLevel, setConfidenceLevel] = useState("");
  const [groupSizeMin, setGroupSizeMin] = useState("");
  const [groupSizeMax, setGroupSizeMax] = useState("");
  const [visibilityKm, setVisibilityKm] = useState("");
  const [seaGlare, setSeaGlare] = useState("");
  const [distanceToAnimalM, setDistanceToAnimalM] = useState("");
  const [directionOfTravel, setDirectionOfTravel] = useState("");
  const [privacyLevel, setPrivacyLevel] = useState<"private" | "anonymous" | "public">("public");
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [mapPickerActive, setMapPickerActive] = useState(false);
  const [showPhotoProbs, setShowPhotoProbs] = useState(false);

  /* ── Hydrate photo from ID wizard (sessionStorage carry-over) ── */
  useEffect(() => {
    try {
      const carried = sessionStorage.getItem("idhelper_photo");
      if (carried && !photoPreview) {
        setPhotoPreview(carried);
        /* Convert data URL back to a File so it gets submitted */
        fetch(carried)
          .then((r) => r.blob())
          .then((blob) => {
            const file = new File([blob], "wizard_photo.jpg", { type: blob.type || "image/jpeg" });
            setPhoto(file);
          })
          .catch(() => { /* non-critical */ });
        sessionStorage.removeItem("idhelper_photo");
      }
    } catch { /* SSR / no sessionStorage */ }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Vessel selection ── */
  const [vessels, setVessels] = useState<{ id: number; vessel_name: string; vessel_type: string; length_m: number | null }[]>([]);
  const [selectedVesselId, setSelectedVesselId] = useState<string>("");

  /* Fetch user's vessels (auto-select from prop or active) */
  useEffect(() => {
    if (!authHeader) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/vessels`, {
          headers: { Authorization: authHeader },
        });
        if (res.ok) {
          const data = await res.json();
          setVessels(data.vessels ?? []);
          // Prop vessel_id takes priority (from event link)
          if (vesselIdProp) {
            setSelectedVesselId(vesselIdProp);
            setObservationPlatform("vessel");
          } else if (data.active_vessel_id) {
            setSelectedVesselId(String(data.active_vessel_id));
            setObservationPlatform("vessel");
          }
        }
      } catch { /* ignore */ }
    })();
  }, [authHeader, vesselIdProp]);

  /* ── Species picker state ── */
  const [speciesDropOpen, setSpeciesDropOpen] = useState(false);
  const [photoLightbox, setPhotoLightbox] = useState<string | null>(null);

  /* ── Submission state ── */
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SightingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCelebration, setShowCelebration] = useState(false);

  /* ── Location validation state ── */
  const [locationWarnings, setLocationWarnings] = useState<string[]>([]);
  const [locationChecking, setLocationChecking] = useState(false);
  const [locationIsOcean, setLocationIsOcean] = useState<boolean | null>(null);
  const locationCheckTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const weatherTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const photoInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);

  /* ── Linked event info ── */
  const [linkedEventTitle, setLinkedEventTitle] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | undefined>(eventId);
  const [myEvents, setMyEvents] = useState<{ id: string; title: string; event_type: string; start_date: string | null }[]>([]);
  const [eventSearch, setEventSearch] = useState("");
  const [eventDropOpen, setEventDropOpen] = useState(false);
  const eventDropRef = useRef<HTMLDivElement>(null);

  /* Fetch title for URL-linked event */
  useEffect(() => {
    if (!eventId) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/events/${eventId}`);
        if (res.ok) {
          const data = await res.json();
          setLinkedEventTitle(data.title ?? null);
        }
      } catch { /* ignore */ }
    })();
  }, [eventId]);



  /* Fetch user's joined events for the search dropdown */
  useEffect(() => {
    if (!authHeader) return;
    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/events/mine?limit=200`,
          { headers: { Authorization: authHeader } },
        );
        if (res.ok) {
          const data = await res.json();
          setMyEvents(
            (data.events ?? []).map((e: Record<string, unknown>) => ({
              id: String(e.id),
              title: String(e.title ?? ""),
              event_type: String(e.event_type ?? "other"),
              start_date: e.start_date ? String(e.start_date) : null,
            })),
          );
        }
      } catch { /* ignore */ }
    })();
  }, [authHeader]);

  /* Close dropdown when clicking outside */
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (eventDropRef.current && !eventDropRef.current.contains(e.target as Node)) {
        setEventDropOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filteredEvents = myEvents.filter((ev) =>
    ev.title.toLowerCase().includes(eventSearch.toLowerCase()),
  );
  const chosenEvent = myEvents.find((ev) => ev.id === selectedEventId);
  const chosenEventTitle = eventId ? linkedEventTitle : chosenEvent?.title ?? null;



  /* ── Debounced location validation ── */
  useEffect(() => {
    if (locationCheckTimer.current) clearTimeout(locationCheckTimer.current);
    setLocationWarnings([]);
    setLocationIsOcean(null);

    const latNum = parseFloat(lat);
    const lonNum = parseFloat(lon);
    if (!lat || !lon || isNaN(latNum) || isNaN(lonNum)) return;
    if (latNum < -90 || latNum > 90 || lonNum < -180 || lonNum > 180) return;

    setLocationChecking(true);
    locationCheckTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/sightings/check-location?lat=${latNum}&lon=${lonNum}`,
        );
        if (res.ok) {
          const data = await res.json();
          setLocationWarnings(data.location_warnings ?? []);
          setLocationIsOcean(data.is_ocean ?? null);
        }
      } catch {
        /* silently ignore — non-critical */
      } finally {
        setLocationChecking(false);
      }
    }, 600);

    return () => {
      if (locationCheckTimer.current) clearTimeout(locationCheckTimer.current);
    };
  }, [lat, lon]);

  /* ── Auto weather suggestions (Beaufort, visibility, glare) ── */
  useEffect(() => {
    if (weatherTimer.current) clearTimeout(weatherTimer.current);
    setSuggestedBeaufort(null);
    setSuggestedVisibility(null);
    setSuggestedGlare(null);
    setWeatherWindKmh(null);
    setWeatherSource("");

    const latNum = parseFloat(lat);
    const lonNum = parseFloat(lon);
    if (!lat || !lon || isNaN(latNum) || isNaN(lonNum)) return;
    if (latNum < -90 || latNum > 90 || lonNum < -180 || lonNum > 180) return;

    setWeatherLoading(true);
    weatherTimer.current = setTimeout(async () => {
      try {
        /* Extract date + hour from the datetime-local value directly
           (avoids timezone shift from Date.toISOString) */
        let dateStr: string;
        let hour: number;

        if (sightingDatetime && sightingDatetime.includes("T")) {
          dateStr = sightingDatetime.slice(0, 10);
          hour = parseInt(sightingDatetime.slice(11, 13), 10);
        } else {
          /* No datetime → use current conditions */
          const now = new Date();
          dateStr = [
            now.getFullYear(),
            String(now.getMonth() + 1).padStart(2, "0"),
            String(now.getDate()).padStart(2, "0"),
          ].join("-");
          hour = now.getHours();
        }

        /* Strategy: try forecast API first (has visibility + radiation).
           It supports ~92 days back. If it fails (400 for old dates),
           fall back to archive API (wind + radiation only, no visibility).
           IMPORTANT: past_days is mutually exclusive with start_date,
           so we never combine them. */
        const forecastUrl =
          `https://api.open-meteo.com/v1/forecast` +
          `?latitude=${latNum}&longitude=${lonNum}` +
          `&hourly=wind_speed_10m,visibility,direct_radiation` +
          `&start_date=${dateStr}&end_date=${dateStr}` +
          `&wind_speed_unit=kmh&timezone=auto`;

        let res = await fetch(forecastUrl);
        let usedArchive = false;

        if (!res.ok) {
          /* Forecast API rejected the date range — fall back to archive */
          const archiveUrl =
            `https://archive-api.open-meteo.com/v1/archive` +
            `?latitude=${latNum}&longitude=${lonNum}` +
            `&hourly=wind_speed_10m,direct_radiation` +
            `&start_date=${dateStr}&end_date=${dateStr}` +
            `&wind_speed_unit=kmh&timezone=auto`;
          res = await fetch(archiveUrl);
          usedArchive = true;
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();
        if (data.error) throw new Error(data.reason ?? "API error");

        const times: string[] = data.hourly?.time ?? [];

        /* Find the closest hour */
        let idx = times.findIndex((t: string) => {
          const h = parseInt(t.slice(11, 13), 10);
          return h === hour;
        });
        if (idx < 0) idx = Math.min(hour, times.length - 1);
        if (idx < 0) idx = 0;

        /* Wind → Beaufort */
        const speeds: (number | null)[] =
          data.hourly?.wind_speed_10m ?? [];
        const wind = speeds[idx];
        if (wind != null) {
          setSuggestedBeaufort(windSpeedToBeaufort(wind));
          setWeatherWindKmh(Math.round(wind));
        }

        /* Visibility (km) — forecast API only (archive has no visibility).
           Filter < 200m as "no data" (ocean model artifacts). */
        if (!usedArchive) {
          const visList: (number | null)[] =
            data.hourly?.visibility ?? [];
          const vis = visList[idx];
          if (vis != null && vis >= 200) {
            setSuggestedVisibility(
              Math.round((vis / 1000) * 10) / 10,
            );
          }
        }

        /* Direct radiation → glare estimate */
        const radList: (number | null)[] =
          data.hourly?.direct_radiation ?? [];
        const rad = radList[idx];
        if (rad != null) {
          setSuggestedGlare(radiationToGlare(rad));
        }

        setWeatherSource(
          sightingDatetime
            ? `${dateStr} ${String(hour).padStart(2, "0")}:00`
            : "current conditions",
        );
      } catch {
        /* non-critical — suggestions are optional */
      } finally {
        setWeatherLoading(false);
      }
    }, 800);

    return () => {
      if (weatherTimer.current) clearTimeout(weatherTimer.current);
    };
  }, [lat, lon, sightingDatetime]);

  /* ── Handlers ── */

  function handlePhoto(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setPhoto(file);
    setExifLat(null);
    setExifLon(null);
    setExifDatetime(null);
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setPhotoPreview(reader.result as string);
      reader.readAsDataURL(file);

      /* Extract EXIF GPS + DateTime from the photo.
         Use two separate calls: exifr.gps() for coordinates (it reads
         the raw GPSLatitude/GPSLongitude/Ref tags and converts to
         decimal degrees), and exifr.parse() with pick for datetime
         tags. Combining gps:true with pick previously filtered out
         the raw GPS tags before conversion could happen. */
      setExifLoading(true);
      const gpsPromise = exifr
        .gps(file)
        .then((gps) => {
          if (
            gps &&
            typeof gps.latitude === "number" &&
            typeof gps.longitude === "number" &&
            Math.abs(gps.latitude) <= 90 &&
            Math.abs(gps.longitude) <= 180
          ) {
            setExifLat(
              Math.round(gps.latitude * 1_000_000) / 1_000_000,
            );
            setExifLon(
              Math.round(gps.longitude * 1_000_000) / 1_000_000,
            );
          }
        })
        .catch(() => {
          /* No GPS in this image — non-critical */
        });

      const dtPromise = exifr
        .parse(file, {
          pick: [
            "DateTimeOriginal",
            "CreateDate",
            "ModifyDate",
          ],
        })
        .then((tags) => {
          if (!tags) return;
          /* DateTimeOriginal > CreateDate > ModifyDate */
          const dt: Date | undefined =
            tags.DateTimeOriginal ?? tags.CreateDate ?? tags.ModifyDate;
          if (dt instanceof Date && !isNaN(dt.getTime())) {
            /* Format as YYYY-MM-DDTHH:MM for datetime-local input */
            const pad = (n: number) =>
              String(n).padStart(2, "0");
            const formatted = [
              dt.getFullYear(),
              "-",
              pad(dt.getMonth() + 1),
              "-",
              pad(dt.getDate()),
              "T",
              pad(dt.getHours()),
              ":",
              pad(dt.getMinutes()),
            ].join("");
            setExifDatetime(formatted);
          }
        })
        .catch(() => {
          /* No datetime tags — non-critical */
        });

      Promise.all([gpsPromise, dtPromise]).finally(() =>
        setExifLoading(false),
      );
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
      setError("Location is required — use GPS, enter coordinates, or click on the map.");
      return;
    }

    if (!speciesGuess) {
      setError("Species is required — use the wizard or search to select a species.");
      return;
    }

    if (!sightingDatetime) {
      setError("Date & time of sighting is required.");
      return;
    }

    if (user && !privacyAccepted) {
      setError("Please accept the privacy policy before submitting.");
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
      if (groupSize) form.append("group_size", groupSize);
      if (photo) form.append("image", photo);
      if (audio) form.append("audio", audio);
      if (selectedEventId) form.append("event_id", selectedEventId);
      if (sightingDatetime) form.append("sighting_datetime", sightingDatetime);
      if (behavior) form.append("behavior", behavior);
      if (lifeStage) form.append("life_stage", lifeStage);
      if (calfPresent !== null) form.append("calf_present", calfPresent ? "true" : "false");
      if (seaState) form.append("sea_state_beaufort", seaState);
      if (observationPlatform) form.append("observation_platform", observationPlatform);
      if (selectedVesselId) form.append("vessel_id", selectedVesselId);
      if (submittedRank) form.append("submitted_rank", submittedRank);
      if (submittedScientificName) form.append("submitted_scientific_name", submittedScientificName);
      if (confidenceLevel) form.append("confidence_level", confidenceLevel);
      if (groupSizeMin) form.append("group_size_min", groupSizeMin);
      if (groupSizeMax) form.append("group_size_max", groupSizeMax);
      if (visibilityKm) form.append("visibility_km", visibilityKm);
      if (seaGlare) form.append("sea_glare", seaGlare);
      if (distanceToAnimalM) form.append("distance_to_animal_m", distanceToAnimalM);
      if (directionOfTravel) form.append("direction_of_travel", directionOfTravel);
      form.append("privacy_level", privacyLevel);
      form.append("privacy_accepted", privacyAccepted ? "true" : "false");

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
      setShowCelebration(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setSpeciesGuess("");
    setWizardOpen(true);
    setSubmittedRank("");
    setSubmittedScientificName("");
    setGroupSize("");
    setInteraction("passive_observation");
    setDescription("");
    setLat("");
    setLon("");
    setPhoto(null);
    setAudio(null);
    setPhotoPreview(null);
    setExifLat(null);
    setExifLon(null);
    setExifDatetime(null);
    setResult(null);
    setError(null);
    setSharePublicly(true);
    setLocationWarnings([]);
    setLocationIsOcean(null);
    setSightingDatetime("");
    setBehavior("");
    setLifeStage("");
    setCalfPresent(null);
    setSeaState("");
    setSuggestedBeaufort(null);
    setSuggestedVisibility(null);
    setSuggestedGlare(null);
    setWeatherWindKmh(null);
    setWeatherSource("");
    setObservationPlatform("");
    setSelectedVesselId("");
    setSpeciesDropOpen(false);
    setPhotoLightbox(null);
    setConfidenceLevel("");
    setGroupSizeMin("");
    setGroupSizeMax("");
    setVisibilityKm("");
    setSeaGlare("");
    setDistanceToAnimalM("");
    setDirectionOfTravel("");
    setPrivacyLevel("public");
    setPrivacyAccepted(false);
    setMapPickerActive(false);
    if (!eventId) setSelectedEventId(undefined);
  }

  /* Object URL for local audio playback in the result view */
  const audioUrl = useMemo(
    () => (audio ? URL.createObjectURL(audio) : null),
    [audio],
  );

  const handleCelebrationClose = useCallback(() => {
    setShowCelebration(false);
  }, []);

  /* ── Render ── */
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Photo lightbox overlay */}
      {photoLightbox && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPhotoLightbox(null)}
        >
          <button
            onClick={() => setPhotoLightbox(null)}
            className="absolute right-4 top-4 rounded-full bg-black/50 p-2 text-white/70 transition hover:bg-black/70 hover:text-white"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <div
            className="relative max-h-[80vh] max-w-[90vw] overflow-hidden rounded-2xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Image
              src={`/species/${photoLightbox}.jpg`}
              alt={speciesGuess || "Species"}
              width={800}
              height={600}
              className="max-h-[80vh] w-auto object-contain"
              priority
            />
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-5 pb-4 pt-10">
              <p className="text-lg font-bold text-white drop-shadow">{speciesGuess.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Species"}</p>
              {SPECIES_DESC[speciesGuess] && (
                <p className="mt-1 max-w-xl text-xs leading-relaxed text-slate-300/90">
                  {SPECIES_DESC[speciesGuess]}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Celebration overlay on successful submission */}
      <CelebrationOverlay
        show={showCelebration}
        onClose={handleCelebrationClose}
      />

      {/* Linked event banner (from URL param) */}
      {eventId && (
        <div className="flex items-center gap-3 rounded-xl border border-ocean-600/30 bg-ocean-500/10 px-4 py-3">
          <IconCalendar className="h-5 w-5 flex-shrink-0 text-ocean-400" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-ocean-200">
              Linked to event
            </p>
            {linkedEventTitle ? (
              <Link
                href={`/events/${eventId}`}
                className="text-xs text-ocean-400 underline decoration-ocean-700 underline-offset-2 transition hover:text-ocean-300"
              >
                {linkedEventTitle}
              </Link>
            ) : (
              <span className="text-xs text-slate-500">Loading…</span>
            )}
          </div>
          <span className="rounded-full bg-ocean-500/20 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ocean-300">
            Event
          </span>
        </div>
      )}

      {/* Event search picker (when not linked via URL) */}
      {!eventId && user && myEvents.length > 0 && (
        <div ref={eventDropRef} className="relative">
          {selectedEventId && chosenEvent ? (
            <div className="flex items-center gap-3 rounded-xl border border-ocean-600/30 bg-ocean-500/10 px-4 py-3">
              <IconCalendar className="h-5 w-5 flex-shrink-0 text-ocean-400" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ocean-200">
                  Linked to event
                </p>
                <Link
                  href={`/events/${selectedEventId}`}
                  className="text-xs text-ocean-400 underline decoration-ocean-700 underline-offset-2 transition hover:text-ocean-300"
                >
                  {chosenEvent.title}
                </Link>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEventId(undefined)}
                className="rounded-lg px-2 py-1 text-xs text-slate-500 transition hover:bg-red-500/10 hover:text-red-400"
              >
                Remove
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setEventDropOpen(!eventDropOpen)}
              className="flex w-full items-center gap-3 rounded-xl border border-dashed border-ocean-800/50 bg-abyss-900/40 px-4 py-3 text-left transition hover:border-ocean-600/40 hover:bg-ocean-500/5"
            >
              <IconCalendar className="h-5 w-5 flex-shrink-0 text-ocean-800/60" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-400">
                  Link to an event
                </p>
                <p className="text-xs text-slate-600">
                  Search your joined events to attach this interaction
                </p>
              </div>
              <svg className={`h-4 w-4 text-slate-600 transition-transform ${eventDropOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          )}

          {eventDropOpen && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-hidden rounded-xl border border-ocean-800/50 bg-abyss-900 shadow-xl">
              <div className="border-b border-ocean-800/30 p-2">
                <input
                  autoFocus
                  value={eventSearch}
                  onChange={(e) => setEventSearch(e.target.value)}
                  placeholder="Search your events…"
                  className="w-full rounded-md border border-ocean-800/40 bg-abyss-950/60 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:border-ocean-500 focus:outline-none"
                />
              </div>
              <div className="max-h-52 overflow-y-auto">
                {filteredEvents.length === 0 ? (
                  <p className="px-3 py-4 text-center text-xs text-slate-500">
                    No matching events
                  </p>
                ) : (
                  filteredEvents.map((ev) => (
                    <button
                      type="button"
                      key={ev.id}
                      onClick={() => {
                        setSelectedEventId(ev.id);
                        setEventSearch("");
                        setEventDropOpen(false);
                      }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-xs transition hover:bg-ocean-800/20"
                    >
                      <IconCalendar className="h-3.5 w-3.5 flex-shrink-0 text-ocean-500" />
                      <div className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-white">
                          {ev.title}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {ev.event_type.replace(/_/g, " ")}
                          {ev.start_date && ` · ${new Date(ev.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Result view ── */}
      {result ? (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-bold">Interaction Submitted ✓</h2>
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
            const guidanceIcons: Record<string, typeof IconAlert> = {
              strike: IconAlert,
              entanglement: IconKnot,
              stranding: IconBeach,
              near_miss: IconWarning,
            };
            const guidanceText: Record<string, { heading: string; body: string; primaryPhone: string }> = {
              strike: {
                heading: "Report Ship Strike Immediately",
                body: `Call ${auth.name} now. Provide vessel name, location, speed, and whale condition. Do not move the vessel until instructed.`,
                primaryPhone: auth.phone,
              },
              entanglement: {
                heading: "Report Entanglement — Do NOT Intervene",
                body: `Contact the stranding network. Stay 100+ yards away, note the whale's location and condition, and keep visual contact until responders arrive.`,
                primaryPhone: auth.stranding_phone,
              },
              stranding: {
                heading: "Report Stranding to Stranding Network",
                body: `Call the stranding hotline. Do not touch, push, or pour water on the animal. Note the exact location and keep bystanders at a safe distance.`,
                primaryPhone: auth.stranding_phone,
              },
              near_miss: {
                heading: "Near-Miss Event — Report & Slow Down",
                body: "Reduce speed to ≤10 knots immediately. Report this near-miss to help map collision risk hotspots.",
                primaryPhone: auth.phone,
              },
            };

            const g = itype ? guidanceText[itype] : null;
            const GIcon = itype ? guidanceIcons[itype] : null;

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
                      {GIcon && <GIcon className="mr-1 inline h-4 w-4" />}{g.heading}
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
                                            <svg className="mr-1.5 inline h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" /></svg> Call {g.primaryPhone}
                    </a>
                  </div>
                )}

                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                    <IconBuilding className="mr-1 inline h-3.5 w-3.5" /> {auth.name}
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
                                            <svg className="mr-1 inline h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" /></svg> Incidents & strikes:{" "}
                      <a
                        href={`tel:${auth.phone}`}
                        className="font-medium text-bioluminescent-400 hover:underline"
                      >
                        {auth.phone}
                      </a>
                    </p>
                    {auth.stranding_phone !== auth.phone && (
                      <p className="text-xs text-slate-300">
                                                <IconAlert className="mr-1 inline h-3 w-3 text-red-400" /> Strandings & entanglement:{" "}
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
                  {/* Rank match info */}
                  {result.species_assessment.model_rank && result.species_assessment.user_rank && result.species_assessment.source !== "user_only" && (
                    <p className="mt-1 text-xs text-slate-500">
                      {result.species_assessment.model_rank === "species" && result.species_assessment.user_rank !== "species" ? (
                        <span className="text-teal-400">
                          Model identified at species level — refines your {result.species_assessment.user_rank}-level guess
                        </span>
                      ) : result.species_assessment.model_rank === "species" && result.species_assessment.user_rank === "species" ? (
                        <span className="text-slate-500">
                          Both model and your guess are at species level
                        </span>
                      ) : null}
                    </p>
                  )}
                  {result.species_assessment.source === "user_only" && result.species_assessment.user_rank && result.species_assessment.user_rank !== "species" && (
                    <p className="mt-1 text-xs text-indigo-400">
                      Reported at {result.species_assessment.user_rank} level — upload a photo or audio for species-level classification
                    </p>
                  )}
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
                                        <IconCamera className="mr-1.5 inline h-4 w-4" /> Submitted Photo
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
                    label="Submitted Audio"
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
                  <p className="mt-2 flex items-center gap-1 text-xs text-slate-500">
                    <IconPin className="inline h-3.5 w-3.5" /> {result.location.lat.toFixed(4)}°, {result.location.lon.toFixed(4)}°
                    {result.location.h3_cell && ` · H3 ${result.location.h3_cell}`}
                    {result.location.gps_source && ` · via ${result.location.gps_source}`}
                  </p>
                  {result.location.location_warnings?.length > 0 && (
                    <div className="mt-2 space-y-1.5">
                      {result.location.location_warnings.map((w, i) => (
                        <p
                          key={i}
                          className={`flex items-start gap-1.5 text-xs ${
                            result.location!.is_ocean === false
                              ? "text-orange-400"
                              : "text-yellow-400/80"
                          }`}
                        >
                          <IconWarning className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                          <span>{w}</span>
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Photo + Audio results side by side */}
          <div className="grid gap-4 md:grid-cols-2">
            {result.photo_classification && (
              <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                                    <IconCamera className="mr-1.5 inline h-4 w-4" /> Photo Classification
                </h3>
                <p className="text-sm">
                  <strong className="text-slate-200">
                    {result.photo_classification.predicted_species.replace(/_/g, " ")}
                  </strong>{" "}
                  ({Math.round(result.photo_classification.confidence * 100)}%)
                </p>
                {/* Runner-ups + collapsible remaining */}
                {Object.keys(result.photo_classification.probabilities).length > 1 && (() => {
                  const sorted = Object.entries(result.photo_classification!.probabilities)
                    .sort(([, a], [, b]) => b - a);
                  const topConf = result.photo_classification!.confidence;
                  return (
                    <div className="mt-3 space-y-1.5">
                      {sorted.slice(1, 3).map(([sp, p], i) => {
                        const gap = topConf - p;
                        const isClose = gap < 0.15;
                        return (
                          <div key={sp}>
                            <div className="flex items-center gap-2 text-xs">
                              <span className="w-4 text-slate-500">
                                {i + 2}.
                              </span>
                              <span
                                className={`w-24 truncate ${
                                  isClose
                                    ? "font-semibold text-amber-300"
                                    : "text-slate-400"
                                }`}
                              >
                                {sp.replace(/_/g, " ")}
                              </span>
                              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-700">
                                <div
                                  className={`h-full rounded-full ${
                                    isClose ? "bg-amber-500" : "bg-ocean-500"
                                  }`}
                                  style={{
                                    width: `${Math.round(p * 100)}%`,
                                  }}
                                />
                              </div>
                              <span
                                className={`w-8 text-right ${
                                  isClose
                                    ? "font-semibold text-amber-300"
                                    : "text-slate-300"
                                }`}
                              >
                                {Math.round(p * 100)}%
                              </span>
                            </div>
                            {isClose && (
                              <p className="ml-6 text-[10px] text-amber-400/70">
                                {Math.round(gap * 100)}pp behind
                              </p>
                            )}
                          </div>
                        );
                      })}
                      {sorted.length > 3 && (
                        <>
                          <button
                            type="button"
                            onClick={() => setShowPhotoProbs((v) => !v)}
                            className="flex items-center gap-1 text-[11px] text-ocean-400 hover:text-ocean-300"
                          >
                            <svg
                              className={`h-3 w-3 transition-transform ${
                                showPhotoProbs ? "rotate-90" : ""
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
                            {showPhotoProbs
                              ? "Less"
                              : `+${sorted.length - 3} more`}
                          </button>
                          {showPhotoProbs &&
                            sorted.slice(3).map(([sp, p]) => (
                              <div
                                key={sp}
                                className="flex items-center gap-2 text-xs"
                              >
                                <span className="ml-4 w-24 truncate text-slate-500">
                                  {sp.replace(/_/g, " ")}
                                </span>
                                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-700">
                                  <div
                                    className="h-full rounded-full bg-slate-600"
                                    style={{
                                      width: `${Math.round(p * 100)}%`,
                                    }}
                                  />
                                </div>
                                <span className="w-8 text-right text-slate-500">
                                  {Math.round(p * 100)}%
                                </span>
                              </div>
                            ))}
                        </>
                      )}
                    </div>
                  );
                })()}
              </section>
            )}

            {/* Similar species comparison (photo) */}
            {result.photo_classification && (() => {
              const LOOK_ALIKES: Record<string, { species: string; distinction: string }[]> = {
                right_whale: [
                  { species: "bowhead", distinction: "No callosities, white chin patch" },
                  { species: "humpback_whale", distinction: "Long white pectoral fins, head tubercles" },
                ],
                humpback_whale: [
                  { species: "fin_whale", distinction: "Tall sickle dorsal, rarely shows flukes" },
                  { species: "minke_whale", distinction: "Much smaller, pointed snout" },
                ],
                fin_whale: [
                  { species: "blue_whale", distinction: "Mottled blue-grey, tiny dorsal far back" },
                  { species: "sei_whale", distinction: "Single head ridge, surfaces at shallow angle" },
                ],
                blue_whale: [
                  { species: "fin_whale", distinction: "Asymmetric jaw (white right side), taller dorsal" },
                  { species: "sei_whale", distinction: "Smaller, taller dorsal, uniform dark grey" },
                ],
                minke_whale: [
                  { species: "sei_whale", distinction: "Larger, no white flipper bands" },
                ],
                sei_whale: [
                  { species: "fin_whale", distinction: "Asymmetric jaw colouring" },
                  { species: "blue_whale", distinction: "Much larger, mottled blue-grey" },
                ],
                killer_whale: [
                  { species: "pilot_whale", distinction: "All dark, rounded melon, no eye patch" },
                ],
              };
              const predicted = result.photo_classification!.predicted_species;
              const alikes = LOOK_ALIKES[predicted];
              if (!alikes || alikes.length === 0) return null;
              return (
                <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Similar species to check
                  </h3>
                  <div className="space-y-1.5">
                    {alikes.map((la) => (
                      <div
                        key={la.species}
                        className="flex items-start gap-2 text-xs"
                      >
                        <span className="w-24 shrink-0 font-medium capitalize text-slate-300">
                          {la.species.replace(/_/g, " ")}
                        </span>
                        <span className="shrink-0 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-amber-400">
                          Easily mistaken
                        </span>
                        <span className="text-amber-300/70">
                          {la.distinction}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })()}

            {result.audio_classification && (
              <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                                    <IconMicrophone className="mr-1.5 inline h-4 w-4" /> Audio Classification
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
          <p className="text-right text-[11px] text-slate-500">
            <span className="text-red-400">*</span> Required field
          </p>

          {/* ── Location ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
                            <IconPin className="mr-1.5 inline h-4 w-4" /> Location <span className="text-red-400">*</span>
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Use your device GPS, enter coordinates, or click the map.
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
                                <IconSatellite className="mr-1 inline h-4 w-4" /> Use GPS
              </button>
              <button
                type="button"
                onClick={() => setMapPickerActive((v) => !v)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                  mapPickerActive
                    ? "border-teal-500/50 bg-teal-600/30 text-teal-300"
                    : "border-blue-600/40 bg-ocean-600/20 text-bioluminescent-400 hover:bg-ocean-600/30"
                }`}
              >
                <IconPin className="mr-1 inline h-4 w-4" /> {mapPickerActive ? "Picking…" : "Pick on Map"}
              </button>
            </div>

            {/* Map picker — always visible when active, or when coords entered */}
            {(mapPickerActive || (lat && lon && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon)) &&
             parseFloat(lat) >= -90 && parseFloat(lat) <= 90 &&
             parseFloat(lon) >= -180 && parseFloat(lon) <= 180)) && (
              <div className="mt-4">
                <LocationPin
                  lat={lat && !isNaN(parseFloat(lat)) ? parseFloat(lat) : 25}
                  lon={lon && !isNaN(parseFloat(lon)) ? parseFloat(lon) : -80}
                  height={mapPickerActive ? 320 : 220}
                  zoom={lat && lon ? 5 : 2}
                  interactive
                  onLocationChange={mapPickerActive ? (newLat, newLon) => {
                    setLat(newLat.toFixed(6));
                    setLon(newLon.toFixed(6));
                  } : undefined}
                />
              </div>
            )}

            {/* Location validation warnings */}
            {locationChecking && (
              <p className="mt-3 text-xs text-slate-500">Checking location…</p>
            )}
            {!locationChecking && locationWarnings.length > 0 && (
              <div className="mt-3 space-y-2">
                {locationWarnings.map((w, i) => (
                  <div
                    key={i}
                    className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${
                      locationIsOcean === false
                        ? "border-orange-600/50 bg-orange-900/20 text-orange-300"
                        : "border-yellow-600/40 bg-yellow-900/15 text-yellow-300"
                    }`}
                  >
                    <IconWarning className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}
            {!locationChecking && lat && lon && locationWarnings.length === 0 && locationIsOcean === true && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-green-400/80">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-400" />
                Ocean location confirmed — risk data available
              </p>
            )}

            {/* EXIF location mismatch warning */}
            {exifLat != null && exifLon != null && lat && lon && (
              Math.abs(parseFloat(lat) - exifLat) > 0.01 ||
              Math.abs(parseFloat(lon) - exifLon) > 0.01
            ) && (
              <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-600/40 bg-amber-900/20 px-3 py-2.5 text-sm text-amber-300">
                <IconCamera className="h-4 w-4 flex-shrink-0" />
                <span className="flex-1">
                  Your location differs from the photo metadata ({exifLat.toFixed(4)}, {exifLon.toFixed(4)}) by ~{(
                    Math.sqrt(
                      Math.pow(parseFloat(lat) - exifLat, 2) +
                      Math.pow(parseFloat(lon) - exifLon, 2),
                    ) * 111
                  ).toFixed(1)} km
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setLat(String(exifLat));
                    setLon(String(exifLon));
                  }}
                  className="shrink-0 rounded bg-amber-600/30 px-2 py-0.5 text-[10px] font-medium text-amber-200 transition hover:bg-amber-600/40"
                >
                  Use photo location
                </button>
              </div>
            )}
          </section>

          {/* ── Species wizard (collapsible) ── */}
          {wizardOpen ? (
            <IDHelper
              mode="callback"
              compact
              lat={exifLat ?? (lat ? parseFloat(lat) : null)}
              lon={exifLon ?? (lon ? parseFloat(lon) : null)}
              userPhoto={photoPreview}
              onSelect={(group) => {
                setSpeciesGuess(group);
                setWizardOpen(false);
                const meta = lookupSpeciesGroup(group);
                if (meta) {
                  setSubmittedRank(meta.rank);
                  setSubmittedScientificName(meta.scientificName);
                }
              }}
            />
          ) : speciesGuess ? (
            <button
              type="button"
              onClick={() => setWizardOpen(true)}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-ocean-700/40 py-2.5 text-xs text-slate-500 transition-colors hover:border-ocean-500/50 hover:text-ocean-400"
            >
              <IconWhale className="h-3.5 w-3.5" />
              Re-identify with guided wizard
            </button>
          ) : null}

          {/* ── Species ── */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <IconWhale className="mr-1 inline h-3.5 w-3.5" />
              Species <span className="text-red-400">*</span>
            </p>
            <SpeciesPicker
              value={speciesGuess}
              onChange={(sel) => {
                setSpeciesGuess(sel.value);
                setSubmittedRank(sel.rank || "");
                setSubmittedScientificName(sel.scientificName || "");
              }}
              open={speciesDropOpen}
              onOpenChange={setSpeciesDropOpen}
              onLightbox={setPhotoLightbox}
            />
          </div>

          {/* ── Group size ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Group Size
            </h3>
            <p className="mb-3 text-[11px] text-slate-500">
              How many individuals of this species did you observe? Give your best
              estimate and optional range.
            </p>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Best Guess
                </label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={groupSize}
                  onChange={(e) => setGroupSize(e.target.value)}
                  placeholder="e.g. 3"
                  className="w-24 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Min
                </label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={groupSizeMin}
                  onChange={(e) => setGroupSizeMin(e.target.value)}
                  placeholder="1"
                  className="w-20 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Max
                </label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={groupSizeMax}
                  onChange={(e) => setGroupSizeMax(e.target.value)}
                  placeholder="5"
                  className="w-20 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
              </div>
            </div>
          </section>

          {/* ── Confidence in identification ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              <IconEye className="mr-1.5 inline h-4 w-4" /> Confidence in Identification
            </h3>
            <p className="mb-3 text-[11px] text-slate-500">
              How confident are you in your species identification?
            </p>
            <div className="flex flex-wrap gap-2">
              {([
                { value: "certain", label: "Certain", desc: "No doubt" },
                { value: "likely", label: "Likely", desc: "Fairly sure" },
                { value: "possible", label: "Possible", desc: "Best guess" },
                { value: "uncertain", label: "Uncertain", desc: "Not sure at all" },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setConfidenceLevel(opt.value)}
                  className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                    confidenceLevel === opt.value
                      ? "border-teal-500/50 bg-teal-600/30 text-teal-300"
                      : "border-ocean-800 text-slate-400 hover:bg-abyss-800"
                  }`}
                >
                  <span className="text-sm font-medium">{opt.label}</span>
                  <p className="text-[10px] opacity-60">{opt.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* ── Interaction type ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
                            <IconRefresh className="mr-1.5 inline h-4 w-4" /> Interaction Type
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
                  <span className="flex items-center gap-1.5 text-sm font-medium"><it.Icon className="h-4 w-4" />{it.label}</span>
                  <p className="mt-0.5 text-xs opacity-60">{it.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* ── Observation details ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
              <IconCalendar className="mr-1.5 inline h-4 w-4" /> Observation Details
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Improves data quality for scientific records &amp; OBIS export.
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              {/* Sighting date/time */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Date &amp; Time of Sighting <span className="text-red-400">*</span>
                </label>
                <input
                  type="datetime-local"
                  value={sightingDatetime}
                  onChange={(e) => setSightingDatetime(e.target.value)}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                />
                {/* EXIF date/time mismatch warning */}
                {exifDatetime && sightingDatetime && sightingDatetime !== exifDatetime && (() => {
                  const userMs = new Date(sightingDatetime).getTime();
                  const exifMs = new Date(exifDatetime).getTime();
                  const diffMin = Math.abs(userMs - exifMs) / 60_000;
                  if (diffMin < 5) return null;
                  const label = diffMin < 60
                    ? `${Math.round(diffMin)} min`
                    : diffMin < 1440
                      ? `${(diffMin / 60).toFixed(1)} hrs`
                      : `${(diffMin / 1440).toFixed(1)} days`;
                  return (
                    <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-600/40 bg-amber-900/20 px-3 py-2 text-[11px] text-amber-300">
                      <IconCamera className="h-3.5 w-3.5 flex-shrink-0" />
                      <span className="flex-1">
                        Differs from photo metadata ({exifDatetime.replace("T", " ")}) by {label}
                      </span>
                      <button
                        type="button"
                        onClick={() => setSightingDatetime(exifDatetime)}
                        className="shrink-0 rounded bg-amber-600/30 px-2 py-0.5 text-[10px] font-medium text-amber-200 transition hover:bg-amber-600/40"
                      >
                        Use photo time
                      </button>
                    </div>
                  );
                })()}
              </div>

              {/* ── Weather conditions card ── */}
              {(weatherLoading || suggestedBeaufort != null || suggestedVisibility != null || suggestedGlare != null) && (
                <div className="sm:col-span-2 rounded-lg border border-ocean-700/40 bg-ocean-900/20 px-4 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="flex items-center gap-1.5 text-xs font-semibold text-ocean-300">
                      <IconWaves className="h-3.5 w-3.5" />
                      Weather Conditions
                      {weatherSource && (
                        <span className="ml-1 font-normal text-slate-500">
                          — {weatherSource}
                        </span>
                      )}
                    </p>
                    {!weatherLoading && (suggestedBeaufort != null || suggestedVisibility != null || suggestedGlare != null) && (
                      <button
                        type="button"
                        onClick={() => {
                          if (suggestedBeaufort != null) setSeaState(String(suggestedBeaufort));
                          if (suggestedVisibility != null) setVisibilityKm(String(suggestedVisibility));
                          if (suggestedGlare != null) setSeaGlare(suggestedGlare);
                        }}
                        className="rounded bg-ocean-600/30 px-2 py-0.5 text-[10px] font-medium text-ocean-200 transition hover:bg-ocean-600/40"
                      >
                        Apply all
                      </button>
                    )}
                  </div>

                  {weatherLoading ? (
                    <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
                      <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border-2 border-slate-500 border-t-transparent" />
                      Looking up weather conditions for this location…
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-x-6 gap-y-1">
                      {suggestedBeaufort != null && (
                        <p className="text-[11px] text-slate-300">
                          <span className="text-slate-500">Sea state:</span>{" "}
                          <strong className="text-ocean-300">
                            Beaufort {suggestedBeaufort} — {BEAUFORT_LABELS[suggestedBeaufort]}
                          </strong>
                          {weatherWindKmh != null && (
                            <span className="text-slate-500"> ({weatherWindKmh} km/h)</span>
                          )}
                        </p>
                      )}
                      {suggestedVisibility != null && (
                        <p className="text-[11px] text-slate-300">
                          <span className="text-slate-500">Visibility:</span>{" "}
                          <strong className="text-ocean-300">{suggestedVisibility} km</strong>
                        </p>
                      )}
                      {suggestedGlare != null && (
                        <p className="text-[11px] text-slate-300">
                          <span className="text-slate-500">Glare:</span>{" "}
                          <strong className="text-ocean-300">{GLARE_LABELS[suggestedGlare] ?? suggestedGlare}</strong>
                        </p>
                      )}
                      {suggestedBeaufort == null && suggestedVisibility == null && suggestedGlare == null && (
                        <p className="text-[11px] text-slate-500">
                          No weather data available for this date/location
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Behavior */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Behavior
                </label>
                <select
                  value={behavior}
                  onChange={(e) => setBehavior(e.target.value)}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                >
                  {BEHAVIOR_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Direction of travel */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Direction of Travel
                </label>
                <select
                  value={directionOfTravel}
                  onChange={(e) => setDirectionOfTravel(e.target.value)}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                >
                  <option value="">Not observed</option>
                  <option value="N">North</option>
                  <option value="NE">Northeast</option>
                  <option value="E">East</option>
                  <option value="SE">Southeast</option>
                  <option value="S">South</option>
                  <option value="SW">Southwest</option>
                  <option value="W">West</option>
                  <option value="NW">Northwest</option>
                  <option value="stationary">Stationary</option>
                  <option value="erratic">Erratic / Circling</option>
                </select>
              </div>

              {/* Life stage */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Life Stage
                </label>
                <select
                  value={lifeStage}
                  onChange={(e) => setLifeStage(e.target.value)}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                >
                  {LIFE_STAGE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Observation platform */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Observation Platform
                </label>
                <select
                  value={observationPlatform}
                  onChange={(e) => {
                    setObservationPlatform(e.target.value);
                    if (e.target.value !== "vessel") setSelectedVesselId("");
                  }}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                >
                  {PLATFORM_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Vessel selector — shown when platform is "vessel" and user has vessels */}
              {observationPlatform === "vessel" && vessels.length > 0 && (
                <div>
                  <label className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-400">
                    <IconAnchor className="h-3 w-3 text-ocean-400" />
                    Your Vessel
                  </label>
                  <select
                    value={selectedVesselId}
                    onChange={(e) => setSelectedVesselId(e.target.value)}
                    className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                  >
                    <option value="">No vessel selected</option>
                    {vessels.map((v) => (
                      <option key={v.id} value={String(v.id)}>
                        {v.vessel_name} ({v.vessel_type.replace(/_/g, " ")}{v.length_m ? `, ${v.length_m}m` : ""})
                      </option>
                    ))}
                  </select>
                  {vessels.length === 0 && (
                    <Link
                      href="/profile"
                      className="mt-1 block text-xs text-ocean-400 hover:underline"
                    >
                      Register a vessel on your profile →
                    </Link>
                  )}
                </div>
              )}
              {observationPlatform === "vessel" && vessels.length === 0 && (
                <div className="flex items-center gap-2 rounded-lg border border-ocean-800/40 bg-ocean-500/5 px-3 py-2">
                  <IconAnchor className="h-4 w-4 shrink-0 text-ocean-400" />
                  <p className="text-xs text-slate-400">
                    <Link href="/profile" className="text-ocean-400 hover:underline">
                      Register a vessel
                    </Link>{" "}
                    on your profile to link boat details automatically.
                  </p>
                </div>
              )}

              {/* Sea state Beaufort */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Sea State (Beaufort)
                </label>
                <select
                  value={seaState}
                  onChange={(e) => setSeaState(e.target.value)}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                >
                  <option value="">Not recorded</option>
                  {BEAUFORT_LABELS.map((lbl, i) => (
                    <option key={i} value={String(i)}>
                      {i} — {lbl}
                    </option>
                  ))}
                </select>
                {weatherLoading && (
                  <p className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500">
                    <span className="inline-block h-2 w-2 animate-spin rounded-full border border-slate-500 border-t-transparent" />
                    Looking up weather conditions…
                  </p>
                )}
                {suggestedBeaufort != null && !weatherLoading && (
                  <div className="mt-1.5">
                    <div className="flex items-center gap-2">
                      <p className="text-[10px] text-ocean-400">
                        <IconWaves className="mr-0.5 inline h-3 w-3" />
                        Estimated: <strong>{suggestedBeaufort} — {BEAUFORT_LABELS[suggestedBeaufort]}</strong>
                        {weatherWindKmh != null && (
                          <span className="ml-1 font-normal text-slate-500">
                            ({weatherWindKmh} km/h wind)
                          </span>
                        )}
                      </p>
                      {seaState !== String(suggestedBeaufort) && (
                        <button
                          type="button"
                          onClick={() => setSeaState(String(suggestedBeaufort))}
                          className="rounded bg-ocean-600/20 px-1.5 py-0.5 text-[10px] font-medium text-ocean-300 transition hover:bg-ocean-600/30"
                        >
                          Use this
                        </button>
                      )}
                    </div>
                    {weatherSource && (
                      <p className="mt-0.5 text-[9px] text-slate-600">
                        Based on {weatherSource}
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Calf present */}
              <div className="flex items-center gap-3 self-end pb-1">
                <label className="text-xs font-medium text-slate-400">
                  Calf / Juvenile Present?
                </label>
                <div className="flex gap-2">
                  {([
                    { v: true, l: "Yes" },
                    { v: false, l: "No" },
                    { v: null as boolean | null, l: "?" },
                  ] as { v: boolean | null; l: string }[]).map((opt) => (
                    <button
                      key={String(opt.v)}
                      type="button"
                      onClick={() => setCalfPresent(opt.v)}
                      className={`rounded-md border px-3 py-1 text-xs transition-colors ${
                        calfPresent === opt.v
                          ? "border-teal-500/50 bg-teal-600/30 text-teal-300"
                          : "border-ocean-800 text-slate-500 hover:bg-abyss-800"
                      }`}
                    >
                      {opt.l}
                    </button>
                  ))}
                </div>
              </div>

              {/* Visibility (km) */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Visibility (km)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min={0}
                  max={100}
                  value={visibilityKm}
                  onChange={(e) => setVisibilityKm(e.target.value)}
                  placeholder="e.g. 10"
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
                {suggestedVisibility != null && !weatherLoading && (
                  <div className="mt-1 flex items-center gap-2">
                    <p className="text-[10px] text-ocean-400">
                      <IconEye className="mr-0.5 inline h-3 w-3" />
                      Estimated: <strong>{suggestedVisibility} km</strong>
                    </p>
                    {visibilityKm !== String(suggestedVisibility) && (
                      <button
                        type="button"
                        onClick={() => setVisibilityKm(String(suggestedVisibility))}
                        className="rounded bg-ocean-600/20 px-1.5 py-0.5 text-[10px] font-medium text-ocean-300 transition hover:bg-ocean-600/30"
                      >
                        Use this
                      </button>
                    )}
                  </div>
                )}
                <p className="mt-0.5 text-[10px] text-slate-600">
                  Horizontal visibility in kilometres
                </p>
              </div>

              {/* Sea glare */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Sea Surface Glare
                </label>
                <select
                  value={seaGlare}
                  onChange={(e) => setSeaGlare(e.target.value)}
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white focus:border-ocean-500 focus:outline-none"
                >
                  <option value="">Not recorded</option>
                  <option value="none">None</option>
                  <option value="slight">Slight</option>
                  <option value="moderate">Moderate</option>
                  <option value="severe">Severe</option>
                </select>
                {suggestedGlare != null && !weatherLoading && (
                  <div className="mt-1 flex items-center gap-2">
                    <p className="text-[10px] text-ocean-400">
                      Estimated: <strong>{GLARE_LABELS[suggestedGlare] ?? suggestedGlare}</strong>
                    </p>
                    {seaGlare !== suggestedGlare && (
                      <button
                        type="button"
                        onClick={() => setSeaGlare(suggestedGlare)}
                        className="rounded bg-ocean-600/20 px-1.5 py-0.5 text-[10px] font-medium text-ocean-300 transition hover:bg-ocean-600/30"
                      >
                        Use this
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Distance to animal */}
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">
                  Distance to Animal (m)
                </label>
                <input
                  type="number"
                  step="1"
                  min={0}
                  max={50000}
                  value={distanceToAnimalM}
                  onChange={(e) => setDistanceToAnimalM(e.target.value)}
                  placeholder="e.g. 200"
                  className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                />
                <p className="mt-0.5 text-[10px] text-slate-600">
                  Estimated distance from you to the animal in metres
                </p>
              </div>
            </div>
          </section>

          {/* ── Media uploads ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
                            <IconPaperclip className="mr-1.5 inline h-4 w-4" /> Media
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
                        setExifLat(null);
                        setExifLon(null);
                        setExifDatetime(null);
                      }}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="mb-2"><IconCamera className="mx-auto h-8 w-8 text-slate-400" /></div>
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
                    <div><IconMusic className="mx-auto h-8 w-8 text-slate-400" /></div>
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
                    <div className="mb-2"><IconMicrophone className="mx-auto h-8 w-8 text-slate-400" /></div>
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

          {/* ── Photo EXIF metadata suggestions ── */}
          {(exifLoading || exifLat != null || exifLon != null || exifDatetime != null) && (
            <section className="rounded-xl border border-cyan-700/40 bg-cyan-950/30 p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-cyan-300">
                  <IconCamera className="h-3.5 w-3.5" />
                  Photo Metadata Detected
                </h3>
                {!exifLoading && (exifLat != null || exifDatetime != null) && (
                  <button
                    type="button"
                    onClick={() => {
                      if (exifLat != null && exifLon != null) {
                        setLat(String(exifLat));
                        setLon(String(exifLon));
                      }
                      if (exifDatetime) setSightingDatetime(exifDatetime);
                    }}
                    className="rounded bg-cyan-600/30 px-2 py-0.5 text-[10px] font-medium text-cyan-200 transition hover:bg-cyan-600/40"
                  >
                    Apply all
                  </button>
                )}
              </div>

              {exifLoading ? (
                <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
                  <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border-2 border-slate-500 border-t-transparent" />
                  Reading photo metadata…
                </p>
              ) : (
                <div className="space-y-2">
                  {/* GPS from EXIF */}
                  {exifLat != null && exifLon != null && (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      <p className="text-[11px] text-slate-300">
                        <span className="text-slate-500">Location:</span>{" "}
                        <strong className="text-cyan-300">
                          {exifLat.toFixed(6)}, {exifLon.toFixed(6)}
                        </strong>
                      </p>
                      {/* Conflict warning */}
                      {lat && lon && (
                        Math.abs(parseFloat(lat) - exifLat) > 0.01 ||
                        Math.abs(parseFloat(lon) - exifLon) > 0.01
                      ) && (
                        <span className="flex items-center gap-1 rounded-full border border-amber-600/40 bg-amber-900/30 px-2 py-0.5 text-[10px] text-amber-300">
                          <IconWarning className="h-3 w-3" />
                          Differs from entered location by{" "}
                          {(
                            Math.sqrt(
                              Math.pow(parseFloat(lat) - exifLat, 2) +
                              Math.pow(parseFloat(lon) - exifLon, 2),
                            ) * 111
                          ).toFixed(1)}{" "}
                          km
                        </span>
                      )}
                      {(!lat || !lon) ? (
                        <button
                          type="button"
                          onClick={() => {
                            setLat(String(exifLat));
                            setLon(String(exifLon));
                          }}
                          className="rounded bg-cyan-600/30 px-2 py-0.5 text-[10px] font-medium text-cyan-200 transition hover:bg-cyan-600/40"
                        >
                          Use this location
                        </button>
                      ) : (
                        lat && lon && (
                          Math.abs(parseFloat(lat) - exifLat) > 0.001 ||
                          Math.abs(parseFloat(lon) - exifLon) > 0.001
                        ) && (
                          <button
                            type="button"
                            onClick={() => {
                              setLat(String(exifLat));
                              setLon(String(exifLon));
                            }}
                            className="rounded bg-cyan-600/30 px-2 py-0.5 text-[10px] font-medium text-cyan-200 transition hover:bg-cyan-600/40"
                          >
                            Use photo location
                          </button>
                        )
                      )}
                    </div>
                  )}

                  {/* DateTime from EXIF */}
                  {exifDatetime && (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      <p className="text-[11px] text-slate-300">
                        <span className="text-slate-500">Date/time:</span>{" "}
                        <strong className="text-cyan-300">
                          {exifDatetime.replace("T", " ")}
                        </strong>
                      </p>
                      {/* Conflict warning */}
                      {sightingDatetime && sightingDatetime !== exifDatetime && (() => {
                        const userMs = new Date(sightingDatetime).getTime();
                        const exifMs = new Date(exifDatetime).getTime();
                        const diffMin = Math.abs(userMs - exifMs) / 60_000;
                        if (diffMin < 5) return null;
                        const label = diffMin < 60
                          ? `${Math.round(diffMin)} min`
                          : diffMin < 1440
                            ? `${(diffMin / 60).toFixed(1)} hrs`
                            : `${(diffMin / 1440).toFixed(1)} days`;
                        return (
                          <span className="flex items-center gap-1 rounded-full border border-amber-600/40 bg-amber-900/30 px-2 py-0.5 text-[10px] text-amber-300">
                            <IconWarning className="h-3 w-3" />
                            Differs by {label}
                          </span>
                        );
                      })()}
                      {!sightingDatetime ? (
                        <button
                          type="button"
                          onClick={() => setSightingDatetime(exifDatetime)}
                          className="rounded bg-cyan-600/30 px-2 py-0.5 text-[10px] font-medium text-cyan-200 transition hover:bg-cyan-600/40"
                        >
                          Use this date/time
                        </button>
                      ) : sightingDatetime !== exifDatetime && (
                        <button
                          type="button"
                          onClick={() => setSightingDatetime(exifDatetime)}
                          className="rounded bg-cyan-600/30 px-2 py-0.5 text-[10px] font-medium text-cyan-200 transition hover:bg-cyan-600/40"
                        >
                          Use photo date/time
                        </button>
                      )}
                    </div>
                  )}

                  {/* No useful metadata found */}
                  {exifLat == null && exifLon == null && !exifDatetime && (
                    <p className="text-[11px] text-slate-500">
                      No location or date/time metadata found in this photo.
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          {/* ── Description ── */}
          <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
            <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
                            <IconPencil className="mr-1.5 inline h-4 w-4" /> Description
            </h3>
            <p className="mb-4 text-xs text-slate-500">
              Optional — any additional details about the interaction.
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

          {/* ── Privacy & sharing ── */}
          {user && (
            <section className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5 space-y-4">
              <div>
                <h3 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
                  <IconShield className="mr-1.5 inline h-4 w-4" /> Privacy Level
                </h3>
                <p className="mb-3 text-xs text-slate-500">
                  Choose how your sighting is shared with the community.
                </p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {([
                    {
                      value: "private" as const,
                      label: "Private",
                      desc: "Whale records only — not shared with community",
                    },
                    {
                      value: "anonymous" as const,
                      label: "Anonymous",
                      desc: "Shared with community, your name hidden",
                    },
                    {
                      value: "public" as const,
                      label: "Public",
                      desc: "Shared with community, with your name",
                    },
                  ]).map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => {
                        setPrivacyLevel(opt.value);
                        setSharePublicly(opt.value !== "private");
                      }}
                      className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                        privacyLevel === opt.value
                          ? "border-teal-500/50 bg-teal-600/30 text-teal-300"
                          : "border-ocean-800 text-slate-400 hover:bg-abyss-800"
                      }`}
                    >
                      <span className="text-sm font-medium">{opt.label}</span>
                      <p className="mt-0.5 text-[10px] opacity-60">{opt.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Privacy policy consent */}
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-ocean-800/30 bg-abyss-800/40 px-4 py-3">
                <input
                  type="checkbox"
                  checked={privacyAccepted}
                  onChange={(e) => setPrivacyAccepted(e.target.checked)}
                  className="mt-0.5 h-5 w-5 rounded border-ocean-800 bg-abyss-800 text-ocean-500 focus:ring-ocean-500"
                />
                <div>
                  <span className="text-sm text-slate-200">
                    I accept the{" "}
                    <Link
                      href="/privacy"
                      target="_blank"
                      className="text-bioluminescent-400 underline hover:text-bioluminescent-300"
                    >
                      Privacy Policy
                    </Link>
                  </span>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    Your data is used for marine conservation research. Location
                    data is shared with scientific databases (OBIS) for
                    verified sightings.
                  </p>
                </div>
              </label>
            </section>
          )}

          {!user && (
            <div className="rounded-xl border border-ocean-800/50 bg-abyss-900/60 p-5">
              <p className="text-sm text-slate-400">
                                <IconLightbulb className="mr-1 inline h-4 w-4 text-bioluminescent-400" />{" "}
                <Link
                  href="/login"
                  className="text-bioluminescent-400 underline hover:text-bioluminescent-300"
                >
                  Log in
                </Link>{" "}
                to save your interaction and share it with the community.
              </p>
            </div>
          )}

          {/* ── Error ── */}
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
              "Submit Interaction Report"
            )}
          </button>
        </form>
      )}
    </div>
  );
}
