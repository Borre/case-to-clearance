"""Huawei Cloud OCR client for document text extraction."""

import datetime
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.utils.retry import async_retry_with_backoff

logger = logging.getLogger(__name__)


class HuaweiOCRClient:
    """Client for Huawei Cloud OCR API."""

    def __init__(
        self,
        ak: str | None = None,
        sk: str | None = None,
        endpoint: str | None = None,
        region: str | None = None,
        project_id: str | None = None,
    ) -> None:
        """Initialize the OCR client.

        Args:
            ak: Access Key (defaults to settings)
            sk: Secret Key (defaults to settings)
            endpoint: OCR endpoint URL (defaults to settings)
            region: Region name (defaults to settings)
            project_id: Project ID (defaults to settings)
        """
        self.ak = ak or settings.ocr_ak
        self.sk = sk or settings.ocr_sk
        self.endpoint = endpoint or settings.ocr_endpoint
        self.region = region or settings.ocr_region
        self.project_id = project_id or settings.ocr_project_id
        self._client: httpx.AsyncClient | None = None
        self._use_fallback = not bool(self.ak and self.sk)

        if self._use_fallback:
            logger.warning("OCR credentials not configured, using fallback mode")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_fallback_text(self, filename: str) -> str:
        """Get pre-extracted text from fallback directory.

        Args:
            filename: Name of the file to find fallback text for

        Returns:
            Pre-extracted text or placeholder
        """
        fallback_dir = Path("samples/text_fallback")

        # Try to find a matching file
        for file in fallback_dir.glob("*.txt"):
            if filename.lower() in file.stem.lower():
                return file.read_text()

        # Return generic fallback text
        return (
            "Fallback OCR text: Document processing text would appear here. "
            "Configure OCR credentials for real extraction."
        )

    async def extract_text(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        """Extract text from a document using OCR.

        Args:
            file_bytes: File content as bytes
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            Dict with extracted text, metadata, processing info
        """
        start_time = datetime.datetime.now()

        if self._use_fallback:
            logger.info(f"Using fallback OCR for {filename}")
            text = self._get_fallback_text(filename)
            return {
                "doc_id": f"doc-{uuid.uuid4().hex[:12]}",
                "text": text,
                "meta": {
                    "filename": filename,
                    "mime": mime_type,
                    "size_bytes": len(file_bytes),
                    "method": "fallback",
                },
                "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "duration_ms": (datetime.datetime.now() - start_time).total_seconds() * 1000,
            }

        # Real OCR implementation
        try:
            result = await self._ocr_extract(file_bytes, filename, mime_type)
            result["duration_ms"] = (
                datetime.datetime.now() - start_time
            ).total_seconds() * 1000
            return result
        except Exception as e:
            logger.error(f"OCR extraction failed for {filename}: {e}, falling back")
            text = self._get_fallback_text(filename)
            return {
                "doc_id": f"doc-{uuid.uuid4().hex[:12]}",
                "text": text,
                "meta": {
                    "filename": filename,
                    "mime": mime_type,
                    "size_bytes": len(file_bytes),
                    "method": "fallback_after_error",
                    "error": str(e),
                },
                "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "duration_ms": (
                    datetime.datetime.now() - start_time
                ).total_seconds() * 1000,
            }

    @async_retry_with_backoff(max_attempts=2, base_delay=0.5)
    async def _ocr_extract(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> dict[str, Any]:
        """Perform actual OCR extraction.

        This is a placeholder for the real Huawei Cloud OCR implementation.
        The actual implementation would call the Huawei OCR API.
        """
        # Placeholder for real OCR implementation
        # Huawei OCR API would be called here

        # For demo purposes, return mock extraction
        return {
            "doc_id": f"doc-{uuid.uuid4().hex[:12]}",
            "text": "[OCR result would appear here - configure credentials for real OCR]",
            "meta": {
                "filename": filename,
                "mime": mime_type,
                "size_bytes": len(file_bytes),
                "method": "huawei_ocr",
            },
            "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    async def extract_from_pdf(self, file_bytes: bytes, filename: str) -> list[dict]:
        """Extract text from a multi-page PDF.

        Args:
            file_bytes: PDF file content
            filename: Original filename

        Returns:
            List of page extractions
        """
        # For demo, return single page result
        result = await self.extract_text(file_bytes, filename, "application/pdf")
        return [result]

    async def extract_from_image(self, file_bytes: bytes, filename: str) -> dict:
        """Extract text from an image file.

        Args:
            file_bytes: Image file content
            filename: Original filename

        Returns:
            Extraction result dict
        """
        return await self.extract_text(file_bytes, filename, "image/jpeg")

    def is_available(self) -> bool:
        """Check if OCR is properly configured."""
        return not self._use_fallback


# Global client instance
_ocr_client: HuaweiOCRClient | None = None


def get_ocr_client() -> HuaweiOCRClient:
    """Get or create the global OCR client."""
    global _ocr_client
    if _ocr_client is None:
        _ocr_client = HuaweiOCRClient()
    return _ocr_client
