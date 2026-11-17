import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  LogOut,
  RefreshCw,
  Send,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api";
import { InlineError, Loading } from "../components/Feedback";
import { StatusPill } from "../components/StatusPill";
import { formatDate } from "../lib/display";
import { useAuth } from "../state/AuthContext";
import type { OperatorBookingDetail, OperatorBookingSummary, OperatorIdentity } from "../types";

function defaultQuoteExpiry(travelStartDate: string): string {
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const travelStart = new Date(`${travelStartDate}T00:00:00Z`);
  const expiry = tomorrow < travelStart ? tomorrow : new Date(travelStart.getTime() - 60 * 60 * 1000);
  return expiry.toISOString();
}

export function OperatorDashboardPage() {
  const { token, signOut } = useAuth();
  const navigate = useNavigate();
  const [identity, setIdentity] = useState<OperatorIdentity | null>(null);
  const [bookings, setBookings] = useState<OperatorBookingSummary[]>([]);
  const [selected, setSelected] = useState<OperatorBookingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [amount, setAmount] = useState("750000");
  const [terms, setTerms] = useState("Synthetic demonstration quote for hackathon workflow testing only.");
  const [reason, setReason] = useState("");

  const handleError = useCallback((reason: unknown) => {
    if (reason instanceof ApiError && reason.status === 401) {
      signOut();
      navigate("/operator/login", { replace: true });
      return;
    }
    setError(reason instanceof ApiError ? reason.message : "The operator workspace could not be loaded.");
  }, [navigate, signOut]);

  const loadDashboard = useCallback(async () => {
    if (!token) {
      navigate("/operator/login?returnTo=/operator", { replace: true });
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [profile, queue] = await Promise.all([api.operatorMe(token), api.operatorBookings(token)]);
      setIdentity(profile);
      setBookings(queue.items);
    } catch (reason) {
      handleError(reason);
    } finally {
      setLoading(false);
    }
  }, [handleError, navigate, token]);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  async function openBooking(reference: string) {
    if (!token) return;
    setError("");
    setNotice("");
    try {
      setSelected(await api.operatorBooking(token, reference));
      setReason("");
    } catch (reason) {
      handleError(reason);
    }
  }

  async function quote(event: FormEvent) {
    event.preventDefault();
    if (!token || !selected) return;
    setActionLoading(true);
    setError("");
    try {
      const updated = await api.quoteBooking(token, selected.booking_reference, {
        amount_minor: Number(amount),
        currency: "TZS",
        expires_at: defaultQuoteExpiry(selected.travel_start_date),
        terms,
      });
      setSelected(updated);
      setNotice("Synthetic quote created and audit history updated.");
      await loadDashboard();
    } catch (reason) {
      handleError(reason);
    } finally {
      setActionLoading(false);
    }
  }

  async function decide(action: "reject" | "confirm") {
    if (!token || !selected || reason.trim().length < 3) return;
    setActionLoading(true);
    setError("");
    try {
      const updated = await api.decideBooking(token, selected.booking_reference, action, reason);
      setSelected(updated);
      setNotice(action === "reject" ? "Request rejected with an audit reason." : "Demo booking status confirmed with an audit reason.");
      await loadDashboard();
    } catch (decisionError) {
      handleError(decisionError);
    } finally {
      setActionLoading(false);
    }
  }

  function logout() {
    signOut();
    navigate("/operator/login", { replace: true });
  }

  if (!token || loading) return <div className="page-shell"><Loading label="Opening the protected operator workspace" /></div>;

  return (
    <div className="operator-page">
      <header className="operator-header">
        <div>
          <span className="overline">Operator workspace</span>
          <h1>{identity?.operator.name ?? "Assigned operator"}</h1>
          <p>{identity?.full_name} · {identity?.email}</p>
        </div>
        <div className="operator-header-actions">
          {identity?.operator.is_demo && <span className="demo-badge"><ShieldAlert size={15} /> Synthetic demo organization</span>}
          <button className="icon-button" type="button" onClick={() => void loadDashboard()} aria-label="Refresh bookings"><RefreshCw size={18} /></button>
          <button className="button button-quiet" type="button" onClick={logout}><LogOut size={17} /> Sign out</button>
        </div>
      </header>

      {error && <InlineError message={error} />}
      {notice && <div className="success-notice" role="status"><CheckCircle2 /> {notice}</div>}

      {!selected ? (
        <section className="operator-queue">
          <div className="queue-heading">
            <div><h2>Assigned booking requests</h2><p>Only requests scoped to this organization appear here.</p></div>
            <span>{bookings.length} total</span>
          </div>
          <div className="booking-table" role="table" aria-label="Assigned booking requests">
            <div className="booking-row table-head" role="row">
              <span>Reference</span><span>Destination</span><span>Travel</span><span>Party</span><span>Status</span><span />
            </div>
            {bookings.map((booking) => (
              <div className="booking-row" role="row" key={booking.booking_reference}>
                <strong>{booking.booking_reference}</strong>
                <span>{booking.destination.name}<small>{booking.destination.region}</small></span>
                <span>{formatDate(booking.travel_start_date)}<small>to {formatDate(booking.travel_end_date)}</small></span>
                <span><Users size={15} /> {booking.party_size}</span>
                <StatusPill status={booking.status} />
                <button type="button" onClick={() => void openBooking(booking.booking_reference)}>Review</button>
              </div>
            ))}
            {!bookings.length && <div className="empty-state">No assigned requests yet. Submit a public booking request for a destination linked to this demo operator.</div>}
          </div>
        </section>
      ) : (
        <section className="booking-detail">
          <button className="back-button" type="button" onClick={() => { setSelected(null); setNotice(""); }}><ArrowLeft /> Back to queue</button>
          <div className="detail-title">
            <div><span>{selected.booking_reference}</span><h2>{selected.destination.name}</h2><p>{selected.destination.region}</p></div>
            <StatusPill status={selected.status} />
          </div>
          <div className="detail-grid">
            <div className="detail-main">
              <article className="detail-section">
                <h3>Trip & customer</h3>
                <dl className="detail-list">
                  <div><dt><CalendarDays /> Dates</dt><dd>{formatDate(selected.travel_start_date)} – {formatDate(selected.travel_end_date)}</dd></div>
                  <div><dt><Users /> Party</dt><dd>{selected.party_size} traveler(s)</dd></div>
                  <div><dt>Customer</dt><dd>{selected.customer_name}</dd></div>
                  <div><dt>Preferred contact</dt><dd>{selected.customer_contact_preference === "email" ? selected.customer_email : selected.customer_phone}</dd></div>
                  <div className="full-definition"><dt>Notes</dt><dd>{selected.special_requests || "No special requests supplied."}</dd></div>
                </dl>
              </article>
              <article className="detail-section">
                <h3>Audit trail</h3>
                <ol className="audit-list">
                  {selected.status_history.map((event, index) => (
                    <li key={`${event.occurred_at}-${index}`}>
                      <span />
                      <div><strong>{event.to_status.replaceAll("_", " ")}</strong><p>{event.reason || `Recorded by ${event.actor_type}`}</p><small>{new Date(event.occurred_at).toLocaleString("en-TZ")}</small></div>
                    </li>
                  ))}
                </ol>
              </article>
            </div>
            <aside className="decision-panel">
              <h3>Permitted action</h3>
              <p>Actions are checked again by the server&apos;s state machine and organization scope.</p>
              {selected.status === "pending_availability" && (
                <>
                  <form onSubmit={quote}>
                    <label>Demo quote amount (TZS)
                      <input type="number" min="1" max="1000000000" value={amount} onChange={(event) => setAmount(event.target.value)} required />
                    </label>
                    <label>Demo terms
                      <textarea rows={3} maxLength={2000} value={terms} onChange={(event) => setTerms(event.target.value)} />
                    </label>
                    <button className="button button-primary full-button" type="submit" disabled={actionLoading}><CircleDollarSign /> Create synthetic quote</button>
                  </form>
                  <div className="decision-divider"><span>or</span></div>
                </>
              )}
              {(selected.status === "pending_availability" || selected.status === "pending_confirmation") && (
                <>
                  <label>Decision reason
                    <textarea rows={3} minLength={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required for an auditable decision" />
                  </label>
                  <div className="decision-buttons">
                    {selected.status === "pending_confirmation" && <button className="button button-primary" type="button" disabled={actionLoading || reason.trim().length < 3} onClick={() => void decide("confirm")}><CheckCircle2 /> Confirm demo status</button>}
                    <button className="button danger-button" type="button" disabled={actionLoading || reason.trim().length < 3} onClick={() => void decide("reject")}><XCircle /> Reject request</button>
                  </div>
                </>
              )}
              {selected.quote && (
                <div className="quote-summary">
                  <small>Synthetic quote</small>
                  <strong>{new Intl.NumberFormat("en-TZ", { style: "currency", currency: selected.quote.currency, maximumFractionDigits: 0 }).format(selected.quote.amount_minor)}</strong>
                  <p>{selected.quote.disclaimer}</p>
                </div>
              )}
              {!["pending_availability", "pending_confirmation"].includes(selected.status) && !selected.quote && (
                <div className="notice neutral"><Send /><p>No operator action is available from this state.</p></div>
              )}
              <small className="reservation-warning">{selected.reservation_disclaimer}</small>
            </aside>
          </div>
        </section>
      )}
    </div>
  );
}
