import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Falcon University Admission",
  description: "Admission pre-assessment assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
