import type { Metadata } from "next";
import { Atkinson_Hyperlegible_Next } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { StatusLine } from "@/components/status-line";
import "./globals.css";

// Designed for legibility: suits a grower reading a phone outdoors.
const atkinson = Atkinson_Hyperlegible_Next({
  variable: "--font-sans",
  subsets: ["latin"],
  // next/font has no size metrics for this font yet, so use a plain system fallback while it loads.
  adjustFontFallback: false,
  fallback: ["system-ui", "sans-serif"],
});

export const metadata: Metadata = {
  title: "AgroPilot",
  description: "Daily drip irrigation plan for each plot.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${atkinson.variable} h-full antialiased`}>
      <body className="min-h-full">
        {/* One container for the header and the content, so the status line stays aligned with the page (max 1280 px). */}
        <div className="mx-auto w-full max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
          <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b py-3">
            <Link href="/" className="text-lg font-bold tracking-tight">
              AgroPilot
            </Link>
            <Suspense fallback={<p className="text-sm text-muted-foreground">Checking services…</p>}>
              <StatusLine />
            </Suspense>
          </header>
          <main className="pt-5">{children}</main>
        </div>
      </body>
    </html>
  );
}
