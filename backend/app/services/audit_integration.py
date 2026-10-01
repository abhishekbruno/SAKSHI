"""
Integration point for future audit subsystem (Milestone 4 / Phase 16 Merkle Audit Trail).
Records who, what, which case, and when without blocking primary case management transactions.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.logging import log_event


class AuditIntegrationService:
    """
    PROPOSED IMPLEMENTATION DECISION:
    Provides a standardized facade for governance audit events.
    In Phase 16, this connects to the append-only cryptographic Merkle audit ledger.
    """

    @staticmethod
    def record_event(
        action: str,
        investigator_id: str,
        case_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        event_payload = {
            "action": action,
            "investigator_id": investigator_id,
            "case_id": case_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {}
        }
        # Log to structured application log
        log_event(
            event_type=f"AUDIT_{action}",
            message=f"Audit action '{action}' on case '{case_id}' by investigator '{investigator_id}'",
            case_id=case_id,
            investigator_id=investigator_id,
            extra_data=event_payload
        )
        return event_payload

    @staticmethod
    def record_auth_event(
        event_type: str,
        subject_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        MOD-02: Record authentication-related audit events.

        Supported event types:
            AUTHENTICATION_SUCCESS
            AUTHENTICATION_FAILURE
            TOKEN_VALIDATION_FAILURE

        SECURITY: Never log tokens, passwords, signing keys, or client secrets.
        Only safe metadata (timestamp, event type, subject_id, result).
        """
        event_payload = {
            "event_type": event_type,
            "subject_id": subject_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {}
        }
        log_event(
            event_type=f"AUDIT_AUTH_{event_type}",
            message=f"Auth event '{event_type}' for subject '{subject_id or 'unknown'}'",
            investigator_id=subject_id,
            extra_data=event_payload
        )
        return event_payload

    @staticmethod
    def record_authorization_event(
        decision: str,
        subject_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        MOD-03: Record authorization decision audit events (RBAC / ABAC).

        Records ALLOW/DENY decisions with subject, resource, policy, and reason.
        SECURITY: Safe audit metadata only — no secrets.
        """
        event_payload = {
            "decision": decision,
            "subject_id": subject_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "policy_id": policy_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {}
        }
        log_event(
            event_type=f"AUDIT_AUTHZ_{decision}",
            message=f"Authorization {decision}: action='{action}' resource='{resource_type}:{resource_id}' subject='{subject_id}' policy='{policy_id}'",
            investigator_id=subject_id,
            case_id=resource_id,
            extra_data=event_payload
        )
        return event_payload
