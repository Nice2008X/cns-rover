"""Deterministic command recording and replay."""
from dataclasses import asdict
from pathlib import Path
import json
import time
import math
from .camera import Camera, png
from .simulator import Simulator
from .scenario import Scenario
from .protocol import VehicleCommand


class Session:
    def __init__(self, scenario, controller):
        self.sim = Simulator(scenario)
        self.camera = Camera()
        self.controller = controller
        controller.reset(scenario.task)
        self.observation = self.camera.observe(self.sim)

    def tick(self, command=None):
        if self.sim.status != "running":
            return None
        observation = self.observation
        self.last_observation = observation
        started = time.perf_counter()
        try:
            action = command if command is not None else self.controller.act(observation)
            self.inference_ms = (time.perf_counter()-started)*1000
            self.sim.submit(action)
        except Exception as exc:
            self.sim.stop("controller_error")
            raise RuntimeError("Controller failed; simulation stopped") from exc
        record = {"time": self.sim.time, "command": asdict(self.sim.command)}
        for _ in range(self.sim.camera_steps):
            self.sim.step()
        record.update(vehicle=asdict(self.sim.vehicle), result=self.sim.result(),
                      debug=getattr(self.controller, "debug", {}))
        self.observation = self.camera.observe(self.sim)
        return record


def run(scenario, controller, output=None, frames=False):
    session = Session(scenario, controller)
    directory = Path(output) if output else None
    log = None
    if directory:
        directory.mkdir(parents=True, exist_ok=False)
        (directory/"scenario.json").write_text(json.dumps(scenario.to_dict(), indent=2))
        (directory/"controller.json").write_text(json.dumps({
            "class": f"{type(controller).__module__}:{type(controller).__name__}",
            "config": getattr(controller, "config", {}),
            "simulator_version": "0.1.0", "physics_hz": 100, "camera_hz": 10}, indent=2))
        log = (directory/"steps.jsonl").open("w")
        if frames:
            (directory/"frames").mkdir()
    index = 0
    try:
        while session.sim.status == "running":
            record = session.tick()
            if log:
                if frames:
                    name = f"frames/{index:06d}.png"
                    (directory/name).write_bytes(png(session.last_observation))
                    record["frame"] = name
                log.write(json.dumps(record, allow_nan=False)+"\n")
            index += 1
    finally:
        if log:
            log.close()
        if directory:
            (directory/"result.json").write_text(json.dumps(session.sim.result(), indent=2))
    return session.sim.result()


def replay(directory):
    directory = Path(directory)
    sim = Simulator(Scenario.load(directory/"scenario.json"))
    metadata = json.loads((directory/"controller.json").read_text())
    vehicle = metadata.get("vehicle", {})
    sim.wheelbase = vehicle.get("wheelbase", sim.wheelbase)
    sim.max_steering = math.radians(vehicle.get("max_steering_degrees", math.degrees(sim.max_steering)))
    count = 0
    with (directory/"steps.jsonl").open() as stream:
        for line in stream:
            record = json.loads(line)
            if sim.status != "running" or abs(sim.time-record["time"]) > 1e-8:
                raise ValueError("Replay timestamp or terminal-state mismatch")
            sim.submit(VehicleCommand(**record["command"]))
            for _ in range(sim.camera_steps):
                sim.step()
            if any(abs(value-record["vehicle"][key]) > 1e-8
                   for key, value in asdict(sim.vehicle).items()):
                raise ValueError(f"Replay diverged at decision {count}")
            count += 1
    expected = json.loads((directory/"result.json").read_text())
    if sim.status == "running" and expected.get("reason") in ("emergency_stop", "reset", "batch_cancelled", "server_shutdown", "controller_error", "recording_error"):
        sim.stop(expected["reason"])
    if sim.result() != expected:
        raise ValueError("Replay final metrics differ")
    return {"verified_decisions": count, "result": sim.result()}
