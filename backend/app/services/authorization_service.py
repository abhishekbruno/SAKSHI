"""
MOD-03: RBAC / ABAC Authorization Engine for SAKSHI Investigation Platform.

Answers the question: "What is this authenticated investigator allowed to do?"

Architecture:
    ┌─────────────────────────────────┐
    │ MOD-02 Identity/OIDC            │
    │ → AuthenticatedInvestigator     │
    └────────────┬────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────┐
    │ MOD-03 Authorization Engine     │
    │                                 │
    │  ┌───────┐ ┌──────┐ ┌───────┐  │
    │  │ RBAC  │ │ ABAC │ │Context│  │
    │  └───┬───┘ └──┬───┘ └───┬───┘  │
    │      └────────┼─────────┘      │
    │               ▼                │
    │        Policy Engine           │
    │               │                │
    │         ┌─────┴─────┐          │
    │       ALLOW        DENY        │
    └─────────────────────────────────┘

CRITICAL RULES:
    - DEFAULT DENY: If no policy explicitly allows → DENY.
    - Authentication (MOD-02) is consumed, NOT reimplemented.
    - Client-supplied roles, stations, jurisdictions are NEVER trusted.
    - Only trusted backend identity (from validated token) and trusted
      resource attributes (from database) are used for authorization.
    - Authorization decisions are auditable and explainable.
    - These are configurable software policies — NOT official police policy.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Set, FrozenSet

from app.core.security import AuthenticatedInvestigator
from app.core.errors import ForbiddenException
from app.core.logging import log_event

logger = logging.getLogger("sakshi.mod03.authorization")


# ═══════════════════════════════════════════════════════════════════════════
# Permissions — explicit actions in the system
# ═══════════════════════════════════════════════════════════════════════════

class Permission(str, Enum):
    """
    Explicit permission strings for SAKSHI operations.
    Only permissions required by the current system are defined.
    Phase 2 permissions (evidence:*) will be added when needed.
    """
    CASE_CREATE = "case:create"
    CASE_READ = "case:read"
    CASE_UPDATE = "case:update"
    CASE_LIST = "case:list"
    CASE_ASSIGN = "case:assign"
    CASE_STAGE_UPDATE = "case:stage:update"


# ═══════════════════════════════════════════════════════════════════════════
# Role-Permission Registry (RBAC)
# ═══════════════════════════════════════════════════════════════════════════

# These are APPLICATION ROLES for configurable authorization.
# They are NOT claimed to represent official police organizational hierarchy.

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "INVESTIGATING_OFFICER": frozenset({
        Permission.CASE_CREATE,
        Permission.CASE_READ,
        Permission.CASE_UPDATE,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
        Permission.CASE_STAGE_UPDATE,
    }),
    "SUPERVISORY_OFFICER": frozenset({
        Permission.CASE_CREATE,
        Permission.CASE_READ,
        Permission.CASE_UPDATE,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
        Permission.CASE_STAGE_UPDATE,
    }),
    "STATION_HEAD": frozenset({
        Permission.CASE_CREATE,
        Permission.CASE_READ,
        Permission.CASE_UPDATE,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
        Permission.CASE_STAGE_UPDATE,
    }),
    "ADMIN": frozenset({
        Permission.CASE_CREATE,
        Permission.CASE_READ,
        Permission.CASE_UPDATE,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
        Permission.CASE_STAGE_UPDATE,
    }),
    # Backward-compat aliases from existing codebase
    "SUPERVISOR": frozenset({
        Permission.CASE_CREATE,
        Permission.CASE_READ,
        Permission.CASE_UPDATE,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
        Permission.CASE_STAGE_UPDATE,
    }),
    "CASE_ADMIN": frozenset({
        Permission.CASE_READ,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
    }),
    "SYSTEM_ADMIN": frozenset({
        Permission.CASE_CREATE,
        Permission.CASE_READ,
        Permission.CASE_UPDATE,
        Permission.CASE_LIST,
        Permission.CASE_ASSIGN,
        Permission.CASE_STAGE_UPDATE,
    }),
}

# Roles that have elevated access (broader visibility, can access other IOs' cases)
SUPERVISORY_ROLES: FrozenSet[str] = frozenset({
    "SUPERVISORY_OFFICER", "STATION_HEAD", "ADMIN", "SUPERVISOR", "SYSTEM_ADMIN"
})


# ═══════════════════════════════════════════════════════════════════════════
# Authorization Decision (explainable result)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AuthorizationDecision:
    """
    Explainable authorization decision.

    Contains enough information for safe logging/debugging
    without exposing internal policy details to clients.
    """
    allowed: bool
    policy_id: str
    reason: str
    action: str
    resource_type: str = "case"
    resource_id: Optional[str] = None
    subject_id: Optional[str] = None
    evaluated_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_audit_dict(self) -> Dict[str, Any]:
        """Safe representation for audit logging — no secrets."""
        return {
            "decision": "ALLOW" if self.allowed else "DENY",
            "policy_id": self.policy_id,
            "reason": self.reason,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "subject_id": self.subject_id,
        }

    def to_safe_client_message(self) -> str:
        """Safe explanation for the client — no policy internals."""
        if self.allowed:
            return "Access granted."
        return "Access denied: you are not authorized to perform this operation."


# ═══════════════════════════════════════════════════════════════════════════
# Authorization Context
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AuthorizationContext:
    """
    Encapsulates all trusted attributes for a single authorization decision.

    SECURITY: All attributes must come from trusted backend sources:
        - Subject attributes → from validated MOD-02 AuthenticatedInvestigator
        - Resource attributes → from database (Case model)
        - Action → from route handler
        - Context → from server-side state

    NEVER from client-supplied request body or query parameters.
    """
    # Subject attributes (from MOD-02 authenticated identity)
    subject_id: str
    subject_role: str
    subject_roles: List[str]
    subject_jurisdiction: Optional[str] = None
    authentication_method: str = "unknown"

    # Resource attributes (from database)
    resource_type: str = "case"
    resource_id: Optional[str] = None
    resource_assigned_io: Optional[str] = None
    resource_jurisdiction: Optional[str] = None
    resource_status: Optional[str] = None
    resource_stage: Optional[str] = None

    # Action
    action: str = ""

    # Additional context
    target_io_id: Optional[str] = None  # For assignment operations
    is_authenticated: bool = True

    @classmethod
    def from_investigator(
        cls,
        investigator: AuthenticatedInvestigator,
        action: str,
        resource_id: Optional[str] = None,
        case=None,
        target_io_id: Optional[str] = None,
    ) -> "AuthorizationContext":
        """
        Build authorization context from trusted sources only.

        investigator: from MOD-02 (validated token)
        case: from database (CaseRepository)
        action: from route handler (server-side)
        """
        ctx = cls(
            subject_id=investigator.subject_id,
            subject_role=investigator.role,
            subject_roles=investigator.roles if investigator.roles else [investigator.role],
            subject_jurisdiction=investigator.station_jurisdiction,
            authentication_method=investigator.authentication_method,
            action=action,
            resource_id=resource_id,
            target_io_id=target_io_id,
            is_authenticated=investigator.is_authenticated,
        )

        if case is not None:
            ctx.resource_id = getattr(case, "case_id", resource_id)
            ctx.resource_assigned_io = getattr(case, "assigned_io_id", None)
            ctx.resource_status = getattr(case, "status", None)
            ctx.resource_stage = getattr(case, "lifecycle_stage", None)
            # Extract jurisdiction from FIR metadata
            fir_meta = getattr(case, "fir_metadata", None)
            if isinstance(fir_meta, dict):
                ctx.resource_jurisdiction = fir_meta.get("jurisdiction_code") or fir_meta.get("police_station")

        return ctx


# ═══════════════════════════════════════════════════════════════════════════
# Policy Engine — RBAC + ABAC evaluation
# ═══════════════════════════════════════════════════════════════════════════

class PolicyEngine:
    """
    Central policy engine that evaluates authorization decisions
    using RBAC (role→permission) and ABAC (attribute-based) rules.

    Evaluation order:
        1. RBAC: Does the investigator's role grant the required permission?
        2. ABAC: Do the resource/subject attributes satisfy the policy constraints?

    DEFAULT DENY: If no policy explicitly allows → DENY.
    """

    def __init__(
        self,
        role_permissions: Dict[str, FrozenSet[str]] = None,
        supervisory_roles: FrozenSet[str] = None,
    ):
        self._role_permissions = role_permissions or ROLE_PERMISSIONS
        self._supervisory_roles = supervisory_roles or SUPERVISORY_ROLES

    def evaluate(self, ctx: AuthorizationContext) -> AuthorizationDecision:
        """
        Central authorization evaluation.

        Runs through the policy chain:
            1. Check role has the required permission (RBAC)
            2. Check attribute-based constraints (ABAC)

        Returns an AuthorizationDecision (never raises directly).
        """
        # Step 1: RBAC — Does the role have the required permission?
        rbac_decision = self._evaluate_rbac(ctx)
        if not rbac_decision.allowed:
            return rbac_decision

        # Step 2: ABAC — Do attributes satisfy constraints?
        abac_decision = self._evaluate_abac(ctx)
        return abac_decision

    def _evaluate_rbac(self, ctx: AuthorizationContext) -> AuthorizationDecision:
        """
        RBAC evaluation: Does the investigator's role grant the required permission?

        Checks all roles the investigator holds (from MOD-02 token claims).
        DEFAULT DENY: Unknown roles have no permissions.
        """
        required_permission = self._action_to_permission(ctx.action)
        if not required_permission:
            return AuthorizationDecision(
                allowed=False,
                policy_id="RBAC_UNKNOWN_ACTION",
                reason=f"No permission mapping for action '{ctx.action}'.",
                action=ctx.action,
                subject_id=ctx.subject_id,
                resource_id=ctx.resource_id,
                evaluated_attributes={"action": ctx.action, "role": ctx.subject_role},
            )

        # Check ALL roles the investigator holds
        roles_to_check = set(ctx.subject_roles) if ctx.subject_roles else {ctx.subject_role}

        for role in roles_to_check:
            role_perms = self._role_permissions.get(role, frozenset())
            if required_permission in role_perms:
                return AuthorizationDecision(
                    allowed=True,
                    policy_id="RBAC_ROLE_PERMISSION",
                    reason=f"Role '{role}' grants permission '{required_permission}'.",
                    action=ctx.action,
                    subject_id=ctx.subject_id,
                    resource_id=ctx.resource_id,
                    evaluated_attributes={
                        "role": role,
                        "permission": required_permission,
                    },
                )

        # DEFAULT DENY
        return AuthorizationDecision(
            allowed=False,
            policy_id="RBAC_PERMISSION_DENIED",
            reason=f"Role(s) {list(roles_to_check)} do not grant permission '{required_permission}'.",
            action=ctx.action,
            subject_id=ctx.subject_id,
            resource_id=ctx.resource_id,
            evaluated_attributes={
                "roles": list(roles_to_check),
                "required_permission": required_permission,
            },
        )

    def _evaluate_abac(self, ctx: AuthorizationContext) -> AuthorizationDecision:
        """
        ABAC evaluation: attribute-based constraints beyond role permissions.

        Policies:
            CASE_ACCESS_ASSIGNED_IO:     Assigned IO can access their own case.
            CASE_ACCESS_SUPERVISORY:     Supervisory roles have broader access.
            CASE_ACCESS_JURISDICTION:    Jurisdiction match for non-supervisory.
            CASE_ASSIGN_SELF:            Self-assignment on creation is permitted.
            CASE_ASSIGN_SUPERVISORY:     Only supervisory roles can reassign to others.
        """
        action = ctx.action

        # For operations that don't involve a specific case resource, RBAC is sufficient
        if action in ("create",) and ctx.resource_id is None:
            return AuthorizationDecision(
                allowed=True,
                policy_id="ABAC_CREATE_NO_RESOURCE",
                reason="Case creation does not require resource-level access check.",
                action=action,
                subject_id=ctx.subject_id,
            )

        if action == "list":
            # List filtering is handled at the query level, not by deny/allow
            return AuthorizationDecision(
                allowed=True,
                policy_id="ABAC_LIST_FILTERED",
                reason="Case listing is filtered by investigator's authorized scope.",
                action=action,
                subject_id=ctx.subject_id,
            )

        if action == "assign":
            return self._evaluate_assign_policy(ctx)

        # For read/update/stage_update — check case-level access
        if action in ("read", "update", "stage_update"):
            return self._evaluate_case_access(ctx)

        # DEFAULT DENY for unknown actions
        return AuthorizationDecision(
            allowed=False,
            policy_id="ABAC_DEFAULT_DENY",
            reason=f"No ABAC policy for action '{action}'.",
            action=action,
            subject_id=ctx.subject_id,
            resource_id=ctx.resource_id,
        )

    def _evaluate_case_access(self, ctx: AuthorizationContext) -> AuthorizationDecision:
        """
        Evaluate case-level access (read, update, stage_update).

        Policy chain (first match wins):
            1. CASE_ACCESS_SUPERVISORY: Supervisory roles → ALLOW
            2. CASE_ACCESS_ASSIGNED_IO: Assigned IO → ALLOW
            3. DEFAULT DENY
        """
        is_supervisory = self._is_supervisory(ctx)

        # Policy 1: Supervisory roles have broad access
        if is_supervisory:
            return AuthorizationDecision(
                allowed=True,
                policy_id="CASE_ACCESS_SUPERVISORY",
                reason="Investigator holds a supervisory role with broad case access.",
                action=ctx.action,
                subject_id=ctx.subject_id,
                resource_id=ctx.resource_id,
                evaluated_attributes={
                    "role": ctx.subject_role,
                    "supervisory": True,
                },
            )

        # Policy 2: Assigned IO can access their own case
        if ctx.resource_assigned_io and ctx.subject_id == ctx.resource_assigned_io:
            return AuthorizationDecision(
                allowed=True,
                policy_id="CASE_ACCESS_ASSIGNED_IO",
                reason="Investigator is the assigned IO for this case.",
                action=ctx.action,
                subject_id=ctx.subject_id,
                resource_id=ctx.resource_id,
                evaluated_attributes={
                    "assigned_io": ctx.resource_assigned_io,
                    "subject_id": ctx.subject_id,
                },
            )

        # Policy 3: Jurisdiction match for non-supervisory (if jurisdiction data is available)
        if (ctx.subject_jurisdiction and ctx.resource_jurisdiction
                and ctx.subject_jurisdiction == ctx.resource_jurisdiction):
            return AuthorizationDecision(
                allowed=True,
                policy_id="CASE_ACCESS_JURISDICTION",
                reason="Investigator's jurisdiction matches the case jurisdiction.",
                action=ctx.action,
                subject_id=ctx.subject_id,
                resource_id=ctx.resource_id,
                evaluated_attributes={
                    "subject_jurisdiction": ctx.subject_jurisdiction,
                    "resource_jurisdiction": ctx.resource_jurisdiction,
                },
            )

        # DEFAULT DENY
        return AuthorizationDecision(
            allowed=False,
            policy_id="CASE_ACCESS_DENIED",
            reason="Investigator is not assigned to this case, does not hold a supervisory role, "
                   "and jurisdiction does not match.",
            action=ctx.action,
            subject_id=ctx.subject_id,
            resource_id=ctx.resource_id,
            evaluated_attributes={
                "subject_id": ctx.subject_id,
                "assigned_io": ctx.resource_assigned_io,
                "subject_jurisdiction": ctx.subject_jurisdiction,
                "resource_jurisdiction": ctx.resource_jurisdiction,
                "supervisory": False,
            },
        )

    def _evaluate_assign_policy(self, ctx: AuthorizationContext) -> AuthorizationDecision:
        """
        Evaluate case assignment authorization.

        Policies:
            CASE_ASSIGN_SELF:         Self-assignment on creation is permitted.
            CASE_ASSIGN_SUPERVISORY:  Only supervisory roles can reassign to others.
        """
        target_io = ctx.target_io_id

        # Self-assignment is permitted for any investigating role
        if target_io and target_io == ctx.subject_id:
            return AuthorizationDecision(
                allowed=True,
                policy_id="CASE_ASSIGN_SELF",
                reason="Self-assignment is permitted.",
                action=ctx.action,
                subject_id=ctx.subject_id,
                resource_id=ctx.resource_id,
                evaluated_attributes={
                    "target_io": target_io,
                    "self_assign": True,
                },
            )

        # Reassignment to another officer requires supervisory role
        if self._is_supervisory(ctx):
            return AuthorizationDecision(
                allowed=True,
                policy_id="CASE_ASSIGN_SUPERVISORY",
                reason="Supervisory role can reassign cases to other officers.",
                action=ctx.action,
                subject_id=ctx.subject_id,
                resource_id=ctx.resource_id,
                evaluated_attributes={
                    "target_io": target_io,
                    "supervisory": True,
                },
            )

        # DEFAULT DENY
        return AuthorizationDecision(
            allowed=False,
            policy_id="CASE_ASSIGN_DENIED",
            reason="Reassigning cases to another officer requires supervisory authorization.",
            action=ctx.action,
            subject_id=ctx.subject_id,
            resource_id=ctx.resource_id,
            evaluated_attributes={
                "target_io": target_io,
                "subject_id": ctx.subject_id,
                "supervisory": False,
            },
        )

    def _is_supervisory(self, ctx: AuthorizationContext) -> bool:
        """Check if any of the investigator's roles are supervisory."""
        roles_to_check = set(ctx.subject_roles) if ctx.subject_roles else {ctx.subject_role}
        return bool(roles_to_check & self._supervisory_roles)

    @staticmethod
    def _action_to_permission(action: str) -> Optional[str]:
        """Map an action string to a Permission value."""
        mapping = {
            "create": Permission.CASE_CREATE,
            "read": Permission.CASE_READ,
            "update": Permission.CASE_UPDATE,
            "list": Permission.CASE_LIST,
            "assign": Permission.CASE_ASSIGN,
            "stage_update": Permission.CASE_STAGE_UPDATE,
        }
        return mapping.get(action)

    def get_permissions_for_role(self, role: str) -> FrozenSet[str]:
        """Return the set of permissions for a given role. Empty set for unknown roles."""
        return self._role_permissions.get(role, frozenset())

    def get_effective_permissions(self, investigator: AuthenticatedInvestigator) -> Set[str]:
        """Return the union of all permissions across all of an investigator's roles."""
        all_perms: Set[str] = set()
        roles = investigator.roles if investigator.roles else [investigator.role]
        for role in roles:
            all_perms.update(self._role_permissions.get(role, frozenset()))
        return all_perms

    def get_case_list_filter(self, investigator: AuthenticatedInvestigator) -> Optional[str]:
        """
        Determine the case listing filter for an investigator.

        Supervisory roles → None (see all cases)
        Regular IOs → filter by assigned_io_id

        This replaces the inline logic in CaseService.list_cases().
        """
        if self._is_supervisory(
            AuthorizationContext(
                subject_id=investigator.subject_id,
                subject_role=investigator.role,
                subject_roles=investigator.roles if investigator.roles else [investigator.role],
                action="list",
            )
        ):
            return None  # Supervisory: see all cases
        return investigator.subject_id  # Regular IO: own cases only


# ═══════════════════════════════════════════════════════════════════════════
# Singleton policy engine instance
# ═══════════════════════════════════════════════════════════════════════════

policy_engine = PolicyEngine()
