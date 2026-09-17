# CNS Rover

**Connectome-guided robot navigation.**

CNS Rover is a Python robot-car simulator and browser workbench for exploring
navigation with MaleCNS-derived neural circuits. Its native controller combines
a freshly trained connectome readout with RGB obstacle avoidance, target tracking,
and braking. Controllers receive camera pixels and simulated time; vehicle pose,
world geometry, target coordinates, and collision state stay inside the simulator.

The Python package and command names remain `cns_car` and `cns-car`.

## Quick start

Run these commands from the repository root using Python 3.10 or newer. Reuse
`.venv` if it already exists:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[brain,web]'
.venv/bin/python -m cns_car serve --controller malecns
```

Open **http://127.0.0.1:8765**. The built frontend and the small native MaleCNS
model are included, so running the dashboard needs no frontend build, dataset
download, R installation, GPU, or neuPrint token.

To start with an obstacle layout:

```sh
.venv/bin/python -m cns_car serve --controller malecns \
  --scenario scenarios/malecns_avoidance.json
```

In the dashboard, select **Models → MaleCNS car + avoidance**, then apply to create
a new run. Running `serve` without `--controller` still selects the camera baseline.
The baseline CLI simulator needs only Python; the dashboard adds the `web`
dependencies and neural controllers add NumPy and SciPy through `brain`.

## Controllers

| CLI selector | Controller | Model source and behavior |
| --- | --- | --- |
| `malecns` | MaleCNS car + avoidance | Original MaleCNS v1.0 connectivity, a new car readout, and camera-based avoidance/braking |
| `malecns-ablated` | Native visual-input ablation | Same native model with neural visual drive disabled; geometric checks and target stopping remain active |
| `baseline` | Camera baseline | Engineered red-ball tracking and curved search; no general obstacle avoidance |
| `connectome` | Legacy connectome policy | Earlier Fly Brain Codex-derived visual circuit and learned car readout |
| `ablated` | Legacy retinal-input ablation | Legacy model with retinal input disabled |
| `your_module:YourController` | Custom controller | Loads a no-argument Python controller class |

The native and legacy model formats are separate. For `malecns`, `--model` points
to a circuit **directory**, defaulting to `data/malecns-car`. For `connectome`, it
points to a readout **file**, defaulting to `data/car-readout.npz`:

```sh
.venv/bin/python -m cns_car serve --controller malecns --model data/malecns-car
.venv/bin/python -m cns_car serve --controller connectome --model data/car-readout.npz
```

## Native MaleCNS controller

The native model uses **1,096 neurons and 29,583 retained anatomical connections**:
712 annotated LC4, LC6, LC11, LPLC1 and LPLC2 visual neurons, plus 384 of their
strongest central/descending partners. Original body IDs, synapse counts, source
hashes, and type annotations are retained alongside the model.

The readout was trained from scratch on 6,000 synthetic visual-sector patterns,
with 1,000 separate validation patterns. Its outputs are target bearing,
avoidance bias, and proximity. It uses no Fly Brain Codex code, circuits, or weights.

```text
RGB → target and obstacle sectors → MaleCNS rate circuit → learned car readout
RGB → visible ground contacts and target outline → local collision map
                              ↓
                forward-path selection and braking
                              ↓
                     steering and throttle
```

The local planner evaluates bicycle-model paths and brakes when none has enough
clearance. It predicts motion from previous commands to retain observations
outside the camera view. Complete target silhouettes replace older estimates;
edge-clipped views preserve the last complete outline.

Visual-field mapping, unsigned weight normalization, rate dynamics, training
labels, and car control are engineering choices. This is a reduced hybrid
controller. Its behavior has not been biologically validated, and the measured
results do not establish an advantage of fly wiring over other wiring.

See the [native controller guide](docs/malecns-controller.md) for the full
architecture, data provenance, training procedure, and limitations.

## Data sources and rebuilding

The vendored `natverse/malecns` package is an R library for accessing the
`male-cns:v1.0` dataset. The bundled native model was built directly from the
[original Janelia public snapshot](https://male-cns.janelia.org/download/), which
provides access without R or a neuPrint token. An alternative exporter executes
the vendored R package.

**Rebuild from the public snapshot** (approximately 1.1 GB for the original
annotations and connectivity; already cached in this workspace):

```sh
.venv/bin/python -m pip install -e '.[malecns]'
.venv/bin/python -m cns_car prepare-malecns --download
```

The builder verifies pinned file sizes and SHA-256 values, extracts the circuit,
and trains a fresh readout. `prepare-malecns` requires `vendor/malecns` to record
and check its dataset configuration. Raw files live in `data/malecns-raw/`;
the default model output is `data/malecns-car/`. Use `--output` with a new directory
to preserve an existing model.

**Build through the vendored R package** after installing R and the dependencies
listed in `vendor/malecns/DESCRIPTION`, plus `devtools` and `jsonlite`, and setting
`neuprint_token` in the environment:

```sh
Rscript scripts/export_malecns.R data/malecns-export
.venv/bin/python -m cns_car prepare-malecns \
  --source data/malecns-export --output data/malecns-car-r
.venv/bin/python -m cns_car serve --controller malecns --model data/malecns-car-r
```

The R export file format has an import round-trip test. Actual R execution remains
untested here because R and credentials are unavailable. neuPrint filtering can
differ from the flat snapshot, so evaluate an R-built model separately.

The legacy pipeline remains available through `fetch-brain`, `inspect-brain`, and
`train-brain`. Its assets are already present in this workspace. To rebuild it:

```sh
.venv/bin/python -m cns_car fetch-brain
.venv/bin/python -m cns_car inspect-brain
OPENBLAS_NUM_THREADS=2 .venv/bin/python -m cns_car train-brain --episodes 20
```

`fetch-brain` downloads a separate, pinned 348 MB Fly Brain Codex archive when
absent. That legacy download is unnecessary for the native `malecns` controller.
See [data attribution](ATTRIBUTION.md) for sources, licenses, and transformations.

## Dashboard and recordings

The React/TypeScript workbench includes a ground-truth world view, raw controller
camera and frame history, task and environment editors, vehicle/camera settings,
model selection, telemetry, and synchronized replay.

Applying configuration creates a paused experiment and preserves the previous
run. **Runs / Logs** reopens recordings. **Analysis** compares controllers on
matched seeded **empty-room** scenarios; use the evaluation script below for
obstacle comparisons.

Manual controls are **W/S** forward/reverse, **A/D** steering, and **Space** brake.
Releasing keys requests braking, and stale manual commands brake after 0.5 wall
seconds. Pause freezes simulation progress; Stop ends the episode; Reset creates
a new recorded experiment.

Browser runs are stored under `runs/workbench/`, with a SQLite index, JSONL
telemetry, and PNG camera frames. Camera images and world poses share capture
timestamps; decisions record their later physical outcomes separately. The native
controller exposes neural activity, proximity, path clearance, and braking or
avoidance overrides in its debug telemetry.

Record and verify a CLI obstacle run:

```sh
.venv/bin/python -m cns_car run --controller malecns \
  --scenario scenarios/malecns_avoidance.json --output runs/rover-demo --frames
.venv/bin/python -m cns_car replay runs/rover-demo
```

Use a new output directory for each recording. Replay reapplies commands and
verifies poses and final metrics. Browser runs support the same CLI verifier:
`replay runs/workbench/RUN_ID`. See the [workbench guide](docs/workbench.md) for
recording semantics, API details, and replay workflows.

## Measured results

The latest native-controller evaluation compares identical seeded scenarios:
10 single-cylinder obstacle layouts (seeds 9900–9909) and 10 empty rooms (seeds
10000–10009), each with a 60-simulated-second limit.

| Controller | Obstacle successes | Obstacle collisions | Empty-room successes | Empty-room collisions |
| --- | ---: | ---: | ---: | ---: |
| Camera baseline | 4/10 | 1 | 10/10 | 0 |
| Native MaleCNS + avoidance | **10/10** | **0** | **10/10** | **0** |
| Native visual-input ablation | 0/10 | 3 | 0/10 | 0 |

All other failures were timeouts. The native controller averaged approximately
2.7 ms inference per frame on obstacle runs and 4.6 ms on empty-room runs on the
evaluation machine, excluding rendering. Full scenarios, outcomes, and
model/source hashes are in [the evaluation report](docs/malecns-evaluation.json).

Reproduce the matched comparison:

```sh
OPENBLAS_NUM_THREADS=2 .venv/bin/python scripts/evaluate_malecns.py
```

These are small synthetic benchmarks. The ablation retains the geometric checks;
its collisions show those checks alone do not guarantee collision-free driving.
Matched shuffled-wiring and non-connectome controls would be needed to attribute
an advantage specifically to the anatomical wiring. Keep the evaluation seeds
separate from future tuning.

The [historical legacy evaluation](docs/evaluation.json) uses different empty-room
seeds (100–119): baseline 20/20 successes, legacy `connectome` 16/20 with one
collision, and legacy `ablated` 0/20 with one collision. Those historical results
are separate from the native-controller evaluation above.

## Development and verification

Built frontend assets are included. For frontend development or rebuilding:

```sh
npm ci --prefix frontend
npm run build --prefix frontend
# With the Python server running:
npm run dev --prefix frontend
```

Install test dependencies and run the checks:

```sh
.venv/bin/python -m pip install -e '.[brain,web,test]'
OPENBLAS_NUM_THREADS=2 .venv/bin/python -m unittest discover -s tests -v
# Install Chromium if the Playwright browser is not already available:
(cd frontend && npx playwright install chromium)
npm run test:e2e --prefix frontend
```

The latest implementation validation passed **36 Python tests**, **4 Playwright
browser tests**, and the frontend build. Tests cover circuit dependence, visual
ablation, model integrity, source imports, avoidance, blind-side target memory,
recording/replay, and workbench behavior. Rebuilding from the pinned original
files reproduced the bundled native model byte for byte. Neural tests require
the included model assets and NumPy/SciPy.

## Simulation contract and limits

- The default vehicle uses a 0.20 m wheelbase, ±30° steering, 1.5 m/s maximum
  forward speed, and 0.7 m/s reverse speed. Dynamics run at 100 Hz; camera and
  controller decisions run at 10 Hz.
- Coordinates are metres with y pointing down. Positive steering turns right.
  Scenario headings are degrees; internal angles are radians. The car cannot
  rotate in place.
- The default camera is a 96×72 RGB pinhole ray caster with 70° horizontal FOV,
  mounted 0.10 m ahead of the rear axle and 0.12 m above the ground. Workbench
  camera and steering/wheelbase settings are passed to the native controller.
- Collision uses a 0.20 m circle at the rear axle and terminates the run. Default
  success requires target-centre distance ≤0.5 m and speed ≤0.03 m/s for 0.5 s.
  Hitting the target is a failure.
- Native perception is calibrated to the renderer's brown cylinders, gray walls,
  flat floor, and a 0.15 m-radius red ball. Other colors, shapes, target sizes,
  occlusion, and unseen objects can defeat its assumptions.
- The native policy drives forward and has no global route planner. Tight layouts
  can cause braking until timeout. A collision-free timeout is still a failure.
  The baseline and legacy policies lack general obstacle avoidance.
- Servo and motor responses use first-order dynamics and rate limits. Stale
  simulated commands brake after 0.5 simulated seconds. The synchronous runner
  cannot interrupt a controller that hangs during inference; hardware use would
  require additional isolation and deadlines.
- This project currently implements simulation only. It provides no hardware
  adapter or demonstrated real-robot safety guarantees.

## Add a controller

Implement a no-argument class with `reset(task)` and
`act(observation) -> VehicleCommand`, then run:

```sh
.venv/bin/python -m cns_car run --controller your_module:YourController
```

`Observation` is immutable and contains packed `rgb` bytes, `width`, `height`, and
`timestamp`. `VehicleCommand` contains normalized `steering`, `throttle`, and an
optional `brake` flag. Commands must be finite and are clamped to [-1, 1]. Optional
`debug` dictionaries appear in recordings and the UI. A controller may implement
`configure(sensor, vehicle)` to receive workbench calibration settings.

See [the native controller guide](docs/malecns-controller.md),
[the workbench guide](docs/workbench.md), and [data attribution](ATTRIBUTION.md)
for further details.
