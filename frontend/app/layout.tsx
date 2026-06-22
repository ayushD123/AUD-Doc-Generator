import type { Metadata } from "next";
import ClickSpark from "@/components/ClickSpark";
import ThemeToggle from "@/components/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "AUD Generator",
  description: "Internal Oracle AUD generation workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <ClickSpark sparkColor="#38bdf8" sparkRadius={22} sparkCount={10}>
          <ThemeToggle />
          {children}
        </ClickSpark>
      </body>
    </html>
  );
}
