"use client";
import { LogoMark } from "./Logo";
import { useI18n } from "@/i18n";

export default function HomeIntroduction() {
  const { t } = useI18n();
  return (
    <section className="home-introduction" aria-labelledby="home-introduction-title">
      <span className="home-introduction-mark" aria-hidden="true">
        <LogoMark size={34} />
      </span>
      <div className="min-w-0">
        <h2 id="home-introduction-title" className="home-introduction-title">
          {t("home.introTitle")}
        </h2>
        <p className="home-introduction-copy mb-0">{t("home.introBody")}</p>
      </div>
    </section>
  );
}
