#!/usr/bin/env python3
"""Comprehensive workflow test for Case-to-Clearance system."""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Configuration
BASE_URL = "http://localhost:8000"
SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class Colors:
    """ANSI color codes."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class WorkflowTester:
    """Test all system workflows."""

    def __init__(self):
        self.client = httpx.Client(timeout=60.0)
        self.results = {}
        self.failed_tests = []

    def print_header(self, text: str) -> None:
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")

    def print_section(self, text: str) -> None:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}▶ {text}{Colors.END}")
        print("-" * 70)

    def print_success(self, text: str) -> None:
        print(f"{Colors.GREEN}  ✓ {text}{Colors.END}")

    def print_error(self, text: str) -> None:
        print(f"{Colors.RED}  ✗ {text}{Colors.END}")
        self.failed_tests.append(text)

    def print_info(self, text: str) -> None:
        print(f"  • {text}")

    def test_health_check(self) -> bool:
        """Test 1: Health Check Endpoint."""
        self.print_section("Workflow 1: Health Check")
        try:
            response = self.client.get(f"{BASE_URL}/health")
            response.raise_for_status()
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            self.print_success(f"Health check OK - Version {data['version']}")
            return True
        except Exception as e:
            self.print_error(f"Health check failed: {e}")
            return False

    def test_ui_routes(self) -> bool:
        """Test 2: UI Routes."""
        self.print_section("Workflow 2: UI Routes")
        passed = True
        try:
            # Test main UI
            response = self.client.get(f"{BASE_URL}/ui")
            assert response.status_code == 200
            self.print_success("Main UI route accessible")

            # Test case UI
            case_id = "test-case-123"
            response = self.client.get(f"{BASE_URL}/ui/case/{case_id}")
            # May return 404 for non-existent case, that's OK
            self.print_success(f"Case UI route responds (status: {response.status_code})")

        except Exception as e:
            self.print_error(f"UI routes failed: {e}")
            passed = False
        return passed

    def test_case_management(self) -> Dict[str, Any]:
        """Test 3: Case Management."""
        self.print_section("Workflow 3: Case Management")
        result = {"created_ids": []}
        passed = True

        try:
            # Test create case
            response = self.client.post(f"{BASE_URL}/api/case/new")
            response.raise_for_status()
            data = response.json()
            case_id = data["case_id"]
            assert case_id.startswith("case-")
            result["created_ids"].append(case_id)
            self.print_success(f"Created case: {case_id}")

            # Test get case
            response = self.client.get(f"{BASE_URL}/api/case/{case_id}")
            response.raise_for_status()
            data = response.json()
            assert data["case_id"] == case_id
            assert "created_at" in data
            assert "updated_at" in data
            self.print_success(f"Retrieved case: {case_id}")

            # Test non-existent case
            response = self.client.get(f"{BASE_URL}/api/case/non-existent")
            assert response.status_code == 404
            self.print_success("Non-existent case returns 404")

        except Exception as e:
            self.print_error(f"Case management failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_citizen_intake(self) -> Dict[str, Any]:
        """Test 4: Citizen Intake (Chat)."""
        self.print_section("Workflow 4: Citizen Intake (Chat)")
        result = {}
        passed = True

        try:
            # Create case for testing
            response = self.client.post(f"{BASE_URL}/api/case/new")
            case_id = response.json()["case_id"]

            # Test chat message 1 - Initial intent
            self.print_info("Message 1: 'I want to import electronics from China'")
            response = self.client.post(
                f"{BASE_URL}/api/case/{case_id}/chat",
                data={"message": "I want to import electronics from China to Peru"}
            )
            response.raise_for_status()
            data = response.json()

            assert "procedure" in data
            assert "collected_fields" in data
            assert "missing_fields" in data
            assert "response" in data

            procedure_id = data.get("procedure", {}).get("id")
            self.print_success(f"Procedure classified: {procedure_id}")
            self.print_info(f"Missing fields: {data.get('missing_fields', [])[:3]}...")

            # Test chat message 2 - Provide some fields
            self.print_info("Message 2: Providing additional information")
            response = self.client.post(
                f"{BASE_URL}/api/case/{case_id}/chat",
                data={"message": "My tax ID is 20601234567, shipping by sea, value $15000"}
            )
            response.raise_for_status()
            data = response.json()

            self.print_success(f"Collected fields: {len(data.get('collected_fields', {}))} fields")
            self.print_info(f"Still missing: {data.get('missing_fields', [])[:3]}...")

            result["case_id"] = case_id
            result["procedure_id"] = procedure_id

        except Exception as e:
            self.print_error(f"Citizen intake failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_document_upload(self, case_id: str) -> Dict[str, Any]:
        """Test 5: Document Upload."""
        self.print_section("Workflow 5: Document Upload")
        result = {}
        passed = True

        try:
            # Upload documents from happy path
            docs_dir = SAMPLES_DIR / "docs_happy_path"
            files = []
            for doc_path in docs_dir.glob("*.png"):
                with open(doc_path, "rb") as f:
                    files.append(("files", (doc_path.name, f.read(), "image/png")))

            response = self.client.post(
                f"{BASE_URL}/api/case/{case_id}/docs/upload",
                files=files
            )
            response.raise_for_status()
            data = response.json()

            assert data["case_id"] == case_id
            assert data["total_files"] > 0
            self.print_success(f"Uploaded {data['total_files']} documents")

            result["uploaded"] = data.get("total_files", 0)

        except Exception as e:
            self.print_error(f"Document upload failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_ocr_extraction(self, case_id: str) -> Dict[str, Any]:
        """Test 6: OCR Extraction."""
        self.print_section("Workflow 6: OCR Extraction")
        result = {}
        passed = True

        try:
            response = self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/run_ocr")
            response.raise_for_status()
            data = response.json()

            assert "ocr_results" in data
            assert data["total_docs"] > 0

            # Check OCR was successful
            for ocr in data.get("ocr_results", []):
                method = ocr.get("meta", {}).get("method", "")
                text_len = len(ocr.get("text", ""))
                self.print_info(f"Doc {ocr.get('doc_id')}: {method} ({text_len} chars)")

                if "huawei_ocr_sdk" in method:
                    self.print_success(f"Huawei Cloud OCR working")

            result["total_docs"] = data.get("total_docs", 0)
            result["methods"] = [o.get("meta", {}).get("method") for o in data.get("ocr_results", [])]

        except Exception as e:
            self.print_error(f"OCR extraction failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_field_extraction(self, case_id: str) -> Dict[str, Any]:
        """Test 7: Field Extraction and Validation."""
        self.print_section("Workflow 7: Field Extraction & Validation")
        result = {}
        passed = True

        try:
            response = self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/extract_validate")
            response.raise_for_status()
            data = response.json()

            extractions = data.get("extractions", [])
            validations = data.get("validations", [])

            self.print_info(f"Extractions: {len(extractions)} documents")
            self.print_info(f"Validations: {len(validations)} rules checked")

            # Check extractions have structured fields
            for ext in extractions:
                doc_type = ext.get("doc_type")
                fields = ext.get("fields", {})
                self.print_info(f"  {doc_type}: {len(fields)} fields extracted")

            # Check validation results
            failed = sum(1 for v in validations if not v.get("passed", True))
            passed_count = sum(1 for v in validations if v.get("passed", True))

            self.print_info(f"Validations: {passed_count} passed, {failed} failed")

            if failed > 0:
                self.print_info(f"Failed validations:")
                for v in validations:
                    if not v.get("passed", True):
                        self.print_info(f"  - {v.get('rule_id')}: {v.get('severity')}")

            result["extractions"] = len(extractions)
            result["validations_passed"] = passed_count
            result["validations_failed"] = failed

        except Exception as e:
            self.print_error(f"Field extraction failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_risk_assessment(self, case_id: str) -> Dict[str, Any]:
        """Test 8: Risk Assessment."""
        self.print_section("Workflow 8: Risk Assessment")
        result = {}
        passed = True

        try:
            response = self.client.post(f"{BASE_URL}/api/case/{case_id}/risk/run")
            response.raise_for_status()
            data = response.json()

            score = data.get("score", 0)
            level = data.get("level", "UNKNOWN")
            factors = data.get("factors", [])
            review = data.get("review_required", False)

            self.print_success(f"Risk Score: {score}/100")
            self.print_info(f"Risk Level: {level}")
            self.print_info(f"Review Required: {review}")
            self.print_info(f"Risk Factors: {len(factors)}")

            if factors:
                for f in factors[:5]:  # Show first 5
                    self.print_info(f"  +{f.get('points_added', 0)} pts: {f.get('description', 'N/A')[:60]}")

            # Check explanation
            explanation = data.get("explanation", {})
            summary = explanation.get("executive_summary", "")
            self.print_info(f"Explanation length: {len(summary)} chars")

            result["score"] = score
            result["level"] = level
            result["factors_count"] = len(factors)
            result["review_required"] = review

        except Exception as e:
            self.print_error(f"Risk assessment failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_full_case_retrieval(self, case_id: str) -> Dict[str, Any]:
        """Test 9: Full Case Retrieval."""
        self.print_section("Workflow 9: Full Case Data")
        result = {}
        passed = True

        try:
            response = self.client.get(f"{BASE_URL}/api/case/{case_id}")
            response.raise_for_status()
            case = response.json()

            # Verify all sections are present
            required_sections = ["case_id", "created_at", "procedure", "citizen_intake", "documents", "risk"]
            for section in required_sections:
                assert section in case, f"Missing section: {section}"
                self.print_info(f"  ✓ Section '{section}' present")

            # Check audit trail
            audit = case.get("audit", {})
            trace = audit.get("trace", [])
            self.print_info(f"  Audit trail: {len(trace)} events")

            result["sections"] = len([s for s in required_sections if s in case])
            result["audit_events"] = len(trace)

        except Exception as e:
            self.print_error(f"Case retrieval failed: {e}")
            passed = False

        result["passed"] = passed
        return result

    def test_all_scenarios(self) -> Dict[str, Any]:
        """Test 10: All Demo Scenarios."""
        self.print_section("Workflow 10: All Demo Scenarios")
        result = {"scenarios": {}}
        all_passed = True

        scenarios = {
            "Happy Path": SAMPLES_DIR / "docs_happy_path",
            "Fraudish": SAMPLES_DIR / "docs_fraudish",
            "Missing Docs": SAMPLES_DIR / "docs_missing_docs",
        }

        for scenario_name, docs_dir in scenarios.items():
            self.print_info(f"Testing scenario: {scenario_name}")
            scenario_passed = True
            scenario_result = {}

            try:
                # Create case
                response = self.client.post(f"{BASE_URL}/api/case/new")
                case_id = response.json()["case_id"]

                # Upload docs
                files = []
                for doc_path in docs_dir.glob("*.png"):
                    with open(doc_path, "rb") as f:
                        files.append(("files", (doc_path.name, f.read(), "image/png")))

                response = self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/upload", files=files)
                uploaded = response.json()["total_files"]

                # Run full pipeline
                self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/run_ocr")
                self.client.post(f"{BASE_URL}/api/case/{case_id}/docs/extract_validate")
                risk_response = self.client.post(f"{BASE_URL}/api/case/{case_id}/risk/run")
                risk_data = risk_response.json()

                scenario_result["uploaded"] = uploaded
                scenario_result["risk_score"] = risk_data.get("score", 0)
                scenario_result["risk_level"] = risk_data.get("level", "UNKNOWN")

                self.print_info(f"  Docs: {uploaded}, Risk: {scenario_result['risk_score']}/100 ({scenario_result['risk_level']})")

            except Exception as e:
                self.print_error(f"  Scenario failed: {e}")
                all_passed = False
                scenario_passed = False

            scenario_result["passed"] = scenario_passed
            result["scenarios"][scenario_name] = scenario_result

        result["passed"] = all_passed
        return result

    def generate_report(self) -> Dict[str, Any]:
        """Generate final test report."""
        self.print_header("COMPREHENSIVE WORKFLOW TEST REPORT")

        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r.get("passed", False))

        print(f"{Colors.BOLD}Test Summary:{Colors.END}")
        print(f"  Total Workflows: {total_tests}")
        print(f"  Passed: {Colors.GREEN}{passed_tests}{Colors.END}")
        print(f"  Failed: {Colors.RED if passed_tests < total_tests else ''}{total_tests - passed_tests}{Colors.END}")

        print(f"\n{Colors.BOLD}Workflow Results:{Colors.END}")
        for name, result in self.results.items():
            status = f"{Colors.GREEN}PASS{Colors.END}" if result.get("passed") else f"{Colors.RED}FAIL{Colors.END}"
            print(f"  [{status}] {name}")

            # Show key metrics
            if "score" in result:
                print(f"      Risk Score: {result['score']}/100 ({result.get('level')})")
            if "factors_count" in result:
                print(f"      Risk Factors: {result['factors_count']}")
            if "extractions" in result:
                print(f"      Extractions: {result['extractions']}, Validations: {result.get('validations_failed', 0)} failed")

        # Scenario comparison
        if "scenarios" in self.results.get("All Demo Scenarios", {}):
            print(f"\n{Colors.BOLD}Scenario Risk Scores:{Colors.END}")
            scenarios = self.results["All Demo Scenarios"]["scenarios"]
            for name, data in scenarios.items():
                score = data.get("risk_score", 0)
                level = data.get("risk_level", "UNKNOWN")
                color = Colors.GREEN if score < 30 else Colors.YELLOW if score < 50 else Colors.RED
                print(f"  {name}: {color}{score}/100 ({level}){Colors.END}")

        # Overall assessment
        print(f"\n{Colors.BOLD}Overall Assessment:{Colors.END}")
        if passed_tests == total_tests:
            print(f"{Colors.GREEN}✓ ALL WORKFLOWS OPERATIONAL{Colors.END}")
        else:
            print(f"{Colors.YELLOW}⚠ SOME WORKFLOWS HAVE ISSUES{Colors.END}")

        if self.failed_tests:
            print(f"\n{Colors.RED}Failed Tests:{Colors.END}")
            for test in self.failed_tests:
                print(f"  • {test}")

        return {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": total_tests - passed_tests,
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all workflow tests."""
        self.print_header("CASE-TO-CLEARANCE WORKFLOW TEST SUITE")
        print(f"  Base URL: {BASE_URL}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Check server health first
        if not self.test_health_check():
            print(f"\n{Colors.RED}Server not available. Please start the server first.{Colors.END}")
            print(f"  Run: uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return {"error": "Server not available"}

        # Run all workflow tests
        self.results["Health Check"] = {"passed": True}
        self.results["UI Routes"] = {"passed": self.test_ui_routes()}
        self.results["Case Management"] = self.test_case_management()
        self.results["Citizen Intake"] = self.test_citizen_intake()

        # Use the case created in citizen intake for document tests
        intake_case = self.results["Citizen Intake"].get("case_id")
        if intake_case:
            self.results["Document Upload"] = self.test_document_upload(intake_case)
            self.results["OCR Extraction"] = self.test_ocr_extraction(intake_case)
            self.results["Field Extraction"] = self.test_field_extraction(intake_case)
            self.results["Risk Assessment"] = self.test_risk_assessment(intake_case)
            self.results["Full Case Retrieval"] = self.test_full_case_retrieval(intake_case)

        self.results["All Demo Scenarios"] = self.test_all_scenarios()

        return self.generate_report()

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def main():
    """Main entry point."""
    tester = WorkflowTester()
    try:
        report = tester.run_all_tests()

        # Save report
        report_dir = Path(__file__).parent.parent / "test_results"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"workflow_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_path, "w") as f:
            # Remove non-serializable items
            serializable_report = {
                k: v for k, v in report.items()
                if k != "results" or isinstance(v, (dict, list, str, int, float, bool, type(None)))
            }
            json.dump(serializable_report, f, indent=2, default=str)

        print(f"\nReport saved to: {report_path}")

        return 0 if report.get("passed", 0) == report.get("total_tests", 0) else 1

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        return 130
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        tester.close()


if __name__ == "__main__":
    sys.exit(main())
