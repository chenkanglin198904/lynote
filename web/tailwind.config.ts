import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14110e",
        panel: "#1d1914",
        raised: "#26211b",
        line: "#3b342b",
        paper: "#efe6d6",
        muted: "#9a8d7c",
        gold: "#c9a227",
        clay: "#c45c4a",
        moss: "#6b8f71",
        haze: "#7d9bb0",
      },
      fontFamily: {
        serif: ["\"Source Serif 4\"", "Georgia", "serif"],
        sans: ["\"Schibsted Grotesk\"", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
