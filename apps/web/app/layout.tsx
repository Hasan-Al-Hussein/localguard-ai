import type { Metadata } from "next";
import { headers } from "next/headers";
import { Geist, Manrope } from "next/font/google";
import type { ReactNode } from "react";
import { AppProviders } from "@/components/providers/app-providers";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
});

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "LocalGuard AI", template: "%s · LocalGuard AI" },
  description: "Auditable, local-first document intelligence and workflow review.",
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  await headers();

  return (
    <html lang="en" className={`${manrope.variable} ${geist.variable}`}>
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
