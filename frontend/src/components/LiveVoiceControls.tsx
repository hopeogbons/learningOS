"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Phone, PhoneOff, Send, Volume2 } from "lucide-react";
import { api, json, ApiError } from "@/lib/api";
import { useI18n } from "@/i18n";
type LiveEvent = { type?: string; transcript?: string; text?: string; delta?: string; item_id?: string; response_id?: string; error?: { message?: string } };
type Connection = { client_secret: string; model: string; webrtc_url: string; max_duration_seconds: number };
export type LiveMessage = { id: string; role: "teacher" | "learner"; text: string };
export default function LiveVoiceControls({ sessionId, itemId, onTranscript, onMessage, draft, onDraft, disabled = false }: {
  sessionId: string; itemId: string; onTranscript: (text: string) => void;
  onMessage: (message: LiveMessage) => void; draft: string; onDraft: (text: string) => void; disabled?: boolean;
}) {
  const { t } = useI18n();
  const [status, setStatus] = useState<"idle" | "connecting" | "connected">("idle");
  const [muted, setMuted] = useState(false), [error, setError] = useState<string | null>(null);
  const peer = useRef<RTCPeerConnection | null>(null), channel = useRef<RTCDataChannel | null>(null), media = useRef<MediaStream | null>(null), audio = useRef<HTMLAudioElement | null>(null);
  const request = useRef<AbortController | null>(null), timer = useRef<ReturnType<typeof setTimeout> | null>(null), generation = useRef(0);
  const callbacks = useRef({ onTranscript, onMessage });
  useEffect(() => { callbacks.current = { onTranscript, onMessage }; }, [onTranscript, onMessage]);
  const disconnect = useCallback(() => {
    generation.current += 1;
    request.current?.abort(); request.current = null;
    if (timer.current) clearTimeout(timer.current);
    channel.current?.close(); channel.current = null;
    peer.current?.close(); peer.current = null;
    media.current?.getTracks().forEach((track) => track.stop()); media.current = null;
    if (audio.current) { audio.current.pause(); audio.current.srcObject = null; }
  }, []);
  useEffect(() => () => disconnect(), [disconnect, sessionId, itemId]);
  function stop() { disconnect(); setStatus("idle"); setMuted(false); }
  async function start() {
    if (status !== "idle" || disabled) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === "undefined") {
      setError("Live voice needs a supported browser and a secure connection. You can still type or send a voice note."); return;
    }
    disconnect(); const current = generation.current;
    const abort = new AbortController(); request.current = abort;
    setError(null); setStatus("connecting"); setMuted(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      if (generation.current !== current) { stream.getTracks().forEach((track) => track.stop()); return; }
      media.current = stream;
      const connection = await api<Connection>(`/sessions/${sessionId}/speech/realtime`, { method: "POST", body: json({ item_id: itemId }), signal: abort.signal });
      if (generation.current !== current) return;
      if (connection.webrtc_url !== "https://api.openai.com/v1/realtime/calls") throw new Error("The voice connection is not configured correctly.");
      const callsUrl = new URL(connection.webrtc_url);
      callsUrl.searchParams.set("model", connection.model);
      const pc = new RTCPeerConnection(); peer.current = pc;
      const player = new Audio(); player.autoplay = true; audio.current = player;
      pc.ontrack = (event) => { if (generation.current !== current) return; player.srcObject = event.streams[0]; void player.play().catch(() => { if (generation.current === current) setError("Tap Listen to enable your teacher's audio."); }); };
      stream.getTracks().forEach((track) => pc.addTrack(track, stream));
      const dc = pc.createDataChannel("oai-events"); channel.current = dc;
      const transcripts = new Map<string, string>();
      dc.onerror = () => { if (generation.current === current) { disconnect(); setStatus("idle"); setError("Your voice connection was interrupted. Try reconnecting or use text."); } };
      dc.onclose = () => { if (generation.current === current) { disconnect(); setStatus("idle"); setError("The voice conversation ended. You can reconnect or continue typing."); } };
      dc.onmessage = (event) => {
        let message: LiveEvent; try { message = JSON.parse(event.data); } catch { return; }
        if (generation.current !== current) return;
        const id = message.item_id || message.response_id || "teacher-response";
        if (message.type === "conversation.item.input_audio_transcription.completed" && message.transcript?.trim()) {
          callbacks.current.onTranscript(message.transcript);
          callbacks.current.onMessage({ id, role: "learner", text: message.transcript });
        } else if (message.type === "response.output_audio_transcript.delta" || message.type === "response.audio_transcript.delta") {
          const text = (transcripts.get(id) || "") + (message.delta || ""); transcripts.set(id, text);
          callbacks.current.onMessage({ id, role: "teacher", text });
        } else if (message.type === "response.output_audio_transcript.done" || message.type === "response.audio_transcript.done" || message.type === "response.output_text.done") {
          callbacks.current.onMessage({ id, role: "teacher", text: message.transcript || message.text || transcripts.get(id) || "" }); transcripts.delete(id);
        } else if (message.type === "error") setError(message.error?.message || "Your teacher could not respond. Try reconnecting.");
      };
      timer.current = setTimeout(() => { if (generation.current === current && dc.readyState !== "open") { disconnect(); setStatus("idle"); setError("Voice connection timed out. Please try again."); } }, 20000);
      dc.onopen = () => {
        if (generation.current !== current) return;
        if (timer.current) clearTimeout(timer.current);
        setStatus("connected");
        dc.send(JSON.stringify({ type: "response.create" }));
        timer.current = setTimeout(() => { disconnect(); setStatus("idle"); setError("This voice conversation has ended. Start again whenever you're ready."); }, Math.min(connection.max_duration_seconds || 300, 300) * 1000);
      };
      pc.onconnectionstatechange = () => {
        if (generation.current !== current) return;
        if (pc.connectionState === "failed" || pc.connectionState === "disconnected" || pc.connectionState === "closed") {
          disconnect(); setStatus("idle"); setError("Voice disconnected. Your study session is saved; reconnect or continue typing.");
        }
      };
      const offer = await pc.createOffer(); await pc.setLocalDescription(offer);
      const response = await fetch(callsUrl.toString(), { method: "POST", headers: { Authorization: `Bearer ${connection.client_secret}`, "Content-Type": "application/sdp" }, body: offer.sdp, signal: abort.signal });
      if (!response.ok) throw new Error("Could not connect to your voice teacher. Try again or continue in text.");
      const sdp = await response.text(); if (generation.current !== current) return;
      await pc.setRemoteDescription({ type: "answer", sdp });
      if (generation.current !== current) return;

    } catch (e) {
      if (generation.current !== current) return;
      disconnect(); setStatus("idle");
      setError((e as Error).name === "NotAllowedError" ? "Allow microphone access to talk with your teacher. Text study is still available." : e instanceof ApiError && e.code === "realtime_unavailable" ? "Live voice is unavailable on this installation. Try again, or continue in text or voice notes." : e instanceof ApiError && e.status === 409 ? "This study turn is not ready for live voice. Continue in text or load the next question." : (e as Error).message);
    }
  }
  function toggleMic() { media.current?.getAudioTracks().forEach((track) => { track.enabled = muted; }); setMuted(!muted); }
  function sendText(e: React.FormEvent) {
    e.preventDefault(); if (!draft.trim() || channel.current?.readyState !== "open") return;
    const text = draft.trim();
    channel.current.send(JSON.stringify({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text }] } }));
    channel.current.send(JSON.stringify({ type: "response.create" }));
    callbacks.current.onMessage({ id: crypto.randomUUID(), role: "learner", text }); onDraft("");
  }
  return <section className="live-voice-panel" aria-label={t("study.modeLive")}>
    <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div><strong>{t(status === "connected" ? "study.liveListening" : status === "connecting" ? "study.liveConnecting" : "study.liveReady")}</strong><p className="small text-body-secondary mb-0">{t("study.liveHelp")}</p></div>
      <div className="d-flex flex-wrap gap-2">
        {status === "idle" ? <button className="btn btn-primary" onClick={start} disabled={disabled}><Phone size={17} /> {t("study.liveStart")}</button> : <button className="btn btn-outline-secondary" onClick={stop}><PhoneOff size={17} /> {t("study.liveEnd")}</button>}
        {status === "connected" && <><button className="btn btn-outline-primary" aria-pressed={muted} onClick={toggleMic}>{muted ? <MicOff size={17} /> : <Mic size={17} />}{t(muted ? "study.liveUnmute" : "study.liveMute")}</button><button className="btn btn-outline-primary" onClick={() => void audio.current?.play().then(() => setError(null)).catch(() => setError("Your browser blocked audio. Check its sound settings."))}><Volume2 size={17} /> {t("study.listen")}</button></>}
      </div>
    </div>
    {error && <p role="alert" className="small mt-3 mb-0">{error}</p>}
    {status === "connected" && <form onSubmit={sendText} className="d-flex gap-2 mt-3"><input className="form-control" aria-label={t("study.liveMessage")} placeholder={t("study.livePlaceholder")} value={draft} onChange={(e) => onDraft(e.target.value)} maxLength={10000} /><button className="btn btn-primary" disabled={!draft.trim()} aria-label={t("study.liveSend")}><Send size={18} /></button></form>}
  </section>;
}
