from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .BaseController import BaseController
from .ProjectController import ProjectController

from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_core.documents import Document

from ..models import ProcessEnum


class ProcessController(BaseController):
    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str) -> str:
        file_extension = Path(file_id).suffix
        return file_extension

    def get_file_loader(self, file_id: str) -> TextLoader | PyMuPDFLoader | None:
        file_extension = self.get_file_extension(file_id=file_id)
        file_path = self.project_path / file_id

        if not file_path.exists():
            return None

        if file_extension == ProcessEnum.TXT.value:
            return TextLoader(file_path=file_path, encoding="utf-8")

        elif file_extension == ProcessEnum.PDF.value:
            return PyMuPDFLoader(file_path=file_path)

        return None

    def get_file_content(self, file_id: str) -> List[Document]:
        file_loader = self.get_file_loader(file_id=file_id)
        if file_loader:
            return file_loader.load()

        return None

    def process_file_content(
        self,
        file_id: int,
        chunk_size: int,
        overlap_size: int,
    ):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function=len,
        )

        file_content: List[Document] = self.get_file_content(file_id=file_id)

        document_content = [split.page_content for split in file_content]
        document_metadata = [split.metadata for split in file_content]

        chunks = text_splitter.create_documents(
            texts=document_content,
            metadatas=document_metadata,
        )

        return chunks
