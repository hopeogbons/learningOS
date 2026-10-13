"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import IntlMessageFormat from "intl-messageformat";
import en from "./catalogs/en.json";
import zh from "./catalogs/zh-Hans.json";
import es from "./catalogs/es.json";
import ar from "./catalogs/ar.json";
import pt from "./catalogs/pt.json";
import fr from "./catalogs/fr.json";
import ja from "./catalogs/ja.json";
import ru from "./catalogs/ru.json";
import de from "./catalogs/de.json";
import id from "./catalogs/id.json";
import { defaultPreferences, isLocale, languageFor, languages, LOCALE_COOKIE, type LanguagePreferences, type Locale } from "./registry";
export * from "./registry";

export const catalogs: Record<Locale, Record<string, string>> = { en, "zh-Hans": zh, es, ar, pt, fr, ja, ru, de, id };
export type MessageValues = Record<string, string | number | boolean | Date>;
const formats = new Map<string, IntlMessageFormat>();
/** ICU formatting uses the requested locale's actual cardinal/number/date rules. */
export function translate(locale: Locale, key: string, values: MessageValues = {}): string {
  const message = catalogs[locale][key];
  if (message === undefined) throw new Error(`Missing message: ${locale}:${key}`);
  const cacheKey = `${locale}:${key}`;
  let formatter = formats.get(cacheKey);
  if (!formatter) {
    formatter = new IntlMessageFormat(message, locale);
    formats.set(cacheKey, formatter);
  }
  return String(formatter.format(values));
}
type ContextValue = {
  locale: Locale;
  preferences: LanguagePreferences;
  languages: typeof languages;
  t: (key: string, values?: MessageValues) => string;
  setLocale: (locale: Locale) => void;
  setPreferences: (preferences: Partial<LanguagePreferences>) => void;
  restorePreferences: (preferences: Partial<LanguagePreferences>) => void;
};
const Context = createContext<ContextValue | null>(null);
export function I18nProvider({ children, initialLocale = "en", initialPreferences, onPreferencesChange }: {
  children: ReactNode;
  initialLocale?: Locale;
  initialPreferences?: Partial<LanguagePreferences>;
  /** Account persistence belongs to the authenticated API client, not translation rendering. */
  onPreferencesChange?: (preferences: LanguagePreferences) => void | Promise<void>;
}) {
  const [preferences, updatePreferences] = useState<LanguagePreferences>(() => ({ ...defaultPreferences(initialLocale), ...initialPreferences }));
  const preferenceRef = useRef(preferences);
  const locale = preferences.ui_locale;
  const userEdited = useRef(false);
  const applyPreferences = useCallback((changes: Partial<LanguagePreferences>) => {
    const next = { ...preferenceRef.current, ...changes };
    if (!isLocale(next.ui_locale) || !isLocale(next.study_locale)) throw new Error("Unsupported language preference");
    // BCP 47 is validated by Intl; unsupported voice availability remains a separate runtime check.
    Intl.getCanonicalLocales(next.speech_locale);
    preferenceRef.current = next;
    updatePreferences(next);
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${LOCALE_COOKIE}=${encodeURIComponent(next.ui_locale)}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
    document.cookie = `learningos_study_locale=${encodeURIComponent(next.study_locale)}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
    document.cookie = `learningos_speech_locale=${encodeURIComponent(next.speech_locale)}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
    return next;
  }, []);
  const setPreferences = useCallback((changes: Partial<LanguagePreferences>) => {
    userEdited.current = true;
    const next = applyPreferences(changes);
    void onPreferencesChange?.(next);
  }, [applyPreferences, onPreferencesChange]);
  const restorePreferences = useCallback((saved: Partial<LanguagePreferences>) => {
    // A late initial account read must not discard an explicit choice made while it loaded.
    if (!userEdited.current) applyPreferences(saved);
  }, [applyPreferences]);
  const setLocale = useCallback((next: Locale) => setPreferences({ ui_locale: next }), [setPreferences]);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = languageFor(locale).direction;
  }, [locale]);
  const value = useMemo(() => ({ locale, preferences, languages, t: (key: string, values?: MessageValues) => translate(locale, key, values), setLocale, setPreferences, restorePreferences }), [locale, preferences, setLocale, setPreferences, restorePreferences]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useI18n(): ContextValue {
  const context = useContext(Context);
  if (!context) throw new Error("useI18n must be inside I18nProvider");
  return context;
}
