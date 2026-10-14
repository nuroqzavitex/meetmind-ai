import type { Metadata } from "next";
import { Be_Vietnam_Pro, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { viVN } from "@clerk/localizations";
import "./globals.css";
import { Providers } from "./providers";
import { AppHeader } from "@/components/app-header";

// Geist has no Vietnamese subset, so diacritics fell back to a system font mid-word.
const beVietnam = Be_Vietnam_Pro({
  variable: "--font-be-vietnam",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: "MeetMind AI",
  description: "Phân tích biên bản cuộc họp",
};

const clerkAppearance = {
  variables: {
    colorPrimary: "#4f46e5",
    colorText: "#111827",
    borderRadius: "0.75rem",
    fontFamily: "var(--font-be-vietnam), system-ui, sans-serif",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider
      localization={viVN}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      appearance={clerkAppearance}
    >
    {/* Font variables must sit on <html>: `font-sans` is applied there and reads them. */}
    <html lang="vi" className={`${beVietnam.variable} ${geistMono.variable}`}>
      <body className="min-h-screen font-sans antialiased">
        <Providers>
          <AppHeader />
          {children}
        </Providers>
      </body>
    </html>
    </ClerkProvider>
  );
}
