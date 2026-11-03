from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse

from ..controllers import DataController

from .base import get_settings, Settings

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

    is_valid, result_signal = data_controller.validate_uploaded_file(file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": result_signal,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "signal": result_signal,
        },
    )
