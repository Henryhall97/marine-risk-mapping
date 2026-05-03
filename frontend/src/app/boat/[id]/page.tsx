"use client";

import { API_BASE } from "@/lib/config";
import { useAuth } from "@/contexts/AuthContext";
import { SonarPing } from "@/components/animations";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  IconAnchor,
  IconCamera,
  IconCheck,
  IconEye,
  IconMap,
  IconSearch,
  IconShip,
  IconStar,
  IconUsers,
  IconUser,
  IconWhale,
} from "@/components/icons/MarineIcons";

/* ── Types ──────────────────────────────────────────────── */

interface CrewMember {
  id: number;
  user_id: number;
  role: string;
  joined_at: string;
  display_name: string | null;
  reputation_tier: string | null;
  avatar_url: string | null;
}

interface VesselStats {
  total_sightings: number;
  species_documented: number;
  verified_sightings: number;
  first_sighting: string | null;
  last_sighting: string | null;
}

interface VesselPublicProfile {
  id: number;
  user_id: number;
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
  profile_photo_url: string | null;
  cover_photo_url: string | null;
  created_at: string;
  stats: VesselStats;
  crew: CrewMember[];
  owner_name: string | null;
  owner_id: number | null;
  owner_avatar_url: string | null;
}

/* ── Constants ──────────────────────────────────────────── */

const VESSEL_TYPE_LABELS: Record<string, string> = {
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

const ROLE_LABELS: Record<string, string> = {
  owner: "Captain",
  crew: "Crew",
  guest: "Guest",
};

const ROLE_COLORS: Record<string, string> = {
  owner: "text-yellow-400",
  crew: "text-ocean-300",
  guest: "text-slate-400",
};

const TIER_STYLE: Record<string, { color: string }> = {
  newcomer: { color: "text-slate-400" },
  observer: { color: "text-sky-400" },
  contributor: { color: "text-emerald-400" },
  expert: { color: "text-purple-400" },
  authority: { color: "text-yellow-400" },
};

/* ── Page ────────────────────────────────────────────────── */

export default function BoatProfilePage() {
  const params = useParams();
  const router = useRouter();
  const { authHeader, user } = useAuth();
  const vesselId = Number(params.id);

  const [profile, setProfile] = useState<VesselPublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [uploadingCover, setUploadingCover] = useState(false);
  const profileInputRef = useRef<HTMLInputElement>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);

  /* ── Crew invite state ────────────────────────────────── */
  const [crewSearch, setCrewSearch] = useState("");
  const [crewResults, setCrewResults] = useState<
    { id: number; display_name: string; reputation_tier: string; avatar_url: string | null }[]
  >([]);
  const [crewSearching, setCrewSearching] = useState(false);
  const [addingCrew, setAddingCrew] = useState<number | null>(null);
  const [inviteRole, setInviteRole] = useState<"crew" | "guest">("crew");
  const crewSearchRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isOwner = profile?.owner_id === user?.id;

  const fetchProfile = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/vessels/${vesselId}/public`
      );
      if (!res.ok) throw new Error("Vessel not found");
      const data = await res.json();
      setProfile(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load vessel"
      );
    } finally {
      setLoading(false);
    }
  }, [vesselId]);

  useEffect(() => {
    if (vesselId) fetchProfile();
  }, [vesselId, fetchProfile]);

  /* ── Photo upload handlers ────────────────────────────── */

  async function handlePhotoUpload(
    file: File,
    type: "photo" | "cover"
  ) {
    if (!authHeader) return;
    const setter = type === "photo" ? setUploadingPhoto : setUploadingCover;
    setter(true);
    try {
      const form = new FormData();
      form.append("image", file);
      const res = await fetch(
        `${API_BASE}/api/v1/vessels/${vesselId}/${type}`,
        { method: "POST", headers: { Authorization: authHeader }, body: form }
      );
      if (!res.ok) throw new Error("Upload failed");
      await fetchProfile();
    } finally {
      setter(false);
    }
  }

  /* ── Crew management ──────────────────────────────────── */

  async function handleRemoveCrew(userId: number) {
    if (!authHeader) return;
    const res = await fetch(
      `${API_BASE}/api/v1/vessels/${vesselId}/crew/${userId}`,
      { method: "DELETE", headers: { Authorization: authHeader } }
    );
    if (res.ok) fetchProfile();
  }

  /* ── Crew invite search ───────────────────────────────── */

  function handleCrewSearchChange(value: string) {
    setCrewSearch(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!value.trim()) {
      setCrewResults([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      if (!authHeader) return;
      setCrewSearching(true);
      try {
        const existingIds = profile?.crew.map((c) => c.user_id).join(",") ?? "";
        const res = await fetch(
          `${API_BASE}/api/v1/auth/users/search?q=${encodeURIComponent(
            value.trim()
          )}&limit=8&exclude=${existingIds}`,
          { headers: { Authorization: authHeader } }
        );
        if (res.ok) setCrewResults(await res.json());
      } finally {
        setCrewSearching(false);
      }
    }, 300);
  }

  async function handleAddCrew(userId: number) {
    if (!authHeader) return;
    setAddingCrew(userId);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/vessels/${vesselId}/crew`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: authHeader,
          },
          body: JSON.stringify({ user_id: userId, role: inviteRole }),
        }
      );
      if (res.ok) {
        setCrewSearch("");
        setCrewResults([]);
        await fetchProfile();
      }
    } finally {
      setAddingCrew(null);
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        crewSearchRef.current &&
        !crewSearchRef.current.contains(e.target as Node)
      ) {
        setCrewResults([]);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /* ── Loading / error ──────────────────────────────────── */

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-abyss-900">
        <SonarPing size={64} ringCount={3} active />
        <p className="mt-4 text-sm text-ocean-400/70">
          Loading vessel profile...
        </p>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-abyss-900">
        <IconAnchor className="h-12 w-12 text-slate-600" />
        <p className="mt-3 text-sm text-slate-400">
          {error ?? "Vessel not found"}
        </p>
        <button
          onClick={() => router.push("/community")}
          className="mt-4 rounded-lg bg-ocean-600/20 px-4 py-2 text-sm text-ocean-300 hover:bg-ocean-600/30"
        >
          Back to Community
        </button>
      </div>
    );
  }

  const typeLabel =
    VESSEL_TYPE_LABELS[profile.vessel_type] ?? profile.vessel_type;

  /* ── Render ────────────────────────────────────────────── */

  return (
    <div className="min-h-screen bg-abyss-900 pb-20">
      {/* Hidden file inputs */}
      <input
        ref={profileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handlePhotoUpload(f, "photo");
        }}
      />
      <input
        ref={coverInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handlePhotoUpload(f, "cover");
        }}
      />

      {/* ── Cover photo ──────────────────────────────────── */}
      <div className="relative h-48 w-full overflow-hidden bg-gradient-to-br from-ocean-900 to-abyss-800 sm:h-64">
        {profile.cover_photo_url && (
          <Image
            src={`${API_BASE}${profile.cover_photo_url}`}
            alt="Cover"
            fill
            unoptimized
            className="object-cover"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-abyss-900/80 to-transparent" />

        {isOwner && (
          <button
            onClick={() => coverInputRef.current?.click()}
            disabled={uploadingCover}
            className="absolute right-4 top-4 flex items-center gap-1.5 rounded-lg bg-black/50 px-3 py-1.5 text-xs text-white/80 backdrop-blur-sm hover:bg-black/70 transition"
          >
            <IconCamera className="h-3.5 w-3.5" />
            {uploadingCover ? "Uploading..." : "Edit Cover"}
          </button>
        )}
      </div>

      {/* ── Header section ────────────────────────────────── */}
      <div className="mx-auto max-w-4xl px-4 sm:px-6">
        <div className="relative -mt-16 flex flex-col items-start gap-4 sm:flex-row sm:items-end sm:gap-6">
          {/* Profile photo */}
          <div className="relative">
            <div className="h-28 w-28 overflow-hidden rounded-2xl border-4 border-abyss-900 bg-ocean-800/50 shadow-xl sm:h-32 sm:w-32">
              {profile.profile_photo_url ? (
                <Image
                  src={`${API_BASE}${profile.profile_photo_url}`}
                  alt={profile.vessel_name}
                  fill
                  unoptimized
                  className="object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center">
                  <IconShip className="h-12 w-12 text-ocean-400/40" />
                </div>
              )}
            </div>
            {isOwner && (
              <button
                onClick={() => profileInputRef.current?.click()}
                disabled={uploadingPhoto}
                className="absolute -bottom-1 -right-1 flex h-8 w-8 items-center justify-center rounded-full bg-ocean-600 text-white shadow-lg hover:bg-ocean-500 transition"
              >
                <IconCamera className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Name & type */}
          <div className="flex-1 pb-1">
            <h1 className="text-2xl font-bold text-white sm:text-3xl">
              {profile.vessel_name}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm">
              <span className="flex items-center gap-1 text-ocean-300">
                <IconShip className="h-3.5 w-3.5" />
                {typeLabel}
              </span>
              {profile.home_port && (
                <span className="flex items-center gap-1 text-slate-400">
                  <IconAnchor className="h-3.5 w-3.5" />
                  {profile.home_port}
                </span>
              )}
              {profile.flag_state && (
                <span className="text-slate-500">
                  {profile.flag_state}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── Description ─────────────────────────────────── */}
        {profile.description && (
          <p className="mt-5 max-w-2xl text-sm leading-relaxed text-slate-300">
            {profile.description}
          </p>
        )}

        {/* ── Stats cards ─────────────────────────────────── */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label="Sightings"
            value={profile.stats.total_sightings}
            icon={<IconEye className="h-4 w-4 text-ocean-400" />}
          />
          <StatCard
            label="Species"
            value={profile.stats.species_documented}
            icon={<IconWhale className="h-4 w-4 text-emerald-400" />}
          />
          <StatCard
            label="Verified"
            value={profile.stats.verified_sightings}
            icon={<IconCheck className="h-4 w-4 text-green-400" />}
          />
          <StatCard
            label="Crew"
            value={profile.crew.length}
            icon={<IconUsers className="h-4 w-4 text-purple-400" />}
          />
        </div>

        {/* ── Vessel specs ────────────────────────────────── */}
        <div className="mt-8 grid gap-5 lg:grid-cols-2">
          {/* Specs panel */}
          <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-5">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300">
              <IconAnchor className="h-4 w-4 text-ocean-400" />
              Vessel Specifications
            </h2>
            <div className="space-y-2">
              {profile.length_m && (
                <SpecRow label="Length" value={`${profile.length_m} m`} />
              )}
              {profile.beam_m && (
                <SpecRow label="Beam" value={`${profile.beam_m} m`} />
              )}
              {profile.draft_m != null && (
                <SpecRow label="Draft" value={`${profile.draft_m} m`} />
              )}
              {profile.hull_material && (
                <SpecRow
                  label="Hull"
                  value={profile.hull_material.replace(/_/g, " ")}
                />
              )}
              {profile.propulsion && (
                <SpecRow
                  label="Propulsion"
                  value={profile.propulsion.replace(/_/g, " ")}
                />
              )}
              {profile.typical_speed_knots && (
                <SpecRow
                  label="Typical Speed"
                  value={`${profile.typical_speed_knots} kn`}
                />
              )}
              {!profile.length_m &&
                !profile.beam_m &&
                !profile.hull_material &&
                !profile.propulsion && (
                  <p className="py-4 text-center text-xs text-slate-500">
                    No specifications provided
                  </p>
                )}
            </div>
          </div>

          {/* Crew panel */}
          <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-5">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300">
              <IconUsers className="h-4 w-4 text-purple-400" />
              Crew ({profile.crew.length})
            </h2>
            {profile.crew.length === 0 ? (
              <p className="py-4 text-center text-xs text-slate-500">
                No crew members
              </p>
            ) : (
              <div className="space-y-2">
                {profile.crew.map((c) => (
                  <CrewRow
                    key={c.id}
                    member={c}
                    isOwner={isOwner}
                    isSelf={c.user_id === user?.id}
                    onRemove={() => handleRemoveCrew(c.user_id)}
                  />
                ))}
              </div>
            )}

            {/* ── Invite crew (owner only) ──────────────── */}
            {isOwner && (
              <div className="mt-4 border-t border-ocean-800/20 pt-4" ref={crewSearchRef}>
                <p className="mb-2 text-xs font-medium text-slate-400">
                  Invite Member
                </p>
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <IconSearch className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      value={crewSearch}
                      onChange={(e) => handleCrewSearchChange(e.target.value)}
                      placeholder="Search by name…"
                      className="w-full rounded-lg border border-ocean-800/40 bg-abyss-900/80 py-1.5 pl-8 pr-3 text-xs text-white placeholder-slate-500 outline-none focus:border-ocean-500"
                    />
                    {/* Results dropdown */}
                    {(crewResults.length > 0 || crewSearching) && crewSearch.trim() && (
                      <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-y-auto rounded-lg border border-ocean-800/50 bg-abyss-900 shadow-xl">
                        {crewSearching && crewResults.length === 0 && (
                          <p className="px-3 py-2 text-xs text-slate-500">
                            Searching…
                          </p>
                        )}
                        {crewResults.map((u) => (
                          <button
                            key={u.id}
                            disabled={addingCrew === u.id}
                            onClick={() => handleAddCrew(u.id)}
                            className="flex w-full items-center gap-2.5 px-3 py-2 text-left transition hover:bg-ocean-900/40 disabled:opacity-50"
                          >
                            {u.avatar_url ? (
                              <UserAvatar
                                displayName={u.display_name}
                                avatarUrl={`${API_BASE}${u.avatar_url}`}
                                size={24}
                              />
                            ) : (
                              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-ocean-800/60 text-[10px] font-bold text-ocean-300">
                                {u.display_name.charAt(0).toUpperCase()}
                              </div>
                            )}
                            <div className="min-w-0 flex-1">
                              <span className="block truncate text-xs font-medium text-slate-200">
                                {u.display_name}
                              </span>
                              <span className="text-[10px] capitalize text-slate-500">
                                {u.reputation_tier}
                              </span>
                            </div>
                            <span className="shrink-0 text-[10px] text-ocean-400">
                              {addingCrew === u.id ? "Adding…" : "+ Add"}
                            </span>
                          </button>
                        ))}
                        {!crewSearching && crewResults.length === 0 && crewSearch.trim().length >= 1 && (
                          <p className="px-3 py-2 text-xs text-slate-500">
                            No members found
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as "crew" | "guest")}
                    className="rounded-lg border border-ocean-800/40 bg-abyss-900/80 px-2 py-1.5 text-xs text-slate-300 outline-none focus:border-ocean-500"
                  >
                    <option value="crew">Crew</option>
                    <option value="guest">Guest</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Activity timeline ───────────────────────────── */}
        <div className="mt-8 rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-5">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
            <IconMap className="h-4 w-4 text-ocean-400" />
            Activity
          </h2>
          {profile.stats.total_sightings === 0 ? (
            <p className="py-6 text-center text-xs text-slate-500">
              No sightings reported from this vessel yet
            </p>
          ) : (
            <div className="flex flex-wrap gap-4 text-xs text-slate-400">
              {profile.stats.first_sighting && (
                <span>
                  First sighting:{" "}
                  <span className="text-slate-300">
                    {new Date(
                      profile.stats.first_sighting
                    ).toLocaleDateString()}
                  </span>
                </span>
              )}
              {profile.stats.last_sighting && (
                <span>
                  Most recent:{" "}
                  <span className="text-slate-300">
                    {new Date(
                      profile.stats.last_sighting
                    ).toLocaleDateString()}
                  </span>
                </span>
              )}
              <span>
                {profile.stats.species_documented} species documented
              </span>
            </div>
          )}
        </div>

        {/* ── Owner link ──────────────────────────────────── */}
        {profile.owner_id && (
          <div className="mt-6">
            <Link
              href={`/profile?user=${profile.owner_id}`}
              className="inline-flex items-center gap-2 rounded-lg border border-ocean-800/30 bg-abyss-900/50 px-4 py-2.5 text-sm text-slate-300 transition hover:bg-ocean-900/40 hover:text-white"
            >
              {profile.owner_avatar_url ? (
                <UserAvatar
                  displayName={profile.owner_name ?? "Owner"}
                  avatarUrl={`${API_BASE}${profile.owner_avatar_url}`}
                  size={24}
                />
              ) : (
                <IconUser className="h-5 w-5 text-slate-500" />
              )}
              <span>
                Owned by{" "}
                <span className="font-medium text-ocean-300">
                  {profile.owner_name ?? "Unknown"}
                </span>
              </span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────── */

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/50 p-3.5">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <div className="mt-1 text-xl font-bold tabular-nums text-white">
        {value}
      </div>
    </div>
  );
}

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium capitalize text-slate-200">{value}</span>
    </div>
  );
}

function CrewRow({
  member,
  isOwner,
  isSelf,
  onRemove,
}: {
  member: CrewMember;
  isOwner: boolean;
  isSelf: boolean;
  onRemove: () => void;
}) {
  const name = member.display_name ?? "Anonymous";
  const roleLabel = ROLE_LABELS[member.role] ?? member.role;
  const roleColor = ROLE_COLORS[member.role] ?? "text-slate-400";
  const tierColor =
    TIER_STYLE[member.reputation_tier ?? ""]?.color ?? "text-slate-500";

  return (
    <div className="group flex items-center gap-3 rounded-lg px-2 py-2 transition hover:bg-ocean-900/30">
      <Link href={`/profile?user=${member.user_id}`}>
        {member.avatar_url ? (
          <UserAvatar
            displayName={name}
            avatarUrl={`${API_BASE}${member.avatar_url}`}
            size={32}
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ocean-800/60 text-[11px] font-bold text-ocean-300">
            {name.charAt(0).toUpperCase()}
          </div>
        )}
      </Link>
      <div className="min-w-0 flex-1">
        <Link
          href={`/profile?user=${member.user_id}`}
          className="block truncate text-sm font-medium text-slate-200 hover:text-white"
        >
          {name}
        </Link>
        <div className="flex items-center gap-2 text-[11px]">
          <span className={roleColor}>{roleLabel}</span>
          {member.reputation_tier && (
            <span className={tierColor}>
              {member.reputation_tier.charAt(0).toUpperCase() +
                member.reputation_tier.slice(1)}
            </span>
          )}
        </div>
      </div>
      {/* Remove button: owner can remove non-owners, or self-remove */}
      {member.role !== "owner" && (isOwner || isSelf) && (
        <button
          onClick={onRemove}
          className="rounded px-2 py-1 text-[10px] text-red-400/60 opacity-0 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
        >
          Remove
        </button>
      )}
    </div>
  );
}
