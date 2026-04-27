from app.graph.graph import build_graph


def test_build_graph_compiles() -> None:
    graph = build_graph()
    assert graph is not None
