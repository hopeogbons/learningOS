"use client";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  I18nProvider,
  useI18n,
  type Locale,
  type LanguagePreferences,
} from "@/i18n";
import { api, json, type Profile } from "@/lib/api";
import { AppState } from "./AppState";
import AppShell from "./AppShell";
import { Status } from "./Shared";
export default function Providers({
  children,
  locale,
  preferences,
}: {
  children: ReactNode;
  locale: Locale;
  preferences: Partial<LanguagePreferences>;
}) {
  const [preferenceError, setPreferenceError] = useState<string | null>(null);
  const persist = useCallback(async (p: LanguagePreferences) => {
    try {
      await api("/me", { method: "PATCH", body: json(p) });
      setPreferenceError(null);
    } catch (e) {
      setPreferenceError((e as Error).message);
    }
  }, []);
  return (
    <I18nProvider
      initialLocale={locale}
      initialPreferences={preferences}
      onPreferencesChange={persist}
    >
      <AccountHydration />
      <AppState>
        <AppShell>
          <Status error={preferenceError} />
          {children}
        </AppShell>
      </AppState>
    </I18nProvider>
  );
}

function AccountHydration() {
  const { restorePreferences } = useI18n();
  useEffect(() => {
    let active = true;
    api<Profile>("/me")
      .then((p) => {
        if (active)
          restorePreferences({
            ui_locale: p.ui_locale as Locale,
            study_locale: p.study_locale as Locale,
            speech_locale: p.speech_locale,
          });
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [restorePreferences]);
  return null;
}
