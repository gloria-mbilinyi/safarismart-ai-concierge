import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

export function Brand() {
  return (
    <Link className="brand" to="/" aria-label="SafariSmart home">
      <span className="brand-mark"><Compass size={21} strokeWidth={2.2} /></span>
      <span>
        <strong>SafariSmart</strong>
        <small>AI Concierge</small>
      </span>
    </Link>
  );
}
