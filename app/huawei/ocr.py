"""Huawei Cloud OCR client for document text extraction."""

import datetime
import logging
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.utils.retry import async_retry_with_backoff

logger = logging.getLogger(__name__)


class HuaweiOCRClient:
    """Client for Huawei Cloud OCR API using the official SDK."""

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
        self.project_id = project_id or settings.ocr_project_id

        # Extract region from endpoint if not provided
        # Format: https://ocr.{region}.myhuaweicloud.com
        if region:
            self.region = region
        else:
            # Try to extract from endpoint
            # e.g., https://ocr.cn-north-4.myhuaweicloud.com -> cn-north-4
            if ".myhuaweicloud.com" in self.endpoint:
                before_com = self.endpoint.split(".myhuaweicloud.com")[0]  # https://ocr.cn-north-4
                after_slash = before_com.split("//")[-1]  # ocr.cn-north-4
                parts = after_slash.split(".")  # ["ocr", "cn-north-4"]
                if len(parts) >= 2:
                    self.region = parts[-2] if parts[-1] in ["myhuaweicloud", "com"] else parts[-1]
                else:
                    self.region = parts[0] if len(parts) == 1 else "cn-north-4"
            else:
                self.region = settings.ocr_region

        self._client: Any = None
        self._use_fallback = not bool(self.ak and self.sk and self.project_id)

        if self._use_fallback:
            logger.warning("OCR credentials not configured, using fallback mode")
        else:
            logger.info(f"OCR configured with endpoint: {self.endpoint}, region: {self.region}, project: {self.project_id}")

    def _get_sdk_client(self) -> Any:
        """Get or create the SDK OCR client."""
        if self._client is None:
            try:
                from huaweicloudsdkcore.auth.credentials import BasicCredentials
                from huaweicloudsdkocr.v1.region.ocr_region import OcrRegion
                from huaweicloudsdkocr.v1 import OcrClient

                credentials = BasicCredentials(self.ak, self.sk, self.project_id)

                # Try to use region enum first, fall back to endpoint
                try:
                    self._client = OcrClient.new_builder() \
                        .with_credentials(credentials) \
                        .with_region(OcrRegion.value_of(self.region)) \
                        .build()
                    logger.debug(f"SDK client initialized with region: {self.region}")
                except Exception:
                    # Fall back to endpoint-based initialization
                    self._client = OcrClient.new_builder() \
                        .with_credentials(credentials) \
                        .with_endpoint(self.endpoint) \
                        .build()
                    logger.debug(f"SDK client initialized with endpoint: {self.endpoint}")

            except ImportError as e:
                logger.error(f"Huawei Cloud SDK not installed: {e}")
                self._use_fallback = True
                return None
            except Exception as e:
                logger.error(f"Failed to initialize SDK client: {e}")
                self._use_fallback = True
                return None

        return self._client

    async def close(self) -> None:
        """Close the SDK client (no-op for SDK client)."""
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
        """Perform actual OCR extraction using Huawei Cloud OCR SDK.

        Args:
            file_bytes: File content as bytes
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            Dict with extracted text and metadata
        """
        import base64

        client = self._get_sdk_client()
        if client is None:
            raise RuntimeError("SDK client not available")

        # Encode image to base64
        image_base64 = base64.b64encode(file_bytes).decode()

        # Import SDK request classes
        from huaweicloudsdkocr.v1.model import GeneralTextRequestBody, RecognizeGeneralTextRequest

        # Build request
        request = RecognizeGeneralTextRequest()
        request.body = GeneralTextRequestBody(
            image=image_base64,
            detect_direction=True,
        )

        logger.debug(f"Calling Huawei OCR SDK: RecognizeGeneralText")

        # Make the API call
        response = client.recognize_general_text(request)

        logger.debug(f"OCR SDK response status: success")

        # Extract text from response
        extracted_text = ""
        if response.result:
            result = response.result.to_dict()
            # SDK returns words_block_list (key may vary by API version)
            words_list = result.get("words_block_list") or result.get("words_block", [])
            for block in words_list:
                if isinstance(block, dict):
                    extracted_text += block.get("words", "") + "\n"
                elif isinstance(block, str):
                    extracted_text += block + "\n"

        extracted_text = extracted_text.strip()

        logger.info(f"OCR extracted {len(extracted_text)} characters from {filename}")

        return {
            "doc_id": f"doc-{uuid.uuid4().hex[:12]}",
            "text": extracted_text,
            "meta": {
                "filename": filename,
                "mime": mime_type,
                "size_bytes": len(file_bytes),
                "method": "huawei_ocr_sdk",
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
