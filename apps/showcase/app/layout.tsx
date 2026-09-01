import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppProviders } from "../components/providers/app-providers";
import "../../web/app/globals.css";
import "./showcase.css";

export const metadata: Metadata = {
  applicationName: "LocalGuard AI Public Showcase",
  title: {
    default: "LocalGuard AI · Public Showcase",
    template: "%s · LocalGuard AI Showcase",
  },
  description:
    "Explore LocalGuard AI through a safe, deterministic portfolio demo with synthetic evidence and browser-only interactions.",
  keywords: [
    "LocalGuard AI",
    "document intelligence",
    "grounded AI",
    "human-in-the-loop",
    "portfolio demo",
  ],
  robots: { follow: true, index: true },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#07131d",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html className="showcase-fonts" data-scroll-behavior="smooth" lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
