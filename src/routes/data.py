from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from ..controllers import DataController, ProjectController, ProcessController

from ..models import ResponseEnum

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
    file: UploadFile,
    project_id: str,
    app_settings: Settings = Depends(get_settings),
):

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

    return JSONResponse(
        content={
            "signal": ResponseEnum.FILE_UPLOAD_SUCESS.value,
            "file_id": file_id,
        },
    )


@data_router.post("/process/{project_id}")
async def process_file(
    project_id: str,
    process_request: ProcessRequest,
):
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size

    process_controller = ProcessController(project_id=project_id)

    chunks = process_controller.process_file_content(
        file_id=file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
    )

    if chunks is None or len(chunks) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseEnum.FILE_PROCESS_FAILED.value,
            },
        )

    return JSONResponse(
        content={
            "signal": ResponseEnum.FILE_PROCESS_SUCCESS.value,
            "content": jsonable_encoder(chunks),
        }
    )
