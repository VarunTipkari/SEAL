
import os
import tempfile
from typing import Any

import docker


class DockerSandbox:

    IMAGE = "code-agent-sandbox"

    def __init__(self):
        self.client = docker.from_env()

    # ==========================================================
    # MAIN ENTRY
    # ==========================================================

    def run(
        self,
        language: str,
        code: str,
        test_cases: list[dict[str, str]]
    ) -> dict[str, Any]:

        with tempfile.TemporaryDirectory() as temp_dir:

            filename = {
                "python": "solution.py",
                "cpp": "solution.cpp",
                "javascript": "solution.js"
            }.get(language)

            if filename is None:
                return {
                    "passed": False,
                    "output": "",
                    "error": f"Unsupported language: {language}",
                    "test_results": []
                }

            # Write generated code
            code_path = os.path.join(temp_dir, filename)

            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code)

            return self.run_tests(
                temp_dir,
                language,
                test_cases
            )

    # ==========================================================
    # RUN ALL TESTS
    # ==========================================================

    def run_tests(
        self,
        temp_dir: str,
        language: str,
        test_cases: list[dict[str, str]]
    ):

        results = []

        for index, test in enumerate(test_cases, start=1):

            # ------------------------------------------
            # Create input.txt
            # ------------------------------------------

            input_file = os.path.join(
                temp_dir,
                "input.txt"
            )

            with open(
                input_file,
                "w",
                encoding="utf-8"
            ) as f:
                f.write(test["input"])

            container = None

            try:

                command = self.get_command(language)

                container = self.client.containers.run(

                    image=self.IMAGE,

                    command=command,

                    volumes={
                        temp_dir: {
                            "bind": "/workspace",
                            "mode": "rw"
                        }
                    },

                    working_dir="/workspace",

                    detach=True,

                    network_disabled=True,

                    mem_limit="256m",

                    cpu_period=100000,
                    cpu_quota=50000,

                    pids_limit=64,

                    security_opt=[
                        "no-new-privileges:true"
                    ],

                    user="sandboxuser"
                )

                try:

                    result = container.wait(timeout=10)

                except Exception:

                    try:
                        container.kill()
                    except Exception:
                        pass

                    results.append({
                        "test": index,
                        "passed": False,
                        "input": test["input"],
                        "expected": test["expected_output"].strip(),
                        "actual": "",
                        "exit_code": -1,
                        "error": "Execution timeout"
                    })

                    continue

                output = (
                    container.logs()
                    .decode(
                        "utf-8",
                        errors="replace"
                    )
                )

                exit_code = result["StatusCode"]

                actual = output.strip()

                expected = (
                    test["expected_output"]
                    .strip()
                )

                passed = (
                    exit_code == 0
                    and actual == expected
                )

                failure_reason = ""
                if not passed:
                    if exit_code != 0:
                        failure_reason = (
                            f"Program exited with code {exit_code}."
                        )
                    elif actual != expected:
                        failure_reason = (
                            "Output mismatch: "
                            f"expected {expected!r}, got {actual!r}."
                        )

                results.append({

                    "test": index,

                    "passed": passed,

                    "input": test["input"],

                    "expected": expected,

                    "actual": actual,

                    "exit_code": exit_code,

                    "error": failure_reason

                })

            except Exception as e:

                results.append({

                    "test": index,

                    "passed": False,

                    "input": test["input"],

                    "expected": (
                        test["expected_output"]
                        .strip()
                    ),

                    "actual": "",

                    "exit_code": -1,

                    "error": str(e)

                })

            finally:

                if container is not None:

                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

        failed = [
            r for r in results
            if not r["passed"]
        ]

        return {

            "passed": len(failed) == 0,

            "output": self.format_results(results),

            "error": (
                self.format_results(failed)
                if failed
                else ""
            ),

            "test_results": results
        }

    # ==========================================================
    # LANGUAGE COMMAND
    # ==========================================================

    @staticmethod
    def get_command(language):

        # Python
        if language == "python":

            return [
                "bash",
                "-lc",
                "python solution.py < input.txt"
            ]

        # JavaScript
        if language == "javascript":

            return [
                "bash",
                "-lc",
                "node solution.js < input.txt"
            ]

        # C++
        if language == "cpp":

            return [
                "bash",
                "-lc",
                "g++ -std=c++17 -O2 solution.cpp -o solution && ./solution < input.txt"
            ]

        raise ValueError(
            f"Unsupported language: {language}"
        )

    # ==========================================================
    # FORMAT RESULT
    # ==========================================================

    @staticmethod
    def format_results(results):

        text = []

        for result in results:

            text.append(
                f"""
TEST {result["test"]}

PASS:
{result["passed"]}

INPUT:
{result["input"]}

EXPECTED:
{result["expected"]}

ACTUAL:
{result["actual"]}

EXIT CODE:
{result["exit_code"]}

ERROR:
{result.get("error", "")}
"""
            )

        return "\n".join(text)