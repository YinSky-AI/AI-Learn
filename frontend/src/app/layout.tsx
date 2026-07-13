import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "AI学堂 - 智能学习平台",
  description: "适合6-18岁青少年的AI驱动个性化学习平台",
  keywords: ["AI学习", "青少年教育", "个性化学习", "智能辅导"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased bg-background text-gray-900`}>
        <ThemeProvider>
          <TooltipProvider delayDuration={300}>
            {children}
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
