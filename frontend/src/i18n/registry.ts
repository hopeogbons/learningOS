/** Exact native-label order supplied by the learner. Languages are not countries. */
export const languages = [
  { locale: "en", native: "English", english: "English", direction: "ltr", speech: "en-GB" },
  { locale: "zh-Hans", native: "中文", english: "Chinese (Simplified)", direction: "ltr", speech: "zh-CN" },
  { locale: "es", native: "Español", english: "Spanish", direction: "ltr", speech: "es-ES" },
  { locale: "ar", native: "العربية", english: "Arabic", direction: "rtl", speech: "ar-SA" },
  { locale: "pt", native: "Português", english: "Portuguese", direction: "ltr", speech: "pt-BR" },
  { locale: "fr", native: "Français", english: "French", direction: "ltr", speech: "fr-FR" },
  { locale: "ja", native: "日本語", english: "Japanese", direction: "ltr", speech: "ja-JP" },
  { locale: "ru", native: "Русский", english: "Russian", direction: "ltr", speech: "ru-RU" },
  { locale: "de", native: "Deutsch", english: "German", direction: "ltr", speech: "de-DE" },
  { locale: "id", native: "Bahasa Indonesia", english: "Indonesian", direction: "ltr", speech: "id-ID" },
] as const;
export type Locale = typeof languages[number]["locale"];
export type LanguagePreferences = { ui_locale: Locale; study_locale: Locale; speech_locale: string };
export const LOCALE_COOKIE = "learningos_locale";
export function isLocale(value: unknown): value is Locale {
  return languages.some((language) => language.locale === value);
}
export function resolveLocale(value: string | undefined | null): Locale {
  if (!value) return "en";
  if (isLocale(value)) return value;
  const normalized = value.toLowerCase();
  if (normalized.startsWith("zh")) return "zh-Hans";
  const base = normalized.split("-")[0];
  return isLocale(base) ? base : "en";
}
export function languageFor(locale: Locale) { return languages.find((entry) => entry.locale === locale)!; }
export function defaultPreferences(locale: Locale): LanguagePreferences {
  return { ui_locale: locale, study_locale: locale, speech_locale: languageFor(locale).speech };
}
/** Stable defaults; a saved account or cookie preference must always outrank browser hints. */
export function browserLocale(acceptLanguage: string | null): Locale {
  const candidates = (acceptLanguage ?? "").split(",").map((part) => {
    const [tag, quality] = part.trim().split(";");
    return { tag, quality: quality?.startsWith("q=") ? Number(quality.slice(2)) : 1 };
  }).filter((entry) => entry.quality > 0).sort((a, b) => b.quality - a.quality);
  for (const { tag } of candidates) {
    const locale = resolveLocale(tag);
    if (locale !== "en" || tag.toLowerCase().startsWith("en")) return locale;
  }
  return "en";
}
