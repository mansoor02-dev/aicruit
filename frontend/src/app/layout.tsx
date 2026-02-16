import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "../index.css";
import { Providers } from "./providers";

const poppins = Poppins({ subsets: ["latin"], weight: ["400"] });

export const metadata: Metadata = {
  title: "AIcruit - AI-Powered Recruitment Platform",
  description: "AI-Powered Recruitment Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={poppins.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

