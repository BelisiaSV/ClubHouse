import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      colors: {
        pitch: { DEFAULT: "#059669", hover: "#047857" },
        electric: { DEFAULT: "#38bdf8" },
      },
    },
  },
  plugins: [],
};

export default config;
