"use client";
import { useId } from "react";
import { useI18n } from "@/i18n";
export default function LanguageSelect({
  compact = false,
}: {
  compact?: boolean;
}) {
  const { t, locale, setLocale, languages } = useI18n();
  const id = useId();
  return (
    <div className={compact ? "language-select compact" : "language-select"}>
      <label
        htmlFor={id}
        className={compact ? "visually-hidden" : "form-label small fw-semibold"}
      >
        {t("common.language")}
      </label>
      <select
        id={id}
        className="form-select form-select-sm"
        value={locale}
        onChange={(e) => setLocale(e.target.value as typeof locale)}
      >
        {languages.map((l) => (
          <option key={l.locale} value={l.locale}>
            {l.native} ({l.english})
          </option>
        ))}
      </select>
    </div>
  );
}
