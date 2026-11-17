import { Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "../api";
import { DestinationCard } from "../components/DestinationCard";
import { InlineError, Loading } from "../components/Feedback";
import type { Destination, DestinationCategory } from "../types";

const filters: Array<{ value: "" | DestinationCategory; label: string }> = [
  { value: "", label: "All places" },
  { value: "national_park", label: "National parks" },
  { value: "conservation_area", label: "Conservation" },
  { value: "mountain", label: "Mountains" },
  { value: "beach", label: "Coast & islands" },
];

export function DestinationsPage() {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<"" | DestinationCategory>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      api.destinations(query, category)
        .then((result) => setDestinations(result.items))
        .catch((reason: unknown) => setError(reason instanceof ApiError ? reason.message : "Could not load destinations"))
        .finally(() => setLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [query, category]);

  return (
    <div className="page-shell">
      <section className="page-intro destination-intro">
        <span className="overline">Curated Tanzania catalog</span>
        <h1>Find the landscape that fits your story.</h1>
        <p>Each description comes from SafariSmart&apos;s maintained catalog. Listings do not imply a partnership, price, or live availability.</p>
      </section>
      <section className="catalog-controls" aria-label="Destination filters">
        <label className="search-field">
          <Search size={18} />
          <span className="sr-only">Search destinations</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name, region, or landscape" />
        </label>
        <div className="filter-row">
          <SlidersHorizontal size={18} aria-hidden="true" />
          {filters.map((filter) => (
            <button
              key={filter.value || "all"}
              type="button"
              className={category === filter.value ? "filter-chip active" : "filter-chip"}
              onClick={() => setCategory(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </section>
      {loading && <Loading label="Loading the destination catalog" />}
      {error && <InlineError message={error} />}
      {!loading && !error && (
        <section className="catalog-grid" aria-live="polite">
          {destinations.map((destination) => <DestinationCard key={destination.id} destination={destination} />)}
          {!destinations.length && <p className="empty-state">No destinations match those filters. Try a broader search.</p>}
        </section>
      )}
    </div>
  );
}
