import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        tier1: {
          bg: "#eff6ff",
          text: "#1d4ed8",
          border: "#bfdbfe",
        },
        tier2: {
          bg: "#fffbeb",
          text: "#b45309",
          border: "#fde68a",
        },
        tier3: {
          bg: "#fef2f2",
          text: "#b91c1c",
          border: "#fecaca",
        },
      },
    },
  },
  plugins: [],
};

export default config;
