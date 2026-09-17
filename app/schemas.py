from typing import Literal

from pydantic import BaseModel, Field


Language = Literal[
    "python",
    "cpp",
    "javascript"
]


class TestCase(BaseModel):

    input: str = Field(
        description=(
            "Input that should be provided to "
            "the program through stdin."
        )
    )

    expected_output: str = Field(
        description=(
            "Expected output from the program."
        )
    )


class GeneratedSolution(BaseModel):

    language: Language

    code: str

    tests: list[TestCase] = Field(
        min_length=1
    )


class VerificationResult(BaseModel):

    verified: bool

    reason: str