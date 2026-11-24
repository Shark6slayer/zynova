from fastapi import APIRouter, HTTPException, status, Depends, Request
from datetime import datetime, timezone
import logging

from app.schemas.all_schemas import (
    DeletionRequestModel,
    DeletionStatusResponse,
    AccountRecoveryRequest,
    AccountRecoveryResponse,
    AuthStatusResponse
)
from app.api.deps import get_current_user
from app.core.rate_limit import (
    check_account_deletion_rate_limit,
    check_account_recovery_rate_limit
)
from app.services.account_deletion_service import AccountDeletionService
from app.core.otp_service import OTPService
from app.services.email_service import EmailService
from app.database.client import get_database

logger = logging.getLogger("super_ai.account_router")

router = APIRouter(prefix="/account", tags=["Account Management & Deletion"])

@router.post(
    "/deletion/request",
    response_model=DeletionStatusResponse,
    dependencies=[Depends(check_account_deletion_rate_limit)]
)
async def request_account_deletion(
    body: DeletionRequestModel,
    current_user: dict = Depends(get_current_user)
):
    """
    Day 0 Deletion Request:
    - Requires authenticated access.
    - Re-authenticates using user's password.
    - Sets account_status = 'pending_deletion'.
    - Starts the 30-day grace period (permanent_deletion_at = now + 30 days).
    - Revokes active sessions and tokens.
    """
    try:
        res = await AccountDeletionService.request_deletion(
            user_id=current_user["id"],
            password=body.password,
            reason=body.reason
        )
        return DeletionStatusResponse(
            status=res["status"],
            account_status=res.get("account_status", "pending_deletion"),
            deletion_requested_at=res.get("deletion_requested_at"),
            permanent_deletion_at=res.get("permanent_deletion_at"),
            days_remaining=res.get("days_remaining"),
            seconds_remaining=res.get("days_remaining", 30) * 86400 if res.get("days_remaining") is not None else None,
            can_recover=True,
            message=res["message"]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Account deletion request error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to process deletion request")

@router.get(
    "/deletion/status",
    response_model=DeletionStatusResponse
)
async def get_deletion_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Checks the current deletion lifecycle status and remaining recovery time.
    """
    res = await AccountDeletionService.get_deletion_status(user_id=current_user["id"])
    return DeletionStatusResponse(
        status=res["status"],
        account_status=res.get("account_status", "active"),
        deletion_requested_at=res.get("deletion_requested_at"),
        permanent_deletion_at=res.get("permanent_deletion_at"),
        days_remaining=res.get("days_remaining"),
        seconds_remaining=res.get("seconds_remaining"),
        can_recover=res.get("can_recover", False),
        message=res["message"]
    )

@router.post(
    "/deletion/recovery-otp",
    response_model=AuthStatusResponse,
    dependencies=[Depends(check_account_recovery_rate_limit)]
)
async def request_recovery_otp(
    request: Request
):
    """
    Dispatches a 6-digit recovery OTP to a verified email address for accounts in pending_deletion status.
    """
    try:
        body = await request.json()
        email = body.get("email", "").lower().strip()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request body")

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user = await db.users.find_one({"email": email})
    # Do not leak user existence for non-pending accounts
    if not user or user.get("account_status") != "pending_deletion":
        return AuthStatusResponse(
            status="otp_dispatched",
            message="If an eligible account pending deletion exists for this email, an OTP has been dispatched.",
            email=email
        )

    otp, ok, cd_remaining = await OTPService.create_email_verification_otp(email)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {cd_remaining} seconds before requesting a new recovery code."
        )

    # Dispatch email if SMTP is configured
    if EmailService.is_configured():
        try:
            await EmailService.send_email(
                to_email=email,
                subject="SUPER_AI – Account Recovery Verification Code",
                html_content=f"<p>Your SUPER_AI account recovery verification code is: <strong>{otp}</strong>. It will expire in 5 minutes.</p>",
                text_content=f"Your SUPER_AI account recovery verification code is: {otp}. It will expire in 5 minutes."
            )
        except Exception as e:
            logger.error(f"Failed to send recovery OTP email to {email}: {e}")

    return AuthStatusResponse(
        status="otp_dispatched",
        message="A verification code has been dispatched to your verified email address.",
        email=email
    )

@router.post(
    "/deletion/recover",
    response_model=AccountRecoveryResponse,
    dependencies=[Depends(check_account_recovery_rate_limit)]
)
async def recover_account(
    body: AccountRecoveryRequest
):
    """
    Days 1-29 Account Recovery:
    - Verifies email and password.
    - Verifies 6-digit cryptographic OTP.
    - Confirms grace period is still active.
    - Atomically cancels deletion and reactivates account.
    """
    try:
        res = await AccountDeletionService.recover_account(
            email=body.email,
            password=body.password,
            otp_code=body.otp_code
        )
        return AccountRecoveryResponse(
            status=res["status"],
            message=res["message"],
            email=res["email"],
            account_status=res["account_status"],
            recovered_at=res["recovered_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Account recovery failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Recovery failed")
