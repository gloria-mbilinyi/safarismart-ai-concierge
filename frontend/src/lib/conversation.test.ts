import { describe, expect, it } from "vitest";

import type { ConversationMessage } from "../types";
import {
  CONVERSATION_STORAGE_KEY,
  MAX_CONTEXT_MESSAGES,
  MAX_STORED_MESSAGES,
  clearConversation,
  conversationContext,
  loadConversation,
  redactSensitiveText,
  saveConversation,
} from "./conversation";

class MemoryStorage {
  values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }

  removeItem(key: string) {
    this.values.delete(key);
  }
}

function message(index: number): ConversationMessage {
  return {
    id: `message-${index}`,
    role: index % 2 ? "assistant" : "user",
    content: `Message ${index}`,
    created_at: `2026-11-17T10:00:${String(index).padStart(2, "0")}Z`,
  };
}

describe("session-scoped concierge conversation", () => {
  it("redacts contact, booking, and secret material before persistence", () => {
    const redacted = redactSensitiveText(
      "Email me@example.com phone +255712345678 ref SS-ABCDEF123456 "
      + "Bearer abcdefghijklmnopqrstuvwxyz api_key=super-secret-value",
    );

    expect(redacted).not.toContain("me@example.com");
    expect(redacted).not.toContain("+255712345678");
    expect(redacted).not.toContain("SS-ABCDEF123456");
    expect(redacted).not.toContain("abcdefghijklmnopqrstuvwxyz");
    expect(redacted).not.toContain("super-secret-value");
  });

  it("round-trips safe messages and caps stored history", () => {
    const storage = new MemoryStorage();
    const messages = Array.from({ length: 25 }, (_, index) => message(index));

    saveConversation(storage, messages);
    const loaded = loadConversation(storage);

    expect(loaded).toHaveLength(MAX_STORED_MESSAGES);
    expect(loaded[0]?.id).toBe("message-5");
    expect(loaded.at(-1)?.id).toBe("message-24");
  });

  it("rejects malformed stored data instead of breaking the chat", () => {
    const storage = new MemoryStorage();
    storage.setItem(CONVERSATION_STORAGE_KEY, "not-json");

    expect(loadConversation(storage)).toEqual([]);
  });

  it("rebuilds only safe optional fields from user-editable session data", () => {
    const storage = new MemoryStorage();
    storage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify([{
      ...message(1),
      intent: 42,
      generation_mode: "untrusted-provider",
      follow_up_suggestions: "not-an-array",
      booking_destination_id: "not-a-uuid",
      unexpected: "ignored",
    }]));

    expect(loadConversation(storage)).toEqual([message(1)]);
  });

  it("sends only recent redacted context to the backend", () => {
    const messages = Array.from({ length: 12 }, (_, index) => message(index));
    messages[11] = { ...messages[11], content: "Call +255712345678" };

    const context = conversationContext(messages);

    expect(context).toHaveLength(MAX_CONTEXT_MESSAGES);
    expect(context[0]?.content).toBe("Message 4");
    expect(context.at(-1)?.content).toBe("Call [removed phone]");
  });

  it("clears the session conversation", () => {
    const storage = new MemoryStorage();
    saveConversation(storage, [message(1)]);

    clearConversation(storage);

    expect(storage.getItem(CONVERSATION_STORAGE_KEY)).toBeNull();
  });
});
