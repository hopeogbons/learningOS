"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BookOpenCheck, ArrowRight, Mic, Volume2, MessageSquare, Radio, Send } from "lucide-react";
import { useI18n } from "@/i18n";
import { api, json, list, useApi, usePagedApi, type Collection, type Session, type SessionItem, type Citation, type Reviewer } from "@/lib/api";
import { useApp } from "../AppState";
import { PageTitle, Status, Empty, CollectionPicker, CitationList } from "../Shared";
import VoiceControls, { type VoiceMessage } from "../VoiceControls";
import LiveVoiceControls, { type LiveMessage } from "../LiveVoiceControls";
type StudyMode = "text" | "note" | "live";
type ChatMessage = LiveMessage & { itemId?: string; feedback?: Reviewer; citations?: string[]; noteId?: VoiceMessage["id"] };
const PENDING_TURNS = ["pending", "generating", "reviewing", "pending_generation", "pending_review", "assessing", "finishing"];
const MODES = [["text", MessageSquare, "study.modeText"], ["note", Mic, "study.modeNote"], ["live", Radio, "study.modeLive"]] as const;
function entryMode(value: string, voice = false): StudyMode { return voice || value === "voice" ? "live" : ["voice-note", "note"].includes(value) ? "note" : "text"; }
function putMessage(messages: ChatMessage[], message: ChatMessage): ChatMessage[] {
  const index = messages.findIndex((entry) => entry.id === message.id);
  if (index >= 0) return messages.map((entry, i) => i === index ? { ...entry, ...message, text: message.text || entry.text } : entry);
  const previous = message.previousId ? messages.findIndex((entry) => entry.id === message.previousId) : -1;
  if (previous >= 0) return [...messages.slice(0, previous + 1), message, ...messages.slice(previous + 1)];
  return [...messages, message];
}
export default function StudyScreen({ initialCollection = "", initialScope = "", initialSession = "", review = "", voice = false, initialMode = "" }: {
  initialCollection?: string; initialScope?: string; initialSession?: string; review?: string; voice?: boolean; initialMode?: string;
}) {
  const { t, preferences } = useI18n(), { data: dashboard, reload } = useApp(), collections = usePagedApi<Collection>("/collections");
  const [collectionId, setCollection] = useState(initialCollection), [sessionId, setSessionId] = useState(initialSession);
  const [item, setItem] = useState<SessionItem | null>(null), [answer, setAnswer] = useState(""), [confidence, setConfidence] = useState<number | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [mode, setMode] = useState<StudyMode>(entryMode(initialMode, voice));
  const [messages, setMessages] = useState<ChatMessage[]>([]), [liveDraft, setLiveDraft] = useState(""), [transcribed, setTranscribed] = useState(false), [turns, setTurns] = useState(0);
  const modeRef = useRef(mode), lastItem = useRef<string | null>(null), turnRequest = useRef<AbortController | null>(null), currentItem = useRef<SessionItem | null>(null), sending = useRef(false);
  const workspace = useRef<HTMLElement | null>(null);
  const trail = useRef<HTMLDivElement | null>(null), followLatest = useRef(true), notePlayback = useRef<((id: VoiceMessage["id"]) => Promise<void>) | null>(null);
  const collection = list(collections.data).find((c) => c.id === collectionId), scope = initialScope || collection?.active_scope?.id;
  const syncMessages = useCallback((next: SessionItem, fresh = false) => {
    const selected = modeRef.current;
    if (selected === "live" && !next.feedback) { if (fresh) setMessages([]); return; }
    setMessages((oldMessages) => {
      let result = fresh ? [] : oldMessages;
      if (next.item_id && selected !== "live" && (!fresh || !next.feedback)) {
        const text = [!review ? next.teaching : "", next.question].filter(Boolean).join("\n\n");
        if (text) result = putMessage(result, { id: `${next.item_id}:teacher`, role: "teacher", text, itemId: next.item_id, citations: next.citation_ids, noteId: selected === "note" ? "lesson" : undefined });
      }
      if (next.item_id && next.feedback?.feedback) result = putMessage(result, { id: `${next.item_id}:feedback`, role: "teacher", text: String(next.feedback.feedback), itemId: next.item_id, feedback: next.feedback, citations: next.feedback.citation_ids, noteId: selected === "note" ? "feedback" : undefined });
      return result;
    });
  }, [review]);
  const selectMode = useCallback((next: StudyMode) => {
    if (next === modeRef.current) return;
    modeRef.current = next; setMode(next); setAnswer(""); setConfidence(null); setTranscribed(false); setLiveDraft(""); followLatest.current = true;
    if (currentItem.current) syncMessages(currentItem.current, true); else setMessages([]);
  }, [syncMessages]);
  useEffect(() => { const timer = setTimeout(() => selectMode(entryMode(initialMode, voice)), 0); return () => clearTimeout(timer); }, [initialMode, voice, selectMode]);
  const unavailableMessage = t("common.notAvailable");
  const fetchTurn = useCallback(async (replace = false) => {
    if (!sessionId) return;
    if (turnRequest.current) { if (!replace) return; turnRequest.current.abort(); }
    const request = new AbortController(); turnRequest.current = request;
    try {
      const next = await api<SessionItem>(`/sessions/${sessionId}/next`, { signal: request.signal });
      if (request.signal.aborted) return;
      if (lastItem.current !== next.item_id) { lastItem.current = next.item_id; setAnswer(""); setConfidence(null); setTranscribed(false); }
      currentItem.current = next; setItem(next); syncMessages(next);
      if (next.voice_turn_count !== undefined) setTurns(next.voice_turn_count);
      setError(["needs_attention", "needs-attention"].includes(next.status) ? unavailableMessage : null);
    } catch (e) { if (!request.signal.aborted) setError((e as Error).message); }
    finally { if (turnRequest.current === request) turnRequest.current = null; }
  }, [sessionId, syncMessages, unavailableMessage]);
  const pending = Boolean(sessionId) && !error && (!item || PENDING_TURNS.includes(item.status));
  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => void fetchTurn(), 0), interval = setInterval(() => void fetchTurn(), 1300);
    return () => { clearTimeout(timer); clearInterval(interval); turnRequest.current?.abort(); };
  }, [pending, fetchTurn]);
  useEffect(() => () => turnRequest.current?.abort(), [sessionId, fetchTurn]);
  useEffect(() => {
    if (!sessionId) return;
    const timer = setTimeout(() => {
      const node = workspace.current;
      if (node) window.scrollTo({ top: window.scrollY + node.getBoundingClientRect().top - 96, behavior: "auto" });
    }, 50);
    return () => clearTimeout(timer);
  }, [sessionId]);
  useEffect(() => { if (followLatest.current && trail.current) trail.current.scrollTop = trail.current.scrollHeight; }, [messages, pending]);
  async function start() {
    if (!collectionId || !scope) return;
    setBusy(true); setError(null);
    try {
      const s = await api<Session>("/sessions", { method: "POST", body: json({ collection_id: collectionId, scope_revision_id: scope, mode: review ? "review" : "study" }) });
      setSessionId(s.id); window.history.replaceState(null, "", `/study?session=${s.id}&mode=${mode === "live" ? "voice" : mode === "note" ? "voice-note" : "text"}`); reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function submitAnswer(text = answer, level = confidence, spoken = transcribed) {
    if (!item?.item_id || !text.trim() || level === null || sending.current || item.feedback) return;
    sending.current = true; setBusy(true); setError(null);
    const selected = modeRef.current;
    if (selected === "text") setMessages((entries) => putMessage(entries, { id: `${item.item_id}:answer`, role: "learner", text: text.trim(), itemId: item.item_id ?? undefined }));
    try {
      await api(`/sessions/${sessionId}/answer`, { method: "POST", body: json({ item_id: item.item_id, answer: text.trim(), confidence: level, expected_version: item.version, voice: selected !== "text" && spoken }) });
      if (selected !== "text" && spoken) setTurns((v) => v + 1);
      await fetchTurn(true); reload();
    } catch (e) { setError((e as Error).message); } finally { sending.current = false; setBusy(false); }
  }
  function receiveSpeech(text: string) {
    if (modeRef.current === "text" || !text.trim()) return;
    const match = text.match(/\bconfidence\s*(?:is\s*)?([1-5]|one|two|three|four|five)\b/i);
    const levels: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5 };
    const level = match ? levels[match[1].toLowerCase()] || Number(match[1]) : confidence;
    const spokenAnswer = match ? text.replace(match[0], "").trim().replace(/^[,.\s]+|[,.\s]+$/g, "") || answer : text;
    setAnswer(spokenAnswer); setTranscribed(true); if (match) setConfidence(level);
    if (modeRef.current === "note") setMessages((entries) => putMessage(entries, { id: crypto.randomUUID(), role: "learner", text: spokenAnswer, itemId: item?.item_id ?? undefined }));
    if (level !== null && (modeRef.current === "note" || match)) void submitAnswer(spokenAnswer, level, true);
  }
  function chooseConfidence(level: number) {
    setConfidence(level);
    if (mode !== "text" && transcribed && answer.trim()) void submitAnswer(answer, level, true);
  }
  async function action(kind: "advance" | "finish") {
    if (!item) return;
    setBusy(true); setError(null);
    try { await api(`/sessions/${sessionId}/${kind}`, { method: "POST", body: json({ expected_version: item.version }) }); await fetchTurn(true); reload(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function retryTurn() {
    if (item?.job_id && ["needs_attention", "needs-attention"].includes(item.status)) {
      setBusy(true); try { await api(`/jobs/${item.job_id}/retry`, { method: "POST" }); await fetchTurn(true); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
    } else await fetchTurn(true);
  }
  const finished = ["finished", "completed"].includes(item?.status ?? ""), blocked = ["needs_attention", "needs-attention"].includes(item?.status ?? ""), feedback = item?.feedback;
  const speechMessages = useMemo<VoiceMessage[]>(() => {
    const result: VoiceMessage[] = [];
    if (item && !feedback) result.push({ id: "lesson", label: t("study.teacher"), text: [!review ? item.teaching : "", item.question].filter(Boolean).join("\n\n") });
    if (feedback?.feedback) result.push({ id: "feedback", label: t("study.teacher"), text: String(feedback.feedback) });
    return result;
  }, [item, feedback, review, t]);
  function changeMode(next: StudyMode) {
    selectMode(next); const url = new URL(window.location.href); url.searchParams.set("mode", next === "live" ? "voice" : next === "note" ? "voice-note" : "text"); window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }
  function tabKey(event: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault(); const direction = document.documentElement.dir === "rtl" ? -1 : 1;
    const next = event.key === "Home" ? 0 : event.key === "End" ? 2 : (index + (event.key === "ArrowRight" ? direction : -direction) + 3) % 3;
    changeMode(MODES[next][0]); document.getElementById(`study-tab-${MODES[next][0]}`)?.focus();
  }
  return <>
    <PageTitle title={t("study.title")} description={t("study.conversationDescription")} />
    <Status error={error} retry={retryTurn} />
    <section ref={workspace} className="study-workspace">
      <div className="study-mode-tabs" role="tablist" aria-label={t("study.modeLabel")}>
        {MODES.map(([value, Icon, label], index) => <button type="button" role="tab" id={`study-tab-${value}`} aria-controls="study-mode-panel" aria-selected={mode === value} tabIndex={mode === value ? 0 : -1} onKeyDown={(event) => tabKey(event, index)} key={value} onClick={() => changeMode(value)}><Icon size={17} />{t(label)}</button>)}
      </div>
      <div id="study-mode-panel" role="tabpanel" aria-labelledby={`study-tab-${mode}`} className="study-mode-panel">
        {!sessionId && <div className="study-setup">
          {mode !== "text" && <p>{t(mode === "live" ? "study.liveIntro" : "study.noteIntro")}</p>}
          <CollectionPicker hasMore={collections.hasMore} onLoadMore={collections.loadMore} moreLoading={collections.moreLoading} items={list(collections.data)} value={collectionId} onChange={setCollection} />
          <Status error={collections.error} loading={collections.loading} retry={collections.reload} />
          <p className="small text-body-secondary">{t("study.studyLanguage")}: <bdi>{preferences.study_locale}</bdi></p>
          {!scope && <Empty href={collectionId ? `/collections/${collectionId}/outline` : "/outline"} label={t("nav.outline")}>{t("study.chooseScope")}</Empty>}
          <div className="d-flex flex-wrap gap-2"><button disabled={!scope || busy} onClick={start} className="btn btn-primary"><BookOpenCheck size={18} />{t(busy ? "common.working" : "study.start")}</button>{dashboard?.resume?.session_id && <button className="btn btn-outline-primary" onClick={() => setSessionId(dashboard.resume?.session_id ?? "")}>{t("study.resume")}</button>}</div>
        </div>}
        {sessionId && <>
          <div ref={trail} className="study-conversation" role="log" aria-live="polite" aria-relevant="additions text" aria-label={t("study.conversationLabel")} tabIndex={0} onScroll={() => { const node = trail.current; if (node) followLatest.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80; }}>
            {messages.map((message) => <div className={`study-message study-message--${message.role}`} key={message.id} data-message-id={message.id} data-speaker={message.role}>
              <span className="study-speaker">{t(message.role === "teacher" ? "study.teacher" : "study.you")}</span>
              {message.noteId ? <><div className="study-note"><Volume2 size={20} /><span>{t("study.modeNote")}</span>{message.itemId === item?.item_id && speechMessages.some((entry) => entry.id === message.noteId) && <button className="btn btn-outline-primary btn-sm" aria-label={`${t("study.listen")}: ${t("study.teacher")}`} onClick={() => void notePlayback.current?.(message.noteId!)}><Volume2 size={16} />{t("study.listen")}</button>}</div><details><summary>{t("study.transcript")}</summary><p dir="auto">{message.text}</p></details></> : message.feedback ? <Feedback value={message.feedback} /> : <p dir="auto">{message.text || "…"}</p>}
              {message.citations?.length ? <Citations ids={message.citations} /> : null}
            </div>)}
            {pending && <Status loading />}
            {mode === "live" && !messages.length && !pending && <p className="study-trail-empty">{t("study.liveReady")}</p>}
          </div>
          {item && !blocked && !finished && <div className="study-controls">
            {mode === "live" && <LiveVoiceControls key={`${sessionId}:${item.item_id}`} sessionId={sessionId} itemId={item.item_id ?? ""} onMessage={(message) => setMessages((entries) => putMessage(entries, message))} draft={liveDraft} onDraft={setLiveDraft} onTranscript={receiveSpeech} disabled={busy || pending} />}
            {mode === "note" && <VoiceControls key={`${sessionId}:${item.item_id}:${feedback ? "feedback" : "question"}`} sessionId={sessionId} itemId={item.item_id ?? ""} messages={speechMessages} canRecord={!feedback && !busy && !pending} autoSpeakMessageId={feedback ? "feedback" : "lesson"} turns={turns} onTranscript={receiveSpeech} onTyping={() => changeMode("text")} playbackRef={notePlayback} />}
            {feedback ? <div className="d-flex flex-wrap gap-2"><button className="btn btn-primary" onClick={() => action("advance")} disabled={busy}>{t(busy ? "common.working" : "study.next")}<ArrowRight size={18} /></button><button className="btn btn-outline-secondary" onClick={() => action("finish")} disabled={busy}>{t("study.finish")}</button></div> : <form onSubmit={(event) => { event.preventDefault(); void submitAnswer(); }} className="study-composer">
              {mode === "text" ? <label className="d-block mb-2"><span className="form-label fw-semibold">{t("study.answer")}</span><textarea aria-label={t("study.answer")} className="form-control" rows={2} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={t("study.answerPlaceholder")} required dir="auto" disabled={busy || pending} autoFocus /></label> : <><p className="small mb-2" role="status">{t(transcribed ? "study.spokenAnswerReady" : "study.voiceAnswerHelp")}</p><details className="study-transcript-edit"><summary>{t("study.transcript")}</summary><label><span className="form-label">{t("study.answer")}</span><textarea aria-label={t("study.answer")} className="form-control" rows={2} value={answer} onChange={(e) => setAnswer(e.target.value)} dir="auto" disabled={busy || pending} /></label></details></>}
              <div className="study-send-row"><fieldset className="confidence-fieldset"><legend className="form-label fw-semibold small">{t("study.confidence")}</legend><div className="confidence-options">{[1, 2, 3, 4, 5].map((n) => <label key={n} className={`confidence-option${confidence === n ? " selected" : ""}`}><input type="radio" name="confidence" value={n} checked={confidence === n} onChange={() => chooseConfidence(n)} disabled={busy || pending} /><span>{n}</span><small>{n === 1 ? t("study.lowConfidence") : n === 5 ? t("study.highConfidence") : ""}</small></label>)}</div></fieldset><button className="btn btn-primary" disabled={busy || pending || confidence === null || !answer.trim()}><Send size={17} />{t(busy ? "common.working" : "study.submit")}</button></div>
            </form>}
          </div>}
          {finished && <div className="study-controls"><h2 className="h4 fw-bold">{t("study.sessionFinished")}</h2><SessionSummary sessionId={sessionId} /><Link className="btn btn-primary mt-3" href="/progress">{t("nav.progress")}</Link></div>}
        </>}
      </div>
    </section>
  </>;
}
function Citations({ ids }: { ids: string[] }) {
  const { t } = useI18n();
  const [citations, setCitations] = useState<Citation[]>([]),
    [error, setError] = useState<string | null>(null);
  const key = ids.join(",");
  useEffect(() => {
    let active = true;
    Promise.all(
      key
        .split(",")
        .filter(Boolean)
        .map((id) => api<Citation>(`/citations/${id}`)),
    )
      .then((c) => {
        if (active) {
          setCitations(c);
          setError(null);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [key]);
  return (
    <>
      <Status error={error} />
      {citations.length > 0 && <details className="study-source-disclosure"><summary>{t("study.source")}</summary><CitationList citations={citations} /></details>}
    </>
  );
}
function Feedback({ value }: { value: Reviewer }) {
  const { t } = useI18n();
  return (
    <div className="reviewer-feedback" role="status">
      <p className="mb-2" dir="auto">
        {String(value.feedback ?? "")}
      </p>
      {value.rationale && (
        <p className="small text-body-secondary mb-2" dir="auto">
          {String(value.rationale)}
        </p>
      )}
      {value.missing_parts?.length ? (
        <ul>
          {value.missing_parts.map((s, i) => (
            <li key={i} dir="auto">
              {s}
            </li>
          ))}
        </ul>
      ) : null}
      {(value.title_completed || value.title_complete) && (
        <span className="badge text-bg-success">{t("outline.completed")}</span>
      )}
    </div>
  );
}
function SessionSummary({ sessionId }: { sessionId: string }) {
  const { t } = useI18n(),
    query = useApi<{
      completed_titles: { id: string; title: string }[];
      remaining_titles: { id: string; title: string }[];
      sample_count: number;
    }>(`/sessions/${sessionId}/summary`);
  return (
    <>
      <Status
        error={query.error}
        loading={query.loading}
        retry={query.reload}
      />
      {query.data && (
        <p>
          {t("common.doneOf", {
            done: query.data.completed_titles.length,
            total:
              query.data.completed_titles.length +
              query.data.remaining_titles.length,
          })}
        </p>
      )}
    </>
  );
}
