import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { cn } from "@/lib/utils";

const geist = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-sans",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "TenderIt",
  description: "Автоматическая подача тендерных заявок на goszakup.gov.kz",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={cn("dark font-sans", geist.variable)}>
      <body className="antialiased bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
