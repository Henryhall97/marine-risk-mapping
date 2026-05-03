import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import Nav from "@/components/Nav";
import Providers from "./Providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: {
    default: "Whale Watch",
    template: "%s — Whale Watch",
  },
  description:
    "Map whale–vessel collision risk across CONUS, Alaska, Hawaii, and Caribbean waters. AI species classification from photos and audio. Community-powered sighting verification.",
  icons: { icon: "/whale_watch_logo.png" },
  openGraph: {
    title: "Whale Watch",
    description:
      "Map whale–vessel collision risk across CONUS, Alaska, Hawaii, and Caribbean waters. AI species classification from photos and audio.",
    siteName: "Whale Watch",
    images: [{ url: "/whale_watch_logo.png", width: 480, height: 320 }],
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Whale Watch",
    description:
      "Map whale–vessel collision risk. AI species classification from photos and audio.",
    images: ["/whale_watch_logo.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jakarta.variable}`}>
      <body className="bg-abyss-950 font-body text-slate-200 antialiased">

        {/* Global watermark */}
        <div
          className="pointer-events-none fixed inset-0 z-0 opacity-[0.025]"
          style={{
            backgroundImage: "url(/whale_watch_logo.png)",
            backgroundRepeat: "repeat",
            backgroundSize: "20vw calc(20vw * 2 / 3)",
            backgroundPosition: "center",
          }}
          aria-hidden
        />
        <Providers>
          <Nav />
          {children}
        </Providers>
      </body>
    </html>
  );
}
