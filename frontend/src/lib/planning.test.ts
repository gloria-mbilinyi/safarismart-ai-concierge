import { describe, expect, it } from "vitest";

import {
  filterDestinationOptions,
  selectionForMode,
  toggleDestination,
  validatePlanSelection,
} from "./planning";
import type { Destination, TripPlanRequest } from "../types";

const destinations: Destination[] = [
  {
    id: "zanzibar-id",
    name: "Zanzibar",
    slug: "zanzibar",
    country: "Tanzania",
    region: "Zanzibar",
    category: "beach",
    description: "Coastal catalog record",
    is_featured: true,
  },
  {
    id: "serengeti-id",
    name: "Serengeti National Park",
    slug: "serengeti-national-park",
    country: "Tanzania",
    region: "Mara",
    category: "national_park",
    description: "Wildlife catalog record",
    is_featured: true,
  },
];

const request: TripPlanRequest = {
  days: 5,
  party_size: 2,
  interests: ["nature"],
  budget_style: "comfort",
  planning_mode: "single_destination",
  destination_ids: [],
  language: "en",
};

describe("trip-planning selection helpers", () => {
  it("clears fixed destinations when switching to Explore Tanzania", () => {
    expect(selectionForMode("explore_tanzania", ["zanzibar-id"])).toEqual([]);
  });

  it("keeps exactly one destination in single mode", () => {
    expect(toggleDestination("single_destination", [], "zanzibar-id")).toEqual([
      "zanzibar-id",
    ]);
  });

  it("validates missing and over-ambitious explicit selections", () => {
    expect(validatePlanSelection(request)).toContain("Choose one destination");
    expect(validatePlanSelection({
      ...request,
      days: 1,
      planning_mode: "multiple_destinations",
      destination_ids: ["zanzibar-id", "serengeti-id"],
    })).toContain("number of trip days");
  });

  it("searches current database options by region and category", () => {
    expect(filterDestinationOptions(destinations, "Mara")[0]?.id).toBe("serengeti-id");
    expect(filterDestinationOptions(destinations, "beach")[0]?.id).toBe("zanzibar-id");
  });
});
