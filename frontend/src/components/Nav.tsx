"use client";

import { useAuth } from "@/contexts/AuthContext";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";
import {
  IconMap,
  IconMicroscope,
  IconWhale,
  IconGlobe,
} from "@/components/icons/MarineIcons";

const LINKS = [
  { href: "/map", label: "Risk Map", Icon: IconMap },
  { href: "/classify", label: "Classify", Icon: IconMicroscope },
  { href: "/report", label: "Report Sighting", Icon: IconWhale },
  { href: "/community", label: "Community", Icon: IconGlobe },
];

export default function Nav() {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  return (
    <nav className="glass-panel-strong fixed left-0 top-0 z-50 flex w-full items-center justify-between px-6 py-2">
      {/* Left: brand + links */}
      <div className="flex items-center gap-6">
        <Link
          href="/"
          className="group flex items-center gap-3 text-lg font-bold tracking-tight"
        >
          <Image
            src="/whale_watch_logo.png"
            alt="Whale Watch"
            width={84}
            height={56}
            className="h-14 w-[84px] object-contain drop-shadow-[0_0_8px_rgba(34,211,238,0.3)] transition-transform group-hover:scale-110"
          />
          <span className="font-display text-lg font-extrabold tracking-wide text-ocean-gradient">
            Whale<span className="text-ocean-bright">Watch</span>
          </span>
        </Link>

        <div className="flex items-center gap-0.5">
          {LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                  active
                    ? "bg-ocean-500/15 text-bioluminescent-400 shadow-ocean-sm"
                    : "text-slate-400 hover:bg-ocean-900/40 hover:text-slate-200"
                }`}
              >
                <l.Icon className="h-4 w-4" />
                {l.label}
              </Link>
            );
          })}
        </div>
      </div>

      {/* Right: auth controls */}
      <div className="flex items-center gap-2">
        {loading ? null : user ? (
          <Link
            href="/profile"
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
              pathname === "/profile"
                ? "bg-ocean-500/15 text-bioluminescent-400"
                : "text-slate-400 hover:bg-ocean-900/40 hover:text-slate-200"
            }`}
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-ocean-500 to-ocean-700 text-xs font-bold text-white shadow-ocean-sm">
              {user.display_name.charAt(0).toUpperCase()}
            </span>
            {user.display_name}
          </Link>
        ) : (
          <Link
            href="/auth"
            className="rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-4 py-1.5 text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400 hover:shadow-ocean-md"
          >
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}
