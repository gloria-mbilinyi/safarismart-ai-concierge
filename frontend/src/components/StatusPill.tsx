import { formatStatus } from "../lib/display";
import type { BookingStatus } from "../types";

export function StatusPill({ status }: { status: BookingStatus }) {
  return <span className={`status-pill status-${status}`}>{formatStatus(status)}</span>;
}
