"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Redirect /events → /community/events.
 * Keeps /events/[id] and /events/join/[code] routes intact.
 */
export default function EventsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/community/events");
  }, [router]);
  return null;
}
