"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { FilePlus2, Camera, Link2, Sheet } from "lucide-react";
import { useI18n } from "@/i18n";
import {
  api,
  json,
  list,
  useApi,
  usePagedApi,
  type Collection,
  type Job,
  type Material,
} from "@/lib/api";
import { friendlyErrorKey } from "@/lib/errors";
import { useApp } from "../AppState";
import {
  Card,
  PageTitle,
  CollectionPicker,
  Status,
  StorageBadge,
  Empty,
} from "../Shared";
type Receipt = {
  material_id: string;
  revision_id: string;
  job_id: string;
  status: string;
  storage_state: string;
  drive_file_id?: string | null;
};
type UploadLimits={max_upload_bytes:number};
const TERMINAL_JOBS = ["succeeded", "failed", "needs_attention", "needs-attention", "cancelled"];
export default function UploadScreen({
  initialCollection = "",
}: {
  initialCollection?: string;
}) {
  const { t } = useI18n(),
    { reload } = useApp(),
    [collectionId, setCollection] = useState(initialCollection),
    [tab, setTab] = useState("file"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [notice, setNotice] = useState(false),
    [receipts, setReceipts] = useState<Receipt[]>([]),
    [droppedFile, setDroppedFile] = useState<File | null>(null),
    [dragActive, setDragActive] = useState(false),
    [jobStatuses, setJobStatuses] = useState<Record<string, string>>({}),
    collections = usePagedApi<Collection>("/collections"),
    limits = useApi<UploadLimits>("/ingestion/limits"),
    materials = usePagedApi<Material>(
      collectionId ? `/collections/${collectionId}/materials` : null,
    ),
    intakeKey = useRef<string | null>(null),
    fileInput = useRef<HTMLInputElement | null>(null);
  const selected = list(collections.data).find((c) => c.id === collectionId);
  const uploadLimit=limits.data?.max_upload_bytes??null;
  const uploadMiB=uploadLimit===null?null:uploadLimit/(1024*1024);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!collectionId) return;
    setBusy(true);
    setError(null);
    setNotice(false);
    const form = e.currentTarget;
    try {
      const payload = new FormData(form);
      const key =
        intakeKey.current ?? (intakeKey.current = crypto.randomUUID());
      let receipt: Receipt;
      if (tab === "link")
        receipt = await api(`/collections/${collectionId}/link`, {
          method: "POST",
          body: json({
            url: payload.get("url"),
            idempotency_key: key,
            source_language: payload.get("source_language"),
          }),
        });
      else {
        const file = droppedFile ?? (payload.get("file") as File | null);
        if (!file?.size) throw new Error(t("upload.selectFile"));
        if (uploadLimit===null) throw new Error(t("common.loading"));
        if (file.size > uploadLimit) throw new Error(t("upload.acceptedLimit",{uploadMiB:uploadLimit/(1024*1024)}));
        const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
        if (["md", "markdown", "txt", "rst", "csv", "tsv", "json", "yml", "yaml", "log"].includes(extension)
          && file.size > 2 * 1024 * 1024) throw new Error(t("upload.limits",{uploadMiB:uploadLimit/(1024*1024)}));
        const uploadForm = new FormData();
        uploadForm.set("file", file);
        uploadForm.set("idempotency_key", key);
        uploadForm.set("source_language", String(payload.get("source_language") ?? "und"));
        receipt = await api(`/collections/${collectionId}/materials`, {
          method: "POST",
          body: uploadForm,
        });
      }
      setReceipts((r) => [receipt, ...r]);
      intakeKey.current = null;
      setNotice(true);
      form.reset();
      setDroppedFile(null);
      setDragActive(false);
      materials.reload();
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const refreshMaterials = materials.reload;
  const onJobStatus = useCallback((jobId: string, status: string) => {
    setJobStatuses((previous) => previous[jobId] === status
      ? previous
      : { ...previous, [jobId]: status });
    if (TERMINAL_JOBS.includes(status)) {
      refreshMaterials();
      reload();
    }
  }, [refreshMaterials, reload]);
  const pendingReceipts = receipts.some(
    (receipt) => !TERMINAL_JOBS.includes(jobStatuses[receipt.job_id] ?? receipt.status),
  );
  useEffect(() => {
    if (!pendingReceipts) return;
    const poll = setInterval(() => {
      refreshMaterials();
      reload();
    }, 2500);
    return () => clearInterval(poll);
  }, [pendingReceipts, refreshMaterials, reload]);
  return (
    <>
      <PageTitle
        title={t("upload.title")}
        description={t("upload.description")}
      />
      <Card>
        <CollectionPicker
          hasMore={collections.hasMore}
          onLoadMore={collections.loadMore}
          moreLoading={collections.moreLoading}
          items={list(collections.data)}
          value={collectionId}
          onChange={(id) => {
                setCollection(id);
                intakeKey.current = null;
                setDroppedFile(null);
                setDragActive(false);
            setReceipts([]);
            setNotice(false);
          }}
        />
        <Status
          error={collections.error}
          loading={collections.loading}
          retry={collections.reload}
        />
        {selected && (
          <div className="destination-note mb-3 p-3 rounded-3 bg-body-tertiary">
            <strong className="small">
              {t("upload.destination")}: <bdi>{selected.name}</bdi>
            </strong>{" "}
            <StorageBadge
              state={
                selected.storage_mode === "drive" &&
                selected.provisioning_state === "ready"
                  ? "drive_ready"
                  : selected.storage_mode === "drive"
                    ? selected.provisioning_state
                    : "local"
              }
            />
            <p className="small text-body-secondary mb-0 mt-2">
              {t(
                selected.storage_mode === "drive"
                  ? "upload.driveWarning"
                  : "upload.localWarning",
              )}
            </p>
            {selected.storage_mode === "drive" && (
              <p className="small mb-0">
                <bdi>
                  {selected.drive_folder_id ?? t("common.provisioning")}
                </bdi>
              </p>
            )}
          </div>
        )}
        <div className="nav nav-pills gap-2 mb-4" role="tablist">
          {[
            { id: "file", key: "upload.file", icon: FilePlus2 },
            { id: "photo", key: "upload.photo", icon: Camera },
            { id: "spreadsheet", key: "upload.spreadsheet", icon: Sheet },
            { id: "link", key: "upload.link", icon: Link2 },
          ].map(({ id, key, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`nav-link d-flex align-items-center gap-2${tab === id ? " active" : ""}`}
              role="tab"
              aria-selected={tab === id}
              aria-controls="upload-panel"
              onClick={() => {
                setTab(id);
                setError(null);
                setDroppedFile(null);
                setDragActive(false);
              }}
            >
              <Icon size={18} />
              {t(key)}
            </button>
          ))}
        </div>
        <form key={tab} id="upload-panel" role="tabpanel" onSubmit={submit}>
          {tab === "link" ? (
            <label className="d-block mb-3">
              <span className="form-label fw-semibold">{t("upload.url")}</span>
              <input
                type="url"
                name="url"
                onChange={() => {
                  intakeKey.current = null;
                }}
                required
                className="form-control"
                placeholder="https://"
                dir="ltr"
                maxLength={4096}
              />
              <small className="text-body-secondary d-block mt-2">
                {t("upload.linkHelp")}
              </small>
            </label>
          ) : (
            <label
              className={`upload-dropzone d-block mb-3${dragActive ? " drag-active" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node | null))
                  setDragActive(false);
              }}
              onDrop={(event) => {
                event.preventDefault();
                setDragActive(false);
                const file = event.dataTransfer.files[0];
                if (file) {
                  setDroppedFile(file);
                  intakeKey.current = null;
                  setError(null);
                }
              }}
            >
              <span className="d-block fw-semibold mb-3">
                {t(dragActive ? "upload.dropHere" : tab === "photo" ? "upload.capture" : "upload.selectFile")}
              </span>
              <input
                ref={fileInput}
                name="file"
                type="file"
                required={!droppedFile}
                onChange={(event) => {
                  intakeKey.current = null;
                  setDroppedFile(event.currentTarget.files?.[0] ?? null);
                }}
                className="form-control"
                accept={
                  tab === "photo"
                    ? "image/jpeg,image/png"
                    : tab === "spreadsheet"
                      ? ".csv,.tsv,.xlsx,.xlsm"
                      : ".pdf,.md,.markdown,.txt,.docx,.rst,.csv,.tsv,.xlsx,.xlsm,.json,.yml,.yaml,.log,.jpg,.jpeg,.png"
                }
                {...(tab === "photo"
                  ? { capture: "environment" as const }
                  : {})}
              />
                <small className="d-block text-body-secondary mt-3">
                 {tab === "photo"?t("upload.photoHelp"):uploadMiB===null?t("common.loading"):t("upload.acceptedLimit",{uploadMiB})}
              </small>
              {droppedFile && (
                <span role="status" className="d-block small fw-semibold mt-2">
                  <bdi>{droppedFile.name}</bdi>
                </span>
              )}
              {tab !== "photo" && (
                <div className="upload-format-chips d-flex flex-wrap justify-content-center gap-2 mt-3" aria-label={t("upload.accepted")}>
                  {(tab === "spreadsheet"
                    ? ["CSV", "TSV", "XLSX", "XLSM"]
                    : ["PDF", "MD", "TXT", "DOCX", "RST", "CSV", "TSV", "XLSX", "JSON", "YAML", "LOG"]
                  ).map((format) => <span className="badge rounded-pill" key={format}>{format}</span>)}
                </div>
              )}
            </label>
          )}
          <SourceLanguageSelect
            onChange={() => {
              intakeKey.current = null;
            }}
          />
          <p className="small text-body-secondary">
            {t("upload.sourceLanguageHelp")}
          </p>
          <Status error={error??limits.error} loading={uploadMiB===null&&!limits.error}/>
          {uploadMiB!==null&&<p className="small text-body-secondary mt-3 mb-0" role="note">{t("upload.limits",{uploadMiB})}</p>}
          {notice && (
            <div role="status" className="alert alert-success">
              {t("upload.success")}
            </div>
          )}
          <button
            className="btn btn-primary d-inline-flex align-items-center gap-2"
            disabled={busy || !collectionId || (tab!=="link"&&uploadLimit===null)}
          >
            <FilePlus2 size={18} />
            {t(busy ? "common.working" : "upload.submit")}
          </button>
        </form>
      </Card>
      <Card className="mt-4">
        <h2 className="h5 fw-bold mb-3">{t("upload.jobs")}</h2>
        {receipts.map((r) => (
          <JobRow key={r.job_id} receipt={r} onStatus={onJobStatus} />
        ))}
        <Status
          error={materials.error}
          loading={Boolean(collectionId) && materials.loading}
          retry={materials.reload}
        />
        {list(materials.data).map((m) => (
          <MaterialRow key={m.id} material={m} collectionId={collectionId} onChanged={materials.reload} />
        ))}
        {materials.hasMore && (
          <button
            className="btn btn-light border btn-sm mt-3"
            disabled={materials.moreLoading}
            onClick={materials.loadMore}
          >
            {t(materials.moreLoading ? "common.loading" : "common.continue")}
          </button>
        )}
        {!receipts.length && !list(materials.data).length && (
          <Empty>{t("upload.noJobs")}</Empty>
        )}
      </Card>
    </>
  );
}

function MaterialRow({material,collectionId,onChanged}:{material:Material;collectionId:string;onChanged:()=>void}) {
  const {t}=useI18n();
  const [confirmOpen,setConfirmOpen]=useState(false);
  const [confirmation,setConfirmation]=useState("");
  const [localDeletionJobId,setDeletionJobId]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const deleteButton=useRef<HTMLButtonElement|null>(null);
  const dialog=useRef<HTMLDivElement|null>(null);
  const deletionJobId=localDeletionJobId||material.deletion_job_id||"";
  const job=useApi<Job>(deletionJobId?`/jobs/${deletionJobId}`:null);
  const deletionActive=Boolean(job.data&&!TERMINAL_JOBS.includes(job.data.status));

  useEffect(()=>{
    if (!deletionJobId || (job.data&&TERMINAL_JOBS.includes(job.data.status))) return;
    const timer=setInterval(job.reload,1500);
    return ()=>clearInterval(timer);
  },[deletionJobId,job.data,job.reload]);
  useEffect(()=>{
    if (job.data?.status&&TERMINAL_JOBS.includes(job.data.status)) onChanged();
  },[job.data?.status,onChanged]);
  useEffect(()=>{
    if(!confirmOpen)return;
    const previous=document.activeElement as HTMLElement|null;
    const deleteTarget=deleteButton.current;
    const close=(event:KeyboardEvent)=>{if(event.key==="Escape")setConfirmOpen(false);};
    window.addEventListener("keydown",close);
    return ()=>{window.removeEventListener("keydown",close);(previous?.isConnected?previous:deleteTarget)?.focus();};
  },[confirmOpen]);

  async function removeMaterial(){
    setBusy(true);setError(null);
    try{
      const result=await api<Job>(`/collections/${collectionId}/materials/${material.id}`,{
        method:"DELETE",body:json({expected_version:material.version,confirmation:"DELETE"}),
      });
      setDeletionJobId(result.id);
      setConfirmOpen(false);setConfirmation("");onChanged();
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }

  async function retryDeletion(){
    if(!deletionJobId)return;
    setError(null);
    try{await api(`/jobs/${deletionJobId}/retry`,{method:"POST"});job.reload();}
    catch(e){setError((e as Error).message);}
  }

  return <>
    <div className="event-row py-3 d-flex align-items-center flex-wrap gap-2">
      <span className="fw-medium flex-grow-1"><bdi>{material.title}</bdi></span>
      <StorageBadge state={material.storage_state??"local"}/>
      <StorageBadge state={deletionActive?"deleting":job.data?.status??material.status}/>
      {material.current_revision_id&&<MaterialLanguage key={`${material.id}:${material.source_language}`} material={material} onSaved={onChanged}/>}
      {!deletionJobId&&<button ref={deleteButton} type="button" className="btn btn-outline-danger btn-sm" onClick={()=>setConfirmOpen(true)}>{t("common.delete")}</button>}
      {deletionJobId&&(!job.data||!TERMINAL_JOBS.includes(job.data.status))&&<span className="small text-body-secondary" role="status">{t("common.working")}</span>}
      {job.data&&["failed","needs_attention","needs-attention"].includes(job.data.status)&&<button type="button" className="btn btn-outline-primary btn-sm" onClick={retryDeletion}>{t("upload.retry")}</button>}
      {(error||job.error||job.data?.error_code)&&<p className="small text-danger mb-0 w-100" role="alert"><bdi>{error??job.error??t(friendlyErrorKey(job.data?.error_code??""))}</bdi></p>}
    </div>
    {material.source_type==="pdf"&&["processing","needs-attention","needs_attention"].includes(material.status)&&<PdfReviewPanel material={material} onChanged={onChanged}/>}
    {confirmOpen&&<>
      <div className="modal-backdrop show" style={{zIndex:1050}}/>
      <div ref={dialog} className="modal d-block" role="dialog" aria-modal="true" aria-labelledby={`delete-title-${material.id}`} onKeyDown={(event)=>{
        if(event.key!=="Tab")return;
        const focusable=dialog.current?.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled])');
        if(!focusable?.length)return;
        const first=focusable[0],last=focusable[focusable.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
      }}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header"><h2 id={`delete-title-${material.id}`} className="modal-title h5">{t("common.delete")} — <bdi>{material.title}</bdi></h2></div>
            <div className="modal-body">
              <p>{t("upload.deleteWarning")}</p>
              <label className="form-label" htmlFor={`delete-confirm-${material.id}`}>{t("upload.deletePrompt")}</label>
              <input id={`delete-confirm-${material.id}`} className="form-control" value={confirmation} onChange={(event)=>setConfirmation(event.target.value)} autoComplete="off" autoFocus/>
              <Status error={error}/>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-light border" disabled={busy} onClick={()=>{setConfirmOpen(false);setConfirmation("");setError(null);}}>{t("common.cancel")}</button>
              <button type="button" className="btn btn-danger" disabled={busy||confirmation!=="DELETE"} onClick={removeMaterial}>{t(busy?"common.working":"common.delete")}</button>
            </div>
          </div>
        </div>
      </div>
    </>}
  </>;
}

type PdfPage={page_number:number;status:string;method:string|null;warning:string|null;text:string;text_truncated?:boolean;chapter_path:string[]};
type PdfPageManifest={version:number;status:string;warning:string|null;page_count:number;processed_pages:number;review_required_count:number;original_url:string;items:PdfPage[];total:number;next_cursor:number|null};

function PdfReviewPanel({material,onChanged}:{material:Material;onChanged:()=>void}){
  const {t}=useI18n();
  const [cursor,setCursor]=useState(0);
  const [saving,setSaving]=useState<number|null>(null);
  const [error,setError]=useState<string|null>(null);
  const textareas=useRef<Record<number,HTMLTextAreaElement|null>>({});
  const query=useApi<PdfPageManifest>(`/materials/${material.id}/ingestion-pages?cursor=${cursor}&limit=40`);
  const manifest=query.data;
  const manifestStatus=manifest?.status;
  useEffect(()=>{
    if(!manifestStatus||!["processing","finalizing"].includes(manifestStatus))return;
    const timer=setInterval(query.reload,2500);
    return ()=>clearInterval(timer);
  },[manifestStatus,query.reload]);

  async function save(page:PdfPage){
    setSaving(page.page_number);setError(null);
    try{
      await api(`/materials/${material.id}/ingestion-pages/${page.page_number}`,{
        method:"PATCH",body:json({expected_version:query.data?.version,text:textareas.current[page.page_number]?.value??page.text}),
      });
      query.reload();onChanged();
    }catch(e){setError((e as Error).message);}
    finally{setSaving(null);}
  }

  if(!manifest&&!query.loading&&!query.error)return null;
  return <div className="border rounded-3 p-3 mb-3 bg-body-tertiary">
    <div className="d-flex gap-2 flex-wrap align-items-center justify-content-between">
      <strong>{t("upload.reviewPages")}</strong>
      {manifest&&<span className="small text-body-secondary">{t("upload.pdfProgress",{processed:manifest.processed_pages,total:manifest.page_count,review:manifest.review_required_count})}</span>}
    </div>
    <Status error={query.error??error} loading={query.loading&&!manifest} retry={query.reload}/>
    {manifest&&manifest.review_required_count===0&&["processing","finalizing"].includes(manifest.status)&&<p className="small text-body-secondary mt-2 mb-0">{t("upload.pdfDone")}</p>}
    {manifest?.status==="needs-review"&&manifest.review_required_count===0&&<p className="alert alert-warning small mt-3 mb-0">{t(friendlyErrorKey(manifest.warning??"pdf_processing_failed"))}</p>}
    {manifest?.items.filter(page=>["needs-review","failed"].includes(page.status)).map((page,index)=><details className="mt-3 border rounded-3 p-3 bg-white" key={page.page_number} open={index===0}>
      <summary className="fw-semibold">{t("upload.pageLabel")} {page.page_number} · {page.warning??t("common.attention")}</summary>
      <p className="small text-body-secondary mt-2">{t("upload.reviewHelp")}{page.chapter_path.length?` · ${page.chapter_path.join(" / ")}`:""}</p>
      <iframe className="w-100 border rounded-2 mb-3" style={{height:480}} title={`${t("upload.pageLabel")} ${page.page_number}`} src={`${manifest.original_url}#page=${page.page_number}`}/>
      {page.text_truncated&&<p className="small text-warning-emphasis">{t("upload.truncatedText")}</p>}
      <label className="form-label" htmlFor={`pdf-page-text-${material.id}-${page.page_number}`}>{t("upload.pageLabel")} {page.page_number}</label>
      <textarea ref={node=>{textareas.current[page.page_number]=node;}} id={`pdf-page-text-${material.id}-${page.page_number}`} className="form-control" rows={8} maxLength={2*1024*1024} defaultValue={page.text}/>
      <button type="button" className="btn btn-primary btn-sm mt-3" disabled={saving===page.page_number} onClick={()=>save(page)}>{t(saving===page.page_number?"common.working":"common.save")}</button>
    </details>)}
    {(cursor>0||manifest?.next_cursor!==null)&&manifest&&<div className="d-flex justify-content-between mt-3">
      <button type="button" className="btn btn-light border btn-sm" disabled={cursor===0} onClick={()=>setCursor(Math.max(0,cursor-40))}>{t("common.back")}</button>
      <button type="button" className="btn btn-light border btn-sm" disabled={manifest.next_cursor===null} onClick={()=>setCursor(manifest.next_cursor??cursor)}>{t("common.continue")}</button>
    </div>}
  </div>;
}
function JobRow({ receipt: r, onStatus }: {
  receipt: Receipt;
  onStatus: (jobId: string, status: string) => void;
}) {
  const { t } = useI18n(),
    query = useApi<Job>(`/jobs/${r.job_id}`),
    [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (
      query.data &&
      TERMINAL_JOBS.includes(
        query.data.status,
      )
    )
      return;
    const interval = setInterval(query.reload, 1200);
    return () => clearInterval(interval);
  }, [query.data, query.reload]);
  useEffect(() => {
    if (query.data?.status) onStatus(r.job_id, query.data.status);
  }, [query.data?.status, r.job_id, onStatus]);
  const storageState = typeof query.data?.result?.storage_state === "string"
    ? query.data.result.storage_state
    : r.storage_state;
  return (
    <div className="event-row py-3">
      <div className="d-flex gap-2 align-items-center flex-wrap">
        <span className="small fw-semibold flex-grow-1">
          <bdi>{r.material_id}</bdi>
        </span>
        <StorageBadge state={storageState} />
        <StorageBadge state={query.data?.status ?? r.status} />
      </div>
      {r.drive_file_id && (
        <p className="small text-body-secondary mt-2 mb-0">
          {t("upload.driveReceipt")}: <bdi>{r.drive_file_id}</bdi>
        </p>
      )}
      {(query.data?.error || query.data?.error_code) && (
        <p className="small text-danger mt-2 mb-0" role="alert">
          <bdi>
            {t(
              friendlyErrorKey(query.data.error ?? query.data.error_code ?? ""),
            )}
          </bdi>
        </p>
      )}
      {query.data && ["failed", "needs_attention", "needs-attention"].includes(query.data.status) && (
        <button
          className="btn btn-outline-primary btn-sm mt-2"
          onClick={async () => {
            try {
              await api(`/jobs/${r.job_id}/retry`, { method: "POST" });
              query.reload();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          {t("upload.retry")}
        </button>
      )}
      <Status error={error ?? query.error} />
    </div>
  );
}

function SourceLanguageSelect({
  value = "und",
  onChange,
}: {
  value?: string;
  onChange?: () => void;
}) {
  const { t, languages } = useI18n();
  return (
    <label className="d-block mb-3">
      <span className="form-label fw-semibold">
        {t("upload.sourceLanguage")}
      </span>
      <select
        className="form-select"
        name="source_language"
        defaultValue={value}
        onChange={onChange}
      >
        <option value="und">{t("upload.unknownLanguage")}</option>
        {value !== "und" &&
          !languages.some((language) => language.locale === value) && (
            <option value={value}>{value}</option>
          )}
        {languages.map((language) => (
          <option key={language.locale} value={language.locale}>
            {language.native}
          </option>
        ))}
      </select>
    </label>
  );
}

function MaterialLanguage({
  material,
  onSaved,
}: {
  material: Material;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source_language = new FormData(event.currentTarget).get(
      "source_language",
    );
    setBusy(true);
    setError(null);
    try {
      await api(`/materials/${material.id}/source-language`, {
        method: "PATCH",
        body: json({ source_language }),
      });
      onSaved();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} className="w-100 mt-2">
      <SourceLanguageSelect value={material.source_language} />
      <button className="btn btn-outline-primary btn-sm" disabled={busy}>
        {t(busy ? "common.working" : "common.save")}
      </button>
      <Status error={error} />
    </form>
  );
}
