"""Huawei Cloud ModelArts MaaS client for LLM chat completions."""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.utils.retry import async_retry_with_backoff

logger = logging.getLogger(__name__)


class HuaweiMaaSClient:
    """Client for Huawei Cloud ModelArts MaaS API."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Initialize the MaaS client.

        Args:
            api_key: Huawei Cloud API key (defaults to settings)
            endpoint: MaaS endpoint URL (defaults to settings)
        """
        self.api_key = api_key or settings.maas_api_key
        self.endpoint = endpoint or settings.maas_chat_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build the request payload.

        Args:
            messages: Chat messages
            model: Model name to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON mode specification

        Returns:
            Request payload dict
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            payload["response_format"] = response_format

        return payload

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0)
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Args:
            messages: List of chat messages with role and content
            model: Model name (defaults to settings.maas_model_reasoner)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            json_mode: Enable JSON output mode

        Returns:
            Response dict with content, model, usage

        Raises:
            httpx.HTTPStatusError: On API errors
            ValueError: On invalid response
        """
        if not self.api_key:
            raise ValueError("MaaS API key not configured")

        model = model or settings.maas_model_reasoner
        client = await self._get_client()

        response_format = {"type": "json_object"} if json_mode else None

        payload = self._build_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        logger.debug(f"MaaS request: model={model}, json_mode={json_mode}")

        start_time = datetime.now()
        response = await client.post(
            self.endpoint,
            headers=self._build_headers(),
            json=payload,
        )
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        response.raise_for_status()
        data = response.json()

        logger.debug(f"MaaS response: status={response.status_code}, duration={duration_ms:.0f}ms")

        # Extract response data
        try:
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices in response")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            return {
                "content": content,
                "model": data.get("model", model),
                "usage": data.get("usage", {}),
                "finish_reason": choices[0].get("finish_reason"),
                "duration_ms": duration_ms,
            }
        except (KeyError, IndexError) as e:
            raise ValueError(f"Invalid response format: {e}") from e

    async def classify_procedure(
        self, user_message: str, procedures: list[dict]
    ) -> dict[str, Any]:
        """Classify the user's request into a procedure type.

        Args:
            user_message: User's input message
            procedures: List of available procedures

        Returns:
            Dict with procedure_id, confidence, rationale
        """
        procedures_text = "\n".join(
            f"- {p['id']}: {p['name']} - {p['description']}"
            for p in procedures
        )

        system_prompt = f"""You are a customs procedure classifier. Analyze the citizen's message and identify the most relevant customs procedure.

Available procedures:
{procedures_text}

Respond ONLY with valid JSON:
{{
  "procedure_id": "procedure-id-from-above",
  "confidence": 0.0-1.0,
  "rationale": "brief explanation of why this procedure matches",
  "detected_fields": {{
    "field_name": "value if detected, or null"
  }}
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.chat(messages, json_mode=True, temperature=0.3)

        import json

        try:
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON: {e}")
            return {
                "procedure_id": None,
                "confidence": 0.0,
                "rationale": "Failed to parse response",
                "detected_fields": {},
            }

    async def extract_fields(
        self, ocr_text: str, doc_type: str, field_definitions: dict
    ) -> dict[str, Any]:
        """Extract structured fields from OCR text.

        Args:
            ocr_text: Extracted text from OCR
            doc_type: Document type (invoice, bl, etc.)
            field_definitions: Field names and descriptions to extract

        Returns:
            Dict with extracted fields, confidence, missing fields
        """
        fields_text = "\n".join(
            f"- {name}: {desc}" for name, desc in field_definitions.items()
        )

        system_prompt = f"""You are a document field extractor for customs documents. Extract structured data from the OCR text.

Document type: {doc_type}

Extract these fields:
{fields_text}

Return ONLY valid JSON:
{{
  "fields": {{
    "field_name": "extracted value or null if not found"
  }},
  "confidence": 0.0-1.0,
  "low_confidence_fields": ["field_name"],
  "missing_fields": ["field_name"]
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ocr_text},
        ]

        response = await self.chat(messages, json_mode=True, temperature=0.2)

        import json

        try:
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction JSON: {e}")
            return {
                "fields": {},
                "confidence": 0.0,
                "low_confidence_fields": [],
                "missing_fields": list(field_definitions.keys()),
            }

    async def generate_explanation(
        self,
        score: int,
        level: str,
        factors: list[dict],
        language: str = "es",
    ) -> dict[str, Any]:
        """Generate a risk explanation for the citizen.

        Args:
            score: Risk score (0-100)
            level: Risk level (LOW/MEDIUM/HIGH/CRITICAL)
            factors: List of risk factors with points
            language: Response language (es/en)

        Returns:
            Dict with executive_summary, bullets, actions
        """
        factors_table = "\n".join(
            f"- [{f['factor_id']}] {f['description']}: +{f['points_added']} points"
            for f in factors
        )

        disclaimer = settings.disclaimer

        lang_note = "in Spanish" if language == "es" else "in English"

        system_prompt = f"""You are a customs risk communication specialist. Write a clear explanation for a risk assessment.

RISK SCORE: {score}/100
RISK LEVEL: {level}

TRIGGERED FACTORS:
{factors_table}

CONSTRAINTS:
- Each bullet MUST reference a factor_id from the table above
- Each number MUST come from the score or factors only
- Do NOT introduce new risk factors
- Include the disclaimer: "{disclaimer}"
- Write the response {lang_note}

Return ONLY valid JSON:
{{
  "executive_summary": "2-3 sentences explaining the overall risk",
  "explanation_bullets": [
    "[factor_id]: explanation referencing the factor"
  ],
  "recommended_next_actions": [
    "actionable step 1",
    "actionable step 2"
  ],
  "risk_reduction_actions": [
    "how to reduce risk 1",
    "how to reduce risk 2"
  ]
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the risk explanation."},
        ]

        response = await self.chat(
            messages, model=settings.maas_model_writer, json_mode=True, temperature=0.7
        )

        import json

        try:
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse explanation JSON: {e}")
            return {
                "executive_summary": f"Risk score: {score}/100 ({level}).",
                "explanation_bullets": [f"Factor analysis resulted in {level} risk level."],
                "recommended_next_actions": ["Review all documents carefully."],
                "risk_reduction_actions": [],
            }

    async def fix_json(
        self, invalid_json: str, error_message: str, expected_schema: dict
    ) -> str:
        """Attempt to fix invalid JSON output.

        Args:
            invalid_json: The invalid JSON string
            error_message: Error from validation
            expected_schema: Expected schema description

        Returns:
            Fixed JSON string
        """
        system_prompt = f"""You are a JSON repair specialist. Fix the following invalid JSON.

ERROR: {error_message}

EXPECTED STRUCTURE: {expected_schema}

INVALID JSON:
{invalid_json}

Return ONLY the corrected JSON, nothing else."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Fix the JSON."},
        ]

        response = await self.chat(messages, json_mode=False, temperature=0.1)
        return response["content"]


# Global client instance
_maas_client: HuaweiMaaSClient | None = None


def get_maas_client() -> HuaweiMaaSClient:
    """Get or create the global MaaS client."""
    global _maas_client
    if _maas_client is None:
        _maas_client = HuaweiMaaSClient()
    return _maas_client
