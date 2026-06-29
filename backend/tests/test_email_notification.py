import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.services.email_notification as email_notification
from app.core.config import Settings
from app.db.base import Base
from app.models import GeneratedDocument, Project
from app.services.email_notification import (
    EmailNotificationService,
    build_aud_ready_email_payload,
    build_generated_document_download_url,
    get_email_ssl_verify,
    notify_aud_ready_for_document,
)
from app.workers.local_worker import should_notify_aud_ready_after_docx_job


def email_settings(**overrides) -> Settings:
    values = {
        "EMAIL_NOTIFICATIONS_ENABLED": True,
        "EMAIL_NOTIFICATION_URL": "https://example.test/send-email",
        "EMAIL_NOTIFICATION_FROM": "audacle@oracle.com",
        "EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL": None,
        "EMAIL_NOTIFICATION_TIMEOUT_SECONDS": 1.0,
        "EMAIL_NOTIFICATION_VERIFY_SSL": True,
        "EMAIL_NOTIFICATION_CA_BUNDLE": None,
        "EMAIL_NOTIFICATION_TRUST_ENV": True,
        **overrides,
    }
    return Settings(_env_file=None, **values)


def make_project() -> Project:
    return Project(
        id="project-1",
        name="Asha Mehta",
        email_id="asha.mehta@example.com",
        customer_name="Vision Operations",
        module_name="Order Management",
    )


def make_generated_document(project_id: str = "project-1") -> GeneratedDocument:
    return GeneratedDocument(
        id="document-1",
        project_id=project_id,
        filename="order-management-aud.docx",
        storage_path=f"projects/{project_id}/outputs/order-management-aud.docx",
    )


class CapturingEmailClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        self.requests.append({"url": url, "json": json})
        if self.error is not None:
            raise self.error

        return httpx.Response(200, request=httpx.Request("POST", url))


@pytest.fixture()
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'email.db').as_posix()}")
    session_local = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    with session_local() as db_session:
        yield db_session

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_aud_ready_email_payload_replaces_placeholders() -> None:
    project = make_project()

    payload = build_aud_ready_email_payload(project, email_settings())

    assert payload is not None
    assert payload["to_email"] == "asha.mehta@example.com"
    assert payload["from_email"] == "audacle@oracle.com"
    assert payload["subject"] == "Your AUD Has Been Generated"
    assert "Hello Asha Mehta" in payload["body"]
    assert "Vision Operations - Order Management" in payload["body"]
    assert "{email_id}" not in payload["body"]
    assert "{customer_name}" not in payload["body_html"]
    assert "{module_name}" not in payload["body_html"]
    assert "{Author_Name}" not in payload["body_html"]
    assert "Asha Mehta" in payload["body_html"]
    assert "Vision Operations" in payload["body_html"]
    assert "Order Management" in payload["body_html"]
    assert payload["cc"] is None
    assert payload["bcc"] is None
    assert payload["replyto"] is None


def test_aud_ready_email_html_escapes_project_values() -> None:
    project = Project(
        id="project-1",
        name="Asha <Lead>",
        email_id="asha.mehta@example.com",
        customer_name="Vision <Operations>",
        module_name="Order & Fulfillment",
    )

    payload = build_aud_ready_email_payload(project, email_settings())

    assert payload is not None
    assert "Asha &lt;Lead&gt;" in payload["body_html"]
    assert "Vision &lt;Operations&gt;" in payload["body_html"]
    assert "Order &amp; Fulfillment" in payload["body_html"]


def test_generated_document_download_url_uses_configured_base_url() -> None:
    url = build_generated_document_download_url(
        make_project(),
        make_generated_document(),
        email_settings(
            EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL="https://aud.example.com/api/"
        ),
    )

    assert url == (
        "https://aud.example.com/api/projects/project-1/generated-documents/"
        "document-1/download"
    )


def test_generated_document_download_url_is_optional() -> None:
    url = build_generated_document_download_url(
        make_project(),
        make_generated_document(),
        email_settings(),
    )

    assert url is None


def test_aud_ready_email_payload_includes_download_link_when_available() -> None:
    download_url = (
        "https://aud.example.com/api/projects/project-1/generated-documents/"
        "document-1/download"
    )

    payload = build_aud_ready_email_payload(
        make_project(),
        email_settings(),
        download_url=download_url,
    )

    assert payload is not None
    assert f"Download link: {download_url}" in payload["body"]
    assert f'href="{download_url}"' in payload["body_html"]
    assert "Download AUD" in payload["body_html"]


def test_email_service_posts_aud_ready_payload() -> None:
    client = CapturingEmailClient()
    service = EmailNotificationService(
        settings=email_settings(
            EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL="https://aud.example.com/api",
        ),
        client=client,
    )

    sent = service.send_aud_ready_notification(
        make_project(),
        make_generated_document(),
    )

    assert sent is True
    assert len(client.requests) == 1
    assert client.requests[0]["url"] == "https://example.test/send-email"
    assert client.requests[0]["json"]["to_email"] == "asha.mehta@example.com"
    assert (
        "https://aud.example.com/api/projects/project-1/generated-documents/"
        "document-1/download"
    ) in client.requests[0]["json"]["body"]


def test_email_service_skips_missing_recipient() -> None:
    client = CapturingEmailClient()
    service = EmailNotificationService(settings=email_settings(), client=client)
    project = make_project()
    project.email_id = None

    sent = service.send_aud_ready_notification(project, make_generated_document())

    assert sent is False
    assert client.requests == []


def test_email_service_failure_is_logged_and_non_blocking(caplog) -> None:
    caplog.set_level(logging.ERROR)
    client = CapturingEmailClient(error=httpx.ConnectError("service unavailable"))
    service = EmailNotificationService(settings=email_settings(), client=client)

    sent = service.send_aud_ready_notification(
        make_project(),
        make_generated_document(),
    )

    assert sent is False
    assert "AUD ready email notification failed" in caplog.text


def test_email_service_can_ignore_proxy_environment(monkeypatch) -> None:
    captured_client_kwargs: dict[str, Any] = {}

    class CapturingHTTPXClient:
        def __init__(self, **kwargs: Any) -> None:
            captured_client_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
            return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(email_notification.httpx, "Client", CapturingHTTPXClient)
    service = EmailNotificationService(
        settings=email_settings(
            EMAIL_NOTIFICATION_TRUST_ENV=False,
            EMAIL_NOTIFICATION_VERIFY_SSL=False,
        ),
    )

    sent = service.send_aud_ready_notification(
        make_project(),
        make_generated_document(),
    )

    assert sent is True
    assert captured_client_kwargs["trust_env"] is False
    assert captured_client_kwargs["verify"] is False
    assert captured_client_kwargs["timeout"] == 1.0


def test_email_ssl_verify_defaults_to_true() -> None:
    assert get_email_ssl_verify(email_settings()) is True


def test_email_ssl_verify_uses_configured_ca_bundle() -> None:
    verify = get_email_ssl_verify(
        email_settings(EMAIL_NOTIFICATION_CA_BUNDLE=" C:/certs/oracle-ca.pem ")
    )

    assert verify == "C:/certs/oracle-ca.pem"


def test_email_ssl_verify_can_be_disabled_explicitly() -> None:
    verify = get_email_ssl_verify(
        email_settings(EMAIL_NOTIFICATION_VERIFY_SSL=False)
    )

    assert verify is False


def test_docx_worker_notification_flag_defaults_to_enabled() -> None:
    assert should_notify_aud_ready_after_docx_job(None) is True
    assert should_notify_aud_ready_after_docx_job("DOCX generation job queued.") is True
    assert (
        should_notify_aud_ready_after_docx_job(
            '{"status_message":"queued","notify_aud_ready":true}'
        )
        is True
    )


def test_docx_worker_notification_flag_can_be_disabled_for_pipeline_stage() -> None:
    assert (
        should_notify_aud_ready_after_docx_job(
            '{"status_message":"queued","notify_aud_ready":false}'
        )
        is False
    )


class SuccessfulNotificationService:
    def __init__(self) -> None:
        self.calls = 0

    def send_aud_ready_notification(
        self,
        project: Project,
        generated_document: GeneratedDocument,
    ) -> bool:
        self.calls += 1
        return True


class FailingNotificationService:
    def send_aud_ready_notification(
        self,
        project: Project,
        generated_document: GeneratedDocument,
    ) -> bool:
        raise RuntimeError("email service failed")


def test_notify_aud_ready_marks_document_and_skips_duplicates(
    session: Session,
) -> None:
    project = make_project()
    generated_document = make_generated_document(project.id)
    session.add_all([project, generated_document])
    session.commit()

    service = SuccessfulNotificationService()

    assert notify_aud_ready_for_document(
        session,
        project.id,
        generated_document,
        service=service,
    ) is True

    metadata = json.loads(generated_document.metadata_json or "{}")
    assert metadata["email_notification"]["status"] == "aud_ready_sent"
    assert metadata["email_notification"]["sent_at"]

    assert notify_aud_ready_for_document(
        session,
        project.id,
        generated_document,
        service=service,
    ) is False
    assert service.calls == 1


def test_notify_aud_ready_handles_service_failure(
    session: Session,
    caplog,
) -> None:
    caplog.set_level(logging.ERROR)
    project = make_project()
    generated_document = make_generated_document(project.id)
    session.add_all([project, generated_document])
    session.commit()

    assert notify_aud_ready_for_document(
        session,
        project.id,
        generated_document,
        service=FailingNotificationService(),
    ) is False

    assert "failed unexpectedly" in caplog.text
    metadata = json.loads(generated_document.metadata_json or "{}")
    assert "email_notification" not in metadata
