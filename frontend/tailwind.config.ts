import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201b",
        moss: "#37624d",
        coral: "#c84f48",
        mint: "#dff3e8"
      }
    }
  },
  plugins: []
};

export default config;

