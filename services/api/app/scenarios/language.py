"""The YAML form of `scenario.v1`: write it, read it, and say where it is wrong.

`to_yaml` writes a spec in one fixed layout (stable key order, block style, UTF-8) so a saved
scenario diffs cleanly. `validate_text` reads text and never raises: it reports YAML syntax errors,
duplicate keys, a document that is not a mapping, an unknown contract and every contract error,
each with the line and column of the offending node, which is what the editor underlines.
`load_text` is the strict version for code that wants a spec or an exception.

The messages are plain English; the stable `code` is the key the web app renders through its
message catalogue (English and Hindi).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Self

import yaml
from pydantic import ValidationError as PydanticError

from app.contracts.loader import PackError, parse_text
from app.contracts.scenario import ScenarioSpec

HEADER = "# Fictional scenario · open-source parameters\n"
CONTRACT = "scenario.v1"

#: Top-level key order of the written form.
KEY_ORDER = (
    "contract",
    "id",
    "version",
    "title",
    "summary",
    "fictional",
    "tick_hz",
    "default_seed",
    "duration_s",
    "meta",
    "world",
    "rule_pack",
    "zones",
    "assets",
    "sensors",
    "degradations",
    "filed_flights",
    "threats",
    "groups",
)


# ------------------------------------------------------------------------------------- writing
class _Dumper(yaml.SafeDumper):
    """Block style with indented sequences, and never an anchor or alias."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)

    def ignore_aliases(self, data: Any) -> bool:  # noqa: ANN401 - PyYAML's signature
        return True


def _pruned(value: Any) -> Any:  # noqa: ANN401 - plain JSON data in, plain JSON data out
    """Drop absent values and empty lists, which are every field's default when they occur."""
    if isinstance(value, dict):
        return {k: _pruned(v) for k, v in value.items() if v is not None and v != []}
    if isinstance(value, list):
        return [_pruned(v) for v in value]
    return value


def to_yaml(spec: ScenarioSpec) -> str:
    """The scenario as YAML text; `load_text(to_yaml(spec)) == spec`."""
    data = _pruned(spec.model_dump(mode="json"))
    ordered = {k: data[k] for k in KEY_ORDER if k in data}
    body = yaml.dump(
        ordered,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    return HEADER + body


# -------------------------------------------------------------------------------------- lines
class LineMap:
    """Where each node of a YAML document sits: path to (line, column), both counted from 1."""

    def __init__(self, root: yaml.Node | None = None) -> None:
        self._root = root

    @classmethod
    def from_text(cls, text: str) -> Self:
        """The map of a document; an empty map when the text does not compose."""
        try:
            return cls(yaml.compose(text, Loader=yaml.SafeLoader))
        except yaml.YAMLError:
            return cls(None)

    def __bool__(self) -> bool:
        return self._root is not None

    def lookup(self, path: tuple[str | int, ...]) -> tuple[int, int]:
        """The position of the node at `path`, or of its deepest ancestor that exists.

        A scalar value is reported where the value is written; a mapping or list value where its
        key is. A path segment no mapping has (a union tag in a contract error, say) is skipped."""
        node = self._root
        if node is None:
            return (1, 1)
        found = (1, 1)
        for segment in path:
            child = self._child(node, segment)
            if child is None:
                if isinstance(segment, str):
                    continue
                break
            node, found = child
        return found

    @staticmethod
    def _child(node: yaml.Node, segment: str | int) -> tuple[yaml.Node, tuple[int, int]] | None:
        if isinstance(node, yaml.MappingNode) and isinstance(segment, str):
            for key, value in node.value:
                if isinstance(key, yaml.ScalarNode) and key.value == segment:
                    at = value if isinstance(value, yaml.ScalarNode) else key
                    return value, _mark(at)
        elif (
            isinstance(node, yaml.SequenceNode)
            and isinstance(segment, int)
            and not isinstance(segment, bool)
            and 0 <= segment < len(node.value)
        ):
            return node.value[segment], _mark(node.value[segment])
        return None


def _mark(node: yaml.Node) -> tuple[int, int]:
    return (node.start_mark.line + 1, node.start_mark.column + 1)


# ------------------------------------------------------------------------------- validation
@dataclass(frozen=True, slots=True)
class ValidationError:
    line: int
    column: int
    #: Dotted path of the offending node, for example `threats.2.route.0.speed_mps`.
    path: str
    #: Plain English; the web app renders `code` through its own catalogue.
    message: str
    #: `yaml.syntax`, `yaml.duplicate-key`, `yaml.not-a-mapping`, `contract.unknown` or
    #: `schema.<pydantic error type>`.
    code: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationError]
    spec: ScenarioSpec | None
    lines: LineMap


class ScenarioTextError(ValueError):
    """The text is not a valid scenario; `errors` says where and why."""

    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = errors
        first = errors[0]
        super().__init__(f"line {first.line}: {first.message}")


def _syntax(error: yaml.YAMLError) -> ValidationError:
    mark = getattr(error, "problem_mark", None)
    line, column = (mark.line + 1, mark.column + 1) if mark is not None else (1, 1)
    problem = getattr(error, "problem", None) or str(error).splitlines()[0]
    return ValidationError(line, column, "", f"YAML syntax: {problem}", "yaml.syntax")


def _mappings(node: yaml.Node, seen: set[int]) -> Iterator[yaml.MappingNode]:
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, yaml.MappingNode):
        yield node
        for key, value in node.value:
            yield from _mappings(key, seen)
            yield from _mappings(value, seen)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from _mappings(item, seen)


def _duplicates(root: yaml.Node) -> list[ValidationError]:
    """Every repeated key, reported at the repeat (a plain loader would keep only the last), and
    every key that is not a plain value."""
    found: list[ValidationError] = []
    for mapping in _mappings(root, set()):
        seen: set[str] = set()
        for key, _ in mapping.value:
            if not isinstance(key, yaml.ScalarNode):
                line, column = _mark(key)
                message = "YAML syntax: a mapping key must be a plain value, not a list or mapping"
                found.append(ValidationError(line, column, "", message, "yaml.syntax"))
                continue
            if key.value in seen:
                line, column = _mark(key)
                found.append(
                    ValidationError(
                        line,
                        column,
                        "",
                        f"duplicate key {key.value!r}: a key may appear once in a mapping",
                        "yaml.duplicate-key",
                    )
                )
            seen.add(key.value)
    return sorted(found, key=lambda e: (e.line, e.column))


_OWNER = re.compile(r"\b(threat|group|zone|asset|sensor|filed flight) ([a-z0-9]+(?:-[a-z0-9]+)*)")
_LISTS = {
    "threat": "threats",
    "group": "groups",
    "zone": "zones",
    "asset": "assets",
    "sensor": "sensors",
    "filed flight": "filed_flights",
}


def _owner_path(message: str, data: dict[str, Any]) -> tuple[str | int, ...]:
    """A whole-document rule that names its subject ("threat t-1: ...") points at that item."""
    for kind, ident in _OWNER.findall(message):
        items = data.get(_LISTS[kind])
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, dict) and item.get("id") == ident:
                    return (_LISTS[kind], i)
    return ()


def _schema_errors(
    error: PydanticError, data: dict[str, Any], lines: LineMap
) -> list[ValidationError]:
    found: list[ValidationError] = []
    for item in error.errors():
        loc = tuple(item["loc"])
        message = str(item["msg"]).removeprefix("Value error, ")
        if not loc:
            loc = _owner_path(message, data)
        line, column = lines.lookup(loc)
        found.append(
            ValidationError(
                line, column, ".".join(str(p) for p in loc), message, f"schema.{item['type']}"
            )
        )
    return sorted(found, key=lambda e: (e.line, e.column, e.path))


def validate_text(text: str) -> ValidationResult:
    """Read scenario text. Never raises: whatever is wrong comes back as errors with positions."""
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as error:
        return ValidationResult(False, [_syntax(error)], None, LineMap(None))
    lines = LineMap(root)
    if root is not None:
        repeated = _duplicates(root)
        if repeated:
            return ValidationResult(False, repeated, None, lines)
    if not isinstance(root, yaml.MappingNode):
        line, column = (1, 1) if root is None else _mark(root)
        what = "the document is empty" if root is None else "a scenario is a mapping of fields"
        found = ValidationError(line, column, "", what, "yaml.not-a-mapping")
        return ValidationResult(False, [found], None, lines)
    try:
        data = parse_text(text, ".yaml")
    except yaml.YAMLError as error:
        return ValidationResult(False, [_syntax(error)], None, lines)
    except PackError as error:  # a repeat the node walk cannot see: `1` and `true` are one key
        return ValidationResult(False, [_loader_repeat(error)], None, lines)
    if data.get("contract") != CONTRACT:
        line, column = lines.lookup(("contract",))
        message = f"unknown contract {data.get('contract')!r}: this editor reads {CONTRACT}"
        unknown = ValidationError(line, column, "contract", message, "contract.unknown")
        return ValidationResult(False, [unknown], None, lines)
    try:
        spec = ScenarioSpec.model_validate(data)
    except PydanticError as error:
        return ValidationResult(False, _schema_errors(error, data, lines), None, lines)
    return ValidationResult(True, [], spec, lines)


def _loader_repeat(error: PackError) -> ValidationError:
    found = re.search(r"at line (\d+)", str(error))
    line = int(found.group(1)) if found else 1
    return ValidationError(line, 1, "", f"{error}", "yaml.duplicate-key")


def load_text(text: str) -> ScenarioSpec:
    """The spec the text describes; `ScenarioTextError` (with every error) if it is not valid."""
    result = validate_text(text)
    if result.spec is None:
        raise ScenarioTextError(result.errors)
    return result.spec
