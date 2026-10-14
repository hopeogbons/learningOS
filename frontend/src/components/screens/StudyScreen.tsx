"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BookOpenCheck, ArrowRight, Mic, Volume2, MessageSquare, Radio, Send } from "lucide-react";
import { useI18n } from "@/i18n";
import {
  api,
  json,
  list,
  useApi,
  usePagedApi,
  type Collection,
  type Session,
  type SessionItem,
  type Citation,
  type Reviewer,
} from "@/lib/api";
import { useApp } from "../AppState";
import {
  Card,
  PageTitle,
  Status,
  Empty,
  CollectionPicker,
  CitationList,
} from "../Shared";
import VoiceControls, { type VoiceMessage } from "../VoiceControls";
import LiveVoiceControls, { type LiveMessage } from "../LiveVoiceControls";
type StudyMode = "text" | "note" | "live";
const PENDING_TURNS = [
  "pending", "generating", "reviewing", "pending_generation",
  "pending_review", "assessing", "finishing",
];
export default function StudyScreen({
  initialCollection = "",
  initialScope = "",
  initialSession = "",
  review = "",
  voice = false,
  initialMode = "",
}: {
  initialCollection?: string;
  initialScope?: string;
  initialSession?: string;
  review?: string;
  voice?: boolean;
  initialMode?: string;
}) {
  const { t, preferences } = useI18n(),
    { data: dashboard, reload } = useApp(),
    collections = usePagedApi<Collection>("/collections"),
    [collectionId, setCollection] = useState(initialCollection),
    [sessionId, setSessionId] = useState(initialSession),
    [item, setItem] = useState<SessionItem | null>(null),
    [answer, setAnswer] = useState(""),
    [confidence, setConfidence] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [mode, setMode] = useState<StudyMode>(voice || initialMode === "voice" ? "live" : ["voice-note", "note"].includes(initialMode) ? "note" : "text"),
    [history, setHistory] = useState<{ item: SessionItem; answer: string }[]>([]),
    [liveMessages, setLiveMessages] = useState<LiveMessage[]>([]),
    [liveDraft, setLiveDraft] = useState(""),
    [submittedAnswer, setSubmittedAnswer] = useState(""),
    [transcribed, setTranscribed] = useState(false),
    [turns, setTurns] = useState(0),
    lastItem = useRef<string | null>(null),
    turnRequest = useRef<AbortController | null>(null),
    currentItem = useRef<SessionItem | null>(null),
    submitted = useRef<Record<string, string>>({});
  const collection = list(collections.data).find((c) => c.id === collectionId),
    scope = initialScope || collection?.active_scope?.id;
  const unavailableMessage = t("common.notAvailable");
  useEffect(() => {
    const update = setTimeout(() => setMode(voice || initialMode === "voice" ? "live" : ["voice-note", "note"].includes(initialMode) ? "note" : "text"), 0);
    return () => clearTimeout(update);
  }, [initialMode, voice]);
  const fetchTurn = useCallback(async (replace = false) => {
    if (!sessionId) return;
    if (turnRequest.current) {
      if (!replace) return;
      turnRequest.current.abort();
    }
    const request = new AbortController();
    turnRequest.current = request;
    try {
      const next = await api<SessionItem>(`/sessions/${sessionId}/next`, { signal: request.signal });
      if (request.signal.aborted) return;
      if (lastItem.current !== next.item_id) {
        const previous = currentItem.current;
        if (previous?.item_id && previous.question) setHistory((entries) => entries.some((entry) => entry.item.item_id === previous.item_id) ? entries : [...entries, { item: previous, answer: submitted.current[previous.item_id!] || "" }]);
        lastItem.current = next.item_id;
        setSubmittedAnswer("");
        setAnswer("");
        setConfidence(null);
        setTranscribed(false);
      }
      currentItem.current = next;
      setItem(next);
      if (next.voice_turn_count !== undefined) setTurns(next.voice_turn_count);
      setError(
        next.status === "needs_attention" || next.status === "needs-attention"
          ? unavailableMessage
          : null,
      );
    } catch (e) {
      if (!request.signal.aborted) setError((e as Error).message);
    } finally {
      if (turnRequest.current === request) turnRequest.current = null;
    }
  }, [sessionId, unavailableMessage]);
  const pending = Boolean(sessionId) && !error && (!item || PENDING_TURNS.includes(item.status));
  useEffect(() => {
    if (!pending) return;
    const initial = setTimeout(() => void fetchTurn(), 0);
    const interval = setInterval(() => void fetchTurn(), 1300);
    return () => {
      clearTimeout(initial);
      clearInterval(interval);
      turnRequest.current?.abort();
    };
  }, [pending, fetchTurn]);
  useEffect(() => () => turnRequest.current?.abort(), [sessionId, fetchTurn]);
  async function start() {
    if (!collectionId || !scope) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api<Session>("/sessions", {
        method: "POST",
        body: json({
          collection_id: collectionId,
          scope_revision_id: scope,
          mode: review ? "review" : "study",
        }),
      });
      setSessionId(s.id);
      window.history.replaceState(
        null,
        "",
        `/study?session=${s.id}&mode=${mode === "live" ? "voice" : mode === "note" ? "voice-note" : "text"}`,
      );
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!item?.item_id || !answer.trim() || confidence === null) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/sessions/${sessionId}/answer`, {
        method: "POST",
        body: json({
          item_id: item.item_id,
          answer: answer.trim(),
          confidence,
          expected_version: item.version,
          voice: mode !== "text" && transcribed,
        }),
      });
      submitted.current[item.item_id] = answer.trim();
      setSubmittedAnswer(answer.trim());
      if (mode !== "text" && transcribed) setTurns((v) => v + 1);
      await fetchTurn(true);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function action(kind: "advance" | "finish") {
    if (!item) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/sessions/${sessionId}/${kind}`, {
        method: "POST",
        body: json({ expected_version: item.version }),
      });
      await fetchTurn(true);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const blocked =
    item?.status === "needs_attention" || item?.status === "needs-attention";
  async function retryTurn() {
    if (item?.job_id && blocked) {
      setBusy(true);
      try {
        await api(`/jobs/${item.job_id}/retry`, { method: "POST" });
        await fetchTurn(true);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    } else await fetchTurn(true);
  }
  const finished = item?.status === "finished" || item?.status === "completed";
  const feedback = item?.feedback;
  const speechMessages = useMemo<VoiceMessage[]>(() => {
    const messages: VoiceMessage[] = [];
    if (item?.teaching && !review)
      messages.push({ id: "teaching", label: t("study.teach"), text: item.teaching });
    if (item?.question)
      messages.push({ id: "question", label: t("study.check"), text: item.question });
    if (item?.feedback?.feedback)
      messages.push({ id: "feedback", label: t("study.teacher"), text: String(item.feedback.feedback) });
    return messages;
  }, [item, review, t]);
  const autoSpeakMessageId: VoiceMessage["id"] | null =
    mode !== "note" ? null : feedback?.voice === true ? "feedback" : feedback ? null : "question";
  function changeMode(next: StudyMode) {
    setMode(next);
    const url = new URL(window.location.href);
    url.searchParams.set("mode", next === "live" ? "voice" : next === "note" ? "voice-note" : "text");
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }
  function addLiveMessage(message: LiveMessage) {
    if (!message.text) return;
    setLiveMessages((messages) => {
      const index = messages.findIndex((entry) => entry.id === message.id && entry.role === message.role);
      if (index < 0) return [...messages, message];
      return messages.map((entry, i) => i === index ? message : entry);
    });
  }
  return (
    <>
      <PageTitle title={t("study.title")} description={t("study.conversationDescription")} />
      <div className="study-mode-tabs mb-3" role="group" aria-label={t("study.modeLabel")}>
        {([ ["text", MessageSquare, "study.modeText"], ["note", Mic, "study.modeNote"], ["live", Radio, "study.modeLive"] ] as const).map(([value, Icon, label]) => <button type="button" key={value} className={`btn ${mode === value ? "btn-primary" : "btn-outline-primary"}`} aria-pressed={mode === value} onClick={() => changeMode(value)}><Icon size={17} />{t(label)}</button>)}
      </div>
      <Status error={error} retry={retryTurn} />
      {!sessionId && <Card>
        {mode !== "text" && <div className="voice-conversation-intro rounded-3 p-3 mb-4" role="note"><div className="d-flex align-items-center gap-2 mb-2"><Volume2 size={18} /><h2 className="h6 fw-bold mb-0">{t(mode === "live" ? "study.modeLive" : "study.modeNote")}</h2></div><p className="small mb-2">{t(mode === "live" ? "study.liveIntro" : "study.noteIntro")}</p><p className="small text-body-secondary mb-0">{t("study.speechLanguage")}: <bdi>{preferences.speech_locale}</bdi></p></div>}
        <CollectionPicker hasMore={collections.hasMore} onLoadMore={collections.loadMore} moreLoading={collections.moreLoading} items={list(collections.data)} value={collectionId} onChange={setCollection} />
        <Status error={collections.error} loading={collections.loading} retry={collections.reload} />
        <p className="small text-body-secondary">{t("study.studyLanguage")}: <bdi>{preferences.study_locale}</bdi></p>
        {!scope && <Empty href={collectionId ? `/collections/${collectionId}/outline` : "/outline"} label={t("nav.outline")}>{t("study.chooseScope")}</Empty>}
        <div className="d-flex flex-wrap gap-2"><button disabled={!scope || busy} onClick={start} className="btn btn-primary"><BookOpenCheck size={18} />{t(busy ? "common.working" : "study.start")}</button>{dashboard?.resume?.session_id && <button className="btn btn-outline-primary" onClick={() => setSessionId(dashboard.resume?.session_id ?? "")}>{t("study.resume")}</button>}</div>
      </Card>}
      {sessionId && <Card>
        <div className="study-conversation" aria-label={t("study.conversationLabel")}>
          {history.map((entry) => <div key={entry.item.item_id} className="study-past-turn"><TeacherMessage item={entry.item} review={Boolean(review)} />{entry.answer && <div className="study-message study-message--learner"><span className="study-speaker">{t("study.you")}</span><p dir="auto">{entry.answer}</p></div>}{entry.item.feedback && <Feedback value={entry.item.feedback} />}<Citations ids={[...new Set([...(entry.item.citation_ids ?? []), ...(entry.item.feedback?.citation_ids ?? [])])]} /></div>)}
          {item && !blocked && !finished && <TeacherMessage item={item} review={Boolean(review)} />}
          {liveMessages.map((message) => <div className={`study-message study-message--${message.role}`} key={`${message.role}:${message.id}`}><span className="study-speaker">{t(message.role === "teacher" ? "study.teacher" : "study.you")}</span><p dir="auto">{message.text}</p></div>)}
          {pending && <Status loading />}
          {item && !pending && !blocked && !finished && <>
            {feedback && <>{(submittedAnswer || answer) && <div className="study-message study-message--learner"><span className="study-speaker">{t("study.you")}</span><p dir="auto">{submittedAnswer || answer}</p></div>}<Feedback value={feedback} /></>}
            <Citations ids={[...new Set([...(item.citation_ids ?? []), ...(feedback?.citation_ids ?? [])])]} />
          </>}
        </div>
        {item && !pending && !blocked && !finished && <>
          {mode === "live" && <LiveVoiceControls key={`${sessionId}:${item.item_id}`} sessionId={sessionId} itemId={item.item_id ?? ""} onMessage={addLiveMessage} draft={liveDraft} onDraft={setLiveDraft} onTranscript={(text) => { setAnswer(text); setTranscribed(true); }} disabled={busy} />}
          {mode === "note" && <VoiceControls key={`${sessionId}:${item.item_id}:${feedback ? "feedback" : "question"}`} sessionId={sessionId} itemId={item.item_id ?? ""} messages={speechMessages} canRecord={!feedback} autoSpeakMessageId={autoSpeakMessageId} turns={turns} onTranscript={(text) => { setAnswer(text); setTranscribed(true); }} onTyping={() => changeMode("text")} />}
          {feedback ? <div className="d-flex flex-wrap gap-2 mt-4"><button className="btn btn-primary" onClick={() => action("advance")} disabled={busy}>{t(busy ? "common.working" : "study.next")}<ArrowRight size={18} /></button><button className="btn btn-outline-secondary" onClick={() => action("finish")} disabled={busy}>{t("study.finish")}</button></div> : <form onSubmit={submit} className="study-composer">
            <label className="d-block mb-3"><span className="form-label fw-semibold">{t("study.answer")}</span><textarea aria-label={t("study.answer")} className="form-control" rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={t("study.answerPlaceholder")} required dir="auto" disabled={busy} autoFocus={mode === "text"} /></label>
            <fieldset className="confidence-fieldset"><legend className="form-label fw-semibold small">{t("study.confidence")}</legend><div className="confidence-options">{[1, 2, 3, 4, 5].map((n) => <label key={n} className={`confidence-option${confidence === n ? " selected" : ""}`}><input type="radio" name="confidence" value={n} checked={confidence === n} onChange={() => setConfidence(n)} required /><span>{n}</span><small>{n === 1 ? t("study.lowConfidence") : n === 5 ? t("study.highConfidence") : ""}</small></label>)}</div></fieldset>
            <button className="btn btn-primary mt-3" disabled={busy || confidence === null || !answer.trim()}><Send size={17} />{t(busy ? "common.working" : "study.submit")}</button>
          </form>}
        </>}
        {finished && <><h2 className="h4 fw-bold">{t("study.sessionFinished")}</h2><SessionSummary sessionId={sessionId} /><Link className="btn btn-primary mt-3" href="/progress">{t("nav.progress")}</Link></>}
      </Card>}
    </>
  );
}
function TeacherMessage({ item, review }: { item: SessionItem; review: boolean }) {
  const { t } = useI18n();
  return <div className="study-message study-message--teacher"><span className="study-speaker">{t("study.teacher")}</span>{item.teaching && !review && <p className="teach-paragraph" dir="auto">{item.teaching}</p>}{review && <p className="badge text-bg-light border py-2">{t("study.coldReview")}</p>}<p className="fw-medium question-text mb-0" dir="auto">{item.question}</p></div>;
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
    <div className="reviewer-feedback study-message study-message--teacher" role="status">
      <h3 className="study-speaker">{t("study.teacher")}</h3>
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
