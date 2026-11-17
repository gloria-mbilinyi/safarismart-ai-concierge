import {
  ArrowRight,
  Bot,
  CheckCircle2,
  MessageSquareText,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

const journey = [
  { icon: Search, title: "Discover", text: "Explore five curated Tanzania highlights with facts from the catalog." },
  { icon: Sparkles, title: "Shape your trip", text: "Turn days and interests into a grounded, clearly labelled trip idea." },
  { icon: Send, title: "Request", text: "Share contact details only with consent and receive a booking reference." },
  { icon: CheckCircle2, title: "Operator review", text: "A synthetic demo operator can quote or reject—never silently confirm." },
];

export function HomePage() {
  return (
    <>
      <section className="hero-section">
        <div className="hero-grid">
          <div className="hero-copy">
            <span className="overline"><span /> Tanzania, planned with clarity</span>
            <h1>Your safari idea,<br /><em>made navigable.</em></h1>
            <p className="hero-lead">
              Discover Tanzania in English or Kiswahili, build a grounded trip idea,
              and send one safe request to an operator for human review.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary" to="/planner">Plan my trip <ArrowRight size={18} /></Link>
              <Link className="button button-quiet" to="/destinations">Explore destinations</Link>
            </div>
            <div className="trust-line">
              <ShieldCheck size={19} />
              <span>No invented prices. No claim of live availability. Your consent is explicit.</span>
            </div>
          </div>
          <div className="hero-visual" aria-label="A stylized SafariSmart journey through Tanzania">
            <div className="route-line route-one" />
            <div className="route-line route-two" />
            <div className="visual-label label-north"><span /> Serengeti</div>
            <div className="visual-label label-mountain"><span /> Kilimanjaro</div>
            <div className="visual-label label-coast"><span /> Zanzibar</div>
            <div className="hero-compass"><Bot /><span>Grounded<br />concierge</span></div>
            <div className="hero-note">
              <MessageSquareText />
              <p><strong>“Nataka safari ya wanyama.”</strong><br />Try the bilingual concierge.</p>
            </div>
            <div className="landscape-layer layer-sun" />
            <div className="landscape-layer layer-mountain" />
            <div className="landscape-layer layer-plain" />
          </div>
        </div>
      </section>

      <section className="story-strip">
        <div><strong>5</strong><span>curated destinations</span></div>
        <div><strong>2</strong><span>concierge languages</span></div>
        <div><strong>3</strong><span>accessible channels</span></div>
        <div><strong>1</strong><span>auditable booking flow</span></div>
      </section>

      <section className="section journey-section">
        <div className="section-heading split-heading">
          <div>
            <span className="overline">From curiosity to review</span>
            <h2>A complete trip-request journey</h2>
          </div>
          <p>SafariSmart separates inspiration from commitment, so every important step is visible and reversible.</p>
        </div>
        <ol className="journey-list">
          {journey.map(({ icon: Icon, title, text }, index) => (
            <li key={title}>
              <span className="journey-number">0{index + 1}</span>
              <Icon />
              <h3>{title}</h3>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="section channel-section">
        <div className="channel-copy">
          <span className="overline light">Designed for reach</span>
          <h2>One tourism service, more than one kind of connection.</h2>
          <p>
            The web experience tells the full story. Africa&apos;s Talking SMS keeps consent-aware
            updates moving, while a read-only USSD flow supports destination discovery in English and Kiswahili.
          </p>
          <Link className="button button-sand" to="/destinations">See the catalog <ArrowRight size={18} /></Link>
        </div>
        <div className="channel-diagram" aria-label="Web, SMS and USSD connect to one booking workflow">
          <div className="channel-node central"><Bot /><span>SafariSmart<br /><small>API</small></span></div>
          <div className="channel-node web">Web</div>
          <div className="channel-node sms">SMS</div>
          <div className="channel-node ussd">USSD</div>
          <span className="connector connector-a" />
          <span className="connector connector-b" />
          <span className="connector connector-c" />
        </div>
      </section>

      <section className="section final-cta">
        <span className="overline">Start with what matters</span>
        <h2>How many days do you have?</h2>
        <p>Tell the concierge your interests. You&apos;ll get a transparent plan you can refine before sharing any personal details.</p>
        <Link className="button button-primary" to="/planner">Build a trip idea <ArrowRight size={18} /></Link>
      </section>
    </>
  );
}
