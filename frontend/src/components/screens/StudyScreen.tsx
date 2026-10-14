"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BookOpenCheck, ArrowRight, Mic, Volume2 } from "lucide-react";
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
}: {
  initialCollection?: string;
  initialScope?: string;
  initialSession?: string;
  review?: string;
  voice?: boolean;
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
    [isVoice, setVoice] = useState(voice),
    [transcribed, setTranscribed] = useState(false),
    [turns, setTurns] = useState(0),
    lastItem = useRef<string | null>(null),
    turnRequest = useRef<AbortController | null>(null);
  const collection = list(collections.data).find((c) => c.id === collectionId),
    scope = initialScope || collection?.active_scope?.id;
  const unavailableMessage = t("common.notAvailable");
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
        lastItem.current = next.item_id;
        setAnswer("");
        setConfidence(null);
        setTranscribed(false);
      }
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
        `/study?session=${s.id}${isVoice ? "&mode=voice" : ""}`,
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
          voice: isVoice && transcribed,
        }),
      });
      if (isVoice && transcribed) setTurns((v) => v + 1);
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
      messages.push({ id: "feedback", label: t("study.feedback"), text: String(item.feedback.feedback) });
    return messages;
  }, [item, review, t]);
  const autoSpeakMessageId: VoiceMessage["id"] | null =
    !isVoice ? null : feedback?.voice === true ? "feedback" : feedback ? null : "question";
  return (
    <>
      <PageTitle
        title={t(isVoice ? "study.voice" : "study.title")}
        description={t(review ? "review.description" : "study.description")}
      />
      <Status error={error} retry={retryTurn} />
      {!sessionId && (
        <Card>
          {isVoice && (
            <div className="voice-conversation-intro rounded-3 p-3 mb-4" role="note">
              <div className="d-flex align-items-center gap-2 mb-2">
                <span className="voice-conversation-icon"><Volume2 size={18} /><Mic size={16} /></span>
                <h2 className="h6 fw-bold mb-0">{t("study.voice")}</h2>
              </div>
              <p className="small mb-2" dir="auto">{t("study.voiceDescription")}</p>
              <p className="small text-body-secondary mb-0">
                {t("study.studyLanguage")}: <bdi>{preferences.study_locale}</bdi>
                {" · "}{t("study.speechLanguage")}: <bdi>{preferences.speech_locale}</bdi>
              </p>
            </div>
          )}
          <CollectionPicker
            hasMore={collections.hasMore}
            onLoadMore={collections.loadMore}
            moreLoading={collections.moreLoading}
            items={list(collections.data)}
            value={collectionId}
            onChange={setCollection}
          />
          <Status
            error={collections.error}
            loading={collections.loading}
            retry={collections.reload}
          />
          <p className="small text-body-secondary">
            {t("study.studyLanguage")}: <bdi>{preferences.study_locale}</bdi>
          </p>
          {!scope && (
            <Empty
              href={
                collectionId
                  ? `/collections/${collectionId}/outline`
                  : "/outline"
              }
              label={t("nav.outline")}
            >
              {t("study.chooseScope")}
            </Empty>
          )}
          <div className="d-flex flex-wrap gap-2">
            <button
              disabled={!scope || busy}
              onClick={start}
              className="btn btn-primary d-inline-flex gap-2 align-items-center"
            >
              <BookOpenCheck size={18} />
              {t(busy ? "common.working" : "study.start")}
            </button>
            {dashboard?.resume?.session_id && (
              <button
                className="btn btn-outline-primary"
                onClick={() => setSessionId(dashboard.resume?.session_id ?? "")}
              >
                {t("study.resume")}
              </button>
            )}
          </div>
        </Card>
      )}
      {sessionId && pending && <Status loading />}
      {sessionId && item && !pending && !blocked && (
        <Card>
          {finished ? (
            <>
              <h2 className="h4 fw-bold">{t("study.sessionFinished")}</h2>
              <SessionSummary sessionId={sessionId} />
              <Link className="btn btn-primary mt-3" href="/progress">
                {t("nav.progress")}
              </Link>
            </>
          ) : (
            <>
              {item.teaching && !review && (
                <section>
                  <h2 className="h5 fw-bold mb-3">{t("study.teach")}</h2>
                  <p className="teach-paragraph" dir="auto">
                    {item.teaching}
                  </p>
                </section>
              )}
              {review && (
                <p className="badge text-bg-light border py-2">
                  {t("study.coldReview")}
                </p>
              )}
              <h2 className="h5 fw-bold mt-4">{t("study.check")}</h2>
              <p className="fw-medium question-text" dir="auto">
                {item.question}
              </p>
              <Citations ids={item.citation_ids ?? []} />
              {feedback ? (
                <>
                  <Feedback value={feedback} />
                  <Citations ids={feedback.citation_ids ?? []} />
                  {isVoice && (
                    <VoiceControls
                      key={`${sessionId}:${item.item_id}:feedback`}
                      sessionId={sessionId}
                      itemId={item.item_id ?? ""}
                      messages={speechMessages}
                      canRecord={false}
                      autoSpeakMessageId={autoSpeakMessageId}
                      turns={turns}
                      onTranscript={setAnswer}
                      onTyping={() => {
                        setVoice(false);
                        setTranscribed(false);
                      }}
                    />
                  )}
                  <div className="d-flex flex-wrap gap-2 mt-4">
                    <button
                      className="btn btn-primary d-inline-flex align-items-center gap-2"
                      onClick={() => action("advance")}
                      disabled={busy}
                    >
                      {t(busy ? "common.working" : "study.next")}
                      <ArrowRight size={18} />
                    </button>
                    <button
                      className="btn btn-outline-secondary"
                      onClick={() => action("finish")}
                      disabled={busy}
                    >
                      {t("study.finish")}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  {isVoice && (
                    <VoiceControls
                      key={`${sessionId}:${item.item_id}:question`}
                      sessionId={sessionId}
                      itemId={item.item_id ?? ""}
                      messages={speechMessages}
                      canRecord
                      autoSpeakMessageId={autoSpeakMessageId}
                      turns={turns}
                      onTranscript={(text) => {
                        setAnswer(text);
                        setTranscribed(true);
                      }}
                      onTyping={() => {
                        setVoice(false);
                        setTranscribed(false);
                      }}
                    />
                  )}
                  <form onSubmit={submit}>
                  <label className="d-block mt-4 mb-3">
                    <span className="form-label fw-semibold">
                      {t("study.answer")}
                    </span>
                    <textarea
                      aria-label={t("study.answer")}
                      className="form-control"
                      rows={4}
                      value={answer}
                      onChange={(e) => {
                        setAnswer(e.target.value);
                      }}
                      placeholder={t("study.answerPlaceholder")}
                      required
                      dir="auto"
                      disabled={busy}
                    />
                  </label>
                  <fieldset className="confidence-fieldset">
                    <legend className="form-label fw-semibold small">
                      {t("study.confidence")}
                    </legend>
                    <div className="confidence-options">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <label
                          key={n}
                          className={`confidence-option${confidence === n ? " selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name="confidence"
                            value={n}
                            checked={confidence === n}
                            onChange={() => setConfidence(n)}
                            required
                          />
                          <span>{n}</span>
                          <small>
                            {n === 1
                              ? t("study.lowConfidence")
                              : n === 5
                                ? t("study.highConfidence")
                                : ""}
                          </small>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <button
                    className="btn btn-primary mt-4"
                    disabled={busy || confidence === null || !answer.trim()}
                  >
                    {t(busy ? "common.working" : "study.submit")}
                  </button>
                  </form>
                </>
              )}
            </>
          )}
        </Card>
      )}
    </>
  );
}
function Citations({ ids }: { ids: string[] }) {
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
      <CitationList citations={citations} />
    </>
  );
}
function Feedback({ value }: { value: Reviewer }) {
  const { t } = useI18n();
  return (
    <div className="reviewer-feedback rounded-3 p-3 mt-4" role="status">
      <h3 className="h6 fw-bold">{t("study.feedback")}</h3>
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
