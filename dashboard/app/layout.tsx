import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EFTR Regulatory Assurance",
  description: "FINTRAC EFT compliance validation platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 min-h-screen font-sans">
        <nav className="border-b px-8 py-4 flex gap-6 text-sm">
          <a href="/" className="font-semibold text-blue-700 hover:underline">Overview</a>
          <a href="/missed" className="text-gray-600 hover:underline">Missed Transactions</a>
          <a href="/findings" className="text-gray-600 hover:underline">Rule Findings</a>
          <a href="/reperformance" className="text-gray-600 hover:underline">Reperformance</a>
        </nav>
        {children}
      </body>
    </html>
  );
}
