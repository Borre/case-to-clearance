#!/usr/bin/env python3
"""End-to-end test script for Case-to-Clearance application."""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# Configuration
BASE_URL = "http://localhost:8000"
SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"  {text}")


class E2ETester:
    """End-to-end test runner."""

    def __init__(self):
        self.client = httpx.Client(timeout=60.0)
        self.results = []
        self.case_ids = {}

    def create_case(self, scenario: str) -> str:
        """Create a new case."""
        print_info(f"Creating case for scenario: {scenario}")
        response = self.client.post(f"{BASE_URL}/api/case/new")
        response.raise_for_status()
        case_id = response.json()["case_id"]
        print_success(f"Case created: {case_id}")
        return case_id

    def upload_documents(self, case_id: str, docs_dir: Path) -> dict:
        """Upload all documents from a directory."""
        docs = list(docs_dir.glob("*.png")) + list(docs_dir.glob("*.pdf")) + list(docs_dir.glob("*.jpg"))
        print_info(f"Uploading {len(docs)} documents...")

        files = []
        for doc_path in docs:
            with open(doc_path, "rb") as f:
                files.append(("files", (doc_path.name, f.read(), "image/png")))

        response = self.client.post(
            f"{BASE_URL}/api/case/{case_id}/docs/upload",
            files=files
        )
        response.raise_for_status()
        result = response.json()

        print_success(f"Uploaded {result['total_files']} documents")
        return result

    def run_ocr(self, case_id: str) -> dict:
        """Run OCR on uploaded documents."""
        print_info("Running OCR extraction...")
        response = self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/run_ocr")
        response.raise_for_status()
        result = response.json()

        # Check for OCR errors
        ocr_results = result.get("ocr_results", [])
        for ocr in ocr_results:
            method = ocr.get("meta", {}).get("method", "")
            if "fallback" in method:
                print_warning(f"OCR used fallback for {ocr.get('doc_id')}")

        print_success(f"OCR completed: {result['total_docs']} documents processed")
        return result

    def extract_and_validate(self, case_id: str) -> dict:
        """Run extraction and validation."""
        print_info("Extracting fields and running validations...")
        response = self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/extract_validate")
        response.raise_for_status()
        result = response.json()

        summary = result.get("summary", {})
        print_info(f"Extractions: {summary.get('extractions', 0)}")
        print_info(f"Validations passed: {summary.get('validations_passed', 0)}")
        print_info(f"Validations failed: {summary.get('validations_failed', 0)}")

        if summary.get('validations_failed', 0) > 0:
            print_warning(f"{summary['validations_failed']} validation(s) failed")

        return result

    def run_risk_assessment(self, case_id: str) -> dict:
        """Run risk assessment."""
        print_info("Computing risk assessment...")
        response = self.client.post(f"{BASE_URL}/api/case/{case_id}/risk/run")
        response.raise_for_status()
        result = response.json()

        score = result.get("score", 0)
        level = result.get("level", "UNKNOWN")

        # Color code risk levels
        level_colors = {
            "LOW": Colors.GREEN,
            "MEDIUM": Colors.YELLOW,
            "HIGH": Colors.RED,
            "CRITICAL": Colors.RED + Colors.BOLD
        }
        color = level_colors.get(level, "")

        print_success(f"Risk score: {score}/100 | Level: {color}{level}{Colors.END}")
        return result

    def get_case_details(self, case_id: str) -> dict:
        """Get full case details."""
        response = self.client.get(f"{BASE_URL}/api/case/{case_id}")
        response.raise_for_status()
        return response.json()

    def run_scenario(self, scenario_name: str, docs_dir: Path) -> dict:
        """Run a complete test scenario."""
        print_header(f"SCENARIO: {scenario_name}")

        start_time = time.time()
        scenario_result = {
            "scenario": scenario_name,
            "success": True,
            "errors": [],
            "case_id": None,
            "documents": 0,
            "risk_score": None,
            "risk_level": None,
            "duration_seconds": 0
        }

        try:
            # Step 1: Create case
            case_id = self.create_case(scenario_name)
            scenario_result["case_id"] = case_id
            self.case_ids[scenario_name] = case_id

            # Step 2: Upload documents
            upload_result = self.upload_documents(case_id, docs_dir)
            scenario_result["documents"] = upload_result.get("total_files", 0)

            # Step 3: Run OCR
            ocr_result = self.run_ocr(case_id)

            # Step 4: Extract and validate
            extract_result = self.extract_and_validate(case_id)

            # Step 5: Risk assessment
            risk_result = self.run_risk_assessment(case_id)
            scenario_result["risk_score"] = risk_result.get("score")
            scenario_result["risk_level"] = risk_result.get("level")

            # Get final case state
            case = self.get_case_details(case_id)

            # Show extracted text preview
            ocr_data = case.get("documents", {}).get("ocr", [])
            if ocr_data:
                print_info(f"\nExtracted text preview (first doc):")
                text = ocr_data[0].get("text", "")[:200]
                print_info(f"  {text}...")

        except Exception as e:
            scenario_result["success"] = False
            scenario_result["errors"].append(str(e))
            print_error(f"Scenario failed: {e}")

        scenario_result["duration_seconds"] = round(time.time() - start_time, 2)
        print_info(f"\nScenario completed in {scenario_result['duration_seconds']}s")

        return scenario_result

    def generate_report(self) -> dict:
        """Generate test report."""
        print_header("TEST REPORT")

        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])

        print(f"{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Total scenarios: {total}")
        print(f"  Passed: {Colors.GREEN}{passed}{Colors.END}")
        print(f"  Failed: {Colors.RED if passed < total else ''}{total - passed}{Colors.END}")

        print(f"\n{Colors.BOLD}Scenario Details:{Colors.END}")
        for result in self.results:
            status = f"{Colors.GREEN}PASS{Colors.END}" if result["success"] else f"{Colors.RED}FAIL{Colors.END}"
            risk_level = result.get("risk_level", "N/A")
            print(f"  [{status}] {result['scenario']}")
            print(f"      Documents: {result['documents']} | Risk: {result['risk_score']}/100 ({risk_level}) | Duration: {result['duration_seconds']}s")
            if result["errors"]:
                for error in result["errors"]:
                    print(f"      Error: {error}")

        # Overall assessment
        print(f"\n{Colors.BOLD}Assessment:{Colors.END}")
        if all(r["success"] for r in self.results):
            print_success("All scenarios completed successfully!")

            # Check risk levels make sense
            happy = next((r for r in self.results if "happy" in r["scenario"].lower()), None)
            fraud = next((r for r in self.results if "fraud" in r["scenario"].lower()), None)
            missing = next((r for r in self.results if "missing" in r["scenario"].lower()), None)

            if happy and fraud:
                if happy.get("risk_score", 0) < fraud.get("risk_score", 0):
                    print_success("Risk scoring correctly identifies fraud scenario as higher risk")
                else:
                    print_warning("Risk scoring may need adjustment - fraud scenario should have higher score")

            if missing and missing.get("risk_score", 0) > 0:
                print_success("Missing documents scenario correctly flagged with risk")
        else:
            print_error("Some scenarios failed - check logs above")

        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "results": self.results,
            "case_ids": self.case_ids
        }

    def run_all_tests(self) -> dict:
        """Run all test scenarios."""
        print_header("CASE-TO-CLEARANCE E2E TEST SUITE")
        print(f"  Base URL: {BASE_URL}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Check server health
        try:
            response = self.client.get(f"{BASE_URL}/health")
            response.raise_for_status()
            print_success(f"Server healthy: {response.json()['version']}")
        except Exception as e:
            print_error(f"Server not responding: {e}")
            print_error("Please start the server first: uvicorn app.main:app")
            return {"error": "Server not available"}

        # Run scenarios
        scenarios = [
            ("Happy Path (Clean Documents)", SAMPLES_DIR / "docs_happy_path"),
            ("Fraudish (Suspicious Patterns)", SAMPLES_DIR / "docs_fraudish"),
            ("Missing Docs (Incomplete)", SAMPLES_DIR / "docs_missing_docs"),
        ]

        for name, docs_dir in scenarios:
            if not docs_dir.exists():
                print_warning(f"Skipping {name} - directory not found: {docs_dir}")
                continue

            result = self.run_scenario(name, docs_dir)
            self.results.append(result)

        return self.generate_report()

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def main():
    """Main entry point."""
    tester = E2ETester()
    try:
        report = tester.run_all_tests()

        # Save report to file
        report_path = Path(__file__).parent.parent / "test_results" / f"e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {report_path}")

        return 0 if report.get("passed", 0) == report.get("total_scenarios", 0) else 1

    except KeyboardInterrupt:
        print_warning("\nTest interrupted by user")
        return 130
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        tester.close()


if __name__ == "__main__":
    sys.exit(main())
