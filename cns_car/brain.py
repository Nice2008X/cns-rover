"""Pinned MaleCNS-derived assets and an explicitly engineered CPU experiment."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from urllib.request import urlopen

REVISION = "18933f06a9e80e9f40c503b2d58b54ab78e9283b"
ARCHIVE_SHA256 = "c4c9295dcc1bc730ff6214aec29e7bf8cd0bbcd8ed5e4b73c3597743835c7d39"
ARCHIVE_BYTES = 348112531
GRAPH_ID = "53e1d528e43cb834982e9207457da777d4c0d55f570844bb96b049ad043c3f7d"
CIRCUIT_ID = "a6975cdd7314f078588f758f434f8cff22787bcf86a4d7d1d239760a5ca18e52"
URL = f"https://huggingface.co/monomyth/fly-brain-codex/resolve/{REVISION}/runtime-assets.tar.gz"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_unpack(archive, destination):
    """Only regular files/directories; reject traversal, links and oversized archives."""
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        total = 0
        seen = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("Unsafe archive path")
            if not (member.isfile() or member.isdir()):
                raise ValueError("Archive links and special files are not permitted")
            if path in seen:
                raise ValueError("Duplicate archive entry")
            seen.add(path)
            total += member.size
            if total > 2_000_000_000:
                raise ValueError("Archive exceeds expanded size limit")
        for member in members:
            target = destination/member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open("xb") as out:
                    shutil.copyfileobj(source, out)


def verify_directory(directory):
    manifest = json.loads((directory/"manifest.json").read_text())
    for name, expected in manifest["files"].items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe manifest path")
        if sha256(directory/name) != expected:
            raise ValueError(f"Asset checksum mismatch: {name}")
    return manifest


def fetch_assets(data):
    data = Path(data)
    cache = data/"raw"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache/"runtime-assets.tar.gz"
    destination = data/"brain"
    if not archive.exists():
        partial = archive.with_suffix(".part")
        try:
            with urlopen(URL, timeout=60) as response, partial.open("wb") as out:
                total = 0
                while block := response.read(1024*1024):
                    total += len(block)
                    if total > ARCHIVE_BYTES:
                        raise ValueError("Download exceeds pinned size")
                    out.write(block)
            if partial.stat().st_size != ARCHIVE_BYTES or sha256(partial) != ARCHIVE_SHA256:
                raise ValueError("Download checksum mismatch")
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    if archive.stat().st_size != ARCHIVE_BYTES or sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("Cached archive checksum mismatch; remove it and retry")
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix=".brain-", dir=data) as temp:
            staged = Path(temp)/"brain"
            staged.mkdir()
            safe_unpack(archive, staged)
            verify_directory(staged/"prepared"/GRAPH_ID)
            verify_directory(staged/"circuits"/CIRCUIT_ID)
            staged.rename(destination)
    result = inspect_graph(data)
    (data/"brain-provenance.json").write_text(json.dumps(result, indent=2))
    return result


def inspect_graph(data):
    root = Path(data)/"brain"
    graph = verify_directory(root/"prepared"/GRAPH_ID)
    circuit = verify_directory(root/"circuits"/CIRCUIT_ID)
    return {"source": URL, "revision": REVISION, "archive_sha256": ARCHIVE_SHA256,
            "graph_id": GRAPH_ID, "nodes": graph["nodes"], "edges": graph["edges"],
            "sensory_inputs": graph["inputs"], "motor_outputs": graph["outputs"],
            "circuit_populations": circuit["populations"],
            "license": "CC-BY-4.0", "biologically_validated": False}


def build_encoder(data):
    """Select a bounded visual subgraph from actual retinal outgoing connections.

    This is a car-specific visual reservoir, not the released arm controller.
    """
    import numpy as np
    from scipy import sparse
    data = Path(data)
    directory = data/"brain"/"circuits"/CIRCUIT_ID
    manifest = verify_directory(directory)
    with np.load(directory/"populations.npz", allow_pickle=False) as pops:
        retina = pops["retina"].copy()
        uv = pops["retina_uv"].copy()
        ids = pops["ids"].copy()
    full = sparse.load_npz(directory/"sensory-signed.npz").tocsr()
    retinal = full[:, retina].tocsr()
    strength = np.asarray(abs(retinal).sum(axis=1)).ravel()
    strength[retina] = 0
    selected = np.argsort(-strength, kind="stable")[:512]
    selected = selected[strength[selected] > 0]
    if not len(selected):
        raise ValueError("No connected visual neurons")
    feed = retinal[selected].tocsr()
    recurrent = full[selected][:, selected].tocsr()
    total = np.asarray(abs(feed).sum(axis=1)+abs(recurrent).sum(axis=1)).ravel()
    scale = sparse.diags(1/np.maximum(total, 1e-8))
    feed, recurrent = (scale@feed).tocsr(), (scale@recurrent).tocsr()
    target = data/"car-encoder"
    target.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(target/"retina.npz", feed)
    sparse.save_npz(target/"recurrent.npz", recurrent)
    np.savez(target/"mapping.npz", uv=uv, retina_ids=ids[retina], output_ids=ids[selected])
    info = {"schema": "cns-car-visual-reservoir-v1", "source_circuit": CIRCUIT_ID,
            "source_manifest_sha256": sha256(directory/"manifest.json"),
            "source_revision": REVISION, "retinal_neurons": len(retina),
            "visual_neurons": len(selected), "feed_edges": feed.nnz,
            "recurrent_edges": recurrent.nnz,
            "retinal_coverage": float(np.count_nonzero(np.asarray(abs(feed).sum(axis=0)))/len(retina)),
            "selection": "512 strongest postsynaptic rows receiving retinal input",
            "encoding": "engineered red salience, nearest retinal UV sampling",
            "dynamics": "two leaky tanh updates per frame; abstract, not biological time",
            "readout": "ridge regression to baseline steering and throttle",
            "files": {name: sha256(target/name) for name in ("retina.npz", "recurrent.npz", "mapping.npz")},
            "biologically_validated": False}
    (target/"manifest.json").write_text(json.dumps(info, indent=2))
    # Preserve original attribution alongside transformed matrices.
    shutil.copyfile(directory/"ATTRIBUTION.md", target/"ATTRIBUTION.md")
    return target


class VisualReservoir:
    def __init__(self, directory):
        import numpy as np
        from scipy import sparse
        self.np = np
        self.directory = Path(directory)
        self.manifest = verify_directory(self.directory)
        self.feed = sparse.load_npz(self.directory/"retina.npz")
        self.recurrent = sparse.load_npz(self.directory/"recurrent.npz")
        with np.load(self.directory/"mapping.npz", allow_pickle=False) as mapping:
            self.uv = mapping["uv"].copy()
        self.state = np.zeros(self.feed.shape[0], dtype=np.float32)
        self.ablated = False

    def reset(self):
        self.state.fill(0)

    def features(self, observation):
        np = self.np
        rgb = np.frombuffer(observation.rgb, dtype=np.uint8).reshape(observation.height, observation.width, 3).astype(np.float32)/255
        salience = np.maximum(0, rgb[:,:,0]-np.maximum(rgb[:,:,1], rgb[:,:,2])-.2)
        # Small max filter makes distant two-pixel targets visible to the sparse retina.
        padded = np.pad(salience, 1)
        salience = np.maximum.reduce([padded[y:y+observation.height, x:x+observation.width]
                                     for y in range(3) for x in range(3)])
        x = np.clip(np.rint(self.uv[:,0]*(observation.width-1)).astype(int), 0, observation.width-1)
        y = np.clip(np.rint(self.uv[:,1]*(observation.height-1)).astype(int), 0, observation.height-1)
        injection = self.feed@salience[y,x]*4
        if self.ablated:
            injection *= 0
        for _ in range(2):
            self.state = .35*self.state+.65*np.tanh(injection+.5*(self.recurrent@self.state))
        return self.state.copy()


class ConnectomeController:
    def __init__(self, model, ablated=False):
        import numpy as np
        self.model = Path(model)
        with np.load(self.model, allow_pickle=False) as saved:
            self.weights = saved["weights"].copy()
            self.mean = saved["mean"].copy()
            self.scale = saved["scale"].copy()
            self.config = json.loads(str(saved["config"]))
        encoder_path = (self.model.parent/self.config["encoder"]).resolve()
        self.encoder = VisualReservoir(encoder_path)
        if sha256(encoder_path/"manifest.json") != self.config["encoder_manifest_sha256"]:
            raise ValueError("Model/encoder identity mismatch")
        self.encoder.ablated = ablated
        expected = self.encoder.feed.shape[0]
        if self.weights.shape != (expected+1, 2) or self.mean.shape != (expected,) or self.scale.shape != (expected,):
            raise ValueError("Readout dimensions do not match encoder")
        if not all(np.isfinite(a).all() for a in (self.weights, self.mean, self.scale)) or np.any(self.scale <= 0):
            raise ValueError("Invalid readout parameters")
        self.config = {**self.config, "model_sha256": sha256(self.model), "ablated": ablated}

    def reset(self, task):
        if "red ball" not in task.lower():
            raise ValueError("This readout supports only red-ball tasks")
        self.encoder.reset()
        self.debug = {"mode": "CONNECTOME", "biologically_validated": False}

    def act(self, observation):
        import numpy as np
        from .protocol import VehicleCommand
        features = self.encoder.features(observation)
        values = np.r_[(features-self.mean)/self.scale, 1.]@self.weights
        if not np.isfinite(values).all():
            raise ValueError("Non-finite neural output")
        steering, throttle = np.clip(values, -1, 1)
        self.debug = {"mode": "CONNECTOME_ABLATED" if self.encoder.ablated else "CONNECTOME",
                      "active_visual_neurons": int(np.count_nonzero(abs(features) > 1e-5)),
                      "steering": float(steering), "throttle": float(throttle)}
        return VehicleCommand(float(steering), float(throttle), brake=bool(throttle < .035))


def train(data, episodes, output):
    """Behavioural cloning from a camera-only teacher, with disjoint evaluation seeds."""
    import numpy as np
    import math
    from .camera import Camera
    from .controllers import BaselineController
    from .scenario import Scenario
    from .simulator import Simulator
    from .runner import Session
    encoder_path = build_encoder(data)
    encoder = VisualReservoir(encoder_path)
    camera = Camera()
    teacher = BaselineController()
    teacher.reset("Find the red ball")
    rng = np.random.default_rng(2026)
    xs, ys = [], []
    # Static views cover stopping, far targets, both image edges, and absence.
    for i in range(episodes*80):
        distance = float(rng.uniform(.37, 4.0))
        angle = float(rng.uniform(-math.pi, math.pi)) if i % 4 == 0 else float(rng.uniform(-.65, .65))
        scenario = Scenario(start=[5., 5., 0.], target=[5+distance*math.cos(angle), 5+distance*math.sin(angle), .15])
        obs = camera.observe(Simulator(scenario))
        encoder.reset()
        for _ in range(3):
            features = encoder.features(obs)
            action = teacher.act(obs)
            xs.append(features)
            ys.append([action.steering, 0 if action.brake else action.throttle])
        if i % 400 == 0:
            print(f"Training views: {i}/{episodes*80}", flush=True)
    # Add continuous states so memory during actual approaches is represented.
    for i in range(episodes):
        angle = float(rng.uniform(-.5, .5))
        distance = float(rng.uniform(1.2, 3.5))
        scenario = Scenario(start=[5., 5., 0.], target=[5+distance*math.cos(angle), 5+distance*math.sin(angle), .15], timeout=25)
        session = Session(scenario, BaselineController())
        encoder.reset()
        while session.sim.status == "running":
            obs = camera.observe(session.sim)
            features = encoder.features(obs)
            action = teacher.act(obs)
            xs.append(features)
            ys.append([action.steering, 0 if action.brake else action.throttle])
            session.tick(action)
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), .01)
    design = np.column_stack(((x-mean)/scale, np.ones(len(x))))
    penalty = np.eye(design.shape[1])*10
    penalty[-1,-1] = 0
    weights = np.linalg.solve(design.T@design+penalty, design.T@y)
    output = Path(output)
    if output.suffix != ".npz":
        raise ValueError("Model output must end in .npz")
    output.parent.mkdir(parents=True, exist_ok=True)
    config = {"schema": "cns-car-readout-v1", "source_revision": REVISION,
              "encoder": os.path.relpath(encoder_path.resolve(), output.parent.resolve()),
              "encoder_manifest_sha256": sha256(encoder_path/"manifest.json"),
              "training_seed": 2026, "episodes": episodes, "samples": len(x),
              "teacher": "camera-only BaselineController", "ridge": 10,
              "biologically_validated": False}
    np.savez_compressed(output, weights=weights, mean=mean, scale=scale, config=json.dumps(config))
    result = {**config, "training_rmse": np.sqrt(np.mean((design@weights-y)**2, axis=0)).tolist(),
              "model_sha256": sha256(output),
              "note": "Training error is not closed-loop success. Evaluate held-out scenarios and ablation."}
    output.with_suffix(".json").write_text(json.dumps(result, indent=2))
    return result
