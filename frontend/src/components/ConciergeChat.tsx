import { Bot, LoaderCircle, MessageCircle, Send, ShieldCheck, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api";
import {
  clearConversation,
  conversationContext,
  limitConversation,
  loadConversation,
  saveConversation,
} from "../lib/conversation";
import type { ConversationMessage } from "../types";

function messageId() {
  return crypto.randomUUID();
}

export function ConciergeChat() {
  const [language, setLanguage] = useState<"en" | "sw">("en");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>(() =>
    loadConversation(window.sessionStorage),
  );
  const [chatting, setChatting] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    saveConversation(window.sessionStorage, messages);
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, chatting, error]);

  function resetConversation() {
    setMessages([]);
    setDraft("");
    setError("");
    clearConversation(window.sessionStorage);
    inputRef.current?.focus();
  }

  function chooseSuggestion(suggestion: string) {
    setDraft(suggestion);
    inputRef.current?.focus();
  }

  async function submitChat(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (chatting || content.length < 2) return;

    const existingMessages = messages;
    const userMessage: ConversationMessage = {
      id: messageId(),
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => limitConversation([...current, userMessage]));
    setDraft("");
    setError("");
    setChatting(true);

    try {
      const response = await api.chat(
        content,
        language,
        conversationContext(existingMessages),
      );
      const assistantMessage: ConversationMessage = {
        id: messageId(),
        role: "assistant",
        content: response.answer,
        created_at: new Date().toISOString(),
        generation_mode: response.generation_mode,
        intent: response.intent,
        safety_notice: response.safety_notice,
        follow_up_suggestions: response.follow_up_suggestions,
        booking_destination_id: response.booking_destination_id,
      };
      setMessages((current) => limitConversation([...current, assistantMessage]));
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "The concierge could not respond. Your message is still visible; please try again.",
      );
    } finally {
      setChatting(false);
    }
  }

  const lastAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const welcome = language === "sw"
    ? "Karibu! Uliza kuhusu mkoa wowote wa Tanzania au mojawapo ya maeneo matano ya booking. Nitatumia taarifa zilizothibitishwa."
    : "Karibu! Ask about any Tanzanian region or one of five featured booking destinations. I’ll use source-checked guide facts.";

  return (
    <section className="chat-panel panel" aria-labelledby="concierge-heading">
      <div className="panel-heading chat-heading">
        <span className="step-dot"><Bot size={18} /></span>
        <div>
          <h2 id="concierge-heading">Ask the concierge</h2>
          <p>Explore Tanzania naturally; recent context stays in this browser tab.</p>
        </div>
        <button
          className="clear-chat-button"
          type="button"
          onClick={resetConversation}
          disabled={chatting || messages.length === 0}
          aria-label="Clear conversation and start a new chat"
        >
          <Trash2 size={14} /> New chat
        </button>
      </div>

      <div className="chat-toolbar">
        <label htmlFor="chat-language">Reply language</label>
        <select
          id="chat-language"
          value={language}
          onChange={(event) => setLanguage(event.target.value as "en" | "sw")}
        >
          <option value="en">English</option>
          <option value="sw">Kiswahili</option>
        </select>
      </div>

      <div className="chat-window" role="log" aria-live="polite" aria-busy={chatting}>
        {!messages.length && (
          <div className="chat-bubble assistant welcome-message">
            <Bot size={18} />
            <div><p>{welcome}</p><small>Try “I want to visit Mwanza.”</small></div>
          </div>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={`chat-bubble ${message.role}`}
            data-chat-intent={message.role === "assistant" ? message.intent : undefined}
            data-generation-mode={message.role === "assistant" ? message.generation_mode : undefined}
          >
            {message.role === "assistant" && <Bot size={18} aria-hidden="true" />}
            <div>
              <p>{message.content}</p>
              {message.safety_notice && <small>{message.safety_notice}</small>}
              {message.booking_destination_id && (
                <Link className="chat-booking-link" to={`/booking?destination=${message.booking_destination_id}`}>
                  Open the booking-request form
                </Link>
              )}
            </div>
          </div>
        ))}
        {chatting && (
          <div className="chat-bubble assistant chat-loading" role="status">
            <LoaderCircle className="spin" size={18} />
            <p>Checking the trusted Tanzania travel guide…</p>
          </div>
        )}
        {error && <div className="chat-error" role="alert">{error}</div>}
        <div ref={endRef} />
      </div>

      {!chatting && lastAssistant?.follow_up_suggestions?.length ? (
        <div className="chat-suggestions" aria-label="Suggested follow-up questions">
          {lastAssistant.follow_up_suggestions.map((suggestion) => (
            <button key={suggestion} type="button" onClick={() => chooseSuggestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}

      <form className="chat-form" onSubmit={submitChat}>
        <label className="sr-only" htmlFor="chat-message">Message the concierge</label>
        <textarea
          ref={inputRef}
          id="chat-message"
          maxLength={500}
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={language === "sw" ? "Uliza kuhusu eneo au safari…" : "Ask about a destination or trip…"}
          disabled={chatting}
        />
        <button type="submit" aria-label="Send message" disabled={chatting || draft.trim().length < 2}>
          <Send size={18} />
        </button>
      </form>
      <div className="chat-footer-note">
        <span>{draft.length}/500</span>
        <p><ShieldCheck size={13} /> Do not share contact details, credentials, or booking references in chat.</p>
      </div>
      <p className="mode-note"><MessageCircle size={14} /> Up to 20 redacted messages stay in this tab; only the latest 8 provide context.</p>
    </section>
  );
}
