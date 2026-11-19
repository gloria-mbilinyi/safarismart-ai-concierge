import type { ChatContextMessage, ConversationMessage } from "../types";

export const CONVERSATION_STORAGE_KEY = "safarismart.concierge.conversation.v1";
export const MAX_STORED_MESSAGES = 20;
export const MAX_CONTEXT_MESSAGES = 8;

export interface ConversationStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const GENERATION_MODES = new Set(["rule_based_fallback", "local_ollama"]);
const CHAT_INTENTS = new Set([
  "greeting",
  "recommendation",
  "destination_overview",
  "activities",
  "trip_duration",
  "comparison",
  "budget",
  "booking_guidance",
  "unsupported_fact",
  "unknown_location",
  "clarification",
]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const SENSITIVE_PATTERNS: Array<[RegExp, string]> = [
  [/\bBearer\s+[A-Za-z0-9._~+/=-]{10,}\b/gi, "[removed bearer token]"],
  [/\bsk-[A-Za-z0-9_-]{10,}\b/g, "[removed API key]"],
  [/\b(?:api[_ -]?key|auth[_ -]?secret|token)\s*[:=]\s*\S+/gi, "[removed secret]"],
  [/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[removed email]"],
  [/\+[1-9]\d{7,14}\b/g, "[removed phone]"],
  [/\bSS-[A-Z0-9-]{6,}\b/g, "[removed booking reference]"],
];

export function redactSensitiveText(value: string): string {
  return SENSITIVE_PATTERNS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    value,
  );
}

function normalizeConversationMessage(value: unknown): ConversationMessage | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  if (
    (candidate.role !== "user" && candidate.role !== "assistant")
    || typeof candidate.id !== "string"
    || typeof candidate.content !== "string"
    || typeof candidate.created_at !== "string"
  ) {
    return null;
  }

  const message: ConversationMessage = {
    role: candidate.role,
    id: candidate.id.slice(0, 100),
    content: redactSensitiveText(candidate.content).slice(0, 1600),
    created_at: candidate.created_at.slice(0, 40),
  };
  if (typeof candidate.generation_mode === "string" && GENERATION_MODES.has(candidate.generation_mode)) {
    message.generation_mode = candidate.generation_mode as ConversationMessage["generation_mode"];
  }
  if (typeof candidate.intent === "string" && CHAT_INTENTS.has(candidate.intent)) {
    message.intent = candidate.intent as ConversationMessage["intent"];
  }
  if (typeof candidate.safety_notice === "string") {
    message.safety_notice = redactSensitiveText(candidate.safety_notice).slice(0, 500);
  }
  if (Array.isArray(candidate.follow_up_suggestions)) {
    message.follow_up_suggestions = candidate.follow_up_suggestions
      .filter((suggestion): suggestion is string => typeof suggestion === "string")
      .slice(0, 3)
      .map((suggestion) => redactSensitiveText(suggestion).slice(0, 200));
  }
  if (typeof candidate.booking_destination_id === "string" && UUID_PATTERN.test(candidate.booking_destination_id)) {
    message.booking_destination_id = candidate.booking_destination_id;
  }
  return message;
}

export function limitConversation(messages: ConversationMessage[]): ConversationMessage[] {
  return messages.slice(-MAX_STORED_MESSAGES);
}

export function loadConversation(storage: ConversationStorage): ConversationMessage[] {
  try {
    const raw = storage.getItem(CONVERSATION_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return limitConversation(
      parsed
        .map(normalizeConversationMessage)
        .filter((message): message is ConversationMessage => message !== null),
    );
  } catch {
    return [];
  }
}

export function saveConversation(
  storage: ConversationStorage,
  messages: ConversationMessage[],
): void {
  const safeMessages = limitConversation(messages)
    .map(normalizeConversationMessage)
    .filter((message): message is ConversationMessage => message !== null);
  try {
    storage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(safeMessages));
  } catch {
    // The live conversation remains usable if session storage is unavailable.
  }
}

export function clearConversation(storage: ConversationStorage): void {
  try {
    storage.removeItem(CONVERSATION_STORAGE_KEY);
  } catch {
    // Clearing local UI state still succeeds if storage is unavailable.
  }
}

export function conversationContext(
  messages: ConversationMessage[],
): ChatContextMessage[] {
  return messages.slice(-MAX_CONTEXT_MESSAGES).map((message) => ({
    role: message.role,
    content: redactSensitiveText(message.content).slice(0, 1200),
  }));
}
