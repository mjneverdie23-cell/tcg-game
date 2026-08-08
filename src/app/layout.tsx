import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { ServiceWorkerRegistrar } from "@/components/pwa/service-worker-registrar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://world-atlas.example.com"),
  title: {
    default: "World Atlas — Interactive Encyclopedia of Every Country",
    template: "%s — World Atlas",
  },
  description:
    "Explore every sovereign country on an interactive world map: history, geography, culture, famous destinations, cuisine, festivals and more — a premium digital encyclopedia built on open data.",
  keywords: ["world atlas", "countries", "geography", "interactive map", "encyclopedia", "flags", "destinations", "history"],
  manifest: "/manifest.webmanifest",
  openGraph: {
    type: "website",
    siteName: "World Atlas",
    title: "World Atlas — Interactive Encyclopedia of Every Country",
    description: "Explore every sovereign country on an interactive world map.",
  },
  icons: { icon: "/icons/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f9f8f4" },
    { media: "(prefers-color-scheme: dark)", color: "#0c111d" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans min-h-dvh flex flex-col`}>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <Header />
          <main className="flex-1 flex flex-col">{children}</main>
          <Footer />
          <ServiceWorkerRegistrar />
        </ThemeProvider>
      </body>
    </html>
  );
}
