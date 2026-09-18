import React, { useEffect, useState } from "react";
import {
  Activity,
  Box,
  BrainCircuit,
  Camera,
  Car,
  ChartNoAxesCombined,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Clock3,
  Crosshair,
  Download,
  Expand,
  FileText,
  Flag,
  FlaskConical,
  Focus,
  Gauge,
  GitBranch,
  Layers3,
  Maximize2,
  Pause,
  Play,
  Radio,
  RotateCcw,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  Terminal,
  TriangleAlert,
  Waypoints,
  X,
} from "lucide-react";
import { api, fmt, title } from "./types";
import type { Config, Live, Run } from "./types";
import { Panel, Row, Button } from "./ui";
import { EnvironmentEditor } from "./editor";
export function RunsPage({
  runs,
  refresh,
  open,
}: {
  runs: Run[];
  refresh: () => void;
  open: (r: Run) => void;
}) {
  const [filter, setFilter] = useState("all");
  const shown = runs.filter(
    (r) => filter === "all" || r.result.status === filter,
  );
  return (
    <div className="page-content">
      <div className="page-title">
        <div>
          <h2>Runs & recordings</h2>
          <p>
            Every experiment, ready to inspect. Select a run to open its
            synchronized replay.
          </p>
        </div>
        <Button icon={RotateCcw} onClick={refresh}>
          Refresh
        </Button>
      </div>
      <div className="filter-row">
        <label>
          Status{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All runs</option>
            <option value="success">Success</option>
            <option value="failed">Failed / stopped</option>
            <option value="running">In progress</option>
          </select>
        </label>
        <span>{shown.length} runs</span>
      </div>
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Experiment</th>
              <th>Controller</th>
              <th>Seed</th>
              <th>Status</th>
              <th>Time</th>
              <th>Distance</th>
              <th>Collisions</th>
              <th>Recording</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td>
                  <b>{r.name}</b>
                  <small>
                    {new Date(r.created * 1000).toLocaleString()} ·{" "}
                    {r.id.slice(0, 8)}
                  </small>
                </td>
                <td>{r.controller}</td>
                <td>{r.seed ?? "—"}</td>
                <td>
                  <span className={"result-pill " + r.result.status}>
                    {r.finished
                      ? title(r.result.reason || r.result.status)
                      : "In progress"}
                  </span>
                </td>
                <td>{fmt(r.result.time, 1)} s</td>
                <td>{fmt(r.result.distance)} m</td>
                <td>{r.result.collisions}</td>
                <td>
                  <div className="table-actions">
                    <button onClick={() => open(r)}>
                      <Play size={12} />
                      Replay
                    </button>
                    <a
                      href={`/api/runs/${r.id}/export`}
                      download
                      aria-label={`Export ${r.name}`}
                    >
                      <Download size={14} />
                    </a>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!shown.length && (
          <div className="empty-state">
            <FileText />
            <h3>No matching recordings</h3>
            <p>Start a simulation to create a recorded experiment.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function ConfigPage({
  page,
  config,
  busy,
  apply,
  report,
}: {
  page: string;
  config: Config;
  busy: boolean;
  apply: (c: Config) => Promise<void>;
  report: (e: unknown) => void;
}) {
  const [draft, setDraft] = useState<Config>(structuredClone(config)),
    [presets, setPresets] = useState<
      { label: string; scenario: Config["scenario"] }[]
    >([]),
    [obstacles, setObstacles] = useState(
      JSON.stringify(config.scenario.obstacles, null, 2),
    );
  useEffect(() => {
    api<typeof presets>("presets").then(setPresets).catch(report);
  }, []);
  const scenario = (key: keyof Config["scenario"], value: unknown) =>
    setDraft((d) => ({ ...d, scenario: { ...d.scenario, [key]: value } }));
  const num = (
    label: string,
    value: number,
    onChange: (n: number) => void,
    min?: number,
    max?: number,
    step = 0.1,
  ) => (
    <label className="field">
      {label}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        required
        onChange={(e) => onChange(e.target.valueAsNumber)}
      />
    </label>
  );
  const coordinate = (
    key: "size" | "start" | "target",
    index: number,
    value: number,
  ) =>
    scenario(
      key,
      draft.scenario[key].map((v, i) => (i === index ? value : v)),
    );
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const parsed = JSON.parse(obstacles);
      if (!Array.isArray(parsed)) throw Error("Obstacles must be an array");
      await apply({
        ...draft,
        scenario: { ...draft.scenario, obstacles: parsed },
      });
    } catch (e) {
      report(e);
    }
  };
  return (
    <div className="page-content">
      <div className="page-title">
        <div>
          <h2>{page}</h2>
          <p>
            Configure the next experiment. Applying changes saves the current
            run and starts a new paused session.
          </p>
        </div>
        <label className="import-button">
          <Download size={13} />
          Import configuration
          <input
            type="file"
            accept=".json,application/json"
            onChange={async (e) => {
              try {
                const file = e.target.files?.[0];
                if (!file) return;
                const data = JSON.parse(await file.text());
                if (
                  !data.scenario ||
                  !Array.isArray(data.scenario.start) ||
                  !Array.isArray(data.scenario.size) ||
                  !Array.isArray(data.scenario.target) ||
                  !Array.isArray(data.scenario.obstacles) ||
                  !data.sensor ||
                  !data.vehicle ||
                  typeof data.controller !== "string"
                )
                  throw Error("Choose an exported experiment configuration");
                const validated = await api<Config>("validate", data);
                setDraft(validated);
                setObstacles(JSON.stringify(data.scenario.obstacles, null, 2));
              } catch (e) {
                report(e);
              }
            }}
          />
        </label>
      </div>
      <form onSubmit={save}>
        {page === "Tasks" ? (
          <Panel title="Find the red ball" icon={Flag}>
            <div className="form-grid">
              <label className="field">
                Experiment name
                <input
                  required
                  maxLength={80}
                  value={draft.scenario.name}
                  onChange={(e) => scenario("name", e.target.value)}
                />
              </label>
              <label className="field">
                Task instruction
                <input
                  required
                  value={draft.scenario.task}
                  onChange={(e) => scenario("task", e.target.value)}
                />
              </label>
              {num(
                "Success distance (m)",
                draft.scenario.success_distance,
                (n) => scenario("success_distance", n),
                0.01,
                10,
                0.01,
              )}
              {num(
                "Maximum stopped speed (m/s)",
                draft.scenario.stop_speed,
                (n) => scenario("stop_speed", n),
                0.001,
                1,
                0.01,
              )}
              {num(
                "Stopped hold (seconds)",
                draft.scenario.stop_duration,
                (n) => scenario("stop_duration", n),
                0.01,
                30,
              )}
              {num(
                "Timeout (seconds)",
                draft.scenario.timeout,
                (n) => scenario("timeout", n),
                1,
                600,
                1,
              )}
            </div>
            <p className="form-note">
              Success requires distance, speed, and hold conditions together.
              Collision terminates the run. Current controllers support the
              red-ball objective; additional task policies are not installed.
            </p>
          </Panel>
        ) : page === "Environment" ? (
          <>
            <Panel title="Environment presets" icon={Layers3}>
              <div className="preset-list">
                {presets.map((p) => (
                  <button
                    type="button"
                    key={p.label}
                    onClick={() => {
                      setDraft((d) => ({ ...d, scenario: p.scenario }));
                      setObstacles(
                        JSON.stringify(p.scenario.obstacles, null, 2),
                      );
                    }}
                  >
                    <Box size={22} />
                    <b>{p.label}</b>
                    <span>
                      {p.scenario.obstacles.length} obstacles ·{" "}
                      {p.scenario.size.join(" × ")} m
                    </span>
                  </button>
                ))}
              </div>
            </Panel>
            <Panel title="Arena & objects" icon={Box}>
              <EnvironmentEditor
                scenario={draft.scenario}
                onChange={(s) => {
                  setDraft((d) => ({ ...d, scenario: s }));
                  setObstacles(JSON.stringify(s.obstacles, null, 2));
                }}
              />
              <div className="form-grid">
                {num(
                  "Arena width (m)",
                  draft.scenario.size[0],
                  (n) => coordinate("size", 0, n),
                  2,
                  100,
                )}
                {num(
                  "Arena height (m)",
                  draft.scenario.size[1],
                  (n) => coordinate("size", 1, n),
                  2,
                  100,
                )}
                {num("Vehicle spawn X (m)", draft.scenario.start[0], (n) =>
                  coordinate("start", 0, n),
                )}
                {num("Vehicle spawn Y (m)", draft.scenario.start[1], (n) =>
                  coordinate("start", 1, n),
                )}
                {num(
                  "Vehicle heading (degrees)",
                  draft.scenario.start[2],
                  (n) => coordinate("start", 2, n),
                  -180,
                  180,
                  1,
                )}
                {num("Target X (m)", draft.scenario.target[0], (n) =>
                  coordinate("target", 0, n),
                )}
                {num("Target Y (m)", draft.scenario.target[1], (n) =>
                  coordinate("target", 1, n),
                )}
                {num(
                  "Target radius (m)",
                  draft.scenario.target[2],
                  (n) => coordinate("target", 2, n),
                  0.01,
                  2,
                  0.01,
                )}
              </div>
              <label className="field">
                Cylindrical obstacles · JSON array of [x, y, radius] in metres
                <textarea
                  rows={4}
                  value={obstacles}
                  onChange={(e) => setObstacles(e.target.value)}
                />
              </label>
              <p className="form-note">
                Geometry is validated for wall clearance and overlapping
                objects. Target size changes can affect the baseline’s stopping
                calibration.
              </p>
            </Panel>
          </>
        ) : page === "Robot / Vehicle" ? (
          <>
            <Panel title="Vehicle geometry" icon={Car}>
              <div className="form-grid">
                {num(
                  "Wheelbase (m)",
                  draft.vehicle.wheelbase,
                  (n) =>
                    setDraft((d) => ({
                      ...d,
                      vehicle: { ...d.vehicle, wheelbase: n },
                    })),
                  0.1,
                  1,
                  0.01,
                )}
                {num(
                  "Maximum steering (degrees)",
                  draft.vehicle.max_steering_degrees,
                  (n) =>
                    setDraft((d) => ({
                      ...d,
                      vehicle: { ...d.vehicle, max_steering_degrees: n },
                    })),
                  5,
                  45,
                  1,
                )}
              </div>
              <p className="form-note">
                Bicycle dynamics · 1.5 m/s forward · 0.7 m/s reverse ·
                conservative 0.20 m collision radius.
              </p>
            </Panel>
            <Panel title="Front RGB camera" icon={Camera}>
              <div className="form-grid">
                <label className="field">
                  Resolution
                  <select
                    value={draft.sensor.width}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        sensor: {
                          ...d.sensor,
                          width: +e.target.value,
                          height: (+e.target.value * 3) / 4,
                        },
                      }))
                    }
                  >
                    <option value="96">96 × 72 (default)</option>
                    <option value="160">160 × 120</option>
                    <option value="320">320 × 240</option>
                  </select>
                </label>
                {num(
                  "Horizontal field of view (degrees)",
                  draft.sensor.fov,
                  (n) =>
                    setDraft((d) => ({
                      ...d,
                      sensor: { ...d.sensor, fov: n },
                    })),
                  40,
                  110,
                  1,
                )}
              </div>
              <p className="form-note">
                Changing the sensor changes real controller input. Larger frames
                increase rendering cost. The baseline is calibrated for 96 × 72,
                70° FOV, and a 0.15 m-radius ball.
              </p>
            </Panel>
          </>
        ) : (
          <Panel title="Controller selection" icon={BrainCircuit}>
            <div className="model-list">
              {[
                [
                  "baseline",
                  "Camera baseline",
                  "Engineered red-ball detection, curved search, approach, and braking.",
                ],
                [
                  "malecns",
                  "MaleCNS rover + avoidance",
                  "New circuit from original MaleCNS v1.0 connectivity, with RGB obstacle avoidance and braking.",
                ],
                [
                  "malecns-ablated",
                  "MaleCNS visual ablation",
                  "New circuit with visual drive disabled; geometric safety remains active.",
                ],
                [
                  "connectome",
                  "Legacy connectome policy",
                  "Earlier Fly Brain Codex-derived retinal circuit and car readout.",
                ],
                [
                  "ablated",
                  "Retinal-input ablation",
                  "Same readout with retinal input disabled, for matched evaluation.",
                ],
              ].map(([value, name, description]) => (
                <label
                  className={
                    "model-option " +
                    (draft.controller === value ? "selected" : "")
                  }
                  key={value}
                >
                  <input
                    type="radio"
                    name="controller"
                    value={value}
                    checked={draft.controller === value}
                    onChange={() =>
                      setDraft((d) => ({ ...d, controller: value }))
                    }
                  />
                  <BrainCircuit size={24} />
                  <div>
                    <h3>{name}</h3>
                    <p>{description}</p>
                  </div>
                  {draft.controller === value && <CircleCheck size={18} />}
                </label>
              ))}
            </div>
            <p className="form-note">
              MaleCNS v1.0 provides anatomical connectivity. The
              connectome-derived controller here is an experimental car
              adaptation, not a full-brain simulation or a pretrained MaleCNS
              driving policy.
            </p>
          </Panel>
        )}
        <div className="form-actions">
          <button type="submit" className="primary" disabled={busy}>
            <Check size={14} />
            Apply & create new run
          </button>
          <button
            type="button"
            onClick={() => {
              try {
                const blob = new Blob(
                  [
                    JSON.stringify(
                      {
                        ...draft,
                        scenario: {
                          ...draft.scenario,
                          obstacles: JSON.parse(obstacles),
                        },
                      },
                      null,
                      2,
                    ),
                  ],
                  { type: "application/json" },
                );
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "experiment-config.json";
                a.click();
                URL.revokeObjectURL(a.href);
              } catch (e) {
                report(e);
              }
            }}
          >
            <Download size={14} />
            Export configuration
          </button>
        </div>
      </form>
    </div>
  );
}

export function AnalysisPage({
  runs,
  live,
  refresh,
  open,
  report,
}: {
  runs: Run[];
  live: Live;
  refresh: () => void;
  open: (r: Run) => void;
  report: (e: unknown) => void;
}) {
  const [seed, setSeed] = useState(1000),
    [count, setCount] = useState(10),
    [models, setModels] = useState(["baseline"]),
    [scope, setScope] = useState("batch");
  const batch = live.batch;
  const selected =
    scope === "batch"
      ? batch.runs
      : runs.filter(
          (r) =>
            r.seed !== null &&
            r.finished &&
            r.result.reason !== "batch_cancelled",
        );
  const groups = [...new Set(selected.map((r) => r.controller))].map(
    (model) => {
      const rows = selected.filter((r) => r.controller === model);
      return {
        model,
        count: rows.length,
        success: rows.filter((r) => r.result.status === "success").length,
        collisions: rows.reduce((s, r) => s + r.result.collisions, 0),
        time: rows.reduce((s, r) => s + r.result.time, 0) / rows.length,
        distance: rows.reduce((s, r) => s + r.result.distance, 0) / rows.length,
      };
    },
  );
  const start = async () => {
    try {
      await api("batch", { seed, count, controllers: models });
    } catch (e) {
      report(e);
    }
  };
  return (
    <div className="page-content">
      <div className="page-title">
        <div>
          <h2>Evaluation & analysis</h2>
          <p>
            Compare controllers on identical seeded scenarios, then inspect the
            runs that need attention.
          </p>
        </div>
        <Button icon={RotateCcw} onClick={refresh}>
          Refresh
        </Button>
      </div>
      <Panel title="Red-ball robustness experiment" icon={FlaskConical}>
        <div className="batch-form">
          <label className="field">
            First seed
            <input
              type="number"
              min="0"
              max="2147482647"
              value={seed}
              onChange={(e) => setSeed(+e.target.value)}
            />
          </label>
          <label className="field">
            Seeds per controller
            <input
              type="number"
              min="1"
              max="1000"
              value={count}
              onChange={(e) => setCount(+e.target.value)}
            />
          </label>
          <div className="batch-models">
            {["baseline", "connectome", "ablated", "malecns", "malecns-ablated"].map((m) => (
              <label key={m}>
                <input
                  type="checkbox"
                  checked={models.includes(m)}
                  onChange={(e) =>
                    setModels(
                      e.target.checked
                        ? [...models, m]
                        : models.filter((x) => x !== m),
                    )
                  }
                />
                {title(m)}
              </label>
            ))}
          </div>
          <Button
            icon={Play}
            primary
            disabled={batch.status === "running" || !models.length}
            onClick={start}
          >
            Run {count * models.length} tests
          </Button>
          {batch.status === "running" && (
            <Button
              icon={Square}
              danger
              onClick={() => api("batch/cancel", {}).catch(report)}
            >
              Cancel
            </Button>
          )}
        </div>
        <p className="form-note">
          Randomizes vehicle position, heading, and target position in an empty
          10 × 10 m room. Each controller receives the same seeds. Current
          sensor, vehicle, and task thresholds apply. Seeds 100–119 remain
          reserved for the original evaluation.
        </p>
        {batch.status !== "idle" && (
          <div className="batch-progress">
            <Row
              label={`Batch ${batch.status}`}
              value={`${batch.completed} / ${batch.total}`}
            />
            <progress value={batch.completed} max={batch.total} />
            {batch.error && <p className="red-text">{batch.error}</p>}
          </div>
        )}
      </Panel>
      <div className="filter-row">
        <label>
          Compare{" "}
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="batch">Current batch (matched seeds)</option>
            <option value="all">All saved seeded runs (descriptive)</option>
          </select>
        </label>
        <span>Metrics include failures. No aggregate score is invented.</span>
      </div>
      <div className="summary-cards">
        {groups.map((g) => (
          <Panel title={title(g.model)} icon={BrainCircuit} key={g.model}>
            <div className="big-number">
              {fmt((g.success / g.count) * 100, 1)}
              <small>% success</small>
            </div>
            <progress value={g.success} max={g.count} />
            <Row
              label="Successful / total"
              value={`${g.success} / ${g.count}`}
            />
            <Row label="Collisions" value={g.collisions} />
            <Row label="Mean elapsed time" value={`${fmt(g.time)} s`} />
            <Row label="Mean distance" value={`${fmt(g.distance)} m`} />
          </Panel>
        ))}
      </div>
      {!selected.length && (
        <div className="empty-state">
          <ChartNoAxesCombined size={30} />
          <h3>Your next benchmark starts here</h3>
          <p>Run a seeded experiment to see success rates and failure cases.</p>
        </div>
      )}
      <Panel title="Runs to investigate" icon={TriangleAlert}>
        <div className="failure-list">
          {selected
            .filter((r) => r.result.status !== "success")
            .map((r) => (
              <button key={r.id} onClick={() => open(r)}>
                <span>
                  Seed {r.seed} · {r.controller}
                </span>
                <span>{title(r.result.reason || "in progress")}</span>
                <Play size={13} />
              </button>
            ))}
          {selected.length > 0 &&
            selected.every((r) => r.result.status === "success") && (
              <p className="green">All selected runs succeeded.</p>
            )}
        </div>
      </Panel>
    </div>
  );
}
