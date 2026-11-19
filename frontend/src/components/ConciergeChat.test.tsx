/* @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { CONVERSATION_STORAGE_KEY } from "../lib/conversation";
import { ConciergeChat } from "./ConciergeChat";

const regionalAnswer = "Mwanza is a Tanzanian region with a verified Saanane Island starting point.";

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
      content: regionalAnswer,
      created_at: "2026-11-19T10:00:00Z",
      generation_mode: "rule_based_fallback",
      intent: "region_overview",
      follow_up_suggestions: ["What can I do there?"],
    }]));

    render(
      <MemoryRouter>
        <ConciergeChat />
      </MemoryRouter>,
    );

    const bubble = screen.getByText(regionalAnswer).closest(".chat-bubble");
    expect(bubble?.getAttribute("data-chat-intent")).toBe("region_overview");
    expect(bubble?.getAttribute("data-generation-mode")).toBe("rule_based_fallback");
    expect(screen.queryByText(/Reliable fallback/i)).toBeNull();
    expect(screen.queryByText(/Local Ollama/i)).toBeNull();
    expect(screen.getByRole("button", { name: "What can I do there?" })).toBeDefined();
  });

  it("introduces regional discovery in the empty-state experience", () => {
    render(
      <MemoryRouter>
        <ConciergeChat />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Ask about any Tanzanian region/i)).toBeDefined();
    expect(screen.getByText(/I want to visit Mwanza/i)).toBeDefined();
    expect(screen.getByRole("combobox", { name: "Reply language" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Clear conversation and start a new chat" })).toBeDefined();
  });
});
