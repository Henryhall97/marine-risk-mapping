"use client";

import { useAuth } from "@/contexts/AuthContext";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";
import { useState, useEffect } from "react";
import {
  IconMap,
  IconMicroscope,
  IconWhale,
  IconChart,
  IconUsers,
  IconShip,
  IconDolphin,
} from "@/components/icons/MarineIcons";

const LINKS = [
  { href: "/map", label: "Risk Map", Icon: IconMap },
  { href: "/insights", label: "Insights", Icon: IconChart },
  { href: "/species", label: "ID Guide", Icon: IconDolphin },
  { href: "/classify", label: "Classify", Icon: IconMicroscope },
  { href: "/report", label: "Interactions", Icon: IconWhale },
  { href: "/report-vessel", label: "Violations", Icon: IconShip },
  { href: "/community", label: "Community", Icon: IconUsers },
];

export default function Nav() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Lock body scroll while drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      <nav className="glass-panel-strong fixed left-0 top-0 z-50 grid w-full grid-cols-[1fr_auto_1fr] items-center px-4 py-2 sm:px-6">
        {/* Left: brand */}
        <Link
          href="/"
          className="group flex items-center gap-2.5 text-lg font-bold tracking-tight"
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

        {/* Centre: desktop nav links — hidden below lg */}
        <div className="hidden items-center gap-0.5 lg:flex">
          {LINKS.map((l) => {
            const active =
              pathname === l.href || pathname.startsWith(l.href + "/");
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

        {/* Right: auth + hamburger */}
        <div className="flex items-center justify-end gap-2">
          {/* Auth — hidden on very small screens, shown on sm+ */}
          {!loading &&
            (user ? (
              <Link
                href="/profile"
                className={`hidden items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-all sm:flex ${
                  pathname === "/profile"
                    ? "bg-ocean-500/15 text-bioluminescent-400"
                    : "text-slate-400 hover:bg-ocean-900/40 hover:text-slate-200"
                }`}
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-ocean-500 to-ocean-700 text-xs font-bold text-white shadow-ocean-sm">
                  {user.display_name.charAt(0).toUpperCase()}
                </span>
                <span className="hidden xl:inline">{user.display_name}</span>
              </Link>
            ) : (
              <Link
                href="/auth"
                className="hidden rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-4 py-1.5 text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400 hover:shadow-ocean-md sm:block"
              >
                Sign In
              </Link>
            ))}

          {/* Hamburger button — visible below lg */}
          <button
            onClick={() => setMobileOpen((v) => !v)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-all hover:bg-ocean-900/40 hover:text-slate-200 lg:hidden"
          >
            {/* Animated 3-bar → X */}
            <span className="relative flex h-5 w-5 flex-col justify-between">
              <span
                className={`block h-0.5 w-full rounded bg-current transition-all duration-300 ${mobileOpen ? "translate-y-[9px] rotate-45" : ""}`}
              />
              <span
                className={`block h-0.5 w-full rounded bg-current transition-all duration-300 ${mobileOpen ? "opacity-0" : ""}`}
              />
              <span
                className={`block h-0.5 w-full rounded bg-current transition-all duration-300 ${mobileOpen ? "-translate-y-[9px] -rotate-45" : ""}`}
              />
            </span>
          </button>
        </div>
      </nav>

      {/* Backdrop */}
      <div
        onClick={() => setMobileOpen(false)}
        aria-hidden
        className={`fixed inset-0 z-40 bg-abyss-950/70 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${
          mobileOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      />

      {/* Slide-in mobile drawer */}
      <div
        className={`glass-panel-strong fixed right-0 top-0 z-50 flex h-full w-72 flex-col px-6 pb-8 pt-20 transition-transform duration-300 ease-out lg:hidden ${
          mobileOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <nav className="flex-1 space-y-1" aria-label="Mobile navigation">
          {LINKS.map((l) => {
            const active =
              pathname === l.href || pathname.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                  active
                    ? "bg-ocean-500/15 text-bioluminescent-400"
                    : "text-slate-400 hover:bg-ocean-900/40 hover:text-slate-200"
                }`}
              >
                <l.Icon className="h-5 w-5 flex-shrink-0" />
                {l.label === "Interactions" ? "Report Interaction" : l.label === "Violations" ? "Report Vessel Violation" : l.label}
              </Link>
            );
          })}
        </nav>

        {/* Auth section at bottom of drawer */}
        <div className="border-t border-ocean-800/20 pt-4">
          {!loading &&
            (user ? (
              <Link
                href="/profile"
                className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-slate-400 transition-all hover:bg-ocean-900/40 hover:text-slate-200"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-ocean-500 to-ocean-700 text-xs font-bold text-white">
                  {user.display_name.charAt(0).toUpperCase()}
                </span>
                {user.display_name}
              </Link>
            ) : (
              <Link
                href="/auth"
                className="block w-full rounded-xl bg-gradient-to-r from-ocean-600 to-ocean-500 px-4 py-3 text-center text-sm font-semibold text-white shadow-ocean-sm transition-all hover:from-ocean-500 hover:to-ocean-400"
              >
                Sign In
              </Link>
            ))}
        </div>
      </div>
    </>
  );
}
