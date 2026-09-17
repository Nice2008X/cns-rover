from dataclasses import dataclass, field, asdict
import json
import math
import random


@dataclass
class Scenario:
    name: str = "find_red_ball"
    task: str = "Find the red ball and stop near it."
    size: list = field(default_factory=lambda: [10.0, 10.0])
    start: list = field(default_factory=lambda: [2.0, 2.0, 0.0])
    target: list = field(default_factory=lambda: [6.0, 3.0, 0.15])
    obstacles: list = field(default_factory=list)  # x, y, radius; cylinders
    timeout: float = 120.0
    success_distance: float = 0.5  # rear-axle reference to target centre
    stop_speed: float = 0.03
    stop_duration: float = 0.5

    def __post_init__(self):
        if len(self.size) != 2 or len(self.start) != 3 or len(self.target) != 3:
            raise ValueError("size needs 2 values; start and target need 3")
        numbers = self.size + self.start + self.target + [self.timeout,
            self.success_distance, self.stop_speed, self.stop_duration]
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in numbers):
            raise ValueError("Scenario values must be finite numbers")
        if min(self.size) < 2 or min(self.timeout, self.success_distance,
                                    self.stop_speed, self.stop_duration) <= 0:
            raise ValueError("Invalid room dimensions or success thresholds")
        objects = [self.target] + self.obstacles
        for obj in objects:
            if len(obj) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in obj):
                raise ValueError("Objects require finite x, y, radius")
            x, y, radius = obj
            if radius <= 0 or not (radius < x < self.size[0]-radius and radius < y < self.size[1]-radius):
                raise ValueError("Objects must fit inside the room")
        x, y, _ = self.start
        if not (0.2 < x < self.size[0]-0.2 and 0.2 < y < self.size[1]-0.2):
            raise ValueError("Start must have wall clearance")
        for i, (ox, oy, radius) in enumerate(objects):
            if math.hypot(x-ox, y-oy) <= radius+0.2:
                raise ValueError("Start overlaps an object")
            for px, py, pr in objects[:i]:
                if math.hypot(px-ox, py-oy) <= pr+radius:
                    raise ValueError("Objects overlap")

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls(**json.load(f))

    def to_dict(self):
        return asdict(self)


def randomized(seed: int) -> Scenario:
    rng = random.Random(seed)
    for _ in range(1000):
        start = [rng.uniform(1, 9), rng.uniform(1, 9), rng.uniform(-180, 180)]
        target = [rng.uniform(1, 9), rng.uniform(1, 9), 0.15]
        if math.dist(start[:2], target[:2]) > 1.5:
            return Scenario(name=f"random_{seed}", start=start, target=target)
    raise RuntimeError("Could not sample a scenario")
