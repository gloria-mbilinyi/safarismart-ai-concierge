export type DestinationCategory =
  | "beach"
  | "conservation_area"
  | "mountain"
  | "national_park";

export interface Destination {
  id: string;
  name: string;
  slug: string;
  country: string;
  region: string;
  category: DestinationCategory;
  description: string;
  is_featured: boolean;
}

export interface DestinationList {
  items: Destination[];
  total: number;
  limit: number;
  offset: number;
}

export type TravelInterest =
  | "wildlife"
  | "beach"
  | "mountain"
  | "culture"
  | "nature";

export interface TripPlanRequest {
  days: number;
  party_size: number;
  interests: TravelInterest[];
  budget_style: "value" | "comfort" | "premium";
  preferred_region?: string;
  language: "en" | "sw";
}

export interface PlanDestination extends Pick<Destination, "id" | "name" | "slug" | "region" | "category" | "description"> {
  match_reasons: string[];
}

export interface TripPlan {
  generation_mode: "rule_based_fallback" | "local_ollama";
  title: string;
  summary: string;
  destinations: PlanDestination[];
  itinerary: Array<{
    day: number;
    title: string;
    destination_id: string;
    destination_name: string;
    focus: string;
  }>;
  disclaimer: string;
}

export interface ChatResponse {
  generation_mode: "rule_based_fallback" | "local_ollama";
  answer: string;
  referenced_destinations: PlanDestination[];
  safety_notice: string | null;
}

export interface BookingSubmission {
  destination_id: string;
  travel_start_date: string;
  travel_end_date: string;
  party_size: number;
  customer_name: string;
  customer_email?: string;
  customer_phone?: string;
  customer_contact_preference: "email" | "phone";
  customer_consent: true;
  special_requests?: string;
}

export interface BookingAcknowledgement {
  booking_reference: string;
  status: BookingStatus;
  destination_id: string;
  travel_start_date: string;
  travel_end_date: string;
  party_size: number;
  created_at: string;
}

export type BookingStatus =
  | "draft"
  | "pending_availability"
  | "quoted"
  | "pending_confirmation"
  | "confirmed"
  | "rejected"
  | "expired"
  | "cancelled";

export interface OperatorIdentity {
  id: string;
  email: string;
  full_name: string;
  operator: { id: string; name: string; slug: string; is_demo: boolean };
}

export interface OperatorBookingSummary {
  booking_reference: string;
  status: BookingStatus;
  destination: { id: string; name: string; region: string };
  travel_start_date: string;
  travel_end_date: string;
  party_size: number;
  created_at: string;
  updated_at: string;
}

export interface OperatorBookingList {
  items: OperatorBookingSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface OperatorBookingDetail extends OperatorBookingSummary {
  customer_name: string;
  customer_email: string | null;
  customer_phone: string | null;
  customer_contact_preference: string;
  customer_consent: boolean;
  special_requests: string | null;
  status_history: Array<{
    from_status: BookingStatus | null;
    to_status: BookingStatus;
    actor_type: "customer" | "operator" | "system";
    reason: string | null;
    occurred_at: string;
  }>;
  quote: null | {
    id: string;
    amount_minor: number;
    currency: string;
    expires_at: string;
    terms: string | null;
    is_demo: boolean;
    disclaimer: string;
  };
  reservation_disclaimer: string;
}
