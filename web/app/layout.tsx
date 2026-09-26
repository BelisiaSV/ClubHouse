import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "The TopsportSpace",
  description: "War room voor de Hoofdcoaches.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="nl" className={inter.variable}>
      <body className="bg-gray-950 font-sans text-gray-100 antialiased">{children}</body>
    </html>
  );
}
