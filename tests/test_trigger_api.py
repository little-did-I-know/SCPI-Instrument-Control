import pytest

from scpi_control.trigger import Trigger


class FakeScope:
    def __init__(self, trig_type: str = "EDGE", source: str = "C1"):
        self.trig_type = trig_type
        self.current_source = source
        self.writes = []

    def query(self, command: str) -> str:
        if command == "TRIG_SELECT?":
            return f"{self.trig_type},SR,{self.current_source}"
        return ""

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command.startswith("TRIG_SELECT"):
            _, params = command.split(" ", 1)
            trig_type, _, source = params.split(",")
            self.trig_type = trig_type
            self.current_source = source


def test_set_source_accepts_integers_and_preserves_trigger_type():
    scope = FakeScope(trig_type="SLEW", source="C3")
    trigger = Trigger(scope)

    trigger.set_source(1)

    assert scope.current_source == "C1"
    assert scope.trig_type == "SLEW"
    assert scope.writes == ["TRIG_SELECT SLEW,SR,C1"]


def test_set_level_updates_source_then_writes_level_command():
    scope = FakeScope(source="C1")
    trigger = Trigger(scope)

    trigger.set_level(2, 0.5)

    assert scope.current_source == "C2"
    assert scope.writes == ["TRIG_SELECT EDGE,SR,C2", "C2:TRLV 0.5"]


def test_set_slope_and_mode_delegate_to_property_writers():
    scope = FakeScope()
    trigger = Trigger(scope)

    trigger.set_slope("neg")
    trigger.set_mode("single")

    assert scope.writes == ["TRIG_SLOPE NEG", "TRIG_MODE SINGLE"]
