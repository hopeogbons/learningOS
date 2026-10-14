import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import {
  LOCALE_COOKIE,
  resolveLocale,
  languageFor,
  isLocale,
} from "@/i18n/registry";
import Providers from "@/components/Providers";
import "bootstrap/dist/css/bootstrap.min.css";
import "./globals.css";
import "@/i18n/fonts.css";
export const metadata: Metadata = {
  title: "Learning OS",
  description:
    "A study partner that makes you learn, not just collect answers. Teach, then check, in small loops, with automatic spaced review.",
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#173b3f",
};
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const jar = await cookies(),
    locale = resolveLocale(jar.get(LOCALE_COOKIE)?.value),
    study = jar.get("learningos_study_locale")?.value,
    speech = jar.get("learningos_speech_locale")?.value;
  return (
    <html
      lang={locale}
      dir={languageFor(locale).direction}
      data-bs-theme="light"
    >
      <body>
        <Providers
          locale={locale}
          preferences={{
            ui_locale: locale,
            ...(isLocale(study) ? { study_locale: study } : {}),
            ...(speech ? { speech_locale: speech } : {}),
          }}
        >
          {children}
        </Providers>
      </body>
    </html>
  );
}
