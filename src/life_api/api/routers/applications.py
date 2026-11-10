from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from life_api.api.deps import RepoDep, SettingsDep
from life_api.domain import Application, ApplicationIn, ApplicationStatus, ApplicationUpdate
from life_api.storage.dynamo import NotFoundError

router = APIRouter(prefix="/v1/applications", tags=["applications"])


def _reject_future(applied_on: date | None, settings: SettingsDep) -> None:
    """Dates are in the app's timezone. A future date usually means the client's
    clock is in a different timezone; fail loudly instead of storing it."""
    today = settings.today()
    if applied_on and applied_on > today:
        raise HTTPException(
            422,
            f"applied_on {applied_on} is in the future; today is {today} ({settings.timezone})",
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationIn, repo: RepoDep, settings: SettingsDep) -> Application:
    _reject_future(body.applied_on, settings)
    now = datetime.now(UTC)
    app = Application(
        **body.model_dump(exclude={"applied_on"}),
        id=uuid.uuid4().hex,
        applied_on=body.applied_on or settings.today(),
        created_at=now,
        updated_at=now,
    )
    repo.put_application(app)
    return app


@router.get("")
def list_applications(
    repo: RepoDep,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    since: date | None = None,
) -> list[Application]:
    apps = repo.list_applications()
    if status_filter:
        apps = [a for a in apps if a.status == status_filter]
    if since:
        apps = [a for a in apps if a.applied_on >= since]
    return apps


@router.get("/{app_id}")
def get_application(app_id: str, repo: RepoDep) -> Application:
    try:
        return repo.get_application(app_id)
    except NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found") from None


@router.patch("/{app_id}")
def update_application(
    app_id: str, body: ApplicationUpdate, repo: RepoDep, settings: SettingsDep
) -> Application:
    if body.status is None and body.notes is None and body.applied_on is None:
        raise HTTPException(422, "Nothing to update")
    _reject_future(body.applied_on, settings)
    try:
        return repo.update_application(app_id, body, datetime.now(UTC).isoformat())
    except NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found") from None


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: str, repo: RepoDep) -> Response:
    try:
        repo.delete_application(app_id)
    except NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
