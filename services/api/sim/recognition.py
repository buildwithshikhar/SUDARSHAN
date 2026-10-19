"""What a truth class is scored as: the operator-vocabulary class of the threat catalogue.

`autonomous-small`, `decoy-small` and `civil-drone` look like a quadcopter, so a trainee who says
`rotary-small` is right. A class the catalogue does not know (a test double, an old scenario) is
scored as itself.
"""

from functools import lru_cache

from .catalogue import Catalogue, load_catalogue


@lru_cache(maxsize=1)
def _catalogue() -> Catalogue:
    return load_catalogue()


def recognition_class(class_id: str) -> str:
    """The operator class the truth class `class_id` is scored as."""
    catalogue = _catalogue()
    return catalogue.recognition_class(class_id) if class_id in catalogue else class_id
