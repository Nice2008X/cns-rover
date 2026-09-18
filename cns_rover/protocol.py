"""Hardware-independent controller boundary. No simulator state crosses it."""
from dataclasses import dataclass
import math
from typing import Protocol


@dataclass(frozen=True)
class Observation:
    rgb: bytes
    width: int
    height: int
    timestamp: float  # simulated seconds


@dataclass(frozen=True)
class VehicleCommand:
    steering: float = 0.0  # positive = right
    throttle: float = 0.0  # positive = forward; zero requests deceleration
    brake: bool = False

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.steering, self.throttle)):
            raise ValueError("Commands must be finite")
        if not isinstance(self.brake, bool):
            raise ValueError("brake must be a boolean")

    def limited(self):
        return VehicleCommand(max(-1, min(1, self.steering)),
                              max(-1, min(1, self.throttle)), self.brake)


class Controller(Protocol):
    def reset(self, task: str) -> None: ...
    def act(self, observation: Observation) -> VehicleCommand: ...
