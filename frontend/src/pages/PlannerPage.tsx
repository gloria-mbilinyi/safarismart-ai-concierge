import { Bot, Check, MessageCircle, Send, Sparkles, WandSparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api";
import { InlineError } from "../components/Feedback";
import type { ChatResponse, TravelInterest, TripPlan, TripPlanRequest } from "../types";

const interestOptions: Array<{ value: TravelInterest; label: string }> = [
  { value: "wildlife", label: "Wildlife" },
  { value: "beach", label: "Coast" },
  { value: "mountain", label: "Mountains" },
  { value: "culture", label: "Culture" },
  { value: "nature", label: "Nature" },
];

export function PlannerPage() {
  const [form, setForm] = useState<TripPlanRequest>({
    days: 5,
    party_size: 2,
    interests: ["wildlife"],
    budget_style: "comfort",
    language: "en",
  });
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState("");
  const [chatMessage, setChatMessage] = useState("");
  const [chat, setChat] = useState<ChatResponse | null>(null);
  const [chatting, setChatting] = useState(false);

  function toggleInterest(interest: TravelInterest) {
    setForm((current) => {
      const selected = current.interests.includes(interest)
        ? current.interests.filter((item) => item !== interest)
        : [...current.interests, interest];
      return { ...current, interests: selected.length ? selected : [interest] };
    });
  }

  async function submitPlan(event: FormEvent) {
    event.preventDefault();
    setPlanning(true);
    setError("");
    try {
      setPlan(await api.plan(form));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "The planner is unavailable. Please try again.");
    } finally {
      setPlanning(false);
    }
  }

  async function submitChat(event: FormEvent) {
    event.preventDefault();
    if (!chatMessage.trim()) return;
    setChatting(true);
    setError("");
    try {
      setChat(await api.chat(chatMessage, form.language));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "The concierge is unavailable. Please try again.");
    } finally {
      setChatting(false);
    }
  }

  return (
    <div className="page-shell planner-page">
      <section className="page-intro planner-intro">
        <span className="overline"><WandSparkles size={15} /> Grounded AI concierge</span>
        <h1>Start with interests.<br />Leave with a clearer route.</h1>
        <p>The model can rank known places, but it cannot invent destinations, prices, operator relationships, or confirmations.</p>
      </section>

      <div className="planner-layout">
        <form className="planner-form panel" onSubmit={submitPlan}>
          <div className="panel-heading">
            <span className="step-dot">1</span>
            <div><h2>Shape your trip</h2><p>A few useful constraints make a better starting point.</p></div>
          </div>
          <div className="form-grid two-columns">
            <label>Days
              <input type="number" min="1" max="14" value={form.days} onChange={(event) => setForm({ ...form, days: Number(event.target.value) })} required />
            </label>
            <label>Travelers
              <input type="number" min="1" max="20" value={form.party_size} onChange={(event) => setForm({ ...form, party_size: Number(event.target.value) })} required />
            </label>
            <label>Planning style
              <select value={form.budget_style} onChange={(event) => setForm({ ...form, budget_style: event.target.value as TripPlanRequest["budget_style"] })}>
                <option value="value">Value-conscious</option>
                <option value="comfort">Comfort</option>
                <option value="premium">Premium style</option>
              </select>
            </label>
            <label>Language
              <select value={form.language} onChange={(event) => setForm({ ...form, language: event.target.value as "en" | "sw" })}>
                <option value="en">English</option>
                <option value="sw">Kiswahili</option>
              </select>
            </label>
          </div>
          <fieldset>
            <legend>What draws you to Tanzania?</legend>
            <div className="choice-grid">
              {interestOptions.map((interest) => {
                const selected = form.interests.includes(interest.value);
                return (
                  <button
                    key={interest.value}
                    className={selected ? "choice-button selected" : "choice-button"}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleInterest(interest.value)}
                  >
                    {selected && <Check size={15} />} {interest.label}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <label>Preferred region <span className="optional">optional</span>
            <input value={form.preferred_region ?? ""} onChange={(event) => setForm({ ...form, preferred_region: event.target.value || undefined })} placeholder="For example, Arusha or Zanzibar" />
          </label>
          <button className="button button-primary full-button" type="submit" disabled={planning}>
            <Sparkles size={18} /> {planning ? "Building your idea…" : "Build my trip idea"}
          </button>
        </form>

        <section className="chat-panel panel">
          <div className="panel-heading">
            <span className="step-dot"><Bot size={18} /></span>
            <div><h2>Ask the concierge</h2><p>Try “I want wildlife and mountains” or “Nataka kwenda pwani.”</p></div>
          </div>
          <div className="chat-window" aria-live="polite">
            <div className="chat-bubble assistant">
              <Bot size={18} />
              <p>Karibu! I can help you discover destinations already in SafariSmart&apos;s Tanzania catalog.</p>
            </div>
            {chatMessage && chat && <div className="chat-bubble traveler"><p>{chatMessage}</p></div>}
            {chat && (
              <div className="chat-bubble assistant">
                <Bot size={18} />
                <div>
                  <p>{chat.answer}</p>
                  {chat.safety_notice && <small>{chat.safety_notice}</small>}
                </div>
              </div>
            )}
          </div>
          <form className="chat-form" onSubmit={submitChat}>
            <label className="sr-only" htmlFor="chat-message">Message the concierge</label>
            <textarea id="chat-message" maxLength={500} rows={3} value={chatMessage} onChange={(event) => { setChatMessage(event.target.value); setChat(null); }} placeholder={form.language === "sw" ? "Niambie unapenda nini…" : "Tell me what you enjoy…"} />
            <button type="submit" aria-label="Send message" disabled={chatting || chatMessage.trim().length < 2}><Send size={18} /></button>
          </form>
          <p className="mode-note"><MessageCircle size={14} /> Responses are catalog-grounded and clearly labelled.</p>
        </section>
      </div>

      {error && <InlineError message={error} />}
      {plan && (
        <section className="plan-result" aria-live="polite">
          <div className="result-heading">
            <div>
              <span className="mode-badge">{plan.generation_mode === "local_ollama" ? "Local AI ranking" : "Reliable fallback mode"}</span>
              <h2>{plan.title}</h2>
              <p>{plan.summary}</p>
            </div>
            <Link className="button button-primary" to={`/booking?destination=${plan.destinations[0]?.id ?? ""}`}>Request operator review</Link>
          </div>
          <div className="itinerary-grid">
            {plan.itinerary.map((day) => (
              <article key={day.day}>
                <span>Day {String(day.day).padStart(2, "0")}</span>
                <h3>{day.destination_name}</h3>
                <p>{day.focus}</p>
              </article>
            ))}
          </div>
          <div className="plan-disclaimer"><strong>Planning boundary</strong><p>{plan.disclaimer}</p></div>
        </section>
      )}
    </div>
  );
}
