import { Check, MapPin, Search, Sparkles, WandSparkles } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api";
import { ConciergeChat } from "../components/ConciergeChat";
import { InlineError, Loading } from "../components/Feedback";
import {
  filterDestinationOptions,
  selectionForMode,
  toggleDestination,
  validatePlanSelection,
} from "../lib/planning";
import type {
  Destination,
  PlanningMode,
  TravelInterest,
  TripPlan,
  TripPlanRequest,
} from "../types";

const interestOptions: Array<{ value: TravelInterest; label: string }> = [
  { value: "wildlife", label: "Wildlife" },
  { value: "beach", label: "Coast" },
  { value: "mountain", label: "Mountains" },
  { value: "culture", label: "Culture" },
  { value: "nature", label: "Nature" },
];

const planningModes: Array<{
  value: PlanningMode;
  label: string;
  description: string;
}> = [
  {
    value: "single_destination",
    label: "Single destination",
    description: "Keep every day focused on one place.",
  },
  {
    value: "multiple_destinations",
    label: "Multiple destinations",
    description: "Use only the places you explicitly select.",
  },
  {
    value: "explore_tanzania",
    label: "Explore Tanzania",
    description: "Let interests and region guide catalog recommendations.",
  },
];

export function PlannerPage() {
  const [form, setForm] = useState<TripPlanRequest>({
    days: 5,
    party_size: 2,
    interests: ["wildlife"],
    budget_style: "comfort",
    budget_tzs: 2_500_000,
    planning_mode: "explore_tanzania",
    destination_ids: [],
    language: "en",
  });
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [destinationQuery, setDestinationQuery] = useState("");
  const [destinationsLoading, setDestinationsLoading] = useState(true);
  const [destinationsError, setDestinationsError] = useState("");
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState("");
  const filteredDestinations = useMemo(
    () => filterDestinationOptions(destinations, destinationQuery),
    [destinations, destinationQuery],
  );

  useEffect(() => {
    api.destinations()
      .then((response) => setDestinations(response.items))
      .catch((reason: unknown) => setDestinationsError(
        reason instanceof ApiError ? reason.message : "Could not load destination choices.",
      ))
      .finally(() => setDestinationsLoading(false));
  }, []);

  function toggleInterest(interest: TravelInterest) {
    setForm((current) => {
      const selected = current.interests.includes(interest)
        ? current.interests.filter((item) => item !== interest)
        : [...current.interests, interest];
      return { ...current, interests: selected.length ? selected : [interest] };
    });
  }

  function choosePlanningMode(mode: PlanningMode) {
    setError("");
    setForm((current) => ({
      ...current,
      planning_mode: mode,
      destination_ids: selectionForMode(mode, current.destination_ids),
      preferred_region: mode === "explore_tanzania" ? current.preferred_region : undefined,
    }));
  }

  function chooseDestination(destinationId: string) {
    setError("");
    setForm((current) => ({
      ...current,
      destination_ids: toggleDestination(
        current.planning_mode,
        current.destination_ids,
        destinationId,
      ),
    }));
  }

  async function submitPlan(event: FormEvent) {
    event.preventDefault();
    const selectionError = validatePlanSelection(form);
    if (selectionError) {
      setError(selectionError);
      return;
    }
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
            <label>Total budget (TZS) <span className="optional">planning context</span>
              <input
                type="number"
                min="100000"
                max="100000000"
                step="50000"
                value={form.budget_tzs ?? ""}
                onChange={(event) => setForm({
                  ...form,
                  budget_tzs: event.target.value ? Number(event.target.value) : undefined,
                })}
                placeholder="2500000"
              />
            </label>
            <label>Language
              <select value={form.language} onChange={(event) => setForm({ ...form, language: event.target.value as "en" | "sw" })}>
                <option value="en">English</option>
                <option value="sw">Kiswahili</option>
              </select>
            </label>
          </div>
          <fieldset className="planning-mode-fieldset">
            <legend>How should destinations be chosen?</legend>
            <div className="planning-mode-grid">
              {planningModes.map((mode) => (
                <label
                  key={mode.value}
                  className={form.planning_mode === mode.value ? "planning-mode-card selected" : "planning-mode-card"}
                >
                  <input
                    type="radio"
                    name="planning-mode"
                    value={mode.value}
                    checked={form.planning_mode === mode.value}
                    onChange={() => choosePlanningMode(mode.value)}
                  />
                  <span><strong>{mode.label}</strong><small>{mode.description}</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          {form.planning_mode !== "explore_tanzania" && (
            <fieldset className="destination-picker">
              <legend>
                {form.planning_mode === "single_destination" ? "Choose one destination" : "Choose two or more destinations"}
              </legend>
              <label className="destination-search">
                <Search size={16} aria-hidden="true" />
                <span className="sr-only">Search destination choices</span>
                <input
                  type="search"
                  value={destinationQuery}
                  onChange={(event) => setDestinationQuery(event.target.value)}
                  placeholder="Search by place, region, or landscape"
                />
              </label>
              {destinationsLoading && <Loading label="Loading destination choices" />}
              {destinationsError && <InlineError message={destinationsError} />}
              {!destinationsLoading && !destinationsError && (
                <div className="destination-option-grid" role="group" aria-label="Destination choices">
                  {filteredDestinations.map((destination) => {
                    const selected = form.destination_ids.includes(destination.id);
                    return (
                      <label
                        key={destination.id}
                        className={selected ? "destination-option selected" : "destination-option"}
                      >
                        <input
                          type={form.planning_mode === "single_destination" ? "radio" : "checkbox"}
                          name={form.planning_mode === "single_destination" ? "destination" : undefined}
                          checked={selected}
                          onChange={() => chooseDestination(destination.id)}
                        />
                        <span>
                          <strong>{destination.name}</strong>
                          <small><MapPin size={12} /> {destination.region} · {destination.category.replaceAll("_", " ")}</small>
                        </span>
                      </label>
                    );
                  })}
                  {!filteredDestinations.length && (
                    <p className="empty-state">No current catalog destination matches that search.</p>
                  )}
                </div>
              )}
              <p className="selection-guidance">
                {form.destination_ids.length} selected
                {form.planning_mode === "multiple_destinations" ? " · maximum five and no more than your trip days" : ""}
              </p>
            </fieldset>
          )}
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
          {form.planning_mode === "explore_tanzania" && (
            <label>Preferred region <span className="optional">optional; used only for Explore Tanzania</span>
              <input value={form.preferred_region ?? ""} onChange={(event) => setForm({ ...form, preferred_region: event.target.value || undefined })} placeholder="For example, Arusha or Zanzibar" />
            </label>
          )}
          <button className="button button-primary full-button" type="submit" disabled={planning}>
            <Sparkles size={18} /> {planning ? "Building your idea…" : "Build my trip idea"}
          </button>
        </form>

        <ConciergeChat />
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
            {plan.destinations.length === 1 && (
              <Link className="button button-primary" to={`/booking?destination=${plan.destinations[0].id}`}>Request operator review</Link>
            )}
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
          {plan.destinations.length > 1 && (
            <div className="plan-booking-options" aria-label="Booking-request destination choices">
              <strong>Continue with one destination</strong>
              <div>
                {plan.destinations.map((destination) => (
                  <Link key={destination.id} className="button button-quiet" to={`/booking?destination=${destination.id}`}>
                    Request {destination.name}
                  </Link>
                ))}
              </div>
            </div>
          )}
          <div className="plan-disclaimer"><strong>Planning boundary</strong><p>{plan.disclaimer}</p></div>
        </section>
      )}
    </div>
  );
}
