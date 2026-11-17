import { AlertCircle, LoaderCircle } from "lucide-react";

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" /> {label}</div>;
}

export function InlineError({ message }: { message: string }) {
  return <div className="inline-error" role="alert"><AlertCircle /> <span>{message}</span></div>;
}
