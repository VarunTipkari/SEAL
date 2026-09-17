from app.graph import graph


def main():

    print("=" * 60)
    print("       LANGGRAPH CODE GENERATION AGENT")
    print("=" * 60)

    query = input(
        "\nWhat do you want to build?\n> "
    ).strip()

    if not query:
        print("\nUnable to generate code.")
        return

    initial_state = {
        "user_query": query,
        "language": "",
        "code": "",
        "tests": [],
        "attempt": 0,
        "passed": False,
        "verified": False,
        "output": "",
        "error": "",
        "test_results": [],
        "verification_reason": "",
        "failure_history": [],
        "current_step": "generate",
        "status": "Starting workflow.",
        "previous_code": ""
    }

    print("\nGenerating and testing code...")

    # IMPORTANT:
    # Do NOT hide the error while debugging.
    try:

        result = dict(initial_state)

        for update in graph.stream(initial_state, stream_mode="updates"):
            for step, state_update in update.items():
                result.update(state_update)
                print(
                    f"[live] {step}: "
                    f"{state_update.get('status', 'step complete')}"
                )

    except Exception as e:

        print("\n" + "=" * 60)
        print("ERROR OCCURRED")
        print("=" * 60)

        print("\nException type:")
        print(type(e).__name__)

        print("\nException message:")
        print(str(e))

        print("\nFull traceback:")

        import traceback
        traceback.print_exc()

        return

    print("\n" + "=" * 60)
    print("GRAPH FINISHED")
    print("=" * 60)


    if (
        result.get("passed")
        and result.get("verified")
    ):

        print("\n" + "=" * 60)
        print("CODE GENERATED SUCCESSFULLY")
        print("=" * 60)

        print(
            f"\nLanguage: "
            f"{result.get('language')}"
        )

        print(
            f"Attempts: "
            f"{result.get('attempt')}"
        )

        print("\nVERIFIED CODE:\n")

        print(
            result.get("code", "")
        )

    else:

        print(
            "\nUnable to generate code."
        )

        print(
            f"\nReason: {result.get('verification_reason') or result.get('error') or 'Maximum attempts reached.'}"
        )

        failures = result.get("failure_history", [])
        if failures:
            print("\nFAILURE HISTORY:")
            for failure in failures:
                print(
                    f"Attempt {failure['attempt']}, test {failure['test']}: "
                    f"{failure['reason']}"
                )
                print(f"Input: {failure['input']!r}")
                print(f"Expected: {failure['expected']!r}")
                print(f"Actual: {failure['actual']!r}")
                print("\nCODE THAT FAILED IN SANDBOX:\n")
                print(failure.get("code", "<code unavailable>"))
                print("\n" + "-" * 60)


if __name__ == "__main__":
    main()