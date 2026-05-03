"use client";

import { useAuth, type Credential } from "@/contexts/AuthContext";
import { API_BASE } from "@/lib/config";
import { SonarPing } from "@/components/animations";
import UserAvatar from "@/components/UserAvatar";
import Image from "next/image";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import type { MapSubmission } from "@/components/SubmissionMap";
import VesselManager from "@/components/VesselManager";
import {
  IconAnchor,
  IconCalendar,
  IconCamera,
  IconCheck,
  IconEye,
  IconMap,
  IconMicroscope,
  IconRefresh,
  IconShield,
  IconStar,
  IconThumbDown,
  IconThumbUp,
  IconUser,
  IconUsers,
  IconWaves,
  IconWhale,
} from "@/components/icons/MarineIcons";

const SubmissionMap = dynamic(() => import("@/components/SubmissionMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full flex-col items-center justify-center gap-2 bg-abyss-900">
      <SonarPing size={56} ringCount={3} active />
      <span className="text-xs text-ocean-400/70">Loading map…</span>
    </div>
  ),
});

/* ── Types ──────────────────────────────────────────────── */

interface SubmissionSummary {
  id: string;
  created_at: string;
  lat: number | null;
  lon: number | null;
  species_guess: string | null;
  model_species: string | null;
  model_confidence: number | null;
  model_source: string | null;
  interaction_type: string | null;
  risk_category: string | null;
  risk_score: number | null;
  is_public: boolean;
  verification_status: string;
  advisory_level: string | null;
  community_agree: number;
  community_disagree: number;
  moderator_status: string | null;
  has_photo: boolean;
  has_audio: boolean;
  group_size: number | null;
  behavior: string | null;
  life_stage: string | null;
  calf_present: boolean | null;
  sea_state_beaufort: number | null;
  observation_platform: string | null;
  scientific_name: string | null;
  sighting_datetime: string | null;
}

type SubView = "list" | "tiles" | "map";

const RISK_ACCENT: Record<string, string> = {
  critical: "from-red-950/30",
  high: "from-orange-950/30",
  medium: "from-yellow-950/20",
  low: "from-green-950/20",
};

const RISK_BAR: Record<string, string> = {
  critical: "bg-red-500/70",
  high: "bg-orange-500/70",
  medium: "bg-yellow-500/70",
  low: "bg-green-500/70",
};

interface RepEvent {
  id: number;
  event_type: string;
  points: number;
  submission_id: string | null;
  description: string | null;
  created_at: string;
}

interface ProfileEvent {
  id: string;
  title: string;
  event_type: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  location_name: string | null;
  member_count: number;
  sighting_count: number;
  my_role: string | null;
  cover_url: string | null;
}

const EVENT_TYPE_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  whale_watching: { bg: "bg-ocean-500/15", text: "text-ocean-400", label: "Whale Watching" },
  research: { bg: "bg-purple-500/15", text: "text-purple-400", label: "Research" },
  citizen_science: { bg: "bg-green-500/15", text: "text-green-400", label: "Citizen Science" },
  cleanup: { bg: "bg-teal-500/15", text: "text-teal-400", label: "Beach Cleanup" },
  education: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Education" },
  other: { bg: "bg-slate-500/15", text: "text-slate-400", label: "Other" },
};

const EVENT_STATUS_STYLE: Record<string, { dot: string; label: string }> = {
  upcoming: { dot: "bg-blue-400", label: "Upcoming" },
  active: { dot: "bg-green-400", label: "Active" },
  completed: { dot: "bg-slate-400", label: "Completed" },
  cancelled: { dot: "bg-red-400", label: "Cancelled" },
};

const STATUS_STYLE: Record<string, { bg: string; dot: string; text: string }> = {
  unverified: { bg: "bg-slate-500/10", dot: "bg-slate-400", text: "text-slate-300" },
  verified: { bg: "bg-emerald-500/15", dot: "bg-emerald-400", text: "text-emerald-300" },
  community_verified: { bg: "bg-green-500/15", dot: "bg-green-400", text: "text-green-300" },
  under_review: { bg: "bg-blue-500/15", dot: "bg-blue-400", text: "text-blue-300" },
  rejected: { bg: "bg-red-500/15", dot: "bg-red-400", text: "text-red-300" },
  disputed: { bg: "bg-yellow-500/15", dot: "bg-yellow-400", text: "text-yellow-300" },
};

const STATUS_LABELS: Record<string, string> = {
  unverified: "Unverified",
  verified: "Mod Verified",
  community_verified: "Community Verified",
  under_review: "Under Review",
  rejected: "Rejected",
  disputed: "Disputed",
};

const RISK_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

const TIER_STYLE: Record<string, { color: string; icon: ReactNode }> = {
  newcomer: { color: "text-slate-400", icon: <IconUser className="inline h-3.5 w-3.5" /> },
  observer: { color: "text-ocean-400", icon: <IconEye className="inline h-3.5 w-3.5" /> },
  contributor: { color: "text-green-400", icon: <IconStar className="inline h-3.5 w-3.5" /> },
  expert: { color: "text-purple-400", icon: <IconMicroscope className="inline h-3.5 w-3.5" /> },
  authority: { color: "text-yellow-400", icon: <IconAnchor className="inline h-3.5 w-3.5" /> },
};

const TIER_THRESHOLDS = [
  { name: "Newcomer", min: 0 },
  { name: "Observer", min: 50 },
  { name: "Contributor", min: 200 },
  { name: "Expert", min: 500 },
  { name: "Authority", min: 1000 },
];

const CREDENTIAL_LABELS: Record<string, string> = {
  marine_biologist: "Marine Biologist",
  certified_observer: "Certified Observer",
  noaa_affiliate: "NOAA Affiliate",
  research_institution: "Research Institution",
  vessel_operator: "Vessel Operator",
  coast_guard: "Coast Guard",
  other: "Other",
};

/* ── Page ───────────────────────────────────────────────── */

export default function ProfilePage() {
  const { user, loading, logout, refreshUser, authHeader } = useAuth();
  const router = useRouter();
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [repHistory, setRepHistory] = useState<RepEvent[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showCredForm, setShowCredForm] = useState(false);
  const [credType, setCredType] = useState("marine_biologist");
  const [credDesc, setCredDesc] = useState("");
  const [credFile, setCredFile] = useState<File | null>(null);
  const [credSubmitting, setCredSubmitting] = useState(false);
  const credFileRef = useRef<HTMLInputElement>(null);
  const [showSubMap, setShowSubMap] = useState(false);
  const [subView, setSubView] = useState<SubView>("tiles");
  const [avatarUploading, setAvatarUploading] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [editingBio, setEditingBio] = useState(false);
  const [bioText, setBioText] = useState(user?.bio ?? "");
  const [bioSaving, setBioSaving] = useState(false);
  const [myEvents, setMyEvents] = useState<ProfileEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const PAGE_SIZE = 20;

  useEffect(() => {
    if (!loading && !user) router.push("/auth");
  }, [loading, user, router]);

  const fetchSubmissions = useCallback(async () => {
    if (!authHeader) return;
    setFetching(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/mine?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
        { headers: { Authorization: authHeader } },
      );
      if (res.ok) {
        const data = await res.json();
        setSubmissions(data.submissions);
        setTotal(data.total);
      }
    } finally {
      setFetching(false);
    }
  }, [authHeader, page]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  /* Fetch user's upcoming/active events */
  useEffect(() => {
    if (!authHeader) return;
    let cancelled = false;
    (async () => {
      setEventsLoading(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/events/mine?limit=50&offset=0`,
          { headers: { Authorization: authHeader } },
        );
        if (res.ok && !cancelled) {
          const data = await res.json();
          // Keep only upcoming and active events
          const upcoming = (data.events ?? []).filter(
            (e: ProfileEvent) => e.status === "upcoming" || e.status === "active",
          );
          setMyEvents(upcoming);
        }
      } finally {
        if (!cancelled) setEventsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [authHeader]);

  const fetchRepHistory = async () => {
    if (!authHeader) return;
    const res = await fetch(
      `${API_BASE}/api/v1/auth/reputation/history?limit=20`,
      { headers: { Authorization: authHeader } },
    );
    if (res.ok) {
      const data = await res.json();
      setRepHistory(data.events);
    }
  };

  const togglePublic = async (id: string, current: boolean) => {
    if (!authHeader) return;
    const res = await fetch(
      `${API_BASE}/api/v1/submissions/${id}/visibility?is_public=${!current}`,
      { method: "PATCH", headers: { Authorization: authHeader } },
    );
    if (res.ok) fetchSubmissions();
  };

  const addCredential = async () => {
    if (!authHeader || !credDesc.trim()) return;
    setCredSubmitting(true);
    try {
      const form = new FormData();
      form.append("credential_type", credType);
      form.append("description", credDesc);
      if (credFile) {
        form.append("evidence", credFile);
      }
      const res = await fetch(
        `${API_BASE}/api/v1/auth/credentials`,
        {
          method: "POST",
          headers: { Authorization: authHeader },
          body: form,
        },
      );
      if (res.ok) {
        setCredDesc("");
        setCredFile(null);
        if (credFileRef.current) credFileRef.current.value = "";
        setShowCredForm(false);
        // Refresh profile to get updated credentials
        window.location.reload();
      }
    } finally {
      setCredSubmitting(false);
    }
  };

  const handleAvatarChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file || !authHeader) return;
    setAvatarUploading(true);
    try {
      const form = new FormData();
      form.append("image", file);
      const res = await fetch(`${API_BASE}/api/v1/auth/avatar`, {
        method: "POST",
        headers: { Authorization: authHeader },
        body: form,
      });
      if (res.ok) {
        await refreshUser();
      } else {
        const body = await res.json().catch(() => ({}));
        console.error("Avatar upload failed:", res.status, body);
        alert(body.detail ?? "Upload failed");
      }
    } finally {
      setAvatarUploading(false);
      // Reset so re-selecting the same file triggers onChange
      if (avatarInputRef.current) avatarInputRef.current.value = "";
    }
  };

  const saveBio = async () => {
    if (!authHeader) return;
    setBioSaving(true);
    try {
      const params = new URLSearchParams({ bio: bioText.trim() });
      const res = await fetch(`${API_BASE}/api/v1/auth/bio?${params}`, {
        method: "PATCH",
        headers: { Authorization: authHeader },
      });
      if (res.ok) {
        await refreshUser();
        setEditingBio(false);
      }
    } finally {
      setBioSaving(false);
    }
  };

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-abyss-950 pt-14">
        <div className="animate-pulse text-slate-400">Loading…</div>
      </div>
    );
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const tier = TIER_STYLE[user.reputation_tier] ?? TIER_STYLE.newcomer;
  const nextTier = TIER_THRESHOLDS.find((t) => t.min > user.reputation_score);
  const currentTierThreshold =
    [...TIER_THRESHOLDS].reverse().find((t) => t.min <= user.reputation_score)
      ?.min ?? 0;
  const progressMax = nextTier ? nextTier.min - currentTierThreshold : 1;
  const progressVal = nextTier
    ? user.reputation_score - currentTierThreshold
    : 1;
  const progressPct = Math.min(100, (progressVal / progressMax) * 100);

  return (
    <div className="min-h-screen bg-abyss-950 px-4 pt-20 pb-12">
      <div className="mx-auto max-w-5xl">
        {/* Profile header + reputation */}
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          {/* User info */}
          <div className="rounded-2xl border border-ocean-800 bg-abyss-900/80 p-6 sm:col-span-2">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                {/* Avatar with upload overlay */}
                <button
                  type="button"
                  onClick={() => avatarInputRef.current?.click()}
                  className="group relative shrink-0"
                  disabled={avatarUploading}
                  title="Change avatar"
                >
                  <UserAvatar
                    avatarUrl={user.avatar_url}
                    displayName={user.display_name}
                    size={64}
                  />
                  <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                    {avatarUploading ? (
                      <span className="text-xs text-white">…</span>
                    ) : (
                      <IconCamera className="h-4 w-4 text-white" />
                    )}
                  </div>
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={handleAvatarChange}
                  />
                </button>

                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-white">
                      {user.display_name}
                    </h1>
                    {user.is_moderator && (
                      <span
                        className="inline-flex items-center gap-1 rounded-full border border-amber-700/60 bg-amber-900/30 px-2.5 py-0.5 text-xs font-semibold text-amber-300"
                        title="Platform Moderator"
                      >
                        <IconShield className="h-3.5 w-3.5" /> Moderator
                      </span>
                    )}
                    <span
                      className={`rounded-full border border-ocean-800 px-2.5 py-0.5 text-xs font-medium ${tier.color}`}
                    >
                      {tier.icon} {user.reputation_tier}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-400">{user.email}</p>
                  <p className="mt-2 text-sm text-slate-500">
                    Joined {new Date(user.created_at).toLocaleDateString()} ·{" "}
                    {total} submission{total !== 1 ? "s" : ""}
                  </p>

                  {/* Bio */}
                  {editingBio ? (
                    <div className="mt-3 flex flex-col gap-2">
                      <textarea
                        value={bioText}
                        onChange={(e) => setBioText(e.target.value)}
                        maxLength={500}
                        rows={3}
                        placeholder="Tell the community about yourself…"
                        className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-ocean-500 focus:outline-none"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          onClick={saveBio}
                          disabled={bioSaving}
                          className="rounded-lg bg-ocean-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-ocean-500 disabled:opacity-50"
                        >
                          {bioSaving ? "Saving…" : "Save"}
                        </button>
                        <button
                          onClick={() => {
                            setEditingBio(false);
                            setBioText(user.bio ?? "");
                          }}
                          className="rounded-lg px-3 py-1.5 text-xs text-slate-400 hover:text-white"
                        >
                          Cancel
                        </button>
                        <span className="ml-auto text-[11px] text-slate-600">
                          {bioText.length}/500
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 group/bio">
                      {user.bio ? (
                        <p className="text-sm leading-relaxed text-slate-300">
                          {user.bio}
                        </p>
                      ) : (
                        <p className="text-sm italic text-slate-600">
                          No bio yet
                        </p>
                      )}
                      <button
                        onClick={() => {
                          setBioText(user.bio ?? "");
                          setEditingBio(true);
                        }}
                        className="mt-1 text-xs text-ocean-400 opacity-0 transition-opacity hover:underline group-hover/bio:opacity-100"
                      >
                        {user.bio ? "Edit bio" : "Add a bio"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => {
                  logout();
                  router.push("/");
                }}
                className="rounded-lg border border-ocean-800 px-4 py-2 text-sm text-slate-400 transition-colors hover:border-red-700 hover:text-red-400"
              >
                Sign Out
              </button>
            </div>

            {/* Credentials */}
            {user.credentials.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {user.credentials.map((c: Credential) => (
                  <span
                    key={c.id}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                      c.is_verified
                        ? "border border-green-800 bg-green-900/30 text-green-300"
                        : "border border-ocean-800 bg-abyss-800 text-slate-400"
                    }`}
                    title={c.description}
                  >
                    {c.is_verified ? <IconCheck className="inline h-3.5 w-3.5" /> : <IconRefresh className="inline h-3.5 w-3.5" />}
                    {CREDENTIAL_LABELS[c.credential_type] ?? c.credential_type}
                    {c.evidence_url && (
                      <a
                        href={`${API_BASE}${c.evidence_url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-0.5 text-ocean-400 hover:text-ocean-300"
                        title="View evidence"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <svg className="inline h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                      </a>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Reputation card */}
          <div className="rounded-2xl border border-ocean-800 bg-abyss-900/80 p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Reputation Score
            </h3>
            <div className={`mt-2 text-3xl font-bold ${tier.color}`}>
              {user.reputation_score}
            </div>

            {/* Progress bar to next tier */}
            {nextTier && (
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-xs text-slate-500">
                  <span>{user.reputation_tier}</span>
                  <span>{nextTier.name}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-abyss-800">
                  <div
                    className="h-full rounded-full bg-ocean-500 transition-all"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  {nextTier.min - user.reputation_score} points to{" "}
                  {nextTier.name}
                </p>
              </div>
            )}

            {/* Quick actions */}
            <div className="mt-4 flex flex-col gap-2">
              <button
                onClick={() => {
                  setShowHistory(!showHistory);
                  if (!showHistory) fetchRepHistory();
                }}
                className="text-left text-xs text-ocean-400 hover:underline"
              >
                {showHistory ? "Hide" : "View"} reputation history
              </button>
              <button
                onClick={() => setShowCredForm(!showCredForm)}
                className="text-left text-xs text-ocean-400 hover:underline"
              >
                {showCredForm ? "Cancel" : "+ Add credential"}
              </button>
            </div>
          </div>
        </div>

        {/* Reputation history (expandable) */}
        {showHistory && repHistory.length > 0 && (
          <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/60 p-4">
            <h3 className="mb-3 text-sm font-semibold text-white">
              Recent Reputation Events
            </h3>
            <div className="space-y-2">
              {repHistory.map((e) => (
                <div
                  key={e.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex-1">
                    <span className="text-slate-300">
                      {e.description ?? e.event_type.replace(/_/g, " ")}
                    </span>
                    <span className="ml-2 text-xs text-slate-600">
                      {new Date(e.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <span
                    className={`font-mono text-sm font-medium ${e.points > 0 ? "text-green-400" : "text-red-400"}`}
                  >
                    {e.points > 0 ? "+" : ""}
                    {e.points}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Add credential form (expandable) */}
        {showCredForm && (
          <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/60 p-4">
            <h3 className="mb-3 text-sm font-semibold text-white">
              Add a Credential
            </h3>
            <p className="mb-3 text-xs text-slate-500">
              Credentials are reviewed and verified. Verified credentials award
              +20 reputation points and increase trust in your submissions.
            </p>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-3 sm:flex-row">
                <select
                  value={credType}
                  onChange={(e) => setCredType(e.target.value)}
                  className="rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white"
                >
                  {Object.entries(CREDENTIAL_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={credDesc}
                  onChange={(e) => setCredDesc(e.target.value)}
                  placeholder="e.g. PhD Marine Biology, Woods Hole Oceanographic"
                  className="flex-1 rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500"
                />
              </div>
              {/* Evidence upload */}
              <div className="flex items-center gap-3">
                <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-ocean-700 bg-abyss-800/50 px-3 py-2 text-xs text-slate-400 transition-colors hover:border-ocean-500 hover:text-slate-300">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                  {credFile ? credFile.name : "Attach evidence (optional)"}
                  <input
                    ref={credFileRef}
                    type="file"
                    className="hidden"
                    accept=".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx"
                    onChange={(e) => setCredFile(e.target.files?.[0] ?? null)}
                  />
                </label>
                {credFile && (
                  <button
                    type="button"
                    onClick={() => {
                      setCredFile(null);
                      if (credFileRef.current) credFileRef.current.value = "";
                    }}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                )}
                <span className="ml-auto text-[10px] text-slate-600">
                  JPG, PNG, PDF, DOC · Max 10 MB
                </span>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={addCredential}
                  disabled={credSubmitting || !credDesc.trim()}
                  className="rounded-lg bg-ocean-600 px-4 py-2 text-sm font-medium text-white hover:bg-ocean-500 disabled:opacity-50"
                >
                  {credSubmitting ? "Submitting…" : "Submit"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* How scoring works */}
        <div className="mb-6 rounded-xl border border-ocean-800 bg-abyss-900/40 p-4">
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium text-slate-400 group-open:text-white">
              How is reputation calculated?
            </summary>
            <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
              <div>
                <span className="font-medium text-green-400">+10</span>{" "}
                Interaction verified by community
              </div>
              <div>
                <span className="font-medium text-green-400">+5</span>{" "}
                Species guess matches ML model
              </div>
              <div>
                <span className="font-medium text-green-400">+3</span>{" "}
                Your verification reaches consensus
              </div>
              <div>
                <span className="font-medium text-green-400">+2</span>{" "}
                Providing a verification vote
              </div>
              <div>
                <span className="font-medium text-green-400">+20</span>{" "}
                Credential verified
              </div>
              <div>
                <span className="font-medium text-red-400">−5</span>{" "}
                Interaction rejected by community
              </div>
              <div>
                <span className="font-medium text-red-400">−2</span>{" "}
                Interaction disputed
              </div>
            </div>
          </details>
        </div>

        {/* Quick stats row */}
        {submissions.length > 0 && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-white">{total}</div>
              <div className="text-xs text-slate-500">Total</div>
            </div>
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-green-400">
                {submissions.filter((s) => s.verification_status === "verified" || s.verification_status === "community_verified").length}
              </div>
              <div className="text-xs text-slate-500">Verified</div>
            </div>
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-ocean-400">
                {new Set(submissions.map((s) => s.model_species ?? s.species_guess).filter(Boolean)).size}
              </div>
              <div className="text-xs text-slate-500">Species</div>
            </div>
            <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-3 text-center">
              <div className="text-xl font-bold text-white">
                {submissions.filter((s) => s.is_public).length}
              </div>
              <div className="text-xs text-slate-500">Public</div>
            </div>
          </div>
        )}

        {/* ── Verification nudge ──────────────────────── */}
        <Link
          href="/community"
          className="mb-6 flex items-center gap-4 rounded-xl border border-ocean-700/30 bg-gradient-to-r from-ocean-900/50 via-abyss-900/60 to-transparent p-4 transition-all hover:border-ocean-600/50 hover:shadow-lg hover:shadow-ocean-900/20"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ocean-500/15">
            <IconEye className="h-4 w-4 text-ocean-400" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-white">
              Help verify community sightings
            </p>
            <p className="text-xs text-slate-400">
              Review reports from other observers and earn{" "}
              <span className="font-medium text-green-400">+2 reputation</span>{" "}
              per vote
            </p>
          </div>
          <span className="shrink-0 rounded-lg bg-ocean-500/20 px-3 py-1.5 text-xs font-medium text-ocean-300">
            Review
          </span>
        </Link>

        {/* ── My Vessels ───────────────────────────────── */}
        <VesselManager />

        {/* ── Upcoming Events ───────────────────────────── */}
        {(eventsLoading || myEvents.length > 0) && (
          <div className="mb-6">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                <IconCalendar className="h-5 w-5 text-ocean-400" />
                Upcoming Events
              </h2>
              <Link
                href="/community?tab=events"
                className="text-xs text-ocean-400 hover:underline"
              >
                Browse all →
              </Link>
            </div>
            {eventsLoading ? (
              <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 py-8 text-center text-sm text-slate-500">
                Loading events…
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {myEvents.map((ev) => {
                  const typeStyle = EVENT_TYPE_STYLE[ev.event_type] ?? EVENT_TYPE_STYLE.other;
                  const evStatus = EVENT_STATUS_STYLE[ev.status] ?? EVENT_STATUS_STYLE.upcoming;
                  const fmtDate = (d: string | null) =>
                    d ? new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : null;
                  return (
                    <Link
                      key={ev.id}
                      href={`/events/${ev.id}`}
                      className="group flex flex-col overflow-hidden rounded-xl border border-ocean-800/40 bg-abyss-900/70 transition-all hover:border-ocean-600/50 hover:shadow-ocean-sm"
                    >
                      {/* Cover photo */}
                      <div className="relative h-28 w-full flex-shrink-0 overflow-hidden bg-gradient-to-br from-ocean-900/60 to-abyss-800/80">
                        {ev.cover_url ? (
                          <Image
                            src={`${API_BASE}${ev.cover_url}`}
                            alt={ev.title}
                            fill
                            unoptimized
                            className="object-cover transition-transform duration-300 group-hover:scale-105"
                            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <IconCalendar className="h-8 w-8 text-ocean-400/25" />
                          </div>
                        )}
                        <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/70 to-transparent" />
                        {/* Status badge */}
                        <span className="absolute top-2 right-2 flex items-center gap-1 rounded-full bg-abyss-800/80 px-2 py-0.5 text-[10px] font-medium text-slate-400 backdrop-blur-sm">
                          <span className={`h-1.5 w-1.5 rounded-full ${evStatus.dot}`} />
                          {evStatus.label}
                        </span>
                        {/* Type chip */}
                        <span className={`absolute bottom-2 left-2 rounded-full px-2 py-0.5 ${typeStyle.bg} ${typeStyle.text} text-[10px] font-medium backdrop-blur-sm`}>
                          {typeStyle.label}
                        </span>
                      </div>

                      {/* Content */}
                      <div className="flex flex-1 flex-col gap-2 p-4">
                      <h3 className="text-sm font-bold text-white line-clamp-1 group-hover:text-ocean-300 transition-colors">
                        {ev.title}
                      </h3>
                      <div className="flex flex-wrap items-center gap-2.5 text-xs text-slate-500">
                        {ev.start_date && (
                          <span className="flex items-center gap-1">
                            <IconCalendar className="h-3 w-3" />
                            {fmtDate(ev.start_date)}{ev.end_date && ev.end_date !== ev.start_date ? ` – ${fmtDate(ev.end_date)}` : ""}
                          </span>
                        )}
                        {ev.location_name && (
                          <span className="flex items-center gap-1">📍 {ev.location_name}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 border-t border-ocean-800/20 pt-2 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                          <IconUsers className="h-3 w-3 text-ocean-400" />
                          {ev.member_count}
                        </span>
                        <span className="flex items-center gap-1">
                          <IconCamera className="h-3 w-3 text-bioluminescent-400" />
                          {ev.sighting_count}
                        </span>
                        {ev.my_role && (
                          <span className="ml-auto text-[10px] text-ocean-400">
                            {ev.my_role === "creator" ? "Organiser" : ev.my_role}
                          </span>
                        )}
                      </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Submissions list header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            Your Submissions
          </h2>
          <div className="flex gap-1 rounded-lg border border-ocean-800 bg-abyss-900 p-1">
            {([
              { key: "tiles" as SubView, label: "▦ Tiles" },
              { key: "list" as SubView, label: "☰ List" },
              ...(submissions.some((s) => s.lat != null)
                ? [{ key: "map" as SubView, label: "" }]
                : []),
            ]).map((v) => (
              <button
                key={v.key}
                onClick={() => {
                  setSubView(v.key);
                  setShowSubMap(v.key === "map");
                }}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  subView === v.key ? "bg-ocean-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {v.key === "map" && <IconMap className="h-3.5 w-3.5" />}
                {v.label || "Map"}
              </button>
            ))}
          </div>
        </div>

        {/* Submissions map */}
        {subView === "map" && (
          <div className="mb-6 h-[380px] overflow-hidden rounded-xl border border-ocean-800">
            <SubmissionMap
              data={submissions
                .filter((s): s is typeof s & { lat: number; lon: number } =>
                  s.lat != null && s.lon != null,
                )
                .map((s) => ({
                  id: s.id,
                  lat: s.lat,
                  lon: s.lon,
                  species: s.model_species ?? s.species_guess ?? "unknown",
                  interaction_type: s.interaction_type,
                  verification_status: s.verification_status,
                  submitter_name: user.display_name,
                  created_at: s.created_at,
                }))}
              onClickSubmission={(id) => window.open(`/submissions/${id}`, "_blank")}
            />
          </div>
        )}

        {subView !== "map" && (fetching && submissions.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            Loading submissions…
          </div>
        ) : submissions.length === 0 ? (
          <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 py-16 text-center">
            <p className="text-slate-400">No submissions yet.</p>
            <Link
              href="/report"
              className="mt-3 inline-block text-sm text-ocean-400 hover:underline"
            >
              Report your first interaction →
            </Link>
          </div>
        ) : (
          <>
            {/* Tile view */}
            {subView === "tiles" && (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {submissions.map((s) => (
                  <ProfileSubmissionCard key={s.id} s={s} onTogglePublic={togglePublic} />
                ))}
              </div>
            )}

            {/* List view */}
            {subView === "list" && (
              <div className="space-y-3">
                {submissions.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between rounded-xl border border-ocean-800 bg-abyss-900/70 px-5 py-4 transition-colors hover:border-ocean-700/60"
                  >
                    <Link href={`/submissions/${s.id}`} className="flex-1">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-white">
                          {s.model_species?.replace(/_/g, " ") ??
                            s.species_guess ??
                            "Unknown"}
                        </span>
                        {s.risk_category && (
                          <span
                            className={`text-xs font-medium ${RISK_COLOR[s.risk_category] ?? "text-slate-400"}`}
                          >
                            {s.risk_category}
                          </span>
                        )}
                        {(() => {
                          const st = STATUS_STYLE[s.verification_status] ?? STATUS_STYLE.unverified;
                          return (
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${st.bg} ${st.text}`}
                            >
                              <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                              {s.moderator_status ? <><IconShield className="inline h-3.5 w-3.5" />{" "}</> : null}
                              {STATUS_LABELS[s.verification_status] ?? s.verification_status}
                            </span>
                          );
                        })()}
                        {(s.community_agree > 0 || s.community_disagree > 0) && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] text-slate-400">
                            <span className="inline-flex items-center gap-0.5 text-green-400"><IconThumbUp className="h-3.5 w-3.5" />{s.community_agree}</span>
                            <span className="inline-flex items-center gap-0.5 text-red-400"><IconThumbDown className="h-3.5 w-3.5" />{s.community_disagree}</span>
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex gap-4 text-xs text-slate-500">
                        <span>
                          {new Date(s.created_at).toLocaleDateString()}
                        </span>
                        {s.lat != null && s.lon != null && (
                          <span>
                            {s.lat.toFixed(2)}°, {s.lon.toFixed(2)}°
                          </span>
                        )}
                        {s.model_source && <span>via {s.model_source}</span>}
                        {s.model_confidence != null && (
                          <span>
                            {(s.model_confidence * 100).toFixed(0)}% conf
                          </span>
                        )}
                      </div>
                    </Link>

                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        togglePublic(s.id, s.is_public);
                      }}
                      className={`ml-4 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        s.is_public
                          ? "border border-green-800 text-green-400 hover:bg-green-900/30"
                          : "border border-ocean-800 text-slate-400 hover:bg-abyss-800"
                      }`}
                      title={
                        s.is_public
                          ? "Click to make private"
                          : "Click to make public for verification"
                      }
                    >
                      {s.is_public ? "Public ✓" : "Private"}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-4">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-lg border border-ocean-800 px-3 py-1.5 text-sm text-slate-400 disabled:opacity-30"
                >
                  ← Prev
                </button>
                <span className="text-sm text-slate-500">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-ocean-800 px-3 py-1.5 text-sm text-slate-400 disabled:opacity-30"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        ))}
      </div>
    </div>
  );
}

/* ── Profile Submission Card (tile view) ──────────────── */

function ProfileSubmissionCard({
  s,
  onTogglePublic,
}: {
  s: SubmissionSummary;
  onTogglePublic: (id: string, current: boolean) => void;
}) {
  const species = s.model_species ?? s.species_guess ?? "unknown";
  const speciesLabel = species.replace(/_/g, " ");
  const status = STATUS_STYLE[s.verification_status] ?? STATUS_STYLE.unverified;
  const riskAccent = RISK_ACCENT[s.risk_category ?? ""] ?? "from-transparent";
  const riskText = RISK_COLOR[s.risk_category ?? ""] ?? "text-slate-500";
  const conf = s.model_confidence != null ? `${(s.model_confidence * 100).toFixed(0)}%` : null;

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 3_600_000) return `${Math.max(1, Math.floor(diff / 60_000))}m`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
    if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)}d`;
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  return (
    <Link
      href={`/submissions/${s.id}`}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-ocean-800/50 bg-gradient-to-b ${riskAccent} to-abyss-900/90 transition-all hover:border-ocean-600/70 hover:shadow-lg hover:shadow-ocean-900/30`}
    >
      {/* Photo or icon header */}
      {s.has_photo ? (
        <div className="relative h-40 overflow-hidden bg-abyss-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${API_BASE}/api/v1/media/${s.id}/photo`}
            alt={speciesLabel}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/80 via-transparent to-transparent" />
          <div className="absolute bottom-2 left-3 right-3 flex items-end justify-between">
            <span className="text-base font-semibold leading-tight text-white drop-shadow">
              {speciesLabel}
            </span>
            {s.has_audio && (
              <span className="rounded-full bg-black/50 px-2 py-0.5 text-xs text-slate-300 backdrop-blur-sm">
                <IconWaves className="inline-block h-3.5 w-3.5" />
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="flex h-28 items-center justify-center bg-gradient-to-br from-abyss-800/80 to-abyss-900/80">
          <IconWhale className="h-16 w-16 text-ocean-800/60" />
        </div>
      )}

      {/* Body */}
      <div className="flex flex-1 flex-col gap-2.5 p-4">
        {/* Species label (when no photo) */}
        {!s.has_photo && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold capitalize text-white">{speciesLabel}</span>
            {s.has_audio && <IconWaves className="h-3.5 w-3.5 text-slate-500" />}
          </div>
        )}

        {/* Chips: verification + risk + interaction */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${status.bg} ${status.text}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
            {s.moderator_status ? <IconShield className="inline h-3 w-3" /> : null}
            {STATUS_LABELS[s.verification_status] ?? s.verification_status}
          </span>
          {(s.community_agree > 0 || s.community_disagree > 0) && (
            <span className="inline-flex items-center gap-1 rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] text-slate-400">
              <span className="text-green-400"><IconThumbUp className="mr-0.5 inline h-3 w-3" />{s.community_agree}</span>
              <span className="text-red-400"><IconThumbDown className="mr-0.5 inline h-3 w-3" />{s.community_disagree}</span>
            </span>
          )}
          {s.risk_category && (
            <span className={`rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] font-medium ${riskText}`}>
              {s.risk_category} risk
            </span>
          )}
          {s.interaction_type && (
            <span className="rounded-full bg-abyss-800/60 px-2 py-0.5 text-[11px] text-slate-500">
              {s.interaction_type.replace(/_/g, " ")}
            </span>
          )}
        </div>

        {/* Bio observation chips */}
        {(s.group_size != null || s.behavior || s.observation_platform) && (
          <div className="flex flex-wrap items-center gap-1.5">
            {s.group_size != null && (
              <span className="inline-flex items-center gap-1 rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-ocean-300">
                <IconUsers className="h-3 w-3" />
                {s.group_size}
              </span>
            )}
            {s.behavior && (
              <span className="rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-ocean-300">
                {s.behavior.replace(/_/g, " ")}
              </span>
            )}
            {s.calf_present && (
              <span className="inline-flex items-center gap-1 rounded-full bg-teal-900/40 px-2 py-0.5 text-[11px] text-teal-300">
                <IconCheck className="h-3 w-3" /> Calf
              </span>
            )}
            {s.observation_platform && s.observation_platform !== "unknown" && (
              <span className="rounded-full bg-ocean-900/40 px-2 py-0.5 text-[11px] text-slate-400">
                {s.observation_platform.replace(/_/g, " ")}
              </span>
            )}
          </div>
        )}

        {/* Confidence bar */}
        {conf && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-[11px] text-slate-500">Conf.</span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-abyss-800">
              <div className="h-full rounded-full bg-ocean-500/70" style={{ width: conf }} />
            </div>
            <span className="text-[11px] tabular-nums text-slate-500">{conf}</span>
          </div>
        )}

        {/* Risk bar */}
        {s.risk_score != null && s.risk_category && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-[11px] text-slate-500">Risk</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-800">
              <div
                className={`h-full rounded-full ${RISK_BAR[s.risk_category] ?? "bg-slate-500/50"}`}
                style={{ width: `${(s.risk_score * 100).toFixed(0)}%` }}
              />
            </div>
            <span className={`text-[11px] font-medium tabular-nums ${riskText}`}>
              {(s.risk_score * 100).toFixed(0)}%
            </span>
          </div>
        )}

        {/* Footer: time + location + public toggle */}
        <div className="mt-auto flex items-center justify-between border-t border-ocean-900/40 pt-2.5 text-[11px] text-slate-500">
          <div className="flex items-center gap-2">
            <span className="tabular-nums">{timeAgo(s.sighting_datetime ?? s.created_at)}</span>
            {s.lat != null && (
              <span className="tabular-nums">{s.lat.toFixed(1)}°, {s.lon!.toFixed(1)}°</span>
            )}
          </div>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onTogglePublic(s.id, s.is_public);
            }}
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors ${
              s.is_public
                ? "bg-green-900/30 text-green-400 hover:bg-green-900/50"
                : "bg-abyss-800 text-slate-500 hover:text-white"
            }`}
          >
            {s.is_public ? "Public" : "Private"}
          </button>
        </div>
      </div>
    </Link>
  );
}
