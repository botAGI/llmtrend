"""Ollama integration for AI-powered trend analysis.

Provides the :class:`LLMAnalyzer` facade that communicates with a local Ollama
instance for niche classification, weekly insight generation, signal
explanation, and ad-hoc Q&A.  Every public method degrades gracefully when
Ollama is disabled or unreachable -- the application never crashes due to LLM
unavailability.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from app.config import get_settings

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LLMAnalyzer:
    """Interface to Ollama for AI-powered trend analysis.

    All network calls use ``httpx.AsyncClient`` and honour the configured
    timeout.  If ``OLLAMA_ENABLED`` is ``False`` or the server is unreachable,
    every method returns a deterministic fallback rather than raising.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url: str = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model: str = model or settings.OLLAMA_MODEL
        self.enabled: bool = settings.OLLAMA_ENABLED
        self.timeout: int = settings.OLLAMA_TIMEOUT
        self.temperature: float = settings.OLLAMA_TEMPERATURE

    # ------------------------------------------------------------------
    # Health / availability
    # ------------------------------------------------------------------

    async def is_available(self) -> bool:
        """Check whether Ollama is reachable and has the configured model.

        Returns:
            ``True`` if the server responds and lists the configured model,
            ``False`` on any error.
        """
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                models: list[dict[str, Any]] = data.get("models", [])
                model_names: list[str] = [
                    m.get("name", "") for m in models
                ]
                # Match with or without tag suffix (e.g. "llama3.1:8b" matches "llama3.1:8b")
                available = any(
                    self.model == name or self.model == name.split(":")[0]
                    for name in model_names
                )
                log.debug("ollama_availability_check", available=available, models=model_names)
                return available
        except Exception as exc:
            log.warning("ollama_unavailable", error=str(exc))
            return False

    async def get_status(self) -> dict[str, Any]:
        """Get Ollama status information.

        Returns:
            A dict with ``available`` (bool), ``model`` (configured model name),
            ``models_available`` (list of model names on server), and
            ``models_running`` (list of currently loaded models).
        """
        status: dict[str, Any] = {
            "available": False,
            "enabled": self.enabled,
            "model": self.model,
            "models_available": [],
            "models_running": [],
        }

        if not self.enabled:
            return status

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Fetch available models
                tags_resp = await client.get(f"{self.base_url}/api/tags")
                tags_resp.raise_for_status()
                tags_data: dict[str, Any] = tags_resp.json()
                status["models_available"] = [
                    m.get("name", "") for m in tags_data.get("models", [])
                ]

                # Fetch running models
                ps_resp = await client.get(f"{self.base_url}/api/ps")
                ps_resp.raise_for_status()
                ps_data: dict[str, Any] = ps_resp.json()
                status["models_running"] = [
                    m.get("name", "") for m in ps_data.get("models", [])
                ]

                status["available"] = True
        except Exception as exc:
            log.warning("ollama_status_error", error=str(exc))

        return status

    # ------------------------------------------------------------------
    # Core chat helper
    # ------------------------------------------------------------------

    async def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request to Ollama.

        Args:
            system_prompt: The system message setting context for the LLM.
            user_prompt: The user message / question.

        Returns:
            The assistant's response text.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx status.
            httpx.TimeoutException: If the request exceeds the timeout.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            content: str = data.get("message", {}).get("content", "")
            return content.strip()

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    async def classify_niche(
        self,
        model_id: str,
        pipeline_tag: str,
        tags: list[str],
        description: str = "",
    ) -> dict[str, Any]:
        """Classify an AI model into a business niche using LLM reasoning.

        Args:
            model_id: The model identifier (e.g. ``"meta-llama/Llama-3-8b"``).
            pipeline_tag: The HuggingFace pipeline tag.
            tags: List of tags associated with the model.
            description: Optional description text.

        Returns:
            A dict with ``niche`` (str), ``confidence`` (float 0-1), and
            ``reasoning`` (str).  Falls back to ``"Uncategorized"`` if the
            LLM is unavailable.
        """
        fallback: dict[str, Any] = {
            "niche": "Uncategorized",
            "confidence": 0.0,
            "reasoning": "AI classification unavailable",
        }

        if not self.enabled:
            return fallback

        system_prompt = (
            "You are an AI model classification expert. Given information about a "
            "machine learning model, classify it into exactly one business niche. "
            "Respond with valid JSON only, no extra text.\n\n"
            "Available niches: Text Generation / LLMs, Code Generation, "
            "Image Generation, Computer Vision, Speech & Audio, Video Generation, "
            "NLP / Text Analysis, Translation, RAG & Search, AI Agents, "
            "Multimodal, Robotics, Healthcare AI, Finance AI, Scientific Research.\n\n"
            "Response format:\n"
            '{"niche": "<niche name>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}'
        )

        user_prompt = (
            f"Model ID: {model_id}\n"
            f"Pipeline Tag: {pipeline_tag}\n"
            f"Tags: {', '.join(tags)}\n"
            f"Description: {description or 'N/A'}"
        )

        try:
            raw = await self._chat(system_prompt, user_prompt)
            # Extract JSON from response (handle potential markdown wrapping)
            json_str = raw.strip()
            if json_str.startswith("```"):
                lines = json_str.split("\n")
                json_str = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                )
            result: dict[str, Any] = json.loads(json_str)
            return {
                "niche": result.get("niche", "Uncategorized"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", ""),
            }
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("classify_niche_parse_error", model_id=model_id, error=str(exc))
            return fallback
        except Exception as exc:
            log.warning("classify_niche_error", model_id=model_id, error=str(exc))
            return fallback

    # ------------------------------------------------------------------
    # Weekly insights
    # ------------------------------------------------------------------

    async def generate_weekly_insights(
        self,
        niches_data: list[dict[str, Any]],
        new_models: list[dict[str, Any]],
        declining: list[dict[str, Any]],
        arxiv_spikes: list[dict[str, Any]],
    ) -> str:
        """Generate a weekly business-intelligence report in Markdown.

        Args:
            niches_data: Summary dicts for each niche.
            new_models: Recently appeared high-traction models.
            declining: Models/repos with negative growth.
            arxiv_spikes: Categories with notable paper surges.

        Returns:
            A formatted Markdown report string.  Falls back to a
            template-based report if the LLM is unavailable.
        """

        # Template-based fallback
        def _template_report() -> str:
            lines: list[str] = ["# Weekly AI Trend Report\n"]

            lines.append("## Niche Overview\n")
            if niches_data:
                for nd in niches_data[:10]:
                    lines.append(
                        f"- **{nd.get('name', 'Unknown')}**: "
                        f"{nd.get('model_count', 0)} models, "
                        f"{nd.get('total_downloads', 0):,} total downloads, "
                        f"avg growth {nd.get('avg_growth_percent', 0):.1f}%"
                    )
            else:
                lines.append("- No niche data available.")

            lines.append("\n## New High-Traction Models\n")
            if new_models:
                for nm in new_models[:10]:
                    lines.append(
                        f"- **{nm.get('identifier', nm.get('model_id', 'Unknown'))}**: "
                        f"{nm.get('downloads', nm.get('metric_value', 0)):,} downloads"
                    )
            else:
                lines.append("- No new notable models this week.")

            lines.append("\n## Declining Trends\n")
            if declining:
                for d in declining[:10]:
                    lines.append(
                        f"- **{d.get('identifier', 'Unknown')}**: "
                        f"{d.get('growth_percent', 0):+.1f}%"
                    )
            else:
                lines.append("- No significant declines detected.")

            lines.append("\n## Research Paper Activity\n")
            if arxiv_spikes:
                for a in arxiv_spikes[:10]:
                    lines.append(
                        f"- **{a.get('category', 'Unknown')}**: "
                        f"{a.get('count', 0)} papers "
                        f"({a.get('growth_percent', 0):+.1f}%)"
                    )
            else:
                lines.append("- No notable paper surges this week.")

            lines.append(
                "\n---\n*Report generated automatically. "
                "AI-powered analysis was unavailable.*\n"
            )
            return "\n".join(lines)

        if not self.enabled:
            return _template_report()

        system_prompt = (
            "You are a senior AI industry analyst. Write a concise weekly trend report "
            "in Markdown format. Include sections for: Executive Summary, Key Trends, "
            "Notable New Entries, Areas of Decline, Research Highlights, and Outlook. "
            "Be data-driven, cite specific numbers, and provide actionable insights. "
            "Keep the total report under 1000 words."
        )

        user_prompt_parts: list[str] = ["Here is the data for this week's report:\n"]

        user_prompt_parts.append("## Niche Performance:")
        for nd in niches_data[:15]:
            user_prompt_parts.append(
                f"- {nd.get('name', 'Unknown')}: {nd.get('model_count', 0)} models, "
                f"{nd.get('total_downloads', 0):,} downloads, "
                f"avg growth {nd.get('avg_growth_percent', 0):.1f}%, "
                f"top model: {nd.get('top_model', 'N/A')}"
            )

        user_prompt_parts.append("\n## New High-Traction Models:")
        for nm in new_models[:10]:
            user_prompt_parts.append(
                f"- {nm.get('identifier', nm.get('model_id', 'Unknown'))}: "
                f"{nm.get('downloads', nm.get('metric_value', 0)):,} downloads"
            )

        user_prompt_parts.append("\n## Declining Trends:")
        for d in declining[:10]:
            user_prompt_parts.append(
                f"- {d.get('identifier', 'Unknown')}: {d.get('growth_percent', 0):+.1f}%"
            )

        user_prompt_parts.append("\n## Research Paper Surges:")
        for a in arxiv_spikes[:10]:
            user_prompt_parts.append(
                f"- {a.get('category', 'Unknown')}: {a.get('count', 0)} papers "
                f"({a.get('growth_percent', 0):+.1f}%)"
            )

        user_prompt = "\n".join(user_prompt_parts)

        try:
            report = await self._chat(system_prompt, user_prompt)
            if not report.strip():
                log.warning("empty_llm_report_response")
                return _template_report()
            return report
        except Exception as exc:
            log.warning("generate_weekly_insights_error", error=str(exc))
            return _template_report()

    # ------------------------------------------------------------------
    # Signal explanation
    # ------------------------------------------------------------------

    async def explain_signal(
        self,
        signal_type: str,
        entity: str,
        context_data: dict[str, Any],
    ) -> str:
        """Generate a human-readable explanation for a detected signal.

        Args:
            signal_type: The type of signal (e.g. ``"download_spike"``).
            entity: The identifier of the affected entity.
            context_data: Additional context (metrics, metadata, etc.).

        Returns:
            A 2--3 sentence explanation.  Falls back to a generic template if
            the LLM is unavailable.
        """
        templates: dict[str, str] = {
            "download_spike": (
                f"The model {entity} experienced a significant increase in downloads. "
                f"Downloads changed from {context_data.get('previous', 'N/A'):,} to "
                f"{context_data.get('current', 'N/A'):,}, representing a "
                f"{context_data.get('growth_percent', 0):.1f}% increase. "
                f"This may indicate growing community interest or a new use case discovery."
            ),
            "star_spike": (
                f"The repository {entity} saw a notable surge in GitHub stars. "
                f"Stars increased from {context_data.get('previous', 'N/A'):,} to "
                f"{context_data.get('current', 'N/A'):,}, a "
                f"{context_data.get('growth_percent', 0):.1f}% jump. "
                f"This could be driven by a viral post, conference presentation, "
                f"or major release."
            ),
            "new_entry": (
                f"A new model {entity} has gained significant traction shortly after "
                f"appearing on HuggingFace with {context_data.get('downloads', 0):,} "
                f"downloads. Early high-traction models often indicate breakthrough "
                f"capabilities or strong backing from a major organization."
            ),
            "paper_surge": (
                f"There has been a surge in research papers related to {entity}. "
                f"Paper count increased by {context_data.get('growth_percent', 0):.1f}%. "
                f"This often foreshadows new model releases and capability improvements "
                f"in the coming weeks."
            ),
        }

        fallback = templates.get(
            signal_type,
            f"A {signal_type} signal was detected for {entity}. "
            f"Review the data for details.",
        )

        if not self.enabled:
            return fallback

        system_prompt = (
            "You are an AI industry analyst. Explain the following trend signal "
            "in 2-3 concise sentences. Focus on what it means for practitioners "
            "and businesses. Be specific and data-driven."
        )

        context_str = "\n".join(f"- {k}: {v}" for k, v in context_data.items())
        user_prompt = (
            f"Signal type: {signal_type}\n"
            f"Entity: {entity}\n"
            f"Context:\n{context_str}"
        )

        try:
            explanation = await self._chat(system_prompt, user_prompt)
            if not explanation.strip():
                return fallback
            return explanation
        except Exception as exc:
            log.warning("explain_signal_error", signal_type=signal_type, entity=entity, error=str(exc))
            return fallback

    # ------------------------------------------------------------------
    # Ad-hoc Q&A
    # ------------------------------------------------------------------

    async def answer_question(
        self,
        question: str,
        context: str,
    ) -> str:
        """Answer a user question about AI trends using provided context.

        Args:
            question: The user's natural-language question.
            context: Relevant data context to ground the answer.

        Returns:
            The answer text, or a fallback message if the LLM is unavailable.
        """
        fallback = (
            "AI analysis is currently unavailable. Please review the "
            "dashboard data directly or try again later."
        )

        if not self.enabled:
            return fallback

        system_prompt = (
            "You are an AI trend analyst assistant for an AI industry monitoring tool. "
            "Answer the user's question using ONLY the provided context data. "
            "If the context does not contain enough information to answer, say so. "
            "Be concise, specific, and data-driven."
        )

        user_prompt = f"Context data:\n{context}\n\nQuestion: {question}"

        try:
            answer = await self._chat(system_prompt, user_prompt)
            if not answer.strip():
                return fallback
            return answer
        except Exception as exc:
            log.warning("answer_question_error", error=str(exc))
            return fallback
