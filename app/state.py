from typing import TypedDict, Any


class AgentState(TypedDict, total=False):

    # Original user request
    user_query: str

    # Detected/generated language
    language: str

    # Current generated code
    code: str

    # Black-box test cases
    tests: list[dict[str, str]]

    # Current attempt number
    attempt: int

    # Whether all tests passed
    passed: bool

    # Whether final verification passed
    verified: bool

    # Program output
    output: str

    # Error / failed test information
    error: str

    # Detailed test results
    test_results: list[dict[str, Any]]

    # Verification explanation
    verification_reason: str

    # Full history of failed test attempts
    failure_history: list[dict[str, Any]]

    # Current workflow progress for live reporting
    current_step: str
    status: str

    # Detect a debugger response that did not change the program
    previous_code: str