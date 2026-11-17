import type {
  BookingAcknowledgement,
  BookingSubmission,
  ChatResponse,
  ChatContextMessage,
  DestinationList,
  OperatorBookingDetail,
  OperatorBookingList,
  OperatorIdentity,
  TripPlan,
  TripPlanRequest,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof URLSearchParams)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg: string }> };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail)) {
        message = payload.detail.map((item) => item.msg).join(". ");
      }
    } catch {
      // Preserve the status-based message when the server does not return JSON.
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  destinations(query = "", category = "") {
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    if (category) params.set("category", category);
    return request<DestinationList>(`/destinations?${params}`);
  },
  plan(payload: TripPlanRequest) {
    return request<TripPlan>("/concierge/plan", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  chat(message: string, language: "en" | "sw", history: ChatContextMessage[] = []) {
    return request<ChatResponse>("/concierge/chat", {
      method: "POST",
      body: JSON.stringify({ message, language, history }),
    });
  },
  submitBooking(payload: BookingSubmission, idempotencyKey: string) {
    return request<BookingAcknowledgement>("/bookings", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    });
  },
  async login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password });
    return request<{ access_token: string; token_type: "bearer"; expires_in: number }>(
      "/auth/token",
      { method: "POST", body },
    );
  },
  operatorMe(token: string) {
    return request<OperatorIdentity>("/operator/me", {}, token);
  },
  operatorBookings(token: string) {
    return request<OperatorBookingList>("/operator/bookings?limit=100", {}, token);
  },
  operatorBooking(token: string, reference: string) {
    return request<OperatorBookingDetail>(`/operator/bookings/${reference}`, {}, token);
  },
  quoteBooking(
    token: string,
    reference: string,
    payload: { amount_minor: number; currency: string; expires_at: string; terms?: string },
  ) {
    return request<OperatorBookingDetail>(`/operator/bookings/${reference}/quote`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  },
  decideBooking(token: string, reference: string, action: "reject" | "confirm", reason: string) {
    return request<OperatorBookingDetail>(`/operator/bookings/${reference}/${action}`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }, token);
  },
};
