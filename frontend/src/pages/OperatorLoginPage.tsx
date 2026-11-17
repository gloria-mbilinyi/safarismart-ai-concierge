import { KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api, ApiError } from "../api";
import { InlineError } from "../components/Feedback";
import { safeReturnPath } from "../lib/display";
import { useAuth } from "../state/AuthContext";

export function OperatorLoginPage() {
  const { token, setToken } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (token) navigate("/operator", { replace: true });
  }, [navigate, token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await api.login(email, password);
      setToken(response.access_token);
      const params = new URLSearchParams(location.search);
      navigate(safeReturnPath(params.get("returnTo")), { replace: true });
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Sign-in is unavailable. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="operator-login-page">
      <section className="login-context">
        <span className="overline light">Protected operator workspace</span>
        <h1>Review requests with context—and accountability.</h1>
        <p>Every booking is scoped to its assigned organization. Every permitted decision adds an audit event.</p>
        <ul>
          <li><ShieldCheck /><span>Organization-scoped access</span></li>
          <li><KeyRound /><span>Short-lived signed sessions</span></li>
          <li><LockKeyhole /><span>No public operator registration</span></li>
        </ul>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <span className="login-icon"><KeyRound /></span>
          <h2>Operator sign in</h2>
          <p>Use credentials created locally with the demo bootstrap command.</p>
          <label>Email address
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required />
          </label>
          <label>Password
            <input type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
          </label>
          {error && <InlineError message={error} />}
          <button className="button button-primary full-button" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Continue securely"}
          </button>
          <small>Credentials are never included in frontend source or documentation.</small>
        </form>
      </section>
    </div>
  );
}
