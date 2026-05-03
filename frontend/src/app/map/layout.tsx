import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Risk Map",
  description:
    "Explore whale–vessel collision risk across CONUS, Alaska, Hawaii, and Caribbean waters. 7 expert-weighted sub-scores per H3 hex cell, toggleable overlays, and ML-enhanced predictions.",
};

export default function MapLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
