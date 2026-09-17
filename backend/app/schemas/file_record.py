from pydantic import BaseModel
from pydantic import ConfigDict


class FileUploadResponse(
    BaseModel
):
    message: str
    file_name: str


class FileRecordSummary(
    BaseModel
):
    """What a listing may show about a stored file.

    Deliberately excludes the stored bytes. The listing is a directory of
    what exists, and returning the contents of every file in it would make a
    page of records hundreds of megabytes and hand out far more than the
    caller asked for. The bytes come from the download endpoint, one file at
    a time, after the ownership check.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    uploaded_by: str
    file_name: str
    file_type: str
    file_size: int | None = None
