# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities privately rather than through public
GitHub issues, discussions, or pull requests.

- **GitHub private reporting:** If enabled for this repository, use
  [Report a vulnerability](https://github.com/Nice2008X/cns-rover/security/advisories/new).
- **Email:** Contact [aixu2008nice@gmail.com](mailto:aixu2008nice@gmail.com) with
  **CNS Rover SECURITY** in the subject line if private reporting is unavailable
  or you prefer email.

Include the affected commit or version, operating system and relevant dependency
versions, the impact, and minimal reproduction steps. For a problematic scenario,
model, or recording, describe its source and provide the smallest necessary
example. Redact credentials and private information from logs and attachments.

Reports will be reviewed to assess impact and coordinate a fix and disclosure
where appropriate. Please allow time for investigation before publishing exploit
details. Response times are not guaranteed. Fixes target the current default
branch; when practical, check whether the issue also affects that revision.

## Project scope

CNS Rover consists of a Python simulator, a local FastAPI HTTP/WebSocket server,
and a React browser workbench. It reads scenario and neural-model files and
persists recordings, camera frames, telemetry, and a SQLite run index on disk.
Optional data-preparation workflows download connectome assets or query neuPrint
through the vendored R package.

Reports of particular interest include:

- Cross-site scripting or injection through scenario names, telemetry, recordings,
  or other content rendered in the workbench.
- Bypasses of HTTP/WebSocket host and origin checks, including browser requests
  that expose local recordings or trigger unauthorized simulation actions.
- Path traversal or unintended filesystem access through recording, replay,
  export, model-loading, or archive-extraction paths.
- Unsafe parsing of JSON, NPZ, Feather, CSV, or downloaded archives, including
  code execution and practical resource-exhaustion attacks.
- Failures in download integrity checks, exposure of neuPrint credentials, or
  dependency and supply-chain vulnerabilities with a credible project impact.

## Deployment and trust boundaries

The provided `serve` command binds to `127.0.0.1`. The workbench has no user
accounts, authentication, or tenant isolation. Host and origin checks provide
some protection against browser-origin attacks; they are not authentication.
Keep the service local. Public hosting, shared-machine access, or reverse-proxy
exposure requires a separate access-control and deployment review.

Custom controllers loaded with `--controller module:Class` execute Python code
with the server process's permissions. The optional R exporter also executes
local R code. These extension mechanisms are not sandboxes; use trusted code.
Load models, scenario files, and recordings from trusted sources. Checksums
check files against recorded or pinned values; a manifest supplied alongside
an untrusted model does not establish its publisher's identity.

Browser recordings are stored under `runs/workbench/` by default, and CLI runs
use the selected output directory. Recordings may contain task text, scenario
settings, camera frames, and controller debug output. Review them before sharing.
Keep neuPrint tokens in the environment or the upstream client's credential
configuration, and out of committed files and reports. Running the bundled
native model does not require a token.

## Simulation behavior and physical safety

Controller collisions, timeouts, and navigation failures without a security
impact are ordinary bugs or research limitations and can be reported in public
issues. Include the scenario, controller, model identity, and relevant recording.

CNS Rover currently provides simulation only. Its obstacle checks and simulated
watchdog do not constitute a physical emergency stop or a real-robot safety
system. Inference runs synchronously, so the simulator cannot interrupt a
controller that hangs during a decision. Hardware integration requires separate
process isolation, deadlines, actuator safeguards, and safety validation.
