from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_aud_plan import router as aud_plan_router
from app.api.routes_dev import router as dev_router
from app.api.routes_evidence_items import router as evidence_items_router
from app.api.routes_extracted_content import router as extracted_content_router
from app.api.routes_files import router as files_router
from app.api.routes_generated_documents import router as generated_documents_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_health import router as health_router
from app.api.routes_open_points import router as open_points_router
from app.api.routes_projects import router as projects_router
from app.api.routes_section_drafts import router as section_drafts_router
from app.api.routes_section_evidence_packs import router as section_evidence_packs_router
from app.api.routes_source_priority import router as source_priority_router
from app.api.routes_source_summaries import router as source_summaries_router
from app.core.config import get_settings
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()
    yield


def create_app(create_tables_on_startup: bool = True) -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan if create_tables_on_startup else None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(dev_router)
    application.include_router(projects_router)
    application.include_router(jobs_router)
    application.include_router(files_router)
    application.include_router(extracted_content_router)
    application.include_router(evidence_items_router)
    application.include_router(source_summaries_router)
    application.include_router(section_evidence_packs_router)
    application.include_router(section_drafts_router)
    application.include_router(source_priority_router)
    application.include_router(aud_plan_router)
    application.include_router(open_points_router)
    application.include_router(generated_documents_router)
    return application


app = create_app()
