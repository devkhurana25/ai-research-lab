import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Research Lab",
  description: "An autonomous investigation engine that shows its work.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col bg-lab-bg text-lab-text antialiased">
        {children}
      </body>
    </html>
  );
}
