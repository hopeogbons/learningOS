"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp, ArrowDown, GripVertical, ListChecks } from "lucide-react";
import { useI18n } from "@/i18n";
import {
  api,
  json,
  list,
  useApi,
  usePagedApi,
  type Collection,
  type Outline,
  type Material,
  type Scope,
  type Chunk,
} from "@/lib/api";
import { useApp } from "../AppState";
import { Card, PageTitle, Status, CollectionPicker, Empty } from "../Shared";
export default function OutlineScreen({
  initialCollection = "",
}: {
  initialCollection?: string;
}) {
  const [collectionId, setCollection] = useState(initialCollection),
    collections = usePagedApi<Collection>("/collections");
  const { t } = useI18n();
  return (
    <>
      {" "}
      <OutlineContent
        key={collectionId}
        collectionId={collectionId}
        items={list(collections.data)}
        select={setCollection}
      />
      {collections.hasMore && (
        <button
          className="btn btn-light border btn-sm mt-3"
          disabled={collections.moreLoading}
          onClick={collections.loadMore}
        >
          {t(collections.moreLoading ? "common.loading" : "common.continue")}
        </button>
      )}
    </>
  );
}
function OutlineContent({
  collectionId,
  items,
  select,
}: {
  collectionId: string;
  items: Collection[];
  select: (id: string) => void;
}) {
  const { t } = useI18n(),
    router = useRouter(),
    { reload } = useApp(),
    query = useApi<Outline>(
      collectionId ? `/collections/${collectionId}/outline` : null,
    ),
    [selected, setSelected] = useState<string[] | null>(null),
    [ordered, setOrdered] = useState<Material[] | null>(null),
    [error, setError] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [drag, setDrag] = useState<{
      material: string;
      chunk: string | null;
    } | null>(null);
  const materials = ordered ?? query.data?.materials ?? [],
    selection = selected ?? query.data?.active_scope?.chunk_ids ?? [],
    choose = (id: string) =>
      setSelected(
        selection.includes(id)
          ? selection.filter((x) => x !== id)
          : [...selection, id],
      );
  function move(materialId: string, chunkId: string | null, delta: number) {
    const next = materials.map((m) => ({
      ...m,
      chunks: m.chunks?.map((c) => ({ ...c })),
    }));
    if (chunkId) {
      const material = next.find((m) => m.id === materialId);
      const a = material?.chunks ?? [];
      const i = a.findIndex((c) => c.id === chunkId),
        j = i + delta;
      if (j >= 0 && j < a.length) [a[i], a[j]] = [a[j], a[i]];
    } else {
      const i = next.findIndex((m) => m.id === materialId),
        j = i + delta;
      if (j >= 0 && j < next.length) [next[i], next[j]] = [next[j], next[i]];
    }
    setOrdered(next);
  }
  async function persistOrder(): Promise<Outline> {
    if (!query.data) throw new Error(t("common.error"));
    if (!ordered) return query.data;
    for (const material of ordered) {
      const original = query.data.materials.find(
        (item) => item.id === material.id,
      );
      const ids = (material.chunks ?? []).map((chunk) => chunk.id);
      if (
        ids.join() !== (original?.chunks ?? []).map((chunk) => chunk.id).join()
      ) {
        await api(
          `/collections/${collectionId}/materials/${material.id}/chunks/reorder`,
          {
            method: "PATCH",
            body: json({
              ordered_ids: ids,
              expected_version: material.version,
            }),
          },
        );
      }
    }
    const ids = ordered.map((material) => material.id);
    if (
      ids.join() !== query.data.materials.map((material) => material.id).join()
    ) {
      await api(`/collections/${collectionId}/materials/reorder`, {
        method: "PATCH",
        body: json({ ordered_ids: ids, expected_version: query.data.version }),
      });
    }
    const fresh = await api<Outline>(`/collections/${collectionId}/outline`);
    query.setData(fresh);
    setOrdered(null);
    reload();
    return fresh;
  }
  async function saveOrder() {
    setBusy(true);
    setError(null);
    try {
      await persistOrder();
    } catch (error) {
      // A partial write is visible on refresh; never continue to create a scope.
      setError((error as Error).message);
      setOrdered(null);
      query.reload();
    } finally {
      setBusy(false);
    }
  }
  async function go() {
    if (!selection.length) return;
    setBusy(true);
    setError(null);
    try {
      const current = await persistOrder();
      const orderedSelection = current.materials
        .flatMap((material) => material.chunks ?? [])
        .filter((chunk) => selection.includes(chunk.id))
        .map((chunk) => chunk.id);
      const result = await api<{ scope_revision: Scope }>(
        `/collections/${collectionId}/scope`,
        {
          method: "POST",
          body: json({
            chunk_ids: orderedSelection,
            expected_version: current.version,
          }),
        },
      );
      const scope = result.scope_revision;
      reload();
      router.push(`/study?collection=${collectionId}&scope=${scope.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function drop(material: Material, chunk: Chunk | null) {
    if (!drag) return;
    if (drag.chunk && chunk && drag.material === material.id) {
      const from = (
          materials.find((m) => m.id === material.id)?.chunks ?? []
        ).findIndex((c) => c.id === drag.chunk),
        to = (material.chunks ?? []).findIndex((c) => c.id === chunk.id);
      move(material.id, drag.chunk, to - from);
    } else if (!drag.chunk && !chunk) {
      const from = materials.findIndex((m) => m.id === drag.material),
        to = materials.findIndex((m) => m.id === material.id);
      move(drag.material, null, to - from);
    }
    setDrag(null);
  }
  return (
    <>
      <PageTitle
        title={t("outline.title")}
        description={t("outline.description")}
      />
      <Card className="mb-3">
        <CollectionPicker
          items={items}
          value={collectionId}
          onChange={select}
        />
        {query.data?.active_scope && (
          <p className="small text-body-secondary mb-0">
            {t("outline.revision", {
              revision: query.data.active_scope.revision_number,
            })}{" "}
            ·{" "}
            {t("common.doneOf", {
              done: query.data.progress.completed_count,
              total: query.data.progress.total_in_scope,
            })}
          </p>
        )}
      </Card>
      <Status
        error={error ?? query.error}
        loading={Boolean(collectionId) && query.loading}
        retry={query.reload}
      />
      {!collectionId && <Empty>{t("outline.chooseFirst")}</Empty>}
      <div className="d-flex flex-column gap-3">
        {materials.map((m, mi) => (
          <Card key={m.id}>
            <div
              className="d-flex align-items-center gap-2 mb-3"
              draggable
              onDragStart={() => setDrag({ material: m.id, chunk: null })}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                drop(m, null);
              }}
            >
              <GripVertical size={18} aria-hidden />
              <h2 className="h6 fw-bold mb-0 flex-grow-1">
                <bdi>{m.title}</bdi>
              </h2>
              <button
                className="icon-btn icon-btn--light"
                aria-label={`${t("outline.up")}: ${m.title}`}
                onClick={() => move(m.id, null, -1)}
                disabled={mi === 0}
              >
                <ArrowUp size={16} />
              </button>
              <button
                className="icon-btn icon-btn--light"
                aria-label={`${t("outline.down")}: ${m.title}`}
                onClick={() => move(m.id, null, 1)}
                disabled={mi === materials.length - 1}
              >
                <ArrowDown size={16} />
              </button>
            </div>
            <ul className="list-unstyled m-0">
              {m.chunks?.map((c, ci) => (
                <li
                  key={c.id}
                  className="outline-row d-flex align-items-center gap-2"
                  draggable
                  onDragStart={(e) => {
                    e.stopPropagation();
                    setDrag({ material: m.id, chunk: c.id });
                  }}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    drop(m, c);
                  }}
                >
                  <GripVertical
                    className="text-body-secondary"
                    size={16}
                    aria-hidden
                  />
                  <label className="d-flex align-items-center gap-3 flex-grow-1 py-2">
                    <input
                      type="checkbox"
                      className="form-check-input m-0"
                      checked={selection.includes(c.id)}
                      onChange={() => choose(c.id)}
                    />
                    <span>
                      <bdi>{c.title}</bdi>
                      {"concept_count" in c &&
                        typeof c.concept_count === "number" && (
                          <small className="d-block text-body-secondary">
                            {t("outline.concepts", { count: c.concept_count })}
                          </small>
                        )}
                    </span>
                  </label>
                  <button
                    className="icon-btn icon-btn--light"
                    aria-label={`${t("outline.up")}: ${c.title}`}
                    onClick={() => move(m.id, c.id, -1)}
                    disabled={ci === 0}
                  >
                    <ArrowUp size={16} />
                  </button>
                  <button
                    className="icon-btn icon-btn--light"
                    aria-label={`${t("outline.down")}: ${c.title}`}
                    onClick={() => move(m.id, c.id, 1)}
                    disabled={ci === (m.chunks?.length ?? 0) - 1}
                  >
                    <ArrowDown size={16} />
                  </button>
                </li>
              ))}
            </ul>
            {!m.chunks?.length && (
              <p className="small text-body-secondary mb-0">
                {t("common.processing")}
              </p>
            )}
          </Card>
        ))}
      </div>
      {collectionId && !query.loading && !materials.length && (
        <Card>
          <Empty
            href={`/add-material?collection=${collectionId}`}
            label={t("nav.addMaterial")}
          >
            {t("outline.empty")}
          </Empty>
        </Card>
      )}
      {materials.length > 0 && (
        <div className="scope-toolbar card border-0 shadow-sm rounded-4 mt-3 p-3 d-flex flex-row align-items-center flex-wrap gap-3">
          <span className="fw-semibold flex-grow-1" aria-live="polite">
            {t("outline.selectedCount", { count: selection.length })}
          </span>
          {ordered && (
            <button
              className="btn btn-outline-primary"
              disabled={busy}
              onClick={saveOrder}
            >
              {t("outline.saveOrder")}
            </button>
          )}
          <button
            className="btn btn-primary d-inline-flex align-items-center gap-2"
            onClick={go}
            disabled={!selection.length || busy}
          >
            <ListChecks size={18} />
            {t(busy ? "common.working" : "outline.go")}
          </button>
        </div>
      )}
    </>
  );
}
