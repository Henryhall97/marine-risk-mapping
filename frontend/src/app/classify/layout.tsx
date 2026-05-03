import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Classify Species",
  description:
    "Upload a whale photograph or underwater audio recording. AI models identify the species and provide local collision risk context.",
};

export default function ClassifyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
