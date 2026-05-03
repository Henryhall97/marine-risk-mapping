import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Community Sightings",
  description:
    "Browse and verify community whale sightings. Filter by species, region, and verification status. Submit your own observations.",
};

export default function CommunityLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
