"use client";

import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { Database } from "@/types/database";

type Message = Database["public"]["Tables"]["messages"]["Row"];
type Profile = Pick<Database["public"]["Tables"]["profiles"]["Row"], "id" | "full_name" | "avatar_url" | "role">;

interface DugoutChatProps {
  currentUserId: string;
  profiles: Profile[];
  initialMessages: Message[];
}

const TIME_FORMAT = new Intl.DateTimeFormat("nl-BE", { hour: "2-digit", minute: "2-digit" });

function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

/**
 * The Dug-out Chat: a single shared, realtime channel for the coaching
 * staff (see supabase/migrations/0001_init.sql — 'messages' has no
 * channel/room concept yet, this is a closed two/three-person team).
 *
 * Sends go straight to Postgres via `insert`; the sender's own message
 * reaches their screen through the same postgres_changes subscription
 * everyone else uses (no local optimistic append) — Supabase Realtime's
 * latency is low enough for a small coaching staff that this keeps the
 * client dead simple with a single source of truth for message state.
 */
export default function DugoutChat({ currentUserId, profiles, initialMessages }: DugoutChatProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const profileById = useMemo(() => {
    const map = new Map<string, Profile>();
    profiles.forEach((profile) => map.set(profile.id, profile));
    return map;
  }, [profiles]);

  useEffect(() => {
    const supabase = createClient();
    const channel = supabase
      .channel("dugout-chat")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "messages" }, (payload) => {
        const incoming = payload.new as Message;
        setMessages((current) => (current.some((m) => m.id === incoming.id) ? current : [...current, incoming]));
      })
      .on("postgres_changes", { event: "DELETE", schema: "public", table: "messages" }, (payload) => {
        const removedId = (payload.old as Partial<Message>).id;
        setMessages((current) => current.filter((m) => m.id !== removedId));
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  useEffect(() => {
    if (autoScroll) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, autoScroll]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoScroll(distanceFromBottom < 80);
  };

  const handleSend = async () => {
    const body = draft.trim();
    if (!body || sending) return;

    setSending(true);
    setError(null);
    setDraft("");

    const supabase = createClient();
    const { error: sendError } = await supabase.from("messages").insert({ sender_id: currentUserId, body });

    if (sendError) {
      setError("Bericht kon niet verstuurd worden. Probeer opnieuw.");
      setDraft(body);
    }
    setSending(false);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
      <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Dug-out</h2>
          <p className="text-lg font-bold text-white">Coach Chat</p>
        </div>
        <span className="flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs font-medium text-gray-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(52,211,153,0.6)]" />
          Live
        </span>
      </header>

      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <p className="pt-10 text-center text-sm text-gray-500">
            Nog geen berichten. Stuur het eerste bericht naar de dug-out.
          </p>
        )}
        {messages.map((message) => {
          const author = message.sender_id ? profileById.get(message.sender_id) : undefined;
          const isOwn = message.sender_id === currentUserId;
          return (
            <div key={message.id} className={`flex items-end gap-2.5 ${isOwn ? "flex-row-reverse" : ""}`}>
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  isOwn ? "bg-sky-500/20 text-sky-300" : "bg-emerald-500/20 text-emerald-300"
                }`}
                title={author?.full_name ?? "Onbekend"}
              >
                {initials(author?.full_name ?? "?")}
              </div>
              <div className={`flex max-w-[75%] flex-col ${isOwn ? "items-end" : "items-start"}`}>
                <span className="px-1 text-[11px] font-medium text-gray-500">
                  {isOwn ? "Jij" : (author?.full_name ?? "Onbekend")} · {TIME_FORMAT.format(new Date(message.created_at))}
                </span>
                <p
                  className={`whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                    isOwn
                      ? "rounded-tr-sm bg-sky-600 text-white"
                      : "rounded-tl-sm border border-white/5 bg-gray-800 text-gray-100"
                  }`}
                >
                  {message.body}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {!autoScroll && (
        <button
          type="button"
          onClick={() => {
            setAutoScroll(true);
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
          }}
          className="mx-auto -mt-2 mb-2 rounded-full bg-emerald-500 px-3 py-1 text-xs font-medium text-white shadow-lg"
        >
          Nieuwe berichten ↓
        </button>
      )}

      {error && <p className="px-5 pb-1 text-xs text-red-400">{error}</p>}

      <div className="flex items-end gap-2 border-t border-white/10 p-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Typ een bericht naar de dug-out…"
          className="max-h-32 flex-1 resize-none rounded-xl border border-white/10 bg-gray-950 px-3.5 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={sending || !draft.trim()}
          className="shrink-0 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Sturen
        </button>
      </div>
    </div>
  );
}
