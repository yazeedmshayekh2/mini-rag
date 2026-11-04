from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse

from ..controllers import DataController, ProjectController

from ..models import ResponseEnum

from .base import get_settings, Settings

import aiofiles

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
    unique_file_name = data_controller.generate_unique_filename(
        orig_filename=file.filename, project_id=project_id
    )
    file_path = project_dir_path / unique_file_name

    print(f"File Path: {file_path}")

    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
            await f.write(chunk)

    return JSONResponse(
        content={
            "signal": ResponseEnum.FILE_UPLOAD_SUCESS.value,
        },
    )
