import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
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
import type { LucideIcon } from "lucide-react";
import { api, fmt, title } from "./types";
import type { Config, Live, Run, Snapshot } from "./types";
import { Chart, VehicleDrawing, World } from "./visuals";
import { Panel, Row, Button, GaugeBar } from "./ui";
import { RunsPage, ConfigPage, AnalysisPage } from "./pages";
import "./style.css";

const tabs: [string, LucideIcon][] = [
  ["Simulation", Box],
  ["Tasks", Flag],
  ["Environment", Layers3],
  ["Robot / Vehicle", Car],
  ["Models", BrainCircuit],
  ["Runs / Logs", FileText],
  ["Analysis", ChartNoAxesCombined],
  ["Settings", Settings],
];
function App() {
  const [live, setLive] = useState<Live | null>(null),
    [connection, setConnection] = useState("Connecting"),
    [page, setPage] = useState("Simulation"),
    [history, setHistory] = useState<Snapshot[]>([]),
    [replay, setReplay] = useState<Snapshot | null>(null),
    [replayRun, setReplayRun] = useState<string | null>(null),
    [playing, setPlaying] = useState(false),
    [playbackRate, setPlaybackRate] = useState(1),
    [runs, setRuns] = useState<Run[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [bottom, setBottom] = useState("Timeline"),
    [fov, setFov] = useState(localStorage.getItem("cns-fov") !== "false"),
    [overlay, setOverlay] = useState(false),
    [cameraFull, setCameraFull] = useState(false),
    [debugExpanded, setDebugExpanded] = useState(false),
    [smooth, setSmooth] = useState(
      localStorage.getItem("cns-smooth") === "true",
    );
  useEffect(() => {
    localStorage.setItem("cns-fov", String(fov));
    localStorage.setItem("cns-smooth", String(smooth));
  }, [fov, smooth]);
  const liveRef = useRef<Live | null>(null),
    runRef = useRef<string | null>(null),
    seekSeq = useRef(0),
    historyRef = useRef<Snapshot[]>([]),
    keys = useRef(new Set<string>());
  const frame = replay || live;
  const report = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));
  const loadRuns = () => api<Run[]>("runs").then(setRuns).catch(report);
  const loadHistory = async (id: string) => {
    const h = await api<Snapshot[]>(`runs/${id}/history`);
    if ((runRef.current || liveRef.current?.run_id) === id) {
      const merged = new Map(h.map((frame) => [frame.index, frame]));
      for (const frame of historyRef.current) {
        if (frame.run_id === id && !merged.has(frame.index))
          merged.set(frame.index, frame);
      }
      historyRef.current = [...merged.values()].sort(
        (a, b) => a.index - b.index,
      );
      setHistory(historyRef.current);
    }
    return h;
  };
  useEffect(() => {
    let disposed = false,
      socket: WebSocket,
      retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/stream`,
      );
      socket.onopen = () => setConnection("Connected");
      socket.onmessage = (e) => {
        const s: Live = JSON.parse(e.data),
          previous = liveRef.current;
        liveRef.current = s;
        setLive(s);
        if (!runRef.current) {
          if (
            previous?.run_id !== s.run_id ||
            s.index > (previous?.index ?? -1) + 1
          ) {
            loadHistory(s.run_id).catch(report);
          } else if (!historyRef.current.some((h) => h.index === s.index)) {
            historyRef.current = [...historyRef.current, s];
            setHistory(historyRef.current);
          }
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (!disposed) {
          setConnection("Reconnecting");
          retry = setTimeout(connect, 1500);
        }
      };
    };
    connect();
    return () => {
      disposed = true;
      clearTimeout(retry);
      socket?.close();
    };
  }, []);
  useEffect(() => {
    if (page === "Runs / Logs" || page === "Analysis") loadRuns();
  }, [page, live?.batch.status]);
  async function action(name: string, body: unknown = {}) {
    setBusy(true);
    setError("");
    try {
      const s = await api<Live>(name, body);
      liveRef.current = s;
      setLive(s);
      if (name === "reset" || name === "configure") {
        runRef.current = null;
        setReplayRun(null);
        setReplay(null);
        setPlaying(false);
        await loadHistory(s.run_id);
      }
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }
  async function seek(
    index: number,
    id = replayRun || liveRef.current?.run_id,
  ) {
    if (!id) return;
    const seq = ++seekSeq.current;
    try {
      const s = await api<Snapshot>(`runs/${id}/frames/${index}`);
      if (seq === seekSeq.current) {
        runRef.current = id;
        setReplayRun(id);
        setReplay(s);
      }
    } catch (e) {
      report(e);
    }
  }
  async function openRun(run: Run) {
    setPlaying(false);
    runRef.current = run.id;
    setReplayRun(run.id);
    try {
      await loadHistory(run.id);
      await seek(Math.max(0, run.frames - 1), run.id);
      setPage("Simulation");
    } catch (e) {
      report(e);
    }
  }
  async function returnLive() {
    ++seekSeq.current;
    setPlaying(false);
    runRef.current = null;
    setReplayRun(null);
    setReplay(null);
    if (liveRef.current)
      await loadHistory(liveRef.current.run_id).catch(report);
  }
  useEffect(() => {
    if (!playing || !replay) return;
    const t = setTimeout(() => {
      const next = history.find((h) => h.index > replay.index);
      if (next) seek(next.index);
      else setPlaying(false);
    }, 100 / playbackRate);
    return () => clearTimeout(t);
  }, [playing, replay, history, playbackRate]);
  useEffect(() => {
    const keydown = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,select,textarea")) return;
      const k = e.key.toLowerCase();
      if (
        liveRef.current?.manual &&
        !runRef.current &&
        ["w", "a", "s", "d", " "].includes(k)
      ) {
        e.preventDefault();
        keys.current.add(k);
      }
    };
    const keyup = (e: KeyboardEvent) =>
      keys.current.delete(e.key.toLowerCase());
    const clear = () => keys.current.clear();
    window.addEventListener("keydown", keydown);
    window.addEventListener("keyup", keyup);
    window.addEventListener("blur", clear);
    const interval = setInterval(() => {
      if (liveRef.current?.manual && !runRef.current) {
        const k = keys.current;
        api("command", {
          steering: Number(k.has("d")) - Number(k.has("a")),
          throttle: (Number(k.has("w")) - Number(k.has("s"))) * 0.4,
          brake: k.has(" ") || k.size === 0,
        }).catch(report);
      }
    }, 100);
    return () => {
      clearInterval(interval);
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("keyup", keyup);
      window.removeEventListener("blur", clear);
    };
  }, []);
  if (!live || !frame)
    return (
      <div className="loading">
        <BrainCircuit size={34} />
        <h1>MaleCNS Simulator</h1>
        <p>{connection} to the simulation service…</p>
        <p>{error}</p>
      </div>
    );
  const r = frame.result,
    status = replay
      ? "REPLAY"
      : live.finished
        ? r.status === "success"
          ? "FINISHED"
          : "STOPPED"
        : live.running
          ? "RUNNING"
          : live.phase === "paused"
            ? "PAUSED"
            : "READY";
  const seekSafe = (i: number) => {
    setPlaying(false);
    seek(i);
  };
  const recent = history.filter((h) => h.index <= frame.index).slice(-5);
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">
            <BrainCircuit size={20} />
          </span>
          <h1>MaleCNS Simulator</h1>
          <span className="version">v0.2</span>
        </div>
        <div className="experiment-name">
          <b>{frame.scenario.name}</b>
          <span>“{frame.scenario.task}”</span>
        </div>
        <div className="header-actions">
          <span className={"status " + status.toLowerCase()}>
            <i />
            {status}
            {status === "FINISHED" && <Check size={12} />}
          </span>
          <span className="time-badge">{fmt(frame.sim_time, 1)} s</span>
          <button disabled={busy || !!replay} onClick={() => action("reset")}>
            Reset
          </button>
          <button
            disabled={busy || !!replay || live.finished}
            onClick={() => action(live.running ? "pause" : "run")}
          >
            {live.running ? "Pause" : "Run"}
          </button>
          <button
            className="settings-button"
            onClick={() => setPage("Settings")}
          >
            <Settings size={13} />
            Settings
          </button>
        </div>
      </header>
      <nav className="navigation" aria-label="Main navigation">
        {tabs.map(([name, Icon]) => (
          <button
            key={name}
            className={page === name ? "active" : ""}
            onClick={() => setPage(name)}
          >
            <Icon size={14} />
            {name}
          </button>
        ))}
        <span className="nav-end">
          <i
            className={
              "dot " + (connection === "Connected" ? "green-dot" : "red")
            }
          />
          {connection}
        </span>
      </nav>
      {error && (
        <div role="alert" className="alert">
          <TriangleAlert size={16} />
          {error}
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={14} />
          </button>
        </div>
      )}
      {live.error && (
        <div role="alert" className="alert">
          {live.error}
        </div>
      )}
      {replay && (
        <div className="replay-banner">
          <Clock3 size={14} />
          <strong>Inspecting recorded frame {replay.index}</strong>
          <span>
            {fmt(replay.sim_time, 2)} s · {replay.run_id.slice(0, 8)}
            {live.running ? " · Live simulation continues" : ""}
          </span>
          <button onClick={returnLive}>
            <Radio size={13} />
            Return to live
          </button>
        </div>
      )}
      {page === "Simulation" ? (
        <main className="cockpit">
          <div className="primary-grid">
            <Panel
              title="Top-Down World (Ground Truth)"
              icon={Box}
              className="world-panel"
              aside={<span className="eyebrow">EVALUATOR ONLY</span>}
            >
              <World frame={frame} history={history} fov={fov} />
              <div className="panel-foot">
                <label>
                  <input
                    type="checkbox"
                    checked={fov}
                    onChange={(e) => setFov(e.target.checked)}
                  />
                  Camera FOV
                </label>
                <span>
                  <i className="dot green-dot" />
                  Success radius
                </span>
              </div>
            </Panel>
            <Panel
              title="Camera View (MaleCNS Input)"
              icon={Camera}
              className={
                cameraFull ? "camera-panel fullscreen" : "camera-panel"
              }
              aside={
                <button
                  className="icon-button"
                  aria-label={
                    cameraFull ? "Close expanded camera" : "Expand camera"
                  }
                  onClick={() => setCameraFull(!cameraFull)}
                >
                  {cameraFull ? <X size={13} /> : <Maximize2 size={13} />}
                </button>
              }
            >
              <div className="camera-stage">
                <img
                  style={{ imageRendering: smooth ? "auto" : "pixelated" }}
                  src={"data:image/png;base64," + frame.camera}
                  alt="Actual RGB camera frame supplied to controller"
                />
                {overlay && frame.debug.visible === true && (
                  <div className="detection-label">
                    Red target visible · controller report
                  </div>
                )}
                <div className="camera-stamp">
                  <i className="dot green-dot" /> FRONT RGB{" "}
                  <span>FRAME {frame.index.toString().padStart(4, "0")}</span>
                </div>
              </div>
              <div className="camera-toolbar">
                <span>
                  Camera: <b>Front</b>
                </span>
                <span>
                  FOV <b>{frame.sensor.fov}°</b>
                </span>
                <span>
                  <b>
                    {frame.sensor.width} × {frame.sensor.height}
                  </b>
                </span>
                <a
                  className="icon-button"
                  aria-label="Download camera frame"
                  download={`frame-${frame.index}.png`}
                  href={"data:image/png;base64," + frame.camera}
                >
                  <Camera size={14} />
                </a>
              </div>
              <div className="camera-history">
                <div className="mini-heading">
                  <span>
                    Camera stream <small>(recent frames)</small>
                  </span>
                  <span>{fmt(frame.sim_time, 2)} s · 10 Hz</span>
                </div>
                <div className="filmstrip">
                  <button
                    aria-label="Previous frame"
                    disabled={frame.index === 0}
                    onClick={() => seekSafe(frame.index - 1)}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  {recent.map((h) => (
                    <button
                      key={h.index}
                      className={h.index === frame.index ? "selected" : ""}
                      onClick={() => seekSafe(h.index)}
                      aria-label={`Inspect frame ${h.index}`}
                    >
                      <FrameThumb frame={h} />
                      <span>{fmt(h.sim_time, 1)}s</span>
                    </button>
                  ))}
                  {Array.from(
                    { length: Math.max(0, 5 - recent.length) },
                    (_, i) => (
                      <div className="empty-frame" key={i}>
                        <Camera size={16} />
                      </div>
                    ),
                  )}
                </div>
              </div>
              <div className="panel-foot">
                <label>
                  <input
                    type="checkbox"
                    checked={overlay}
                    onChange={(e) => setOverlay(e.target.checked)}
                  />
                  Controller annotations
                </label>
                <span>Raw sensor pixels</span>
              </div>
            </Panel>
            <div className="right-stack">
              <Panel
                title="Task & Status"
                icon={Crosshair}
                className="task-panel"
              >
                <div
                  className={
                    "task-result " +
                    (r.status === "success"
                      ? "success"
                      : r.status === "failed"
                        ? "failed"
                        : "")
                  }
                >
                  <span className="task-symbol">
                    {r.status === "success" ? (
                      <Check size={26} />
                    ) : r.status === "failed" ? (
                      <Square size={19} />
                    ) : (
                      <Focus size={26} />
                    )}
                  </span>
                  <div>
                    <h3>
                      {r.status === "success"
                        ? "Task Completed"
                        : r.status === "failed"
                          ? "Run Stopped"
                          : live.running && !replay
                            ? "Finding the red ball"
                            : replay
                              ? "Recorded observation"
                              : live.phase === "paused"
                                ? "Simulation Paused"
                                : "Ready to Explore"}
                    </h3>
                    <p>
                      {r.reason
                        ? title(r.reason)
                        : "Find the red ball and stop nearby"}
                    </p>
                  </div>
                </div>
                <div className="task-timing">
                  <Row
                    label="Simulated time"
                    value={`${fmt(frame.sim_time, 1)} s`}
                  />
                  <Row
                    label="Compute time (active)"
                    value={`${fmt(frame.wall_elapsed, 1)} s`}
                  />
                  <Row
                    label="Status"
                    value={
                      r.status === "running"
                        ? replay
                          ? "recorded"
                          : live.phase
                        : r.status
                    }
                    good={r.status === "success"}
                  />
                </div>
                <div
                  className={
                    "task-progress " +
                    (r.status === "success" ? "complete" : "")
                  }
                >
                  <i
                    style={{
                      width:
                        r.status === "success"
                          ? "100%"
                          : `${Math.min(95, (frame.sim_time / frame.scenario.timeout) * 100)}%`,
                    }}
                  />
                </div>
                <div className="target-summary">
                  <span className="target-icon">
                    <Crosshair size={15} />
                  </span>
                  <div>
                    <Row label="Target" value="Red ball" />
                    <Row
                      label="Ground-truth distance"
                      value={`${fmt(r.final_target_distance)} m`}
                    />
                    <Row
                      label="Success threshold"
                      value={`≤ ${fmt(frame.scenario.success_distance)} m`}
                    />
                    <Row
                      label="Stopped hold"
                      value={`${frame.scenario.stop_duration} s at ≤ ${frame.scenario.stop_speed} m/s`}
                    />
                  </div>
                </div>
              </Panel>
              <Panel
                title="Controls"
                icon={SlidersHorizontal}
                className="controls-panel"
              >
                <div className="run-controls">
                  <Button
                    icon={Play}
                    primary
                    disabled={busy || !!replay || live.running || live.finished}
                    onClick={() => action("run")}
                  >
                    Run
                  </Button>
                  <Button
                    icon={Pause}
                    disabled={busy || !!replay || !live.running}
                    onClick={() => action("pause")}
                  >
                    Pause
                  </Button>
                  <Button
                    icon={Square}
                    danger
                    disabled={busy || live.finished}
                    onClick={() => action("stop")}
                  >
                    Stop
                  </Button>
                  <Button
                    icon={RotateCcw}
                    disabled={busy || !!replay}
                    onClick={() => action("reset")}
                  >
                    Reset
                  </Button>
                </div>
                <div className="speed-control">
                  <label htmlFor="sim-speed">
                    Simulation speed{" "}
                    <span>
                      {live.speed_multiplier.toFixed(2).replace(/0$/, "")} ×
                    </span>
                  </label>
                  <input
                    id="sim-speed"
                    type="range"
                    min="0"
                    max="4"
                    step="1"
                    value={[0.25, 0.5, 1, 2, 4].indexOf(live.speed_multiplier)}
                    disabled={!!replay}
                    onChange={(e) =>
                      action("speed", {
                        value: [0.25, 0.5, 1, 2, 4][+e.target.value],
                      })
                    }
                  />
                </div>
                <label className="manual-toggle">
                  <input
                    type="checkbox"
                    checked={live.manual}
                    disabled={!!replay}
                    onChange={(e) =>
                      action("manual", { enabled: e.target.checked })
                    }
                  />
                  Manual keyboard control <kbd>W A S D</kbd>
                </label>
                <div className="controls-note">
                  {live.manual
                    ? "Hold W/S to drive · A/D steer · Space brakes"
                    : "Camera-only control · fixed 100 Hz physics"}
                </div>
              </Panel>
            </div>
          </div>
          <div className="telemetry-grid">
            <Panel title="Vehicle State" icon={Car}>
              <div className="vehicle-card">
                <div>
                  <Row
                    label="Position (x, y)"
                    value={`${fmt(frame.vehicle.x)}, ${fmt(frame.vehicle.y)} m`}
                  />
                  <Row
                    label="Heading"
                    value={`${fmt((frame.vehicle.heading * 180) / Math.PI, 1)}°`}
                  />
                  <Row
                    label="Speed"
                    value={`${fmt(frame.vehicle.speed)} m/s`}
                  />
                  <Row
                    label="Steering"
                    value={`${fmt((frame.vehicle.steering * 180) / Math.PI, 1)}°`}
                  />
                  <Row
                    label="Collision"
                    value={r.collisions ? "Yes" : "No"}
                    good={!r.collisions}
                  />
                </div>
                <VehicleDrawing steering={frame.vehicle.steering} />
              </div>
            </Panel>
            <Panel title="MaleCNS Output (Control)" icon={BrainCircuit}>
              <GaugeBar
                label="Steering command"
                value={frame.command.steering}
                left="Left"
                right="Right"
              />
              <GaugeBar
                label="Throttle command"
                value={frame.command.throttle}
                left="Reverse"
                right="Forward"
              />
              <div className="control-state">
                <span className="mode-tag">
                  {String(frame.debug.mode || "NO DECISION")}
                </span>
                <span>Brake: {frame.command.brake ? "ON" : "off"}</span>
                <button
                  className="text-button"
                  onClick={() => setDebugExpanded(!debugExpanded)}
                >
                  {debugExpanded ? "Hide" : "Inspect"} loop
                </button>
              </div>
            </Panel>
            <Panel title="Metrics" icon={ChartNoAxesCombined}>
              <div className="metrics-list">
                <Row
                  label="Distance travelled"
                  value={`${fmt(r.distance)} m`}
                />
                <Row
                  label="Elapsed simulation"
                  value={`${fmt(frame.sim_time)} s`}
                />
                <Row
                  label="Collisions / reversals"
                  value={`${r.collisions} / ${r.reversals}`}
                />
                <Row
                  label="Avg. / max. speed"
                  value={`${fmt(r.average_speed)} / ${fmt(r.maximum_speed)} m/s`}
                />
                <Row
                  label="Steering variation"
                  value={`${fmt(r.steering_variation)} rad`}
                />
                <Row label="Decisions made" value={r.decisions} />
                <Row
                  label="Mean inference"
                  value={`${fmt(frame.performance.avg_inference_ms)} ms`}
                />
              </div>
            </Panel>
            <Panel title="Environment" icon={Layers3}>
              <div className="environment-info">
                <div className="arena-mini">
                  <span className="ball" />
                  <span className="mini-car" />
                </div>
                <div>
                  <Row
                    label="Map"
                    value={
                      frame.scenario.obstacles.length
                        ? "Obstacles"
                        : "Simple arena"
                    }
                  />
                  <Row
                    label="Size"
                    value={`${frame.scenario.size.join(" × ")} m`}
                  />
                  <Row
                    label="Obstacles"
                    value={frame.scenario.obstacles.length}
                  />
                  <Row label="Target" value="Red ball" />
                  <Row label="Physics" value="Bicycle model" />
                </div>
              </div>
              <button
                className="wide-button"
                onClick={() => setPage("Environment")}
              >
                <SlidersHorizontal size={13} />
                Edit Environment
              </button>
            </Panel>
          </div>
          {debugExpanded && (
            <Panel
              title="Camera → Perception → Decision → Control → Vehicle"
              icon={GitBranch}
            >
              <div className="decision-loop">
                <span>
                  <Camera />
                  Frame {frame.index}
                  <small>{fmt(frame.sim_time, 2)} s</small>
                </span>
                <b>→</b>
                <span>
                  <Focus />
                  Target{" "}
                  {frame.debug.visible === undefined
                    ? "unknown"
                    : frame.debug.visible
                      ? "visible"
                      : "not visible"}
                  <small>Confidence: {fmt(frame.debug.confidence)}</small>
                </span>
                <b>→</b>
                <span>
                  <BrainCircuit />
                  {String(frame.debug.mode || "No decision")}
                  <small>{frame.controller}</small>
                </span>
                <b>→</b>
                <span>
                  <Gauge />
                  Steer {fmt(frame.command.steering)}
                  <small>Throttle {fmt(frame.command.throttle)}</small>
                </span>
                <b>→</b>
                <span>
                  <Car />
                  {fmt(frame.vehicle.speed)} m/s
                  <small>Measured at capture</small>
                </span>
              </div>
            </Panel>
          )}
          <section className="panel debugger">
            <div className="debugger-tabs" role="tablist">
              {[
                ["Timeline", Activity],
                ["Console Log", Terminal],
                ["Events", Flag],
                ["Model I/O", BrainCircuit],
                ["Performance", Gauge],
              ].map(([label, Icon]) => {
                const I = Icon as LucideIcon;
                return (
                  <button
                    key={String(label)}
                    role="tab"
                    aria-selected={bottom === label}
                    className={bottom === label ? "active" : ""}
                    onClick={() => setBottom(String(label))}
                  >
                    <I size={13} />
                    {String(label)}
                    {label === "Events" && (
                      <span className="count">{frame.events.length}</span>
                    )}
                  </button>
                );
              })}
              <span className="debugger-extra">
                {history.length} recorded frames
              </span>
            </div>
            {bottom === "Timeline" ? (
              <>
                <div className="timeline-layout">
                  <Chart history={history} frame={frame} onSeek={seekSafe} />
                  <div className="key-events">
                    <h3>Key Events</h3>
                    {frame.events.slice(-5).map((e, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          const h = history.find((h) => h.sim_time >= e.time);
                          if (h) seekSafe(h.index);
                        }}
                      >
                        <i
                          className={
                            "dot " +
                            (e.type === "SUCCESS" ? "green-dot" : "blue")
                          }
                        />
                        <span>{e.message}</span>
                        <time>t = {fmt(e.time, 2)} s</time>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="scrubber">
                  <button
                    aria-label={playing ? "Pause replay" : "Play replay"}
                    onClick={() => {
                      if (!replay) {
                        seek(0).then(() => setPlaying(true));
                      } else setPlaying(!playing);
                    }}
                  >
                    {playing ? <Pause size={13} /> : <Play size={13} />}
                  </button>
                  <input
                    aria-label="Replay timeline"
                    type="range"
                    min="0"
                    max={Math.max(0, ...history.map((h) => h.index))}
                    value={frame.index}
                    onChange={(e) => seekSafe(+e.target.value)}
                  />
                  <select
                    aria-label="Replay speed"
                    value={playbackRate}
                    onChange={(e) => setPlaybackRate(+e.target.value)}
                  >
                    {[0.25, 0.5, 1, 2, 4].map((rate) => (
                      <option key={rate} value={rate}>
                        {rate}× replay
                      </option>
                    ))}
                  </select>
                  <span>{fmt(frame.sim_time, 2)} s</span>
                  <button
                    className="icon-button"
                    aria-label="Next frame"
                    disabled={
                      frame.index >= Math.max(0, ...history.map((h) => h.index))
                    }
                    onClick={() => seekSafe(frame.index + 1)}
                  >
                    <ChevronRight size={15} />
                  </button>
                </div>
              </>
            ) : bottom === "Model I/O" ? (
              <pre className="debug-content">
                {JSON.stringify(
                  frame.decision || {
                    frame: frame.index,
                    timestamp: frame.sim_time,
                    note: "No controller decision at this state (initial or terminal snapshot).",
                  },
                  null,
                  2,
                )}
              </pre>
            ) : bottom === "Performance" ? (
              <div className="performance-grid">
                <Row label="Physics" value="100 Hz (fixed)" />
                <Row label="Sensor / controller" value="10 Hz (simulated)" />
                <Row
                  label="Last inference"
                  value={`${fmt(frame.performance.last_inference_ms)} ms`}
                />
                <Row
                  label="Mean inference"
                  value={`${fmt(frame.performance.avg_inference_ms)} ms`}
                />
                <Row
                  label="P95 inference"
                  value={`${fmt(frame.performance.p95_inference_ms)} ms`}
                />
                <p>
                  Synchronous inference. Simulation speed is a pacing target;
                  compute can make it slower.
                </p>
              </div>
            ) : (
              <div className="event-log">
                {frame.events.map((e, i) => (
                  <div key={i}>
                    <time>{fmt(e.time, 3)} s</time>
                    <span className="mode-tag">{e.type}</span>
                    <span>{e.message}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>
      ) : page === "Runs / Logs" ? (
        <RunsPage runs={runs} refresh={loadRuns} open={openRun} />
      ) : page === "Analysis" ? (
        <AnalysisPage
          runs={runs}
          live={live}
          refresh={loadRuns}
          open={openRun}
          report={report}
        />
      ) : page === "Settings" ? (
        <div className="page-content">
          <div className="page-title">
            <h2>Workbench settings</h2>
            <p>Presentation and local service details.</p>
          </div>
          <Panel title="Display" icon={Settings}>
            <label className="setting-row">
              <span>
                Smooth camera enlargement
                <small>
                  Presentation only; controller input remains unchanged.
                </small>
              </span>
              <input
                type="checkbox"
                checked={smooth}
                onChange={(e) => setSmooth(e.target.checked)}
              />
            </label>
            <label className="setting-row">
              <span>Show camera field of view</span>
              <input
                type="checkbox"
                checked={fov}
                onChange={(e) => setFov(e.target.checked)}
              />
            </label>
          </Panel>
          <Panel title="Recording & runtime" icon={ShieldCheck}>
            <Row label="Artifact storage" value="runs/workbench/" />
            <Row label="Run index" value="SQLite" />
            <Row label="Recorder" value="Automatic · JSONL + PNG" />
            <Row label="Connection" value={connection} />
            <p className="muted">
              Stop ends the current experiment. Reset preserves its recording
              and creates a new run. All vehicle and target measurements in the
              world view are evaluator ground truth.
            </p>
          </Panel>
        </div>
      ) : (
        <ConfigPage
          key={page + live.run_id}
          page={page}
          config={live.config}
          busy={busy}
          apply={(c) => action("configure", c)}
          report={report}
        />
      )}
      <footer className="statusbar">
        <span>
          <i
            className={
              "dot " + (connection === "Connected" ? "green-dot" : "red")
            }
          />
          {replay
            ? "Replay inspection"
            : live.running
              ? "Simulation running"
              : "Ready"}
        </span>
        <span>
          <ShieldCheck size={11} />
          Camera-only controller boundary
        </span>
        <span className="footer-right">
          Physics: 100 Hz <b>│</b> Sensor: 10 Hz <b>│</b> {frame.controller}{" "}
          <b>│</b> Sim time: {fmt(frame.sim_time, 1)} s
        </span>
      </footer>
    </div>
  );
}

function FrameThumb({ frame }: { frame: Snapshot }) {
  const [src, setSrc] = useState(frame.camera);
  useEffect(() => {
    let active = true;
    if (!frame.camera)
      api<Snapshot>(`runs/${frame.run_id}/frames/${frame.index}`)
        .then((s) => active && setSrc(s.camera))
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [frame.run_id, frame.index]);
  return src ? (
    <img
      src={"data:image/png;base64," + src}
      alt={`Camera at ${fmt(frame.sim_time, 1)} seconds`}
    />
  ) : (
    <Camera size={16} />
  );
}

createRoot(document.getElementById("root")!).render(<App />);
