import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "./providers";

export const metadata: Metadata = {
  title: "InfraForge — Real Infrastructure Labs",
  description: "Practice and prove your infra skills in isolated, graded environments.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-950 text-gray-100 antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
