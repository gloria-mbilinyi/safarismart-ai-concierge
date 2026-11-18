import { ArrowUpRight, MapPin } from "lucide-react";
import { Link } from "react-router-dom";

import { categoryLabel } from "../lib/display";
import type { Destination } from "../types";
import { DestinationPhoto } from "./DestinationPhoto";

export function DestinationCard({ destination }: { destination: Destination }) {
  return (
    <article className="destination-card">
      <DestinationPhoto destination={destination} />
      <div className="destination-card-body">
        <div className="eyebrow-row">
          <span className="category-chip">{categoryLabel[destination.category]}</span>
          <span className="region"><MapPin size={14} /> {destination.region}</span>
        </div>
        <h3>{destination.name}</h3>
        <p>{destination.description}</p>
        <div className="card-actions">
          <Link to={`/booking?destination=${destination.id}`}>Request booking <ArrowUpRight size={16} /></Link>
          <Link className="text-link" to="/planner">Add to a plan</Link>
        </div>
      </div>
    </article>
  );
}
