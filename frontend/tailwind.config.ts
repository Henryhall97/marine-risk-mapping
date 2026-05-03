import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      /* ── Ocean-inspired colour palette ─────────────────── */
      colors: {
        ocean: {
          50: "#e6f4fa",
          100: "#b3dff0",
          200: "#80cae6",
          300: "#4db5dc",
          400: "#26a5d5",
          500: "#0891b2", // primary cyan-teal
          600: "#067a97",
          700: "#04627a",
          800: "#034a5c",
          900: "#01323e",
          950: "#001a24",
        },
        abyss: {
          50: "#e8edf5",
          100: "#c5cfe6",
          200: "#9daed4",
          300: "#748cc2",
          400: "#5673b5",
          500: "#3a5a9f",
          600: "#2e4a87",
          700: "#1e3564",
          800: "#142647",
          900: "#0b1a30",
          950: "#060e1c",
        },
        coral: {
          400: "#ff8a80",
          500: "#ff6b6b",
          600: "#e74c3c",
        },
        seafoam: {
          300: "#a7f3d0",
          400: "#6ee7b7",
          500: "#34d399",
        },
        bioluminescent: {
          400: "#67e8f9",
          500: "#22d3ee",
          600: "#06b6d4",
        },
      },
      /* ── Custom animations ─────────────────────────────── */
      animation: {
        "wave": "wave 8s ease-in-out infinite",
        "wave-slow": "wave 12s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "float-delayed": "float 6s ease-in-out 2s infinite",
        "shimmer": "shimmer 3s ease-in-out infinite",
        "glow-pulse": "glow-pulse 4s ease-in-out infinite",
        "gradient-shift": "gradient-shift 8s ease infinite",
        "fade-in-up": "fade-in-up 0.6s ease-out forwards",
        "scale-in": "scale-in 0.5s ease-out forwards",
        "ripple": "ripple 0.6s ease-out",
        "tail-flick": "tail-flick 4s ease-in-out infinite",
        "dive": "dive-down 3s ease-in-out infinite",
        "pod-swim": "pod-swim 5s ease-in-out infinite",
        "slide-in-right": "slide-in-right 0.4s ease-out forwards",
        "cta-wiggle": "cta-wiggle 2s ease-in-out infinite",
      },
      keyframes: {
        wave: {
          "0%, 100%": { transform: "translateY(0) rotate(0deg)" },
          "50%": { transform: "translateY(-8px) rotate(2deg)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "0.8", transform: "scale(1.05)" },
        },
        "gradient-shift": {
          "0%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
          "100%": { backgroundPosition: "0% 50%" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(24px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.9)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        ripple: {
          "0%": { transform: "scale(0)", opacity: "0.5" },
          "100%": { transform: "scale(4)", opacity: "0" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(24px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "cta-wiggle": {
          "0%, 100%": { transform: "rotate(0deg) translateY(0)" },
          "20%": { transform: "rotate(-6deg) translateX(-3px)" },
          "40%": { transform: "rotate(0deg) translateY(0)" },
          "60%": { transform: "rotate(6deg) translateX(3px)" },
          "80%": { transform: "rotate(0deg) translateY(0)" },
        },
      },
      /* ── Backdrop / glass helpers ──────────────────────── */
      backdropBlur: {
        xs: "2px",
      },
      backgroundImage: {
        "ocean-gradient":
          "linear-gradient(135deg, #060e1c 0%, #01323e 40%, #034a5c 70%, #0b1a30 100%)",
        "ocean-radial":
          "radial-gradient(ellipse at 50% 0%, #0891b220 0%, transparent 70%)",
        "shimmer-gradient":
          "linear-gradient(90deg, transparent 0%, #22d3ee10 50%, transparent 100%)",
      },
      boxShadow: {
        "ocean-sm": "0 2px 8px rgba(8,145,178,0.10)",
        "ocean-md": "0 4px 24px rgba(8,145,178,0.15)",
        "ocean-lg": "0 8px 48px rgba(8,145,178,0.20)",
        "ocean-glow": "0 0 30px rgba(34,211,238,0.15)",
        "coral-glow": "0 0 20px rgba(255,107,107,0.20)",
      },
      fontFamily: {
        display: [
          "Plus Jakarta Sans",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
        body: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
