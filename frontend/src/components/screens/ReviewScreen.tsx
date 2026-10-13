"use client";
import { useState } from "react";
import { useI18n } from "@/i18n";
import { usePagedApi, list, type Collection } from "@/lib/api";
import { PageTitle } from "../Shared";
import DueForReview from "../DueForReview";
export default function ReviewScreen() {
  const { t } = useI18n(),
    [collection, setCollection] = useState(""),
    query = usePagedApi<Collection>("/collections");
  return (
    <>
      <PageTitle
        title={t("review.title")}
        description={t("review.description")}
      />
      <label className="d-block mb-4">
        <span className="visually-hidden">{t("outline.chooseCollection")}</span>
        <select
          className="form-select"
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
        >
          <option value="">{t("review.all")}</option>
          {list(query.data).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {query.hasMore && (
        <button
          className="btn btn-light border btn-sm mb-3"
          disabled={query.moreLoading}
          onClick={query.loadMore}
        >
          {t(query.moreLoading ? "common.loading" : "common.continue")}
        </button>
      )}
      <DueForReview full collectionId={collection} />
    </>
  );
}
