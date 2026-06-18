from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.llm import (
    LLMConfigurationError,
    LLMError,
    LLMInputTooLongError,
    LLMInvalidJSONError,
    build_llm_service,
)

router = APIRouter(prefix="/dev", tags=["dev"])


class LLMTestRequest(BaseModel):
    prompt: str


@router.post("/llm-test")
def test_llm(
    payload: LLMTestRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if settings.ENVIRONMENT.strip().lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found.",
        )

    try:
        llm_service = build_llm_service(settings)
        result = llm_service.generate_json(payload.prompt)
    except LLMInputTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LLMInvalidJSONError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "provider": settings.LLM_PROVIDER,
        "result": result,
    }
