import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* CSS 变量映射（shadcn/ui 兼容） */
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        /* 品牌主色 */
        brand: {
          blue: "#2563EB",
          orange: "#F59E0B",
          green: "#10B981",
          red: "#EF4444",
          gray: "#6B7280",
        },
        /* 侧边栏边线 */
        "sidebar-border": "#E5E7EB",
        /* 学科色块 */
        subject: {
          math: { light: "#DBEAFE", DEFAULT: "#3B82F6", dark: "#1D4ED8" },
          science: { light: "#FEF3C7", DEFAULT: "#F59E0B", dark: "#D97706" },
          chinese: { light: "#FCE7F3", DEFAULT: "#EC4899", dark: "#DB2777" },
          english: { light: "#FEF9C3", DEFAULT: "#EAB308", dark: "#CA8A04" },
          programming: { light: "#E0E7FF", DEFAULT: "#6366F1", dark: "#4F46E5" },
          art: { light: "#EDE9FE", DEFAULT: "#8B5CF6", dark: "#7C3AED" },
          history: { light: "#D1FAE5", DEFAULT: "#10B981", dark: "#059669" },
        },
        /* 年龄主题色 */
        age: {
          "06-09": { primary: "#FF6B6B", secondary: "#4ECDC4", accent: "#FFE66D", bg: "#FFF5F5" },
          "10-12": { primary: "#2563EB", secondary: "#10B981", accent: "#F59E0B", bg: "#F0F9FF" },
          "13-15": { primary: "#6366F1", secondary: "#EC4899", accent: "#14B8A6", bg: "#EEF2FF" },
          "16-18": { primary: "#1E293B", secondary: "#2563EB", accent: "#6366F1", bg: "#F8FAFC" },
        },
      },
      borderRadius: {
        "card-sm": "12px",
        "card-md": "16px",
        "card-lg": "20px",
      },
      boxShadow: {
        card: "0 8px 24px rgba(15, 23, 42, 0.04)",
        "card-hover": "0 12px 32px rgba(15, 23, 42, 0.08)",
      },
      width: {
        sidebar: "256px",
      },
      height: {
        topbar: "64px",
      },
      fontFamily: {
        sans: [
          "Inter",
          "PingFang SC",
          "Microsoft YaHei",
          "Noto Sans SC",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
