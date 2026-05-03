import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Stakeholder Insights",
  description:
    "Tailored whale–vessel collision risk dashboards for vessel captains, policy makers, marine researchers, conservation groups, and port authorities.",
};

export default function InsightsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
