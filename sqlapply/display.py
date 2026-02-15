COLORS = {
    "reset": "\033[0m",
    "cyan": "\033[96m",
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "white": "\033[97m",
    "gray": "\033[90m",
}


def color_text(text: str, color: str) -> str:
    return COLORS.get(color, "") + text + COLORS["reset"]


class CSNode:
    def __init__(self, name: str, color: str = "white"):
        self.name = str(name)
        self.color = color
        self.children: list["CSNode"] = []

    def add(self, child: "CSNode"):
        self.children.append(child)


class CSTree:
    def __init__(self, root: CSNode):
        self.root = root

    def render(self) -> str:
        lines = [color_text(self.root.name, self.root.color)]

        def _walk(node: CSNode, prefix: str, is_last: bool):
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            lines.append(f"{prefix}{connector}{color_text(node.name, node.color)}")
            new_prefix = prefix + ("    " if is_last else "\u2502   ")
            for i, child in enumerate(node.children):
                _walk(child, new_prefix, i == len(node.children) - 1)

        for i, child in enumerate(self.root.children):
            _walk(child, "", i == len(self.root.children) - 1)
        return "\n".join(lines)

    def display(self):
        print(self.render())
