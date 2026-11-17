import type { Destination, PlanningMode, TripPlanRequest } from "../types";

export function selectionForMode(mode: PlanningMode, current: string[]): string[] {
  if (mode === "explore_tanzania") return [];
  if (mode === "single_destination") return current.slice(0, 1);
  return current.slice(0, 5);
}

export function toggleDestination(
  mode: PlanningMode,
  current: string[],
  destinationId: string,
): string[] {
  if (mode === "single_destination") return [destinationId];
  if (mode === "explore_tanzania") return [];
  if (current.includes(destinationId)) {
    return current.filter((id) => id !== destinationId);
  }
  return current.length < 5 ? [...current, destinationId] : current;
}

export function validatePlanSelection(request: TripPlanRequest): string {
  const count = request.destination_ids.length;
  if (request.planning_mode === "single_destination" && count !== 1) {
    return "Choose one destination for a single-destination plan.";
  }
  if (request.planning_mode === "multiple_destinations" && count < 2) {
    return "Choose at least two destinations for a multi-destination plan.";
  }
  if (request.planning_mode === "multiple_destinations" && count > request.days) {
    return "Choose no more destinations than the number of trip days.";
  }
  if (request.planning_mode === "explore_tanzania" && count > 0) {
    return "Explore Tanzania uses interests instead of fixed destination choices.";
  }
  return "";
}

export function filterDestinationOptions(
  destinations: Destination[],
  query: string,
): Destination[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return destinations;
  return destinations.filter((destination) =>
    [destination.name, destination.region, destination.category]
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalized),
  );
}
