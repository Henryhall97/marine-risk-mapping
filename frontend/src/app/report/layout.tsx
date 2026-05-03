import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Report Interaction",
  description:
    "Report a whale interaction with photo and audio evidence. AI classifies the species and provides a real-time collision risk advisory.",
};

export default function ReportLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
