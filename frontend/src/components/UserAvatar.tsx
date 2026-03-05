"use client";

import { API_BASE } from "@/lib/config";
import Image from "next/image";
import { useState } from "react";

/* ── Props ──────────────────────────────────────────────── */

interface UserAvatarProps {
  /** Public avatar URL path (e.g. /api/v1/media/avatar/42) or null */
  avatarUrl: string | null | undefined;
  /** User display name — used for initials fallback */
  displayName: string | null | undefined;
  /** Pixel size (width = height). Default 36. */
  size?: number;
  /** Extra Tailwind classes on the outer wrapper */
  className?: string;
}

/* ── Helpers ────────────────────────────────────────────── */

function getInitials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

const GRADIENT_PAIRS = [
  ["#0ea5e9", "#6366f1"], // sky → indigo
  ["#14b8a6", "#0ea5e9"], // teal → sky
  ["#8b5cf6", "#ec4899"], // violet → pink
  ["#f59e0b", "#ef4444"], // amber → red
  ["#10b981", "#3b82f6"], // emerald → blue
  ["#f97316", "#eab308"], // orange → yellow
];

function gradientForName(name: string | null | undefined): string {
  const hash = (name ?? "?")
    .split("")
    .reduce((a, c) => a + c.charCodeAt(0), 0);
  const pair = GRADIENT_PAIRS[hash % GRADIENT_PAIRS.length];
  return `linear-gradient(135deg, ${pair[0]}, ${pair[1]})`;
}

/* ── Component ──────────────────────────────────────────── */

export default function UserAvatar({
  avatarUrl,
  displayName,
  size = 36,
  className = "",
}: UserAvatarProps) {
  const [imgError, setImgError] = useState(false);

  const showImage = avatarUrl && !imgError;
  const fullUrl = avatarUrl?.startsWith("http")
    ? avatarUrl
    : `${API_BASE}${avatarUrl}`;

  const fontSize = Math.max(10, Math.round(size * 0.38));

  return (
    <div
      className={`relative flex shrink-0 items-center justify-center overflow-hidden rounded-full ${className}`}
      style={{
        width: size,
        height: size,
        background: showImage ? undefined : gradientForName(displayName),
      }}
    >
      {showImage ? (
        <Image
          src={fullUrl}
          alt={displayName ?? "Avatar"}
          width={size}
          height={size}
          className="h-full w-full object-cover"
          onError={() => setImgError(true)}
          unoptimized
        />
      ) : (
        <span
          className="select-none font-semibold text-white/90"
          style={{ fontSize }}
        >
          {getInitials(displayName)}
        </span>
      )}
    </div>
  );
}
