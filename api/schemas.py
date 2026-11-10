# Purpose: define the API request format and validation rules.
# Work: validate the question, optional week, and source-page limit.

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class AskRequest(BaseModel):
    # Trim leading and trailing whitespace before validation.
    model_config = ConfigDict(str_strip_whitespace=True)

    # Require a question containing at least one non-whitespace character.
    question: str = Field(min_length=1, max_length=1000)

    # Accept any positive optional week number, including newly added weeks.
    week: int | None = Field(default=None, ge=1)

    # Limit the maximum number of source pages to retrieve.
    top_k: int = Field(default=4, ge=1, le=10)







# Purpose: define the format of each source returned to the frontend.
class SourceReference(BaseModel):
    # Match this number to references such as [1] and [2] in the answer.
    id: int = Field(ge=1)

    # Identify the original PDF filename and page number.
    source: str
    page: int = Field(ge=1)


# Purpose: define a consistent successful API response format.
class AskResponse(BaseModel):
    question: str
    answer: str

    # Indicate a generated answer or insufficient support in the notes.
    mode: Literal["local_rag", "no_support"]

    sources: list[SourceReference] = Field(default_factory=list)

    # This retrieval score is not the probability that an answer is correct.
    best_similarity: float | None = None

    # Let the frontend identify truncated answers and missing citations.
    truncated: bool = False
    citation_warning: bool = False


# Purpose: report the current PDF catalogue and index readiness.
class LibraryDocument(BaseModel):
    source: str
    week: int | None = None


class LibraryResponse(BaseModel):
    documents: list[LibraryDocument]
    pdf_count: int
    page_count: int | None = None
    chunk_count: int | None = None
    index_status: Literal["ready", "missing", "stale"]
    message: str | None = None
