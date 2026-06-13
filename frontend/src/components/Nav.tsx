"use client";

import { useAuth } from "@/contexts/AuthContext";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";
import { Fragment, useState, useEffect } from "react";
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
  { href: "/map", label: "Risk Map", Icon: IconMap, group: "explore", desc: "Interactive collision-risk map" },
  { href: "/insights", label: "Insights", Icon: IconChart, group: "explore", desc: "Stakeholder analytics & reports" },
  { href: "/species", label: "ID Guide", Icon: IconDolphin, group: "explore", desc: "Identify whales & dolphins" },
  { href: "/classify", label: "Classify", Icon: IconMicroscope, group: "explore", desc: "AI photo & audio ID" },
  { href: "/report", label: "Interactions", Icon: IconWhale, group: "contribute", desc: "Report a sighting" },
  { href: "/report-vessel", label: "Violations", Icon: IconShip, group: "contribute", desc: "Report a vessel violation" },
  { href: "/community", label: "Community", Icon: IconUsers, group: "contribute", desc: "Feeds, events & verification" },
] as const;

const GROUPS = [
  { id: "explore", label: "Explore" },
  { id: "contribute", label: "Contribute" },
] as const;

export default function Nav() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState<string | null>(null);

  // Close drawer + any open dropdown on route change
  useEffect(() => {
    setMobileOpen(false);
    setOpenGroup(null);
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

        {/* Centre: desktop dropdown menus — hidden below lg */}
        <div className="hidden items-center gap-1 lg:flex">
          {GROUPS.map((g) => {
            const items = LINKS.filter((l) => l.group === g.id);
            const groupActive = items.some(
              (l) => pathname === l.href || pathname.startsWith(l.href + "/"),
            );
            const isOpen = openGroup === g.id;
            return (
              <div
                key={g.id}
                className="relative"
                onMouseEnter={() => setOpenGroup(g.id)}
                onMouseLeave={() => setOpenGroup(null)}
              >
                <button
                  type="button"
                  aria-haspopup="true"
                  aria-expanded={isOpen}
                  onClick={() => setOpenGroup(isOpen ? null : g.id)}
                  className={`group relative flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                    groupActive || isOpen
                      ? "text-bioluminescent-400"
                      : "text-slate-300 hover:text-slate-100"
                  }`}
                >
                  {g.label}
                  <svg
                    viewBox="0 0 12 12"
                    className={`h-3 w-3 transition-transform duration-300 ${isOpen ? "rotate-180" : ""}`}
                    aria-hidden
                  >
                    <path
                      d="M2.5 4.5 6 8l3.5-3.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  {/* Glow underline when group active */}
                  <span
                    aria-hidden
                    className={`pointer-events-none absolute inset-x-3 -bottom-[7px] h-0.5 origin-center rounded-full bg-gradient-to-r from-ocean-400 to-bioluminescent-400 transition-transform duration-300 ${
                      groupActive
                        ? "scale-x-100 shadow-[0_0_10px_rgba(34,211,238,0.7)]"
                        : "scale-x-0"
                    }`}
                  />
                </button>

                {/* Dropdown panel */}
                <div
                  className={`absolute left-1/2 top-full z-50 w-64 -translate-x-1/2 pt-3 transition-all duration-200 ${
                    isOpen
                      ? "visible translate-y-0 opacity-100"
                      : "invisible -translate-y-1 opacity-0"
                  }`}
                >
                  <div className="glass-panel-strong overflow-hidden rounded-2xl border border-ocean-800/40 p-1.5 shadow-ocean-md">
                    {items.map((l) => {
                      const active =
                        pathname === l.href ||
                        pathname.startsWith(l.href + "/");
                      return (
                        <Link
                          key={l.href}
                          href={l.href}
                          aria-current={active ? "page" : undefined}
                          className={`group/item flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors ${
                            active
                              ? "bg-ocean-500/15"
                              : "hover:bg-ocean-900/50"
                          }`}
                        >
                          <span
                            className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
                              active
                                ? "bg-gradient-to-br from-ocean-500 to-ocean-700 text-white shadow-ocean-sm"
                                : "bg-ocean-900/60 text-slate-400 group-hover/item:text-bioluminescent-400"
                            }`}
                          >
                            <l.Icon className="h-4 w-4" />
                          </span>
                          <span className="min-w-0">
                            <span
                              className={`block text-sm font-semibold ${
                                active
                                  ? "text-bioluminescent-400"
                                  : "text-slate-200"
                              }`}
                            >
                              {l.label}
                            </span>
                            <span className="block text-xs leading-snug text-slate-500">
                              {l.desc}
                            </span>
                          </span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              </div>
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

        {/* Bottom hairline accent */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-ocean-500/40 to-transparent"
        />
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
          {LINKS.map((l, i) => {
            const active =
              pathname === l.href || pathname.startsWith(l.href + "/");
            const prev = LINKS[i - 1];
            const showLabel = !prev || prev.group !== l.group;
            return (
              <Fragment key={l.href}>
                {showLabel && (
                  <p
                    className={`px-4 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600 ${
                      i === 0 ? "" : "pt-4"
                    }`}
                  >
                    {l.group === "explore" ? "Explore" : "Contribute"}
                  </p>
                )}
                <Link
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
              </Fragment>
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
