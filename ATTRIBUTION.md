# Data attribution

MaleCNS data: FlyEM at HHMI Janelia, University of Cambridge, MRC Laboratory of
Molecular Biology, Google Research, and collaborators.
Source: https://male-cns.janelia.org/download/
License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

Prepared graph and circuit assets: Monomyth's Fly Brain Codex,
https://huggingface.co/monomyth/fly-brain-codex
revision 18933f06a9e80e9f40c503b2d58b54ab78e9283b.
Derived assets are CC BY 4.0. Original attribution files are retained under
data/brain and copied alongside the derived car encoder.

CNS Car modifications: select 512 visually driven neurons from the published
signed retinal circuit, renormalize the selected incoming weights, introduce
red-salience image encoding and abstract rate dynamics, and fit a new car
steering/throttle readout. These are engineering assumptions and are not
validated biological dynamics. The released robot-arm policy is not used.

The natverse R repository was inspected for background and is retained in
vendor/malecns with its GPL-3.0 license. No R code is incorporated into the Python runtime. The optional
`scripts/export_malecns.R` now executes the vendored package for data export. The Python reference source is retained under
vendor/fly-brain-codex with its MIT license. Neither vendor tree is required
at runtime.

## Independent native MaleCNS car model

`data/malecns-car/` is derived directly from Janelia's original MaleCNS v1.0
flat connectivity and annotations, not from Fly Brain Codex. Source URLs and
SHA-256 values, plus hashes of the inspected vendored natverse/malecns files,
are recorded in its manifest. The optional R exporter calls the vendored package.

Data attribution: FlyEM / HHMI Janelia, University of Cambridge, MRC Laboratory
of Molecular Biology, Google Research, and collaborators. Source and license:
https://male-cns.janelia.org/download/ and
https://creativecommons.org/licenses/by/4.0/.

New modifications: select annotated LC4/LC6/LC11/LPLC1/LPLC2 inputs and their
strongest central/descending partners, retain actual synapse counts, engineer
sector inputs and normalized unsigned rate dynamics, fit a new car readout,
and add a separate RGB local avoidance planner. These transformations and the
resulting car behavior are not biologically validated.
