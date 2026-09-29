"""SmartCycle AI assistant chat route.

Public by design: the assistant explains how SmartCycle works and holds no user
data, so a signed-out visitor can use it. It therefore takes no auth dependency
and reads no session.

This module contains no Gemini SDK logic. Everything provider-related lives in
``app.services.gemini_service``.
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import gemini_service


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask the SmartCycle AI assistant a question",
)
def chat(payload: ChatRequest) -> ChatResponse:
    """Answer a question about SmartCycle using the Gemini assistant.

    Error handling follows two different precedents already in this codebase:

    * A **missing API key** is an operator problem, not a transient one, so it
      returns ``503`` with a safe message. This mirrors how the API already
      treats a missing ``JWT_SECRET_KEY``.
    * Any **provider failure** (rate limit, network error, timeout, empty
      answer) returns ``200`` with a fixed apology in ``response``. This mirrors
      the valuation path, which degrades to the rule-based estimator instead of
      failing the request.

    Request-shape problems (a missing, blank, or over-long ``message``) are left
    to FastAPI's own validation, which answers ``422``.
    """
    if not gemini_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=gemini_service.NOT_CONFIGURED_MESSAGE,
        )

    return ChatResponse(response=gemini_service.generate_reply(payload.message))
