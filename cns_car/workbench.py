"""Experiment lifecycle and durable, synchronized debugger recordings."""
from pathlib import Path
import base64
import copy
import json
import math
import sqlite3
import threading
import time
import uuid
from .camera import Camera, png
from .controllers import load_controller
from .protocol import VehicleCommand
from .runner import Session
from .scenario import Scenario, randomized


DEFAULT_SENSOR = {"width": 96, "height": 72, "fov": 70}
DEFAULT_VEHICLE = {"wheelbase": .2, "max_steering_degrees": 30}


def validate_config(data):
    for section in ("scenario", "sensor", "vehicle"):
        if not isinstance(data.get(section, {}), dict):
            raise ValueError(f"{section} must be an object")
    if set(data.get("sensor", {})) - set(DEFAULT_SENSOR) or set(data.get("vehicle", {})) - set(DEFAULT_VEHICLE):
        raise ValueError("Unknown sensor or vehicle field")
    try:
        scenario = Scenario(**data.get("scenario", {}))
    except (TypeError, KeyError) as exc:
        raise ValueError(f"Invalid scenario: {exc}") from exc
    if not isinstance(scenario.name, str) or not isinstance(scenario.task, str):
        raise ValueError("Scenario name and task must be strings")
    if scenario.timeout > 600:
        raise ValueError("Interactive runs are limited to 600 simulated seconds")
    sensor = {**DEFAULT_SENSOR, **data.get("sensor", {})}
    if type(sensor["width"]) is not int or type(sensor["height"]) is not int or (sensor["width"], sensor["height"]) not in [(96, 72), (160, 120), (320, 240)]:
        raise ValueError("Choose a supported sensor resolution")
    if not isinstance(sensor["fov"], (int, float)) or not 40 <= sensor["fov"] <= 110:
        raise ValueError("FOV must be between 40 and 110 degrees")
    vehicle = {**DEFAULT_VEHICLE, **data.get("vehicle", {})}
    for key, low, high in [("wheelbase", .1, 1), ("max_steering_degrees", 5, 45)]:
        if not isinstance(vehicle[key], (int, float)) or not low <= vehicle[key] <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
    model = data.get("controller", "baseline")
    if model not in ("baseline", "connectome", "ablated", "malecns", "malecns-ablated", "custom"):
        raise ValueError("Unsupported controller")
    return {"scenario": scenario.to_dict(), "sensor": sensor, "vehicle": vehicle, "controller": model}


class RunStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.database() as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, summary TEXT NOT NULL)")

    def database(self):
        return sqlite3.connect(self.root / "index.sqlite3", timeout=10)

    def directory(self, run_id):
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("Invalid run ID")
        path = self.root / run_id
        if not path.is_dir():
            raise FileNotFoundError("Run not found")
        return path

    def index(self, summary):
        with self.database() as db:
            db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?)", (summary["id"], json.dumps(summary)))

    def list(self):
        with self.database() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT summary FROM runs ORDER BY rowid DESC LIMIT 1000")]

    def records(self, run_id):
        path = self.directory(run_id) / "snapshots.jsonl"
        with path.open() as stream:
            return [json.loads(line) for line in stream if line.endswith("\n")]

    def snapshot(self, run_id, index):
        records = self.records(run_id)
        if index < 0 or index >= len(records):
            raise ValueError("Frame index out of range")
        result = records[index]
        result["camera"] = base64.b64encode((self.directory(run_id) / result["frame_path"]).read_bytes()).decode()
        return result


class Experiment:
    def __init__(self, config, factory, store, seed=None):
        self.config = copy.deepcopy(config)
        self.store = store
        self.id = uuid.uuid4().hex
        self.path = store.root / self.id
        self.path.mkdir()
        (self.path / "frames").mkdir()
        (self.path / "steps.jsonl").touch()
        self.session = Session(Scenario(**config["scenario"]), factory())
        if hasattr(self.session.controller, "configure"):
            self.session.controller.configure(config["sensor"], config["vehicle"])
        self.session.camera = Camera(**config["sensor"])
        self.session.sim.wheelbase = config["vehicle"]["wheelbase"]
        self.session.sim.max_steering = math.radians(config["vehicle"]["max_steering_degrees"])
        self.session.observation = self.session.camera.observe(self.session.sim)
        self.created = time.time()
        self.seed = seed
        self.events = []
        self.count = 0
        self.inference = []
        self.last_mode = None
        self.finished = False
        self.started = False
        self.wall_elapsed = 0.0
        self.event("READY", "Experiment ready")
        self.write_json("config.json", config)
        self.write_json("scenario.json", config["scenario"])
        self.write_json("controller.json", {"class": f"{type(self.session.controller).__module__}:{type(self.session.controller).__name__}", "config": getattr(self.session.controller, "config", {}), "simulator_version": "0.2.0", "physics_hz": 100, "camera_hz": 10, "sensor": config["sensor"], "vehicle": config["vehicle"]})
        self.latest = self.capture(self.session.sim.state(), self.session.observation, {}, None)

    def write_json(self, name, value):
        (self.path / name).write_text(json.dumps(value, indent=2, allow_nan=False))

    def event(self, kind, message, timestamp=None):
        self.events.append({"type": kind, "message": message, "time": self.session.sim.time if timestamp is None else timestamp})

    def summary(self):
        return {"id": self.id, "created": self.created, "name": self.config["scenario"]["name"], "controller": self.config["controller"], "seed": self.seed, "frames": self.count, "finished": self.finished, "result": self.session.sim.result()}

    def capture(self, state, obs, debug, decision):
        index = self.count
        frame_path = f"frames/{index:06d}.png"
        raw = png(obs)
        (self.path / frame_path).write_bytes(raw)
        snapshot = {"version": 1, "run_id": self.id, "index": index, "sim_time": obs.timestamp, "frame_path": frame_path, **state, "debug": copy.deepcopy(debug), "decision": decision, "events": copy.deepcopy(self.events), "sensor": self.config["sensor"], "vehicle_config": self.config["vehicle"], "controller": self.config["controller"], "wall_elapsed": self.wall_elapsed, "performance": {"last_inference_ms": self.inference[-1] if self.inference else None, "avg_inference_ms": sum(self.inference)/len(self.inference) if self.inference else None, "p95_inference_ms": sorted(self.inference)[max(0, math.ceil(len(self.inference)*.95)-1)] if self.inference else None}}
        with (self.path / "snapshots.jsonl").open("a") as stream:
            stream.write(json.dumps(snapshot, allow_nan=False)+"\n")
        self.count += 1
        self.store.index(self.summary())
        return {**snapshot, "camera": base64.b64encode(raw).decode()}

    def tick(self, command=None):
        if self.finished:
            return
        started = time.monotonic()
        if not self.started:
            self.started = True
            self.event("START", "Simulation started")
        sim = self.session.sim
        before = copy.deepcopy(sim.state())
        obs = self.session.observation
        try:
            # Session reuses this same observation for the controller decision.
            record = self.session.tick(command)
        except Exception as exc:
            self.event("ERROR", str(exc))
            self.finish()
            return
        elapsed = (time.monotonic()-started)*1000
        if command is None:
            self.inference.append(self.session.inference_ms)
        self.wall_elapsed += elapsed/1000
        debug = copy.deepcopy(getattr(self.session.controller, "debug", {})) if command is None else {"mode": "MANUAL"}
        mode = debug.get("mode")
        if mode != self.last_mode:
            self.event("STATE", f"Controller: {mode or 'unknown'}", obs.timestamp)
            self.last_mode = mode
        if debug.get("visible") and not any(e["type"] == "TARGET_VISIBLE" for e in self.events):
            self.event("TARGET_VISIBLE", "Target detected in camera", obs.timestamp)
        with (self.path / "steps.jsonl").open("a") as stream:
            stream.write(json.dumps(record, allow_nan=False)+"\n")
        before["command"] = record["command"]
        decision = {"frame_id": self.count, "timestamp": obs.timestamp, "input": {"width": obs.width, "height": obs.height, "camera": f"frames/{self.count:06d}.png"}, "output": record["command"], "debug": debug, "outcome_time": sim.time, "outcome": record["vehicle"], "source": "manual" if command is not None else "controller"}
        self.latest = self.capture(before, obs, debug, decision)
        if sim.status != "running":
            self.finish()

    def finish(self, reason=None):
        if self.finished:
            return
        if reason:
            self.session.sim.stop(reason)
        self.finished = True
        self.event("SUCCESS" if self.session.sim.status == "success" else "STOP", self.session.sim.reason or "Stopped")
        self.latest = self.capture(self.session.sim.state(), self.session.camera.observe(self.session.sim), {}, None)
        self.write_json("result.json", self.session.sim.result())
        self.store.index(self.summary())


class Workbench:
    def __init__(self, scenario, factory, root, controller="baseline", model=None):
        self.lock = threading.RLock()
        self.store = RunStore(root)
        self.factory = factory
        if model is None:
            model = "data/malecns-car" if controller in ("malecns", "malecns-ablated") else "data/car-readout.npz"
        self.model = Path(model) if controller not in ("malecns", "malecns-ablated") else Path("data/car-readout.npz")
        self.malecns_model = Path(model) if controller in ("malecns", "malecns-ablated") else Path("data/malecns-car")
        self.config = validate_config({"scenario": scenario.to_dict(), "controller": controller})
        self.current = Experiment(self.config, self.get_factory(controller), self.store)
        self.running = False
        self.has_run = False
        self.manual = False
        self.command = VehicleCommand(brake=True)
        self.command_time = 0
        self.speed = 1.0
        self.error = None
        self.batch = {"status": "idle", "completed": 0, "total": 0, "runs": []}
        self.batch_cancel = threading.Event()
        self.closed = threading.Event()

    def get_factory(self, name):
        if name == "custom":
            return self.factory
        if name in ("malecns", "malecns-ablated"):
            from .malecns_controller import MaleCNSController
            return lambda: MaleCNSController(self.malecns_model, ablated=name == "malecns-ablated")
        if name == "baseline":
            return lambda: load_controller("baseline")
        from .brain import ConnectomeController
        return lambda: ConnectomeController(self.model, ablated=name == "ablated")

    def state(self):
        with self.lock:
            return {"type": "snapshot", **self.current.latest, "running": self.running, "phase": "finished" if self.current.finished else "running" if self.running else "paused" if self.has_run else "ready", "manual": self.manual, "speed_multiplier": self.speed, "error": self.error, "frame_count": self.current.count, "finished": self.current.finished, "config": self.config, "batch": copy.deepcopy(self.batch)}

    def worker(self):
        while not self.closed.wait(.1/self.speed):
            with self.lock:
                if not self.running:
                    continue
                try:
                    command = (self.command if time.monotonic()-self.command_time < .5 else VehicleCommand(brake=True)) if self.manual else None
                    self.current.tick(command)
                except Exception as exc:
                    self.error = str(exc)
                    self.current.finish("recording_error")
                if self.current.finished:
                    self.running = False

    def action(self, name, payload):
        with self.lock:
            if name == "run":
                if self.current.finished:
                    raise ValueError("Reset before starting a new run")
                self.running = True
                self.has_run = True
            elif name == "pause":
                self.running = False
            elif name == "stop":
                self.running = False
                self.current.finish("emergency_stop")
            elif name in ("reset", "configure"):
                config = validate_config(payload) if name == "configure" else self.config
                # Construct/validate the new controller before ending the previous run.
                fresh = Experiment(config, self.get_factory(config["controller"]), self.store)
                self.current.finish("reset")
                self.config, self.current = config, fresh
                self.running = self.manual = self.has_run = False
                self.command = VehicleCommand(brake=True)
                self.error = None
            elif name == "manual":
                if not isinstance(payload.get("enabled"), bool):
                    raise ValueError("enabled must be boolean")
                self.manual = payload["enabled"]
                self.command = VehicleCommand(brake=True)
                self.command_time = 0
            elif name == "command":
                self.command = VehicleCommand(**payload).limited()
                self.command_time = time.monotonic()
            elif name == "speed":
                speed = payload.get("value")
                if not isinstance(speed, (int, float)) or speed not in [.25, .5, 1, 2, 4]:
                    raise ValueError("Invalid playback speed")
                self.speed = speed
            else:
                raise ValueError("Unknown action")
        return self.state()

    def start_batch(self, payload):
        with self.lock:
            if self.batch["status"] == "running":
                raise ValueError("A batch is already running")
            count, seed = payload.get("count", 10), payload.get("seed", 1000)
            models = payload.get("controllers", [self.config["controller"]])
            if type(count) is not int or not 1 <= count <= 1000 or type(seed) is not int or not 0 <= seed <= 2147482647:
                raise ValueError("Use 1–1000 seeds and a nonnegative integer starting seed")
            if not isinstance(models, list) or not models or len(models) > 5 or any(m not in ["baseline", "connectome", "ablated", "malecns", "malecns-ablated"] for m in models):
                raise ValueError("Choose supported controllers")
            config = copy.deepcopy(self.config)
            self.batch = {"status": "running", "completed": 0, "total": count*len(models), "runs": [], "seed": seed}
            self.batch_cancel.clear()
        def execute():
            try:
                for model in models:
                    for number in range(seed, seed+count):
                        if self.batch_cancel.is_set() or self.closed.is_set():
                            break
                        run_config = copy.deepcopy(config)
                        sampled = randomized(number)
                        # Batch explicitly randomizes an empty room; retain task thresholds.
                        run_config["scenario"].update(name=f"random_{number}", size=sampled.size, start=sampled.start, target=sampled.target, obstacles=[])
                        run_config["controller"] = model
                        experiment = Experiment(run_config, self.get_factory(model), self.store, seed=number)
                        while not experiment.finished and not self.batch_cancel.is_set() and not self.closed.is_set():
                            experiment.tick()
                        if not experiment.finished:
                            experiment.finish("batch_cancelled")
                        with self.lock:
                            self.batch["runs"].append(experiment.summary())
                            self.batch["completed"] += 1
                with self.lock:
                    self.batch["status"] = "cancelled" if self.batch_cancel.is_set() or self.closed.is_set() else "complete"
            except Exception as exc:
                with self.lock:
                    self.batch.update(status="failed", error=str(exc))
        self.batch_thread = threading.Thread(target=execute, daemon=True)
        self.batch_thread.start()
        return copy.deepcopy(self.batch)
