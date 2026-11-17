import { Menu, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { Brand } from "./Brand";

const links = [
  ["Discover", "/destinations"],
  ["Plan with AI", "/planner"],
  ["Request booking", "/booking"],
] as const;

export function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <div className="header-inner">
          <Brand />
          <button
            className="menu-button"
            type="button"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X /> : <Menu />}
          </button>
          <nav className={open ? "site-nav is-open" : "site-nav"} aria-label="Primary">
            {links.map(([label, path]) => (
              <NavLink key={path} to={path} onClick={() => setOpen(false)}>{label}</NavLink>
            ))}
            <NavLink className="operator-link" to="/operator" onClick={() => setOpen(false)}>
              Operator portal
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="main">{children}</main>
      <footer className="site-footer">
        <div className="footer-grid">
          <div>
            <Brand />
            <p>Thoughtful Tanzania discovery across web, SMS, and USSD.</p>
          </div>
          <div>
            <strong>Hackathon MVP</strong>
            <p>Built for Africa&apos;s Talking Open Hackathon 2026 by Gloria Beneth Mbilinyi.</p>
          </div>
          <div>
            <strong>Important</strong>
            <p>Plans and demo quotes are not live availability or confirmed reservations.</p>
          </div>
        </div>
        <div className="footer-bottom">© 2026 SafariSmart · Tanzania-focused, consent-aware travel planning</div>
      </footer>
    </div>
  );
}
