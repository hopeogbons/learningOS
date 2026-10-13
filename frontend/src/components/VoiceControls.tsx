"use client";
import { useEffect, useRef, useState } from "react";
import { Mic, Square, Volume2, Keyboard } from "lucide-react";
import { useI18n } from "@/i18n";
import { api, apiBlob } from "@/lib/api";
type RecognitionEvent = {
  results: { [index: number]: { [index: number]: { transcript: string } } };
};
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};
/** Inventory can arrive asynchronously; observe voiceschanged before server fallback. */
async function browserVoices(): Promise<SpeechSynthesisVoice[]> {
  const synthesis = window.speechSynthesis;
  if (!synthesis) return [];
  const ready = synthesis.getVoices();
  if (ready.length) return ready;
  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer);
      synthesis.removeEventListener("voiceschanged", finish);
      resolve(synthesis.getVoices());
    };
    const timer = setTimeout(finish, 1000);
    synthesis.addEventListener("voiceschanged", finish);
  });
}
export default function VoiceControls({
  sessionId,
  itemId,
  messageId,
  text,
  turns,
  onTranscript,
  onTyping,
}: {
  sessionId: string;
  itemId: string;
  messageId: "teaching" | "question" | "feedback";
  text: string;
  turns: number;
  onTranscript: (text: string) => void;
  onTyping: () => void;
}) {
  const { t, preferences } = useI18n(),
    [recording, setRecording] = useState(false),
    [speaking, setSpeaking] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState<string | null>(null);
  const recognition = useRef<Recognition | null>(null),
    recorder = useRef<MediaRecorder | null>(null),
    stream = useRef<MediaStream | null>(null),
    audio = useRef<HTMLAudioElement | null>(null),
    audioUrl = useRef<string | null>(null),
    active = useRef(false),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    request = useRef<AbortController | null>(null),
    transcriptCallback = useRef(onTranscript);
  useEffect(() => {
    transcriptCallback.current = onTranscript;
  }, [onTranscript]);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      request.current?.abort();
      if (timer.current) clearTimeout(timer.current);
      if (recognition.current) {
        recognition.current.onresult = null;
        recognition.current.onerror = null;
        recognition.current.onend = null;
        recognition.current.stop();
      }
      if (recorder.current) {
        recorder.current.onstop = null;
        recorder.current.ondataavailable = null;
        if (recorder.current.state === "recording") recorder.current.stop();
      }
      stream.current?.getTracks().forEach((track) => track.stop());
      window.speechSynthesis?.cancel();
      audio.current?.pause();
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    };
  }, []);
  function cancelRecording() {
    if (timer.current) clearTimeout(timer.current);
    if (recognition.current) {
      recognition.current.onresult = null;
      recognition.current.onerror = null;
      recognition.current.onend = null;
      recognition.current.stop();
    }
    if (recorder.current) {
      recorder.current.onstop = null;
      if (recorder.current.state === "recording") recorder.current.stop();
    }
    stream.current?.getTracks().forEach((track) => track.stop());
    request.current?.abort();
    if (active.current) {
      setRecording(false);
      setBusy(false);
    }
  }
  function stopRecording() {
    if (timer.current) clearTimeout(timer.current);
    recognition.current?.stop();
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (active.current) setRecording(false);
  }
  function stopSpeech() {
    window.speechSynthesis?.cancel();
    audio.current?.pause();
    request.current?.abort();
    if (active.current) {
      setSpeaking(false);
      setBusy(false);
    }
  }
  async function serverRecord() {
    try {
      if (
        !navigator.mediaDevices?.getUserMedia ||
        typeof MediaRecorder === "undefined"
      ) {
        setNotice(t("study.voiceUnavailable"));
        return;
      }
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!active.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mime = ["audio/webm", "audio/mp4", "audio/ogg"].find((value) =>
        MediaRecorder.isTypeSupported(value),
      );
      const recording = new MediaRecorder(
        media,
        mime ? { mimeType: mime } : {},
      );
      recorder.current = recording;
      const chunks: BlobPart[] = [];
      let bytes = 0;
      recording.ondataavailable = (event) => {
        bytes += event.data.size;
        if (bytes > 5 * 1024 * 1024) {
          cancelRecording();
          if (active.current) setNotice(t("study.voiceUnavailable"));
        } else if (event.data.size) chunks.push(event.data);
      };
      recording.onstop = async () => {
        media.getTracks().forEach((track) => track.stop());
        if (timer.current) clearTimeout(timer.current);
        if (!active.current) return;
        setRecording(false);
        setBusy(true);
        const abort = new AbortController();
        request.current = abort;
        try {
          const form = new FormData();
          form.set("item_id", itemId);
          form.set(
            "audio",
            new Blob(chunks, { type: recording.mimeType.split(";")[0] }),
            `speech.${recording.mimeType.includes("mp4") ? "mp4" : "webm"}`,
          );
          const result = await api<{ text: string }>(
            `/sessions/${sessionId}/speech/transcribe`,
            { method: "POST", body: form, signal: abort.signal },
          );
          if (!active.current || abort.signal.aborted) return;
          transcriptCallback.current(result.text);
          setNotice(t("study.serverSpeech"));
        } catch {
          if (active.current && !abort.signal.aborted)
            setNotice(t("study.voiceUnavailable"));
        } finally {
          if (active.current && !abort.signal.aborted) setBusy(false);
        }
      };
      recording.start(1000);
      timer.current = setTimeout(stopRecording, 60000);
      setRecording(true);
      setNotice(t("study.serverSpeech"));
    } catch (error) {
      if (active.current)
        setNotice(
          t(
            (error as Error).name === "NotAllowedError"
              ? "study.micDenied"
              : "study.voiceUnavailable",
          ),
        );
    }
  }
  function record() {
    setNotice(null);
    const Constructor =
      (window as SpeechWindow).SpeechRecognition ??
      (window as SpeechWindow).webkitSpeechRecognition;
    if (!Constructor) {
      void serverRecord();
      return;
    }
    const instance = new Constructor();
    recognition.current = instance;
    instance.lang = preferences.speech_locale;
    instance.continuous = false;
    instance.interimResults = false;
    instance.onresult = (event) => {
      if (!active.current) return;
      transcriptCallback.current(event.results[0][0].transcript);
      if (timer.current) clearTimeout(timer.current);
      setRecording(false);
    };
    instance.onerror = (event) => {
      if (!active.current) return;
      if (timer.current) clearTimeout(timer.current);
      setRecording(false);
      if (
        event.error === "not-allowed" ||
        event.error === "service-not-allowed"
      )
        setNotice(t("study.micDenied"));
      else void serverRecord();
    };
    instance.onend = () => {
      if (active.current) setRecording(false);
    };
    try {
      instance.start();
      timer.current = setTimeout(stopRecording, 60000);
      setRecording(true);
      setNotice(t("study.browserSpeech"));
    } catch {
      void serverRecord();
    }
  }
  async function speak() {
    stopSpeech();
    setNotice(null);
    setBusy(true);
    const voices = await browserVoices();
    if (!active.current) return;
    const target = preferences.speech_locale.toLowerCase(),
      voice =
        voices.find((value) => value.lang.toLowerCase() === target) ??
        voices.find(
          (value) =>
            value.lang.toLowerCase().split("-")[0] === target.split("-")[0],
        );
    if (voice) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = voice.lang;
      utterance.voice = voice;
      utterance.onend = () => {
        if (active.current) setSpeaking(false);
      };
      utterance.onerror = () => {
        if (active.current) {
          setSpeaking(false);
          setNotice(t("study.voiceUnavailable"));
        }
      };
      window.speechSynthesis.speak(utterance);
      setSpeaking(true);
      setBusy(false);
      return;
    }
    setNotice(t("study.speechFallback"));
    const abort = new AbortController();
    request.current = abort;
    try {
      const blob = await apiBlob(
        `/sessions/${sessionId}/speech/synthesize`,
        { item_id: itemId, message_id: messageId },
        abort.signal,
      );
      if (!active.current || abort.signal.aborted) return;
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = URL.createObjectURL(blob);
      audio.current = new Audio(audioUrl.current);
      audio.current.onended = () => {
        if (active.current) setSpeaking(false);
      };
      await audio.current.play();
      if (!active.current || abort.signal.aborted) return;
      setSpeaking(true);
      setNotice(t("study.serverSpeech"));
    } catch {
      if (active.current && !abort.signal.aborted)
        setNotice(t("study.voiceUnavailable"));
    } finally {
      if (active.current && !abort.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="voice-controls rounded-3 p-3 mb-3">
      <div className="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
        <strong className="small">{t("study.voice")}</strong>
        <span className="small">{t("study.voiceTurns", { count: turns })}</span>
      </div>
      <p className="small text-body-secondary mb-3">
        {t("study.voiceDescription")}
      </p>
      <p className="small text-body-secondary">
        {t("study.speechLanguage")}: <bdi>{preferences.speech_locale}</bdi>
      </p>
      <div className="d-flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-danger btn-sm d-flex align-items-center gap-2"
          onClick={recording ? stopRecording : record}
          disabled={
            !recording && (turns >= 3 || busy || messageId === "feedback")
          }
        >
          {recording ? <Square size={16} /> : <Mic size={16} />}{" "}
          {t(recording ? "study.stopRecording" : "study.microphone")}
        </button>
        <button
          type="button"
          className="btn btn-outline-primary btn-sm d-flex align-items-center gap-2"
          onClick={speaking ? stopSpeech : speak}
          disabled={busy || !text}
        >
          <Volume2 size={16} />
          {t(speaking ? "study.stopSpeech" : "study.listen")}
        </button>
        <button
          type="button"
          className="btn btn-light border btn-sm d-flex align-items-center gap-2"
          onClick={() => {
            cancelRecording();
            stopSpeech();
            onTyping();
          }}
        >
          <Keyboard size={16} />
          {t("study.typing")}
        </button>
      </div>
      {turns >= 3 && <p className="small mt-2 mb-0">{t("study.turnLimit")}</p>}
      {notice && (
        <p role="status" className="small mt-2 mb-0">
          {notice}
        </p>
      )}
    </div>
  );
}
