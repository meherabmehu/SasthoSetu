from pydantic import BaseModel


class FileUploadResponse(
    BaseModel
):
    message: str
    file_name: str