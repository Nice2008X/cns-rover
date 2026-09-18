# Independent MaleCNS robot-car controller

`malecns` is a new hybrid controller built from original MaleCNS v1.0 connectivity.
It does not import `cns_rover.brain`, use `vendor/fly-brain-codex`, or consume the old
`data/brain`, `data/rover-encoder`, or `data/rover-readout.npz` assets.

## Run

The small extracted circuit and freshly fitted readout are included in
`data/malecns-rover/`. NumPy and SciPy are needed at runtime:

```sh
.venv/bin/python -m pip install -e '.[brain,web]'
.venv/bin/python -m cns_rover serve --controller malecns
.venv/bin/python -m cns_rover run --controller malecns --scenario scenarios/malecns_avoidance.json
```

In the dashboard, select **Models → MaleCNS rover + avoidance** and apply. Both
baseline-started and MaleCNS-started servers can switch controllers. The new
**MaleCNS visual ablation** option disables the circuit's visual drive while
retaining perception-based braking and the local collision check.

`--model /path/to/circuit-directory` loads another compatible native circuit and
readout. This path is a directory, unlike the legacy `connectome` controller's
single NPZ argument. Model identities, calibration and ablation state are saved
in run metadata. Debug telemetry includes neural bearing, avoidance bias,
proximity, active-neuron count, local obstacle points, clearance and safety overrides.

## Where the data comes from

The vendored `natverse/malecns` is an R **data-access library**, not model weights
or a neural simulator. Its `R/zzz.R`, `R/urls.R` and `R/neuprint.R` identify
`male-cns:v1.0` and provide metadata/connectivity access. The new builder records
hashes of these files and the package description.

There are two import paths:

1. **Original public snapshot (the model built here).** The builder reads the
   official [Janelia flat connectivity and annotations](https://male-cns.janelia.org/download/),
   the same dataset targeted by the vendored package. This avoids needing R or
   a neuPrint token. Public-source file sizes and SHA-256 values are pinned;
   these are locally measured acquisition pins, not upstream signed checksums.
2. **Actual vendored R package.** `scripts/export_malecns.R` uses
   `devtools::load_all('vendor/malecns')`, `mcns_neuprint_meta` and
   `mcns_connection_table` to export the circuit's source tables. The Python
   builder accepts those tables through `--source`. This path requires R, the
   dependencies in the vendored DESCRIPTION, and a neuPrint token. It was not
   executed here because R and credentials are unavailable. neuPrint's neuron
   filtering can differ from the flat snapshot; rebuild and evaluate that model
   rather than assuming the resulting graph is identical.

Rebuild from the public original data (~1.1 GB download; already cached here):

```sh
.venv/bin/python -m pip install -e '.[malecns]'
.venv/bin/python -m cns_rover prepare-malecns --download
```

Rebuild using the vendored R package after installing its dependencies and
configuring `neuprint_token` in the environment (never put tokens in commands):

```sh
Rscript scripts/export_malecns.R data/malecns-export
.venv/bin/python -m cns_rover prepare-malecns \
  --source data/malecns-export --output data/malecns-rover-r
.venv/bin/python -m cns_rover serve --controller malecns --model data/malecns-rover-r
```

Preparation writes to the specified output directory. Use a new output directory
to preserve an existing circuit/readout. There is no silent fallback to a mock
brain or to the legacy policy when assets are absent or invalid.

## Circuit and car adaptation

The included extraction selects 712 LC4, LC6, LC11, LPLC1 and LPLC2 neurons with
left/right soma annotations, then the 384 central/descending partners receiving
the strongest total input from that population. It retains 29,583 actual directed
connections with at least five synapses, including recurrent downstream edges.
`anatomy.npz` preserves original body IDs, edge endpoints and synapse counts;
`neurons.json` preserves type and side annotations.

```text
RGB + camera calibration
  ├─ 7 target-salience sectors + 7 obstacle-proximity sectors
  │    → mapped visual neurons → measured anatomical connections
  │    → four tanh rate updates → new learned car readout
  │    → target bearing / avoidance bias / proximity
  └─ visible ground contacts + observed target outline
       → local obstacle map using command-based motion prediction
       → bicycle-path clearance check and braking
                         ↓
                  steering + throttle
```

All visual-field assignment is engineered: soma side divides hemispheres and
body-ID order assigns sectors. It is **not measured retinotopy**. LC11 receives
target salience; the other selected populations receive proximity. Incoming
synapse counts are normalized and treated as unsigned excitatory couplings.
No neurotransmitter signs or biological timing are claimed. The network begins
at zero for each frame and performs four propagation updates.

The ridge readout is newly trained on 6,000 synthetic sector patterns, with
1,000 separate validation patterns (seed 2718). Labels are explicit equations
for target bearing, lateral obstacle bias and proximity. They do not come from
the old controller, fly motor behavior or robot-arm weights. Only downstream
neural activity reaches this readout; there is no direct sensory skip connection.
The small sensory validation error in `training.json` is **not** navigation
performance. Circuit-lesion and ablation tests verify that signals actually
propagate through the anatomical matrices.

The camera-only planner is a separate engineered component. It estimates visible
wall/cylinder ground contacts from camera height and focal length, inflates
clearance for the car's footprint, evaluates forward bicycle arcs, and brakes
when none is clear. It uses its previous commands to predict ego motion; it never
reads vehicle pose, world objects, target coordinates, or collision flags.
Observed obstacles persist briefly outside the view; the most recent target
outline is retained longer to avoid clipping it from the side. Target outlines
are replaced on complete redetection rather than accumulating noisy monocular
estimates. Edge-clipped views retain the last complete silhouette.

## Validation and limitations

Run the regression and matched evaluation suites:

```sh
OPENBLAS_NUM_THREADS=2 .venv/bin/python -m unittest discover -s tests -v
npm run build --prefix frontend
npm run test:e2e --prefix frontend
OPENBLAS_NUM_THREADS=2 .venv/bin/python scripts/evaluate_malecns.py
```

The evaluation script reports baseline, native MaleCNS and visual ablation on
identical scenarios, with full per-run results and model/source hashes in
`docs/malecns-evaluation.json`. Seeds 9300–9309 / 9400–9409 and 9700–9709 / 9800–9809 were used during
safety development; final evaluation uses obstacle seeds 9900–9909 and empty-room seeds 10000–10009.
Do not tune on final evaluation seeds and continue calling them held out.
Workbench Analysis still samples **empty rooms**; use the evaluation script for
the obstacle suite.

Final measured results (10 runs per suite, 60 simulated seconds per run):

| Controller | Obstacle successes | Obstacle collisions | Empty-room successes | Empty-room collisions |
| --- | ---: | ---: | ---: | ---: |
| Camera baseline | 4/10 | 1 | 10/10 | 0 |
| Native MaleCNS + avoidance | 10/10 | 0 | 10/10 | 0 |
| Native visual-input ablation | 0/10 | 3 | 0/10 | 0 |

All remaining failures were timeouts. Mean controller inference was approximately
2.7 ms per frame in the obstacle suite and 4.6 ms in the empty-room suite on this
machine (rendering excluded). The ablation's three collisions demonstrate that
the geometric checks alone do not guarantee collision-free driving. The sample
is small, and the scenes use one cylinder per obstacle run; tighter layouts and
multiple obstacles are covered by development checks, not this success rate.

Validation: 36 Python tests and 4 Playwright browser tests pass; the frontend
build succeeds. The CLI obstacle demo completes and replays exactly. Rebuilding
the circuit and readout from the pinned original files reproduces all bundled
model files byte for byte. The R export file contract is tested by round-trip
import; actual R execution remains untested in this environment.

This is a reduced connectome-derived **hybrid engineering controller**, not a
whole-brain simulation. Its collision check and stopping still use raw vision
when neural input is ablated. Comparisons against a baseline without avoidance
cannot establish that fly wiring is better than other neural wiring; that would
require matched shuffled-connectivity and non-connectome controls.

Perception is calibrated to the synthetic renderer's brown cylinders, gray walls,
flat floor, fixed camera height/offset, and a 0.15 m red ball. Sensor FOV and
vehicle wheelbase/steering settings are propagated from the workbench, but this
is not a general object detector or a real-robot safety system. Occluded ground
contacts, noisy blob ranges, unseen objects outside the forward camera, long
motion-prediction drift, and different object colors/shapes remain limitations.

It only drives forward, has no global route planner, and can stop indefinitely
in a tight layout. A car starting very close to a wall may brake until timeout
instead of reversing into an unobserved area. A collision-free timeout counts
as failure, not success. Collision still terminates an episode.
