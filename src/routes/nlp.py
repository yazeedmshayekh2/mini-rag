import asyncio
import logging

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Request, status

from src.models.db_schemas.project import Project

from ..dependencies import (
    ChunksCollectionDep,
    DbDep,
    IndexingServiceDep,
    ProjectDep,
    VectorStoreDep,
)
from ..models import AssetModel
from ..models.enums import IndexStatusEnum, ResponseEnum
from ..services.IndexingService import IndexingService
from .schemas import (
    FailedAsset,
    IndexInfoResponse,
    IndexPushResponse,
    PushRequest,
    StatusBucket,
)

logger = logging.getLogger(__name__)

nlp_router = APIRouter(prefix="/api/v1/nlp", tags=["api_v1", "nlp"])


async def run_indexing(
    service: IndexingService, project_id: ObjectId, force: bool
) -> None:
    """Background entry point. Nobody is listening for this exception, so log it."""
    try:
        await service.index_project(project_id=project_id, force=force)
    except Exception:
        logger.exception("Background indexing crashed for project %s", project_id)


@nlp_router.post(
    "/index/push/{project_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IndexPushResponse,
)
async def push_index(
    request: Request,
    project: ProjectDep,
    service: IndexingServiceDep,
    backgroud_tasks: BackgroundTasks,
    push: PushRequest = PushRequest(),
):
    backgroud_tasks.add_task(
        run_indexing, service=service, project_id=project.id, force=push.force
    )
    return IndexPushResponse(
        signal=ResponseEnum.INDEXING_STARTED.value,
        project_id=project.project_id,
        status_url=str(request.url_for("index_info", project_id=project.project_id)),
    )


@nlp_router.get(
    "/index/info/{project_id}",
    name="index_info",
    response_model=IndexInfoResponse,
)
async def index_info(
    project: ProjectDep,
    db: DbDep,
    vector_store: VectorStoreDep,
    collection: ChunksCollectionDep,
):
    asset_model = AssetModel(db=db)
    summary, failed, points = await asyncio.gather(  # Mongo and Qdrant concurrently
        asset_model.get_index_summary(project.id),
        asset_model.get_failed_assets(project_id=project.id),
        vector_store.count(collection=collection, project_id=str(project.id)),
    )

    # stable shape: every status is present, even with zero assets
    statuses = {s: StatusBucket(**summary.get(s.value, {})) for s in IndexStatusEnum}
    is_indexing = statuses[IndexStatusEnum.INDEXING].assets > 0

    return IndexInfoResponse(
        signal=ResponseEnum.INDEX_INFO_SUCCESS.value,
        project_id=project.project_id,
        collection=collection,
        statuses=statuses,
        vector_points=points,
        is_indexing=is_indexing,
        in_sync=not is_indexing and points == statuses[IndexStatusEnum.INDEXED].chunks,
        failed_assets=[
            FailedAsset(asset_name=a.asset_name, error=a.asset_index_error)
            for a in failed
        ],
    )
