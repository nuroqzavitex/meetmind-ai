import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

# Names end up in "[hh:mm:ss] Name: text" lines, so they must satisfy the transcript parser:
# start with a letter, no ":" or newline, at most 40 characters.
_NAME_RE = re.compile(r"[^\W\d][^:\n]{0,39}")


def _valid_name(value: str) -> str:
    name = " ".join(value.split())
    if not _NAME_RE.fullmatch(name):
        raise ValueError("Tên phải bắt đầu bằng chữ cái, tối đa 40 ký tự và không chứa dấu ':'")
    return name


class SpeakerOut(BaseModel):
    label: str
    count: int
    samples: list[str]


class SpeakerAssignment(BaseModel):
    label: str
    name: Annotated[str, AfterValidator(_valid_name)]
    is_decision_maker: bool = False


class SpeakersIn(BaseModel):
    speakers: list[SpeakerAssignment] = Field(min_length=1, max_length=100)
