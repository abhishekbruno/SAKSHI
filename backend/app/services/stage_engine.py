"""
MOD-04: Stage Engine for SAKSHI Investigation Platform.

Controls the lifecycle and state machine of unnatural death investigations.

Architecture:
    MOD-02: Identity / OIDC       → "Who are you?"
    MOD-03: RBAC / ABAC           → "Are you allowed to perform actions on this case?"
    MOD-04: Stage Engine          → "Is this lifecycle transition valid?"
    MOD-01: Case Management       → Perform persisted state transition

Pipeline Flow:
    INITIALIZED
        │
        ▼
    EVIDENCE_INGESTION (Phase 2 Gate)
        │
        ▼
    EVIDENCE_PROCESSING (Phase 3 Integrity & Analysis)
        │
        ▼
    ANALYSIS (Phase 4-7 EC-MORE Timeline & Contradiction)
        │
        ▼
    REVIEW (Supervisory / Final Report Prep)
        │
        ▼
    CLOSED (Final Invariant / Archived)

Special States:
    SUSPENDED: Administrative or legal stay
    REOPENED: New evidence discovered after closure (Supervisory only)
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set

from app.core.errors import InvalidStageException
from app.core.security import AuthenticatedInvestigator
from app.core.logging import log_event

logger = logging.getLogger("sakshi.mod04.stage_engine")


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle Stages
# ═══════════════════════════════════════════════════════════════════════════

class CaseStage(str, Enum):
    """
    Formal lifecycle stages for SAKSHI unnatural death investigations.
    Corresponds to the sequential progression across pipeline phases.
    """
    INITIALIZED = "INITIALIZED"
    EVIDENCE_INGESTION = "EVIDENCE_INGESTION"
    EVIDENCE_PROCESSING = "EVIDENCE_PROCESSING"
    ANALYSIS = "ANALYSIS"
    REVIEW = "REVIEW"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"
    REOPENED = "REOPENED"


# ═══════════════════════════════════════════════════════════════════════════
# Transition Graph
# ═══════════════════════════════════════════════════════════════════════════

STAGE_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    CaseStage.INITIALIZED.value: frozenset({
        CaseStage.EVIDENCE_INGESTION.value,
        CaseStage.SUSPENDED.value,
    }),
    CaseStage.EVIDENCE_INGESTION.value: frozenset({
        CaseStage.EVIDENCE_PROCESSING.value,
        CaseStage.INITIALIZED.value,
        CaseStage.SUSPENDED.value,
    }),
    CaseStage.EVIDENCE_PROCESSING.value: frozenset({
        CaseStage.ANALYSIS.value,
        CaseStage.EVIDENCE_INGESTION.value,
        CaseStage.SUSPENDED.value,
    }),
    CaseStage.ANALYSIS.value: frozenset({
        CaseStage.REVIEW.value,
        CaseStage.EVIDENCE_INGESTION.value,
        CaseStage.SUSPENDED.value,
    }),
    CaseStage.REVIEW.value: frozenset({
        CaseStage.CLOSED.value,
        CaseStage.ANALYSIS.value,
        CaseStage.EVIDENCE_INGESTION.value,
        CaseStage.SUSPENDED.value,
    }),
    CaseStage.SUSPENDED.value: frozenset({
        CaseStage.INITIALIZED.value,
        CaseStage.EVIDENCE_INGESTION.value,
        CaseStage.EVIDENCE_PROCESSING.value,
        CaseStage.ANALYSIS.value,
        CaseStage.REVIEW.value,
    }),
    CaseStage.CLOSED.value: frozenset({
        CaseStage.REOPENED.value,
    }),
    CaseStage.REOPENED.value: frozenset({
        CaseStage.EVIDENCE_INGESTION.value,
        CaseStage.ANALYSIS.value,
        CaseStage.SUSPENDED.value,
    }),
}

# Transitions requiring supervisory authority
SUPERVISORY_TRANSITIONS: Set[str] = {
    CaseStage.CLOSED.value,
    CaseStage.REOPENED.value,
}

SUPERVISORY_ROLES: FrozenSet[str] = frozenset({
    "SUPERVISORY_OFFICER", "STATION_HEAD", "ADMIN", "SUPERVISOR", "SYSTEM_ADMIN"
})


# ═══════════════════════════════════════════════════════════════════════════
# Stage Transition Decision Model
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class StageTransitionDecision:
    """
    Explainable outcome of a lifecycle stage validation request.
    """
    valid: bool
    current_stage: str
    target_stage: str
    reason: str
    allowed_transitions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, any]:
        return {
            "valid": self.valid,
            "current_stage": self.current_stage,
            "target_stage": self.target_stage,
            "reason": self.reason,
            "allowed_transitions": self.allowed_transitions,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Stage Engine Core
# ═══════════════════════════════════════════════════════════════════════════

class StageEngine:
    """
    Deterministic state machine for case lifecycle governance.
    Enforces valid progression, prevents illegal jumps, and audits transitions.
    """

    def __init__(
        self,
        transitions: Optional[Dict[str, FrozenSet[str]]] = None,
        supervisory_transitions: Optional[Set[str]] = None,
        supervisory_roles: Optional[FrozenSet[str]] = None,
    ):
        self._transitions = transitions or STAGE_TRANSITIONS
        self._supervisory_transitions = supervisory_transitions or SUPERVISORY_TRANSITIONS
        self._supervisory_roles = supervisory_roles or SUPERVISORY_ROLES

    def validate_transition(
        self,
        current_stage: str,
        target_stage: str,
        investigator: Optional[AuthenticatedInvestigator] = None,
    ) -> StageTransitionDecision:
        """
        Validate whether transitioning from current_stage to target_stage is permitted.

        Checks:
            1. Valid stage names (member of CaseStage)
            2. Idempotent self-transition check
            3. State machine path legality (must be in allowed transitions)
            4. Supervisory privilege requirements (e.g. CLOSED, REOPENED)
        """
        current_stage = (current_stage or "").strip().upper()
        target_stage = (target_stage or "").strip().upper()

        # 1. Validate target stage exists
        valid_stage_names = {s.value for s in CaseStage}
        if target_stage not in valid_stage_names:
            return StageTransitionDecision(
                valid=False,
                current_stage=current_stage,
                target_stage=target_stage,
                reason=f"Target stage '{target_stage}' is not a recognized lifecycle stage. Valid stages: {sorted(valid_stage_names)}",
                allowed_transitions=self.get_allowed_transitions(current_stage),
            )

        if current_stage not in valid_stage_names:
            return StageTransitionDecision(
                valid=False,
                current_stage=current_stage,
                target_stage=target_stage,
                reason=f"Current case stage '{current_stage}' is invalid or corrupted.",
                allowed_transitions=[],
            )

        # 2. Self-transition check
        if current_stage == target_stage:
            return StageTransitionDecision(
                valid=False,
                current_stage=current_stage,
                target_stage=target_stage,
                reason=f"Case is already in stage '{current_stage}'. Redundant transition rejected.",
                allowed_transitions=self.get_allowed_transitions(current_stage),
            )

        # 3. Path legality check
        allowed = self._transitions.get(current_stage, frozenset())
        if target_stage not in allowed:
            return StageTransitionDecision(
                valid=False,
                current_stage=current_stage,
                target_stage=target_stage,
                reason=f"Invalid lifecycle transition from '{current_stage}' to '{target_stage}'. Permitted transitions: {sorted(allowed)}",
                allowed_transitions=sorted(allowed),
            )

        # 4. Supervisory privilege check
        if target_stage in self._supervisory_transitions and investigator:
            roles = set(investigator.roles) if investigator.roles else {investigator.role}
            if not (roles & self._supervisory_roles):
                return StageTransitionDecision(
                    valid=False,
                    current_stage=current_stage,
                    target_stage=target_stage,
                    reason=f"Transitioning to '{target_stage}' requires supervisory authorization. Current role '{investigator.role}' is insufficient.",
                    allowed_transitions=sorted(allowed),
                )

        return StageTransitionDecision(
            valid=True,
            current_stage=current_stage,
            target_stage=target_stage,
            reason=f"Lifecycle transition from '{current_stage}' to '{target_stage}' is valid.",
            allowed_transitions=sorted(allowed),
        )

    def get_allowed_transitions(self, current_stage: str) -> List[str]:
        """Return a sorted list of permitted target stages from the current stage."""
        stage_key = (current_stage or "").strip().upper()
        return sorted(self._transitions.get(stage_key, frozenset()))

    def can_transition(
        self,
        current_stage: str,
        target_stage: str,
        investigator: Optional[AuthenticatedInvestigator] = None,
    ) -> bool:
        """Convenience boolean check."""
        return self.validate_transition(current_stage, target_stage, investigator).valid


# Singleton StageEngine instance
stage_engine = StageEngine()
