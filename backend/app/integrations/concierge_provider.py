"""Optional local-model adapter constrained to ranking known catalog slugs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


class ConciergeProviderError(RuntimeError):
    """Raised when an optional provider cannot return a safe ranking."""


class DestinationRankingProvider(Protocol):
    """Provider boundary that cannot introduce destination facts or prose."""

    mode: str

    def rank_slugs(
        self,
        *,
        allowed_slugs: list[str],
        interests: list[str],
        preferred_region: str | None,
    ) -> list[str]:
        """Return a permutation or subset of the supplied catalog slugs."""


@dataclass(frozen=True, slots=True)
class OllamaDestinationRankingProvider:
    """Use Ollama only to rank identifiers already supplied by SafariSmart."""

    base_url: str
    model: str
    timeout_seconds: float
    mode: str = "local_ollama"

    def rank_slugs(
        self,
        *,
        allowed_slugs: list[str],
        interests: list[str],
        preferred_region: str | None,
    ) -> list[str]:
        """Request strict JSON and reject every unknown or malformed identifier."""

        prompt = (
            "Rank only the destination slugs in ALLOWED_SLUGS for the supplied "
            "travel interests. Return JSON only in this exact form: "
            '{"slugs":["slug"]}. Do not add facts, prose, or new slugs.\n'
            f"ALLOWED_SLUGS={json.dumps(allowed_slugs)}\n"
            f"INTERESTS={json.dumps(interests)}\n"
            f"PREFERRED_REGION={json.dumps(preferred_region)}"
        )
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "num_predict": 120},
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                provider_payload = json.loads(response.read().decode("utf-8"))
            ranking_payload = json.loads(provider_payload["response"])
            ranked_slugs = ranking_payload["slugs"]
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ConciergeProviderError("Local model ranking failed") from error

        allowed = set(allowed_slugs)
        if (
            not isinstance(ranked_slugs, list)
            or not ranked_slugs
            or any(not isinstance(slug, str) or slug not in allowed for slug in ranked_slugs)
            or len(set(ranked_slugs)) != len(ranked_slugs)
        ):
            raise ConciergeProviderError("Local model returned an unsafe ranking")
        return ranked_slugs


def build_ranking_provider(
    settings: Settings,
) -> DestinationRankingProvider | None:
    """Construct the configured optional provider; fallback mode uses no network."""

    if settings.ai_provider == "fallback":
        return None
    return OllamaDestinationRankingProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
