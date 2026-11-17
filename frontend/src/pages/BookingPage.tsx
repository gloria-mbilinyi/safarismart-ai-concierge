import { CalendarDays, CheckCircle2, LockKeyhole, Send, Users } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { InlineError, Loading } from "../components/Feedback";
import { minimumTravelDate } from "../lib/display";
import type { BookingAcknowledgement, BookingSubmission, Destination } from "../types";

export function BookingPage() {
  const [searchParams] = useSearchParams();
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BookingAcknowledgement | null>(null);
  const earliest = useMemo(() => minimumTravelDate(), []);
  const [form, setForm] = useState({
    destination_id: searchParams.get("destination") ?? "",
    travel_start_date: earliest,
    travel_end_date: earliest,
    party_size: 2,
    customer_name: "",
    customer_email: "",
    customer_phone: "",
    customer_contact_preference: "email" as "email" | "phone",
    special_requests: "",
    customer_consent: false,
  });

  useEffect(() => {
    api.destinations()
      .then((response) => {
        setDestinations(response.items);
        setForm((current) => ({ ...current, destination_id: current.destination_id || response.items[0]?.id || "" }));
      })
      .catch((reason: unknown) => setError(reason instanceof ApiError ? reason.message : "Could not load destinations"))
      .finally(() => setLoading(false));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.customer_consent) return;
    setSubmitting(true);
    setError("");
    const payload: BookingSubmission = {
      destination_id: form.destination_id,
      travel_start_date: form.travel_start_date,
      travel_end_date: form.travel_end_date,
      party_size: form.party_size,
      customer_name: form.customer_name,
      customer_contact_preference: form.customer_contact_preference,
      customer_consent: true,
      ...(form.customer_email ? { customer_email: form.customer_email } : {}),
      ...(form.customer_phone ? { customer_phone: form.customer_phone } : {}),
      ...(form.special_requests ? { special_requests: form.special_requests } : {}),
    };
    try {
      setResult(await api.submitBooking(payload, crypto.randomUUID()));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Your request could not be submitted. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="page-shell"><Loading label="Preparing the booking request" /></div>;
  if (result) {
    const destination = destinations.find((item) => item.id === result.destination_id);
    return (
      <div className="page-shell success-page">
        <div className="success-mark"><CheckCircle2 /></div>
        <span className="overline">Request received</span>
        <h1>Your next step is human review.</h1>
        <p>Keep this reference. It acknowledges your request; it is not a confirmed reservation.</p>
        <div className="reference-box">
          <small>Booking reference</small>
          <strong>{result.booking_reference}</strong>
          <span>{destination?.name ?? "Selected destination"} · {result.party_size} traveler(s)</span>
        </div>
        <div className="notice neutral"><LockKeyhole /><p>Customer status access is intentionally deferred until verified SMS or authenticated customer sessions are available.</p></div>
        <div className="hero-actions centered">
          <Link className="button button-primary" to="/destinations">Explore another place</Link>
          <Link className="button button-quiet" to="/">Back home</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell booking-page">
      <section className="page-intro compact-intro">
        <span className="overline">Operator-reviewed request</span>
        <h1>Turn your trip idea into a careful request.</h1>
        <p>We collect only what the demo workflow needs. Submitting does not reserve inventory or charge you.</p>
      </section>
      <div className="booking-layout">
        <form className="booking-form panel" onSubmit={submit}>
          <section>
            <div className="form-section-heading"><span>01</span><div><h2>Trip details</h2><p>Choose a destination and tentative dates.</p></div></div>
            <div className="form-grid two-columns">
              <label className="span-two">Destination
                <select value={form.destination_id} onChange={(event) => setForm({ ...form, destination_id: event.target.value })} required>
                  {destinations.map((destination) => <option key={destination.id} value={destination.id}>{destination.name} — {destination.region}</option>)}
                </select>
              </label>
              <label><CalendarDays size={16} /> Start date
                <input type="date" min={earliest} value={form.travel_start_date} onChange={(event) => setForm({ ...form, travel_start_date: event.target.value, travel_end_date: event.target.value > form.travel_end_date ? event.target.value : form.travel_end_date })} required />
              </label>
              <label><CalendarDays size={16} /> End date
                <input type="date" min={form.travel_start_date} value={form.travel_end_date} onChange={(event) => setForm({ ...form, travel_end_date: event.target.value })} required />
              </label>
              <label><Users size={16} /> Party size
                <input type="number" min="1" max="50" value={form.party_size} onChange={(event) => setForm({ ...form, party_size: Number(event.target.value) })} required />
              </label>
            </div>
          </section>
          <section>
            <div className="form-section-heading"><span>02</span><div><h2>How should we reach you?</h2><p>Your preferred channel must have a matching contact.</p></div></div>
            <div className="form-grid two-columns">
              <label className="span-two">Full name
                <input minLength={2} maxLength={150} value={form.customer_name} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} autoComplete="name" required />
              </label>
              <label>Email
                <input type="email" value={form.customer_email} onChange={(event) => setForm({ ...form, customer_email: event.target.value })} autoComplete="email" required={form.customer_contact_preference === "email"} />
              </label>
              <label>Phone <small>E.164, e.g. +255…</small>
                <input type="tel" pattern="\+[1-9][0-9]{7,14}" value={form.customer_phone} onChange={(event) => setForm({ ...form, customer_phone: event.target.value })} autoComplete="tel" required={form.customer_contact_preference === "phone"} />
              </label>
            </div>
            <fieldset>
              <legend>Preferred contact</legend>
              <div className="radio-row">
                {(["email", "phone"] as const).map((preference) => (
                  <label key={preference} className={form.customer_contact_preference === preference ? "radio-card selected" : "radio-card"}>
                    <input type="radio" name="contact" value={preference} checked={form.customer_contact_preference === preference} onChange={() => setForm({ ...form, customer_contact_preference: preference })} />
                    <span>{preference === "email" ? "Email" : "SMS / phone"}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label>Notes <span className="optional">optional</span>
              <textarea rows={4} maxLength={1000} value={form.special_requests} onChange={(event) => setForm({ ...form, special_requests: event.target.value })} placeholder="Accessibility needs, interests, or questions for the operator" />
            </label>
          </section>
          <label className="consent-box">
            <input type="checkbox" checked={form.customer_consent} onChange={(event) => setForm({ ...form, customer_consent: event.target.checked })} required />
            <span><strong>I consent to SafariSmart storing these details for this booking request.</strong> I understand this is not a confirmed reservation and the synthetic demo operator may contact me through my selected channel.</span>
          </label>
          {error && <InlineError message={error} />}
          <button className="button button-primary full-button" type="submit" disabled={submitting || !form.customer_consent || !form.destination_id}>
            <Send size={18} /> {submitting ? "Sending securely…" : "Submit booking request"}
          </button>
        </form>
        <aside className="booking-aside">
          <div className="aside-number">03</div>
          <h2>What happens next?</h2>
          <ol>
            <li><span>1</span><p><strong>Reference issued</strong>Your request begins as pending availability.</p></li>
            <li><span>2</span><p><strong>Operator review</strong>The assigned synthetic operator may quote or reject.</p></li>
            <li><span>3</span><p><strong>Auditable updates</strong>Each permitted status change is recorded.</p></li>
          </ol>
          <div className="notice"><LockKeyhole /><p>Never send payment details, passwords, or identity documents in the notes.</p></div>
        </aside>
      </div>
    </div>
  );
}
