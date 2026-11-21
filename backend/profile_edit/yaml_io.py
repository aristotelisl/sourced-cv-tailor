"""Round-trip profile.yaml with ruamel, so edits keep every comment, quote and flow-style list.

Loading and dumping an unchanged profile gives back the same text (a test checks this).
"""
import copy
import io
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.tokens import CommentToken


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    # Keep `key: null` as written (ruamel's default writes an empty value).
    y.representer.add_representer(type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null"))
    return y


def load(text: str) -> CommentedMap:
    return _yaml().load(text)


def dump(doc: CommentedMap) -> str:
    out = io.StringIO()
    _yaml().dump(doc, out)
    return out.getvalue()


def flow_seq(items: list) -> CommentedSeq:
    seq = CommentedSeq(items)
    seq.fa.set_flow_style()
    return seq


def _last_slot(node: Any) -> tuple[Any, Any] | None:
    """The innermost (container, key) of the last line of `node`, where ruamel keeps what follows it."""
    if isinstance(node, CommentedMap) and node:
        key = list(node)[-1]
    elif isinstance(node, CommentedSeq) and node and not node.fa.flow_style():
        key = len(node) - 1
    else:
        return None
    return _last_slot(node[key]) or (node, key)


def _token_pos(container: Any) -> int:
    """Where ruamel keeps the comment after an item: slot 0 for list items, 2 for mapping values."""
    return 0 if isinstance(container, CommentedSeq) else 2


def _take_trailing(node: Any) -> CommentToken | None:
    """Detach what follows the last line of `node` (blank lines, the next block's comments).

    An end-of-line comment on that last line stays. The returned token's value starts
    with the newline that ends a line.
    """
    slot = _last_slot(node)
    if slot is None:
        return None
    container, key = slot
    tokens = container.ca.items.get(key)
    pos = _token_pos(container)
    token = tokens[pos] if tokens and len(tokens) > pos else None
    if token is None:
        return None
    if not token.value.startswith("#"):
        tokens[pos] = None
        return token
    own, newline, rest = token.value.partition("\n")
    if not rest:
        return None
    moved = copy.copy(token)
    moved.value = newline + rest
    token.value = own + newline
    return moved


def _put_trailing(node: Any, trailing: CommentToken | None, comment: str | None) -> None:
    slot = _last_slot(node)
    if slot is None or not (trailing or comment):
        return
    container, key = slot
    if comment:
        container.yaml_add_eol_comment(f"# {comment}", key)
        container.ca.items[key][2].value = f"# {comment}" + (trailing.value if trailing else "\n")
    else:
        container.ca.items.setdefault(key, [None, None, None, None])[2] = trailing


def append_item(seq: CommentedSeq, item: Any, comment: str | None = None) -> None:
    """Append to a block list; whatever followed the old last item (a blank line, a comment) now follows the new one."""
    trailing = _take_trailing(seq[-1]) if len(seq) else None
    seq.append(item)
    _put_trailing(item, trailing, comment)


def set_key(mapping: CommentedMap, key: str, value: Any, comment: str | None = None) -> None:
    """Set a key. A new key goes at the end, before whatever followed the old last key."""
    if key in mapping or not mapping:
        mapping[key] = value
        if comment:
            set_eol_comment(mapping, key, comment)
        return
    trailing = _take_trailing(mapping)
    mapping[key] = value
    _put_trailing(mapping, trailing, comment)


def set_eol_comment(mapping: CommentedMap, key: str, comment: str) -> None:
    """Replace the end-of-line comment on `key`, keeping blank lines that followed it."""
    tokens = mapping.ca.items.get(key)
    old = tokens[2].value if tokens and len(tokens) > 2 and tokens[2] is not None else "\n"
    rest = old.partition("\n")[2] if old.startswith("#") else old[1:]
    mapping.yaml_add_eol_comment(f"# {comment}", key)
    mapping.ca.items[key][2].value = f"# {comment}\n{rest}"
