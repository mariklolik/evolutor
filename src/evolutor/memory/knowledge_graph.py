"""Code knowledge graph using tree-sitter and networkx."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import structlog

from evolutor.types.memory import KnowledgeNode, NodeKind

logger = structlog.get_logger()

EDGE_TYPES = ("calls", "imports", "inherits", "contains")


class KnowledgeGraph:
    """Build and query a code knowledge graph."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._nodes: dict[str, KnowledgeNode] = {}

    def parse_file(self, file_path: str) -> list[KnowledgeNode]:
        """Parse a Python file and extract nodes. Uses tree-sitter with ast fallback."""
        nodes: list[KnowledgeNode] = []
        try:
            import tree_sitter_languages
            parser = tree_sitter_languages.get_parser("python")
            source = Path(file_path).read_bytes()
            tree = parser.parse(source)
            self._walk_tree(tree.root_node, file_path, nodes, source)
        except Exception:
            # Fallback to ast for Python files
            self._parse_with_ast(file_path, nodes)
        return nodes

    def _parse_with_ast(self, file_path: str, nodes: list[KnowledgeNode]) -> None:
        import ast
        try:
            source = Path(file_path).read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    kn = KnowledgeNode(
                        kind=NodeKind.cls, name=node.name, file_path=file_path,
                        start_line=node.lineno, end_line=node.end_lineno or node.lineno,
                    )
                    self.add_node(kn)
                    nodes.append(kn)
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                            fn = KnowledgeNode(
                                kind=NodeKind.function, name=item.name, file_path=file_path,
                                start_line=item.lineno, end_line=item.end_lineno or item.lineno,
                            )
                            self.add_node(fn)
                            nodes.append(fn)
                            self.add_edge(kn.id, fn.id, "contains")
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    # Only top-level functions (not methods already handled)
                    if not any(n.name == node.name for n in nodes):
                        kn = KnowledgeNode(
                            kind=NodeKind.function, name=node.name, file_path=file_path,
                            start_line=node.lineno, end_line=node.end_lineno or node.lineno,
                        )
                        self.add_node(kn)
                        nodes.append(kn)
                elif isinstance(node, ast.Import | ast.ImportFrom):
                    text = ast.dump(node)
                    kn = KnowledgeNode(
                        kind=NodeKind.import_, name=text, file_path=file_path,
                        start_line=node.lineno, end_line=node.lineno,
                    )
                    self.add_node(kn)
                    nodes.append(kn)
        except Exception as e:
            logger.warning("ast_parse_failed", file=file_path, error=str(e))

    def _walk_tree(self, node, file_path: str, nodes: list, source: bytes, parent_id: str | None = None) -> None:
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode() if name_node else "unknown"
            kn = KnowledgeNode(
                kind=NodeKind.cls, name=name, file_path=file_path,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
            )
            self.add_node(kn)
            nodes.append(kn)
            if parent_id:
                self.add_edge(parent_id, kn.id, "contains")
            for child in node.children:
                self._walk_tree(child, file_path, nodes, source, kn.id)
            return

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode() if name_node else "unknown"
            kn = KnowledgeNode(
                kind=NodeKind.function, name=name, file_path=file_path,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
            )
            self.add_node(kn)
            nodes.append(kn)
            if parent_id:
                self.add_edge(parent_id, kn.id, "contains")
            return

        if node.type == "import_statement" or node.type == "import_from_statement":
            text = source[node.start_byte:node.end_byte].decode()
            kn = KnowledgeNode(
                kind=NodeKind.import_, name=text, file_path=file_path,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
            )
            self.add_node(kn)
            nodes.append(kn)
            return

        for child in node.children:
            self._walk_tree(child, file_path, nodes, source, parent_id)

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.id] = node
        self.graph.add_node(node.id, **node.model_dump())

    def add_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        self.graph.add_edge(from_id, to_id, type=edge_type)

    def query_by_name(self, name: str) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.name == name]

    def query_by_file(self, file_path: str) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.file_path == file_path]

    def get_dependencies(self, node_id: str) -> list[KnowledgeNode]:
        if node_id not in self.graph:
            return []
        return [self._nodes[n] for n in self.graph.successors(node_id) if n in self._nodes]

    def get_dependents(self, node_id: str) -> list[KnowledgeNode]:
        if node_id not in self.graph:
            return []
        return [self._nodes[n] for n in self.graph.predecessors(node_id) if n in self._nodes]

    def find_related(self, node_id: str, max_depth: int = 2) -> list[KnowledgeNode]:
        if node_id not in self.graph:
            return []
        related = set()
        visited = {node_id}
        frontier = [node_id]
        for _ in range(max_depth):
            next_frontier = []
            for nid in frontier:
                for neighbor in list(self.graph.successors(nid)) + list(self.graph.predecessors(nid)):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
                        related.add(neighbor)
            frontier = next_frontier
        return [self._nodes[n] for n in related if n in self._nodes]

    def to_context_string(self, file_path: str | None = None) -> str:
        nodes = self.query_by_file(file_path) if file_path else list(self._nodes.values())
        lines = []
        for n in nodes:
            lines.append(f"[{n.kind.value}] {n.name} ({n.file_path}:{n.start_line})")
        return "\n".join(lines)
