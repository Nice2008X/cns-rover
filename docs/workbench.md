# MaleCNS workbench

The desktop interface follows the two references in `todos/`: two large visual panels, a task/control column, four telemetry cards, and a full-width debugger. It runs on the existing vehicle physics and controllers.

## Start and develop

Use the repository virtual environment:

```sh
.venv/bin/python -m pip install -e '.[web,test]'
.venv/bin/python -m cns_rover serve
```

Open http://127.0.0.1:8765. Built frontend assets are included in `cns_rover/web/`, so Node is only needed when changing the interface. Vite 8 requires Node.js 20.19+ or 22.12+ (Node 24 is supported):

```sh
npm ci --prefix frontend
npm run build --prefix frontend
# Or run Vite with API and WebSocket proxying to the Python service:
npm run dev --prefix frontend
```

## Workflow

1. Configure Tasks, Environment, Robot / Vehicle, and Models. The environment editor supports dragging vehicle/target/obstacles, adding/removing cylindrical obstacles, presets, numeric fields, and an explicit obstacle JSON editor. Apply validates the configuration, preserves the old recording, and creates a paused experiment.
2. Run, pause, stop, or reset from Simulation. Manual mode uses W/S, A/D, and Space. Releasing keys or losing focus requests braking; stale manual commands also brake after 0.5 wall seconds.
3. Watch the actual raw camera input, ground-truth world, trajectory, field of view, controller commands, and measured actuators. World objects are inspectable. Camera annotations are optional and use only controller debug reports.
4. Click a frame thumbnail, chart, event, or timeline slider to inspect a recording. Replay updates the camera, world, state, commands, metrics, events, and model I/O together. Use playback controls or Return to live. Inspecting history does not pause the live simulation; the banner says when it continues. The stop control remains available.
5. Reopen runs from Runs / Logs. Export JSONL telemetry or PNG camera frames. Export/import experiment configurations from configuration pages.
6. In Analysis, run 1–1,000 seeded empty-room scenarios per selected controller. All selected controllers receive identical seeds and the current camera/vehicle/task settings. Progress, cancellation, success rates, collisions, mean time/distance, and failure replay are available. Current-batch comparisons are matched; the all-saved-runs view is descriptive and may mix configurations.

## Recording semantics

`runs/workbench/index.sqlite3` indexes runs. Each run directory contains:

- `config.json`, `scenario.json`, `controller.json`: resolved experiment and controller configuration.
- `snapshots.jsonl`: versioned, synchronized debugger snapshots.
- `steps.jsonl`: commands and resulting states, compatible with the CLI replay verifier.
- `frames/*.png`: lossless sensor frames.
- `result.json`: final metrics, including externally stopped runs.

Snapshots describe the world **at camera capture time**, with the command issued in response to that image. `decision.outcome_time` and `decision.outcome` explicitly describe the later physical result. The initial snapshot has no decision; each control interval records its decision snapshot; a terminal snapshot captures the final physical state and camera with no new decision. Consequently the initial and first decision snapshots share time zero. This avoids presenting a pre-step image as if it showed a post-step pose.

Controller observations remain immutable RGB bytes, dimensions, and simulation time. Ground-truth coordinates, distances, success conditions, and collisions never enter the observation. Optional confidence and estimates stay unavailable when the controller does not provide them.

Run the existing deterministic verifier against a completed browser run:

```sh
.venv/bin/python -m cns_rover replay runs/workbench/RUN_ID
```

Vehicle geometry overrides are restored during verification. Manual and reset/stop terminal events are handled without treating them as controller decisions. Historical CLI recordings remain verifiable, but are not automatically imported into the new browser run index.

## Architecture

- `frontend/src/main.tsx`: live/replay state and cockpit.
- `frontend/src/pages.tsx`: experiment forms, saved runs, and batch analysis.
- `frontend/src/ui.tsx`, `visuals.tsx`, `editor.tsx`: shared panels, SVG views, chart, and editor.
- `cns_rover/server.py`: FastAPI, REST, WebSocket stream, and built asset serving.
- `cns_rover/workbench.py`: run lifecycle, persistence, validated configuration, and batch worker.
- `cns_rover/runner.py`: existing fixed-step simulation and deterministic command replay.

The service binds to loopback and checks request hosts and mutation/WebSocket origins. Browser sampling does not drive physics. Simulation speed changes wall-clock pacing, not the 100 Hz physical timestep.

## Validation

```sh
.venv/bin/python -m unittest discover -s tests -v
npm run build --prefix frontend
npx --prefix frontend playwright install chromium
npm run test:e2e --prefix frontend
```

Backend tests verify original physics/controller behavior, every saved frame against its recorded world pose, configured-geometry replay, reset/empty recordings, invalid configuration isolation, seeded batches, HTTP/WebSocket controls, persistence, and the manual watchdog. Browser tests cover run/pause/success, timeline/model-I/O inspection, environment configuration, batch results, saved-run replay, invalid inputs, settings persistence, and a 390 px mobile viewport. Browser-test recordings use temporary directories.

## Current limits

The camera remains the actual simple ray-cast sensor, rather than a decorative rendering of the reference image. Supported resolutions are 96×72, 160×120, and 320×240; 70° FOV remains the default. Changed target size, sensor settings, or vehicle geometry can alter controller performance and need separate evaluation.

Only the existing red-ball objective and controllers are executable. Richer task plugins, lighting/noise randomization, richer rendering, video export, external controller process isolation, and the physical hardware bridge remain later work. Inference is synchronous; a hung external controller cannot be interrupted by the simulated-time watchdog. The simulation speed is a pacing target, not a real-time guarantee. Active compute time is measured separately from simulation time.

Confidence, estimated depth, detection boxes, and a composite score are not synthesized. Steering variation is measured in radians and is not labeled as an oscillation count. Model selection accurately distinguishes the engineering baseline, experimental connectome-derived policy, and retinal-input ablation.

## Verified build

The implementation was checked with 23 Python tests and three browser tests,
including actual object dragging. The production frontend build and Python wheel
build pass; the wheel includes the compiled dashboard assets. Desktop and mobile
captures are saved in [screenshots/](screenshots/), including the
[completed-run cockpit](screenshots/cockpit-completed.png).
