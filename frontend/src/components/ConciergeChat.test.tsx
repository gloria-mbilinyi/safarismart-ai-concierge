/* @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { CONVERSATION_STORAGE_KEY } from "../lib/conversation";
import { ConciergeChat } from "./ConciergeChat";

const fallbackAnswer = "Sorry, I currently don't have information about Mwanza.";

beforeEach(() => {
  window.sessionStorage.clear();
  Element.prototype.scrollIntoView = () => undefined;
});

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
});

describe("ConciergeChat", () => {
  it("keeps diagnostics in data attributes instead of public response labels", () => {
    window.sessionStorage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify([{
      id: "assistant-1",
      role: "assistant",
      content: fallbackAnswer,
      created_at: "2026-11-19T10:00:00Z",
      generation_mode: "rule_based_fallback",
      intent: "unknown_location",
      follow_up_suggestions: ["Tell me about Zanzibar"],
    }]));

    render(
      <MemoryRouter>
        <ConciergeChat />
      </MemoryRouter>,
    );

    const bubble = screen.getByText(fallbackAnswer).closest(".chat-bubble");
    expect(bubble?.getAttribute("data-chat-intent")).toBe("unknown_location");
    expect(bubble?.getAttribute("data-generation-mode")).toBe("rule_based_fallback");
    expect(screen.queryByText(/Reliable fallback/i)).toBeNull();
    expect(screen.queryByText(/Local Ollama/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Tell me about Zanzibar" })).toBeDefined();
  });

  it("introduces only the five supported destinations in the empty state", () => {
    render(
      <MemoryRouter>
        <ConciergeChat />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Ask about Serengeti, Ngorongoro, Mount Kilimanjaro/i)).toBeDefined();
    expect(screen.getByText(/I want to visit Zanzibar/i)).toBeDefined();
    expect(screen.queryByText(/Mwanza/i)).toBeNull();
    expect(screen.getByRole("combobox", { name: "Reply language" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Clear conversation and start a new chat" })).toBeDefined();
  });
});
