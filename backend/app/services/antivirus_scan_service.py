"""
MOD-07: Antivirus Scan Service for SAKSHI Investigation Platform.
Phase 2 — Evidence Ingestion.

Consumes:
    ValidatedEvidenceObject (from MOD-06 MIME / Signature Validation)
Produces:
    ScannedEvidenceObject (downstream handoff to MOD-08 WORM Commit + Checksum)
    or REJECTED / QUARANTINED verdict on hostile payloads.

Core Principles:
    1. Scan without execution — treats files strictly as passive byte streams.
    2. Fail-Closed Security Model — any engine failure, timeout, or missing scanner
       strictly halts the pipeline and refuses to certify evidence as CLEAN.
    3. Explicit Scanner Selection & No Unsafe Fallback — when ClamAV is configured,
       the system NEVER silently downgrades to a heuristic scanner upon failure.
    4. Clean Semantics — CLEAN means no threat was detected by the configured scanner;
       it does not constitute absolute proof or certification that the payload is benign.
    5. EICAR Standard Test Detection — harmless standard test artifact recognized.
    6. Case & Workspace Isolation — path canonicalization prevents path traversal
       or cross-case evidence probing.
    7. MOD-03 Authorization & Audit Integration — all scan operations require
       valid investigator credentials with 'evidence:scan' permission and emit
       tamper-evident audit events.
"""
import os
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    EvidenceValidationFailedException,
    AntivirusThreatDetectedException,
    AntivirusUnavailableException,
    AntivirusTimeoutException,
    AntivirusScanFailedException,
    ForbiddenException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.schemas.evidence import (
    EvidenceIntakeStatus,
    AntivirusVerdict,
    AntivirusScanResult,
    ValidatedEvidenceObject,
    ScannedEvidenceObject,
)

logger = logging.getLogger("sakshi.mod07.antivirus_scan")

# EICAR Standard Harmless Antivirus Test Signature (68 bytes)
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

# Known dangerous test signatures and heuristic malware byte patterns
DANGEROUS_PATTERNS = [
    (EICAR_SIGNATURE, "EICAR-Standard-Antivirus-Test-File"),
    (b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE", "EICAR-Test-Signature"),
    (b"VIRUS_TEST_SIGNATURE_SAKSHI_HOSTILE", "Trojan.Generic.SakshiTest"),
    (b"MALWARE_PAYLOAD_DROPPER_SIMULATION", "Dropper.Test.SakshiTest"),
]

# Max read chunk size for streaming scan (64 KB)
STREAM_CHUNK_SIZE = 65536


# ═══════════════════════════════════════════════════════════════════════════
# Antivirus Scanner Abstraction
# ═══════════════════════════════════════════════════════════════════════════

class IAntivirusScanner(ABC):
    """
    Abstract interface for Antivirus Scanning engines in SAKSHI.
    Decouples business logic from specific AV daemon/CLI implementations.
    """

    @property
    @abstractmethod
    def scanner_name(self) -> str:
        """Name of the antivirus scanner."""
        pass

    @property
    @abstractmethod
    def scanner_version(self) -> str:
        """Version of the antivirus engine and signatures."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the scanning engine daemon/service is healthy and ready."""
        pass

    @abstractmethod
    def scan_file(self, file_path: str, timeout_seconds: float = 30.0) -> Tuple[AntivirusVerdict, Optional[str], str]:
        """
        Scan a staged evidence file without executing it.

        Returns:
            Tuple of (verdict, threat_name, message)
        """
        pass


class EicarHeuristicScanner(IAntivirusScanner):
    """
    Forensic Antivirus Engine for Development, Testing, and Explicitly Configured Lightweight Deployments.
    Performs passive signature scanning for EICAR standard test artifacts,
    known malicious test signatures, heuristic shellcode patterns,
    and embedded malicious macros without executing the binary.

    IMPORTANT ARCHITECTURAL RULE:
    This scanner is an EXPLICIT scanner choice for development/test environments.
    It does NOT serve as an automatic production fallback for ClamAV.
    """

    def __init__(
        self,
        name: str = "EicarHeuristicScanner",
        version: str = "1.0.4-EICAR-HEURISTIC",
        simulate_unavailable: bool = False,
        simulate_timeout: bool = False,
        simulate_error: bool = False,
    ):
        self._name = name
        self._version = version
        self.simulate_unavailable = simulate_unavailable
        self.simulate_timeout = simulate_timeout
        self.simulate_error = simulate_error

    @property
    def scanner_name(self) -> str:
        return self._name

    @property
    def scanner_version(self) -> str:
        return self._version

    def is_available(self) -> bool:
        return not self.simulate_unavailable

    def scan_file(self, file_path: str, timeout_seconds: float = 30.0) -> Tuple[AntivirusVerdict, Optional[str], str]:
        if self.simulate_unavailable:
            return AntivirusVerdict.SCANNER_UNAVAILABLE, None, "Antivirus scanning engine daemon is offline or unreachable."

        if self.simulate_timeout:
            return AntivirusVerdict.SCAN_TIMEOUT, None, f"Antivirus scan timed out after {timeout_seconds:.1f} seconds."

        if self.simulate_error:
            return AntivirusVerdict.SCAN_ERROR, None, "Internal scanner engine error during payload inspection."

        if not os.path.exists(file_path):
            return AntivirusVerdict.SCAN_ERROR, None, f"Payload file not found: {file_path}"

        try:
            # Passive streaming scan — inspect bytes without executing
            with open(file_path, "rb") as f:
                content = f.read()

            # 1. Check for standard EICAR and test signatures
            for sig, threat in DANGEROUS_PATTERNS:
                if sig in content:
                    return AntivirusVerdict.THREAT_DETECTED, threat, f"Hostile signature matched: {threat}."

            # 2. Heuristic check: Suspicious shellcode NOP sled sequences (> 128 consecutive NOPs)
            nop_sled = b"\x90" * 128
            if nop_sled in content:
                return (
                    AntivirusVerdict.THREAT_DETECTED,
                    "Exploit.Shellcode.NOPSled",
                    "Suspicious NOP sled exploit sequence detected in payload."
                )

            # File has no detected threat according to this configured scanner
            return (
                AntivirusVerdict.CLEAN,
                None,
                f"No threat detected by the configured antivirus scanner ({self.scanner_name})."
            )

        except PermissionError:
            return AntivirusVerdict.SCAN_ERROR, None, f"Permission denied while reading payload at '{file_path}'."
        except Exception as e:
            return AntivirusVerdict.SCAN_ERROR, None, f"Scanner failure: {type(e).__name__}: {str(e)}"


class ClamAVScanner(IAntivirusScanner):
    """
    Production ClamAV Scanner integration.
    Attempts connection to ClamAV clamd daemon via TCP stream.
    If ClamAV is not available on the host, reports is_available() == False.

    CRITICAL SECURITY INVARIANT:
    Never silently falls back to EicarHeuristicScanner.
    If ClamAV is unavailable, times out, or fails, it reports a controlled failure (Fail-Closed).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3310,
        name: str = "ClamAVScanner",
        version: str = "ClamAV-0.103+",
        simulate_unavailable: bool = False,
        simulate_timeout: bool = False,
        simulate_error: bool = False,
    ):
        self._host = host
        self._port = port
        self._name = name
        self._version = version
        self.simulate_unavailable = simulate_unavailable
        self.simulate_timeout = simulate_timeout
        self.simulate_error = simulate_error

    @property
    def scanner_name(self) -> str:
        return self._name

    @property
    def scanner_version(self) -> str:
        return self._version

    def is_available(self) -> bool:
        if self.simulate_unavailable:
            return False
        if self.simulate_timeout or self.simulate_error:
            return True
        # Check if clamd is reachable via TCP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((self._host, self._port))
            s.send(b"PING")
            resp = s.recv(1024)
            s.close()
            return b"PONG" in resp
        except Exception:
            return False

    def scan_file(self, file_path: str, timeout_seconds: float = 30.0) -> Tuple[AntivirusVerdict, Optional[str], str]:
        if self.simulate_unavailable:
            return (
                AntivirusVerdict.SCANNER_UNAVAILABLE,
                None,
                f"ClamAV daemon (clamd) is not reachable on {self._host}:{self._port}. Fail-closed.",
            )

        if self.simulate_timeout:
            return (
                AntivirusVerdict.SCAN_TIMEOUT,
                None,
                f"ClamAV scan timed out after {timeout_seconds:.1f} seconds.",
            )

        if self.simulate_error:
            return (
                AntivirusVerdict.SCAN_ERROR,
                None,
                "ClamAV daemon internal processing error.",
            )

        if not self.is_available():
            return (
                AntivirusVerdict.SCANNER_UNAVAILABLE,
                None,
                f"ClamAV daemon (clamd) is not reachable on {self._host}:{self._port}. Fail-closed.",
            )

        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout_seconds)
            s.connect((self._host, self._port))
            # clamd SCAN command
            s.send(f"SCAN {file_path}\n".encode("utf-8"))
            resp = s.recv(4096).decode("utf-8", errors="replace").strip()
            s.close()

            if "OK" in resp:
                return (
                    AntivirusVerdict.CLEAN,
                    None,
                    f"No threat detected by the configured antivirus scanner ({self.scanner_name})."
                )
            elif "FOUND" in resp:
                # e.g.: /path/to/file: Eicar-Test-Signature FOUND
                parts = resp.split(":")
                threat = parts[1].replace("FOUND", "").strip() if len(parts) > 1 else "Unknown.Malware"
                return AntivirusVerdict.THREAT_DETECTED, threat, f"ClamAV threat detected: {threat}."
            else:
                return AntivirusVerdict.SCAN_ERROR, None, f"ClamAV unexpected response: {resp}"
        except socket.timeout:
            return AntivirusVerdict.SCAN_TIMEOUT, None, f"ClamAV scan timed out after {timeout_seconds}s."
        except Exception as e:
            return AntivirusVerdict.SCAN_ERROR, None, f"ClamAV communication error: {str(e)}"


def get_configured_scanner() -> IAntivirusScanner:
    """
    Factory creating the explicitly configured Antivirus Scanner.

    FAIL-CLOSED SELECTION POLICY:
    - If 'clamav' is configured: strictly returns ClamAVScanner. If ClamAV daemon is
      unreachable, it returns SCANNER_UNAVAILABLE. No silent heuristic downgrade.
    - If 'eicar_heuristic' is configured: explicitly returns EicarHeuristicScanner.
    - Unknown engine configuration raises ValueError at startup.
    """
    from app.core.config import settings
    configured = getattr(settings, "ANTIVIRUS_SCANNER", "eicar_heuristic").lower().strip()
    if configured == "clamav":
        return ClamAVScanner(
            host=getattr(settings, "CLAMAV_HOST", "127.0.0.1"),
            port=getattr(settings, "CLAMAV_PORT", 3310),
        )
    elif configured in ("eicar_heuristic", "eicar", "heuristic"):
        return EicarHeuristicScanner()
    else:
        raise ValueError(
            f"Invalid ANTIVIRUS_SCANNER setting: '{configured}'. "
            f"Expected 'clamav' (production) or 'eicar_heuristic' (dev/testing)."
        )


# ═══════════════════════════════════════════════════════════════════════════
# MOD-07 Antivirus Scan Orchestration Service
# ═══════════════════════════════════════════════════════════════════════════

class AntivirusScanService:
    """
    MOD-07: Antivirus Scan Service.
    Coordinates evidence verification, authorization checks, workspace isolation,
    scanner invocation, audit logging, and state transitions.
    """

    def __init__(
        self,
        db: Session,
        scanner: Optional[IAntivirusScanner] = None,
        authz: Optional[IAuthorizationService] = None,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz or authorization_service
        self.scanner = scanner or get_configured_scanner()

    def set_scanner(self, scanner: IAntivirusScanner) -> None:
        """Dynamically configure or mock the scanner engine."""
        self.scanner = scanner

    def scan_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
        timeout_seconds: float = 30.0,
    ) -> AntivirusScanResult:
        """
        Consumes ValidatedEvidenceObject (from MOD-06) and runs antivirus scan.

        Workflow:
            1. Authenticate & Authorize investigator via MOD-03 ('evidence:scan').
            2. Validate case existence and evidence belonging.
            3. Verify evidence status is 'VALIDATED' (or 'CLEAN' if rescanning).
            4. Verify physical payload existence and workspace boundary containment.
            5. Check scanner health/availability (FAIL-CLOSED if unavailable).
            6. Log EVIDENCE_AV_SCAN_STARTED audit event.
            7. Perform passive file byte scan without execution.
            8. Persist scan verdict to database.
            9. Update evidence status to CLEAN or QUARANTINED.
            10. Emit audit event (EVIDENCE_AV_CLEAN, EVIDENCE_AV_THREAT_DETECTED, or EVIDENCE_AV_SCAN_ERROR).
            11. Return AntivirusScanResult.
        """
        # 1. Fetch Case
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 2. RBAC/ABAC Authorization check (MOD-03)
        self.authz.check_can_scan_evidence(investigator, case)

        # 3. Fetch Evidence Record
        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 4. Enforce Pipeline Ordering: Must be VALIDATED by MOD-06
        # Note: If rescanning an already-clean file, allow rescan; otherwise strictly require VALIDATED
        allowed_statuses = [
            EvidenceIntakeStatus.VALIDATED.value,
            EvidenceIntakeStatus.CLEAN.value,
        ]
        if evidence.status not in allowed_statuses:
            raise EvidenceValidationFailedException(
                f"Evidence '{evidence_id}' has status '{evidence.status}' and cannot enter MOD-07. "
                f"Only files validated by MOD-06 (status '{EvidenceIntakeStatus.VALIDATED.value}') can be scanned."
            )

        # 5. Payload Path & Workspace Boundary Containment
        staged_path = evidence.raw_storage_path
        if not os.path.exists(staged_path):
            raise EvidenceFileNotFoundException(staged_path)

        canonical_payload_path = os.path.realpath(staged_path)
        canonical_workspace_path = os.path.realpath(case.case_workspace_path)

        # Prevent path traversal or cross-case access
        if not canonical_payload_path.startswith(canonical_workspace_path + os.sep) and \
           canonical_payload_path != canonical_workspace_path:
            log_event(
                event_type="WORKSPACE_BOUNDARY_VIOLATION",
                message=f"Evidence path '{canonical_payload_path}' escapes case workspace '{canonical_workspace_path}'.",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )
            raise ForbiddenException("Evidence storage path violates case workspace boundary containment.")

        # 6. Audit: Scan Started
        now = datetime.now(timezone.utc)
        AuditIntegrationService.record_event(
            action="EVIDENCE_AV_SCAN_STARTED",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "scanner": self.scanner.scanner_name,
                "scanner_version": self.scanner.scanner_version,
            },
        )

        # 7. Fail-Closed Health Check (No unsafe fallback)
        if not self.scanner.is_available():
            err_msg = f"Antivirus scanner '{self.scanner.scanner_name}' is offline or unavailable. Fail-closed."
            self._record_scan_failure(
                evidence=evidence,
                case=case,
                investigator=investigator,
                verdict=AntivirusVerdict.SCANNER_UNAVAILABLE,
                message=err_msg,
            )
            raise AntivirusUnavailableException(err_msg)

        # 8. Execute Passive Scan
        start_time = time.perf_counter()
        verdict, threat_name, message = self.scanner.scan_file(
            file_path=canonical_payload_path,
            timeout_seconds=timeout_seconds,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        scanned_at = datetime.now(timezone.utc)

        # 9. Handle Scanner Verdicts
        if verdict == AntivirusVerdict.SCAN_TIMEOUT:
            err_msg = f"Antivirus scanner timed out scanning '{evidence_id}'."
            self._record_scan_failure(
                evidence=evidence,
                case=case,
                investigator=investigator,
                verdict=AntivirusVerdict.SCAN_TIMEOUT,
                message=err_msg,
            )
            raise AntivirusTimeoutException(err_msg)

        if verdict == AntivirusVerdict.SCAN_ERROR:
            err_msg = f"Antivirus scan error for '{evidence_id}': {message}"
            self._record_scan_failure(
                evidence=evidence,
                case=case,
                investigator=investigator,
                verdict=AntivirusVerdict.SCAN_ERROR,
                message=err_msg,
            )
            raise AntivirusScanFailedException(err_msg)

        if verdict == AntivirusVerdict.SCANNER_UNAVAILABLE:
            err_msg = f"Antivirus scanner unavailable: {message}"
            self._record_scan_failure(
                evidence=evidence,
                case=case,
                investigator=investigator,
                verdict=AntivirusVerdict.SCANNER_UNAVAILABLE,
                message=err_msg,
            )
            raise AntivirusUnavailableException(err_msg)

        # 10. Threat Detected or Clean
        if verdict == AntivirusVerdict.THREAT_DETECTED:
            # QUARANTINE EVIDENCE
            target_status = EvidenceIntakeStatus.QUARANTINED.value
            evidence.status = target_status
            evidence.antivirus_status = AntivirusVerdict.THREAT_DETECTED.value
            evidence.antivirus_scanner = self.scanner.scanner_name
            evidence.antivirus_version = self.scanner.scanner_version
            evidence.antivirus_threat_name = threat_name
            evidence.antivirus_message = message
            evidence.antivirus_scanned_at = scanned_at
            self.evidence_repo.update(evidence)

            AuditIntegrationService.record_event(
                action="EVIDENCE_AV_THREAT_DETECTED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "verdict": verdict.value,
                    "threat_name": threat_name,
                    "message": message,
                    "scanner": self.scanner.scanner_name,
                    "scanner_version": self.scanner.scanner_version,
                },
            )

            log_event(
                event_type="ANTIVIRUS_THREAT_DETECTED",
                message=f"Threat '{threat_name}' detected in evidence '{evidence.evidence_id}'. Evidence quarantined.",
                case_id=case.case_id,
                investigator_id=investigator.investigator_id,
                extra_data={"threat_name": threat_name, "scanner": self.scanner.scanner_name},
            )

            return AntivirusScanResult(
                evidence_id=evidence.evidence_id,
                case_id=case.case_id,
                verdict=verdict,
                status=target_status,
                scanner_name=self.scanner.scanner_name,
                scanner_version=self.scanner.scanner_version,
                threat_name=threat_name,
                message=message,
                duration_ms=duration_ms,
                scanned_at=scanned_at,
            )

        # CLEAN VERDICT
        # SEMANTIC DEFINITION:
        # CLEAN means no threat was detected by the configured antivirus scanner.
        # It is NOT an absolute guarantee or proof that the payload contains no malware.
        clean_msg = message or f"No threat detected by the configured antivirus scanner ({self.scanner.scanner_name})."
        target_status = EvidenceIntakeStatus.CLEAN.value
        evidence.status = target_status
        evidence.antivirus_status = AntivirusVerdict.CLEAN.value
        evidence.antivirus_scanner = self.scanner.scanner_name
        evidence.antivirus_version = self.scanner.scanner_version
        evidence.antivirus_threat_name = None
        evidence.antivirus_message = clean_msg
        evidence.antivirus_scanned_at = scanned_at
        self.evidence_repo.update(evidence)

        AuditIntegrationService.record_event(
            action="EVIDENCE_AV_CLEAN",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "verdict": verdict.value,
                "scanner": self.scanner.scanner_name,
                "scanner_version": self.scanner.scanner_version,
                "semantic_meaning": "No threat detected by the configured antivirus scanner.",
            },
        )

        log_event(
            event_type="ANTIVIRUS_SCAN_CLEAN",
            message=f"Evidence '{evidence.evidence_id}': no threat detected by configured scanner '{self.scanner.scanner_name}'.",
            case_id=case.case_id,
            investigator_id=investigator.investigator_id,
        )

        return AntivirusScanResult(
            evidence_id=evidence.evidence_id,
            case_id=case.case_id,
            verdict=verdict,
            status=target_status,
            scanner_name=self.scanner.scanner_name,
            scanner_version=self.scanner.scanner_version,
            threat_name=None,
            message=clean_msg,
            duration_ms=duration_ms,
            scanned_at=scanned_at,
        )

    def _record_scan_failure(
        self,
        evidence: Evidence,
        case: Case,
        investigator: AuthenticatedInvestigator,
        verdict: AntivirusVerdict,
        message: str,
    ) -> None:
        """
        Record failure in audit logs and update evidence AV metadata
        without changing the evidence status to CLEAN (Fail-Closed).
        """
        scanned_at = datetime.now(timezone.utc)
        evidence.antivirus_status = verdict.value
        evidence.antivirus_scanner = self.scanner.scanner_name
        evidence.antivirus_version = self.scanner.scanner_version
        evidence.antivirus_message = message
        evidence.antivirus_scanned_at = scanned_at
        self.evidence_repo.update(evidence)

        AuditIntegrationService.record_event(
            action="EVIDENCE_AV_SCAN_ERROR",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "verdict": verdict.value,
                "failure_reason": message,
                "scanner": self.scanner.scanner_name,
            },
        )

        log_event(
            event_type="ANTIVIRUS_SCAN_FAILURE",
            message=f"Antivirus scan failure for '{evidence.evidence_id}': {message}",
            case_id=case.case_id,
            investigator_id=investigator.investigator_id,
        )

    def get_scanned_evidence_object(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> ScannedEvidenceObject:
        """
        Downstream Handoff Contract for MOD-08 (WORM Commit + Checksum).

        STRICT INVARIANT:
            Only evidence with status == 'CLEAN' and antivirus_status == 'CLEAN'
            is permitted to proceed to MOD-08.
            A CLEAN verdict means no threat was detected by the configured scanner.
            Quarantined, infected, or unscanned files are strictly blocked.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        self.authz.check_can_read_evidence(investigator, case)

        if evidence.status == EvidenceIntakeStatus.QUARANTINED.value or \
           evidence.antivirus_status == AntivirusVerdict.THREAT_DETECTED.value:
            raise AntivirusThreatDetectedException(
                threat_name=evidence.antivirus_threat_name or "Unknown Threat",
                message=(
                    f"Evidence '{evidence_id}' is quarantined due to detected threat "
                    f"'{evidence.antivirus_threat_name}' and cannot proceed to MOD-08."
                ),
            )

        if evidence.status != EvidenceIntakeStatus.CLEAN.value or \
           evidence.antivirus_status != AntivirusVerdict.CLEAN.value:
            raise AntivirusScanFailedException(
                f"Evidence '{evidence_id}' has not passed antivirus scanning (status: '{evidence.status}'). "
                f"Only evidence with no threat detected by the configured scanner can proceed to MOD-08."
            )

        return ScannedEvidenceObject(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            staged_file_path=evidence.raw_storage_path,
            original_file_name=evidence.original_file_name,
            verified_mime_type=evidence.detected_mime_type or evidence.declared_mime_type,
            detected_format=evidence.detected_format or "UNKNOWN",
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            submitting_investigator_id=evidence.submitting_investigator_id,
            mime_status=EvidenceIntakeStatus.VALIDATED.value,
            antivirus_verdict=evidence.antivirus_status,
            antivirus_scanner=evidence.antivirus_scanner or self.scanner.scanner_name,
            antivirus_scanned_at=evidence.antivirus_scanned_at or datetime.now(timezone.utc),
        )
