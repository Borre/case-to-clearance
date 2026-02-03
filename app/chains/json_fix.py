"""JSON fixing chain for repairing invalid LLM outputs."""

import json
import logging
from typing import Any

from app.chains.prompts import JSON_FIX_SYSTEM
from app.config import settings
from app.huawei.maas import get_maas_client

logger = logging.getLogger(__name__)


class JsonFixChain:
    """Chain for fixing invalid JSON outputs."""

    def __init__(self) -> None:
        """Initialize the JSON fix chain."""
        self.maas = get_maas_client()
        self.max_retries = 3

    async def fix_json(
        self,
        invalid_json: str,
        error_message: str,
        expected_schema: dict[str, Any] | None = None,
    ) -> str:
        """Attempt to fix invalid JSON.

        Args:
            invalid_json: The invalid JSON string
            error_message: Error from JSON parsing
            expected_schema: Expected schema description

        Returns:
            Fixed JSON string

        Raises:
            ValueError: If unable to fix after max retries
        """
        schema_desc = self._describe_schema(expected_schema) if expected_schema else "Unknown"

        for attempt in range(1, self.max_retries + 1):
            try:
                fixed = await self._call_fixer(invalid_json, error_message, schema_desc)

                # Try to parse it
                json.loads(fixed)
                return fixed

            except json.JSONDecodeError as e:
                logger.warning(f"Fix attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt >= self.max_retries:
                    raise ValueError(f"Unable to fix JSON after {self.max_retries} attempts")

                # Update for next attempt
                invalid_json = fixed
                error_message = str(e)

        raise ValueError("Unable to fix JSON")

    async def _call_fixer(
        self, invalid_json: str, error_message: str, schema_desc: str
    ) -> str:
        """Call the LLM to fix JSON.

        Args:
            invalid_json: Invalid JSON string
            error_message: Error message
            schema_desc: Schema description

        Returns:
            Fixed JSON string
        """
        messages = [
            {
                "role": "system",
                "content": JSON_FIX_SYSTEM.format(
                    error_message=error_message,
                    expected_schema=schema_desc,
                    invalid_json=invalid_json[:4000],
                ),
            },
            {"role": "user", "content": "Please fix the JSON above."},
        ]

        response = await self.maas.chat(
            messages=messages,
            model=settings.maas_model_reasoner,
            json_mode=False,
            temperature=0.1,
        )

        return response["content"].strip()

    def _describe_schema(self, schema: dict[str, Any]) -> str:
        """Generate a human-readable schema description.

        Args:
            schema: Schema dict

        Returns:
            Description string
        """
        parts = []
        for key, value in schema.items():
            if isinstance(value, dict):
                type_info = value.get("type", "any")
                desc = value.get("description", "")
                parts.append(f"- {key}: {type_info} ({desc})" if desc else f"- {key}: {type_info}")
            else:
                parts.append(f"- {key}: {value}")

        return "\n".join(parts)


# Global chain instance
_json_fix_chain: JsonFixChain | None = None


def get_json_fix_chain() -> JsonFixChain:
    """Get or create the global JSON fix chain."""
    global _json_fix_chain
    if _json_fix_chain is None:
        _json_fix_chain = JsonFixChain()
    return _json_fix_chain
