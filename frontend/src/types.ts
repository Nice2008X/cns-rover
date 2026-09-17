export type Scenario = {
  name: string;
  task: string;
  size: number[];
  start: number[];
  target: number[];
  obstacles: number[][];
  timeout: number;
  success_distance: number;
  stop_speed: number;
  stop_duration: number;
};
export type Config = {
  scenario: Scenario;
  sensor: { width: number; height: number; fov: number };
  vehicle: { wheelbase: number; max_steering_degrees: number };
  controller: string;
};
export type Vehicle = {
  x: number;
  y: number;
  heading: number;
  speed: number;
  steering: number;
};
export type Result = {
  status: string;
  reason: string | null;
  time: number;
  distance: number;
  collisions: number;
  decisions: number;
  reversals: number;
  maximum_speed: number;
  average_speed: number;
  steering_variation: number;
  final_target_distance: number;
};
export type Run = {
  id: string;
  name: string;
  controller: string;
  created: number;
  seed: number | null;
  frames: number;
  finished: boolean;
  result: Result;
};
export type Snapshot = {
  version: number;
  run_id: string;
  index: number;
  sim_time: number;
  vehicle: Vehicle;
  scenario: Scenario;
  result: Result;
  command: { steering: number; throttle: number; brake: boolean };
  debug: Record<string, unknown>;
  decision: Record<string, unknown> | null;
  events: { type: string; message: string; time: number }[];
  sensor: Config["sensor"];
  vehicle_config: Config["vehicle"];
  controller: string;
  camera?: string;
  wall_elapsed: number;
  performance: {
    last_inference_ms: number | null;
    avg_inference_ms: number | null;
    p95_inference_ms: number | null;
  };
};
export type Live = Snapshot & {
  running: boolean;
  phase: string;
  manual: boolean;
  speed_multiplier: number;
  error: string | null;
  frame_count: number;
  finished: boolean;
  config: Config;
  batch: {
    status: string;
    completed: number;
    total: number;
    runs: Run[];
    error?: string;
  };
};
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(
    "/api/" + path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!r.ok) {
    const e = await r.json();
    throw Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return r.json();
}
export const fmt = (n: unknown, d = 2) =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(d) : "—";
export const title = (s: string) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
