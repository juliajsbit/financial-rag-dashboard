import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0f1117",
        panel: "#161b27",
        brand: "#1a56db",
        "brand-light": "#3b82f6",
      },
    },
  },
  plugins: [],
};

export default config;
