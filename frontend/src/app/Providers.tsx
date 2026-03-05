"use client";

import { AuthProvider } from "@/contexts/AuthContext";
import type { ReactNode } from "react";

/** Client-side providers wrapper — keeps layout.tsx as a server component. */
export default function Providers({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
