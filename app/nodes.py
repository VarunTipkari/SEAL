import json
import os

from .llm import llm

from .schemas import (
    GeneratedSolution,
    VerificationResult
)

from .sandbox import DockerSandbox

from .prompts import (
    GENERATOR_PROMPT,
    DEBUG_PROMPT,
    VERIFY_PROMPT
)


sandbox = DockerSandbox()


MAX_ATTEMPTS = int(
    os.getenv(
        "MAX_ATTEMPTS",
        "5"
    )
)


# =========================================================
# GENERATE
# =========================================================

def generate_code(state):

    print("[generate] Creating a solution and test cases...")

    prompt = GENERATOR_PROMPT.format(
        query=state["user_query"]
    )

    structured_llm = (
        llm.with_structured_output(
            GeneratedSolution
        )
    )

    result = structured_llm.invoke(
        prompt
    )

    return {

        "language": result.language,

        "code": result.code,

        "tests": [
            test.model_dump()
            for test in result.tests
        ],

        "attempt": 1,
        "current_step": "sandbox",
        "status": "Generated solution; starting tests."
    }


# =========================================================
# SANDBOX
# =========================================================

def run_sandbox(state):

    print(
        f"[sandbox] Running tests for attempt {state['attempt']}..."
    )

    result = sandbox.run(

        language=state["language"],

        code=state["code"],

        test_cases=state["tests"]
    )

    failures = [
        result for result in result["test_results"]
        if not result["passed"]
    ]

    if failures:
        print("\n[sandbox] CODE FAILED")
        print(f"[sandbox] Attempt: {state['attempt']}")
        print("[sandbox] Failed test cases:")
        for failure in failures:
            print(
                f"  Test {failure['test']}: "
                f"input={failure.get('input', '')!r}, "
                f"expected={failure.get('expected', '')!r}, "
                f"actual={failure.get('actual', '')!r}"
            )
            print(
                f"  Reason: {failure.get('error', 'Unknown failure')}"
            )
        print("\n[sandbox] CODE THAT FAILED:\n")
        print(state["code"])
        print("\n" + "-" * 60)

    failure_history = list(state.get("failure_history", []))
    failure_history.extend(
        {
            "attempt": state["attempt"],
            "test": failure["test"],
            "reason": failure.get("error", "Unknown failure"),
            "input": failure.get("input", ""),
            "expected": failure.get("expected", ""),
            "actual": failure.get("actual", ""),
            "exit_code": failure.get("exit_code", -1),
            "code": state["code"]
        }
        for failure in failures
    )

    return {

        "passed": result["passed"],

        "output": result["output"],

        "error": result["error"],

        "test_results": result["test_results"],
        "failure_history": failure_history,
        "current_step": (
            "verify" if result["passed"] else "debug"
        ),
        "status": (
            "All tests passed; verifying solution."
            if result["passed"]
            else f"{len(failures)} test(s) failed; debugging."
        )
    }


# =========================================================
# DEBUG
# =========================================================

def debug_code(state):

    print(
        f"[debug] Fixing failures from attempt {state['attempt']}..."
    )

    failed_tests = [
        test for test in state["test_results"]
        if not test["passed"]
    ]

    prompt = DEBUG_PROMPT.format(

        query=state["user_query"],

        language=state["language"],

        code=state["code"],

        tests=json.dumps(
            state["tests"],
            indent=2
        ),

        result=json.dumps(failed_tests, indent=2)
    )

    response = llm.invoke(
        prompt
    )

    corrected_code = response.content.strip()
    if corrected_code.startswith("```"):
        corrected_code = corrected_code.strip("`")
        corrected_code = corrected_code.split("\n", 1)[-1]

    if not corrected_code or corrected_code == state["code"]:
        return {
            "attempt": MAX_ATTEMPTS,
            "current_step": "failed",
            "status": (
                "Debugger returned no new code; stopping retries."
            )
        }

    return {

        "code": corrected_code,

        "attempt": state["attempt"] + 1,
        "current_step": "sandbox",
        "status": "Generated a correction; rerunning tests."
    }


# =========================================================
# VERIFY
# =========================================================

def verify_code(state):

    print("[verify] Checking the final solution against the requirement...")

    prompt = VERIFY_PROMPT.format(

        query=state["user_query"],

        language=state["language"],

        code=state["code"],

        tests=json.dumps(
            state["tests"],
            indent=2
        ),

        results=json.dumps(
            state["test_results"],
            indent=2
        )
    )

    structured_llm = (
        llm.with_structured_output(
            VerificationResult
        )
    )

    result = structured_llm.invoke(
        prompt
    )

    return {

        "verified": result.verified,

        "verification_reason": result.reason,
        "current_step": "done",
        "status": (
            "Verification passed."
            if result.verified
            else "Verification rejected the solution."
        )
    }


# =========================================================
# ROUTER
# =========================================================

def route_after_sandbox(state):

    # ----------------------------------
    # All tests passed
    # ----------------------------------

    if state["passed"]:

        return "verify"


    # ----------------------------------
    # Maximum attempts reached
    # ----------------------------------

    if state["attempt"] >= MAX_ATTEMPTS:

        return "failed"


    # ----------------------------------
    # Try debugging
    # ----------------------------------

    return "debug"