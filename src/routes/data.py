from fastapi import Request, APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse

from src.models.db_schemas.data_chunk import DataChunk
from src.models.db_schemas.asset import Asset

from ..controllers import DataController, ProjectController, ProcessController

from ..models import ProjectModel, ChunkModel, AssetModel
from ..models import ResponseEnum, AssetTypeEnum

from .base import get_settings, Settings

from .schemas import ProcessRequest

import aiofiles
import logging

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)


@data_router.post("/upload/{project_id}")
async def upload_file(
    request: Request,
    file: UploadFile,
    project_id: str,
    app_settings: Settings = Depends(get_settings),
):
    project_model = await ProjectModel.create_instance(db=request.app.db)

    project = await project_model.get_or_create_project(project_id=project_id)

    data_controller = DataController()
    project_controller = ProjectController()

    is_valid, result_signal = data_controller.validate_uploaded_file(file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": result_signal,
            },
        )

    project_dir_path = project_controller.get_project_path(project_id=project_id)
    file_path, file_id = data_controller.generate_unique_file_path(
        orig_filename=file.filename, project_id=project_id
    )
    file_path = project_dir_path / file_path

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:

        logger.error(f"Error while uploading file: {e}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseEnum.FILE_UPLOAD_FAILED,
            },
        )

    asset_model = await AssetModel.create_instance(db=request.app.db)

    file_size = data_controller.get_file_size(file_path=file_path)

    asset_resource = Asset(
        asset_project_id=project.id,
        asset_type=AssetTypeEnum.File.value,
        asset_name=file_id,
        asset_size=file_size,
    )

    asset = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
        content={
            "signal": ResponseEnum.FILE_UPLOAD_SUCESS.value,
            "file_id": asset.asset_name,
        },
    )


@data_router.post("/process/{project_id}")
async def process_file(
    request: Request,
    project_id: str,
    process_request: ProcessRequest,
):
    project_model = await ProjectModel.create_instance(db=request.app.db)
    project = await project_model.get_or_create_project(project_id=project_id)

    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    chunk_model = await ChunkModel.create_instance(db=request.app.db)
    asset_model = await AssetModel.create_instance(db=request.app.db)

    process_controller = ProcessController(project_id=project_id)

    project_files_ids = {}
    if file_id:
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.id, asset_name=file_id
        )

        if not asset_record:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "signal": ResponseEnum.FILE_ID_ERROR.value,
                },
            )

        project_files_ids[asset_record.id] = asset_record.asset_name
    else:
        project_files = await asset_model.get_all_project_assets(
            project_id=project.id,
            asset_type=AssetTypeEnum.File.value,
        )
        project_files_ids = {record.id: record.asset_name for record in project_files}

    if not project_files_ids:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "signal": ResponseEnum.NO_FILES_ERROR.value,
            },
        )

    if do_reset == 1:
        await chunk_model.delete_chunks_by_project_id(project_id=project.id)

    total_inserted = 0
    failed_files = []
    for asset_id, file_id in project_files_ids.items():
        try:
            chunks = process_controller.process_file_content(
                file_id=file_id,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )
        except Exception as e:
            logger.error(f"Failed to process {file_id}: {e}")
            failed_files.append(file_id)
            continue

        if not chunks:
            failed_files.append(file_id)
            continue

        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.id,
                chunk_asset_id=asset_id,
            )
            for i, chunk in enumerate(chunks)
        ]

        total_inserted += await chunk_model.insert_many_chunks(
            chunks=file_chunks_records
        )

    if total_inserted == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseEnum.FILE_PROCESS_FAILED.value,
                "failed_files": failed_files,
            },
        )

    return JSONResponse(
        content={
            "signal": ResponseEnum.FILE_PROCESS_SUCCESS.value,
            "inserted_chunks": total_inserted,
            "processed_files": len(project_files_ids) - len(failed_files),
            "failed_files": failed_files,
        }
    )
