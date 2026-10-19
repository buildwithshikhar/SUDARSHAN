"""What a truth class is scored as, and the operator vocabulary that goes with it."""

from sim.catalogue import load_catalogue
from sim.recognition import recognition_class
from sim.roe import OPERATOR_CLASSES


def test_the_operator_vocabulary_is_the_recognition_set_plus_unknown() -> None:
    catalogue = load_catalogue()
    assert set(OPERATOR_CLASSES) == catalogue.recognition_set | {"unknown"}
    assert len(OPERATOR_CLASSES) == len(set(OPERATOR_CLASSES)) == 9


def test_the_first_four_classes_keep_their_decision_panel_keys() -> None:
    assert OPERATOR_CLASSES[:4] == ("rotary-small", "fixed-wing-small", "bird", "unknown")


def test_look_alike_classes_are_scored_as_a_quadcopter() -> None:
    for class_id in ("autonomous-small", "decoy-small", "civil-drone"):
        assert recognition_class(class_id) == "rotary-small"


def test_a_class_the_catalogue_does_not_know_is_scored_as_itself() -> None:
    assert recognition_class("unlisted-class") == "unlisted-class"
