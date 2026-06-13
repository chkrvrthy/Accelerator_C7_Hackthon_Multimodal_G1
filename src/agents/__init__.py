"""Agent package.

Six specialist agents + one synthesizer + the LangGraph wiring.

Every agent file follows the same shape so reviews are fast:

    def run(state: GraphState, deps: AgentDeps) -> dict:
        ...

    if __name__ == "__main__":
        # per-slice CLI runner using build_default_deps()
        ...

The graph (``src/agents/graph.py``) wires those nodes into a parallel
fan-out + synthesizer DAG.
"""

__all__: list[str] = []
