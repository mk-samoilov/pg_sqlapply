COLOR_CODES = \
    {
        "reset": "\033[0m",
        "cyan": "\033[96m",
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "white": "\033[97m",
        "gray": "\033[90m"
    }


def color_text(text, color):
    return COLOR_CODES.get(color, "") + text + COLOR_CODES["reset"]


class CSNode:
    def __init__(self, name: str, color: str = "white"):
        self.name = str(name)
        self.color = color
        self.children = []

    def add(self, child_node):
        self.children.append(child_node)


class CSTree:
    def __init__(self, root: CSNode):
        self.root = root

    def render(self):
        lines = []

        def _render_node(node, prefix="", is_last=True):
            line = f"{prefix}{'└── ' if is_last else '├── '}{color_text(node.name, node.color)}"
            lines.append(line)

            new_prefix = prefix + ("    " if is_last else "│   ")
            for i_, child_ in enumerate(node.children):
                _render_node(child_, new_prefix, i_ == len(node.children) - 1)

        # Root line (without ├──)
        lines.append(f"{color_text(self.root.name, self.root.color)}")
        for i, child in enumerate(self.root.children):
            _render_node(child, "", i == len(self.root.children) - 1)
        return "\n".join(lines)

    def display(self):
        print(self.render())
