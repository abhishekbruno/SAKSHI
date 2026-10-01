"""
Standardized error codes and exception handlers for SAKSHI Case Management Service.
Ensures internal DB errors and stack traces are never leaked to external clients.
"""
from typing import Any, Optional
from fastapi import HTTPException, status


class SakshiException(HTTPException):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Any] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": details
            }
        )


class CaseNotFoundException(SakshiException):
    def __init__(self, case_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="CASE_NOT_FOUND",
            message=f"Investigation case with ID '{case_id}' was not found.",
            details={"case_id": case_id}
        )


class UnauthorizedException(SakshiException):
    def __init__(self, message: str = "Authentication required or credentials invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message=message
        )


class ForbiddenException(SakshiException):
    def __init__(self, message: str = "Investigator is not authorized to perform this operation."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            message=message
        )


class InvalidCaseDataException(SakshiException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_CASE_DATA",
            message=message,
            details=details
        )


class InvalidInvestigatorException(SakshiException):
    def __init__(self, message: str = "Invalid or unverified investigator reference."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_INVESTIGATOR",
            message=message
        )


class CaseCreationFailedException(SakshiException):
    def __init__(self, message: str = "Failed to establish case record or workspace."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CASE_CREATION_FAILED",
            message=message
        )


class InvalidStageException(SakshiException):
    def __init__(self, message: str = "Invalid case lifecycle stage transition."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_STAGE",
            message=message
        )


# ─── MOD-02: Authentication Error Types ─────────────────────────────────

class AuthenticationRequiredException(SakshiException):
    """No authentication credentials were provided."""
    def __init__(self, message: str = "Authentication required. Provide a valid Bearer token."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            message=message
        )


class InvalidTokenException(SakshiException):
    """Token is malformed, undecodable, or structurally invalid."""
    def __init__(self, message: str = "The provided authentication token is invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_TOKEN",
            message=message
        )


class TokenExpiredException(SakshiException):
    """Token has passed its expiration time."""
    def __init__(self, message: str = "The authentication token has expired."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_EXPIRED",
            message=message
        )


class TokenIssuerInvalidException(SakshiException):
    """Token issuer does not match the trusted OIDC provider."""
    def __init__(self, message: str = "Token issuer is not trusted."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_ISSUER_INVALID",
            message=message
        )


class TokenAudienceInvalidException(SakshiException):
    """Token audience does not match the expected SAKSHI audience."""
    def __init__(self, message: str = "Token audience is invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_AUDIENCE_INVALID",
            message=message
        )


class IdentityClaimMissingException(SakshiException):
    """Required identity claim (e.g. 'sub') is missing from the token."""
    def __init__(self, claim: str = "sub", message: Optional[str] = None):
        msg = message or f"Required identity claim '{claim}' is missing from the token."
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="IDENTITY_CLAIM_MISSING",
            message=msg,
            details={"missing_claim": claim}
        )


class OIDCConfigurationException(SakshiException):
    """OIDC is enabled but required configuration is missing or invalid."""
    def __init__(self, message: str = "OIDC authentication is misconfigured."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="OIDC_CONFIGURATION_ERROR",
            message=message
        )

