from langgraph.graph import (
    StateGraph,
    START,
    END
)

from .state import AgentState

from .nodes import (
    generate_code,
    run_sandbox,
    debug_code,
    verify_code,
    route_after_sandbox
)


# =========================================================
# CREATE GRAPH
# =========================================================

builder = StateGraph(
    AgentState
)


# =========================================================
# ADD NODES
# =========================================================

builder.add_node(
    "generate",
    generate_code
)

builder.add_node(
    "sandbox",
    run_sandbox
)

builder.add_node(
    "debug",
    debug_code
)

builder.add_node(
    "verify",
    verify_code
)


# =========================================================
# START
# =========================================================

builder.add_edge(
    START,
    "generate"
)


# =========================================================
# GENERATE -> SANDBOX
# =========================================================

builder.add_edge(
    "generate",
    "sandbox"
)


# =========================================================
# SANDBOX -> CONDITIONAL
# =========================================================

builder.add_conditional_edges(

    "sandbox",

    route_after_sandbox,

    {

        "debug": "debug",

        "verify": "verify",

        "failed": END
    }
)


# =========================================================
# DEBUG -> SANDBOX
# =========================================================

builder.add_edge(
    "debug",
    "sandbox"
)


# =========================================================
# VERIFY -> END
# =========================================================

builder.add_edge(
    "verify",
    END
)


# =========================================================
# COMPILE
# =========================================================

graph = builder.compile()
# =========================================================
# VISUALIZE GRAPH
# =========================================================

try:

    png_bytes = (
        graph
        .get_graph()
        .draw_mermaid_png()
    )

    with open(
        "langgraph.png",
        "wb"
    ) as f:

        f.write(png_bytes)

    print(
        "\nGraph visualization saved to:"
        " langgraph.png"
    )

except Exception as e:

    print(
        f"\nCould not generate graph visualization: {e}"
    )