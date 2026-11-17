import type { BookingStatus, DestinationCategory } from "../types";

export const categoryLabel: Record<DestinationCategory, string> = {
  beach: "Coast & island",
  conservation_area: "Conservation area",
  mountain: "Mountain",
  national_park: "National park",
};

export function formatStatus(status: BookingStatus): string {
  return status.replaceAll("_", " ");
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-TZ", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

export function minimumTravelDate(today = new Date()): string {
  const date = new Date(today);
  date.setDate(date.getDate() + 1);
  return date.toISOString().slice(0, 10);
}

export function safeReturnPath(value: string | null): string {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/operator";
}
