import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GRC Risk Intelligence",
  description: "AI-powered GRC Risk Intelligence Platform demo with CrustData ingestion"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

