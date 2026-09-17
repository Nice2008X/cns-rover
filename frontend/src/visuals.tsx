import { useState } from "react";
import { Crosshair, Maximize2, X } from "lucide-react";
import type { Snapshot } from "./types";
import { fmt } from "./types";

export function World({
  frame,
  history,
  fov = true,
}: {
  frame: Snapshot;
  history: Snapshot[];
  fov?: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null),
    [full, setFull] = useState(false);
  const { scenario: s, vehicle: v } = frame;
  const scale = 440 / Math.max(...s.size),
    ox = 30 + (440 - s.size[0] * scale) / 2,
    oy = 26 + (440 - s.size[1] * scale) / 2;
  const Xp = (x: number) => ox + x * scale,
    Yp = (y: number) => oy + y * scale;
  const a = (v.heading * 180) / Math.PI;
  const trail = history
    .filter((h) => h.sim_time <= frame.sim_time)
    .map((h) => `${Xp(h.vehicle.x)},${Yp(h.vehicle.y)}`)
    .join(" ");
  const half = (frame.sensor.fov * Math.PI) / 360,
    len = 2.3 * scale;
  const click = (name: string) => () =>
    setSelected(selected === name ? null : name);
  return (
    <div className={full ? "world-container fullscreen" : "world-container"}>
      <div className="world-tools">
        <span>
          <i className="dot red" />
          Target (red ball)
          <br />
          <i className="dot blue" />
          Vehicle (you)
          <br />
          <i className="trail-key" />
          Path travelled
        </span>
        <span>
          Grid: 1 m<br />
          World: {s.size.join(" × ")} m
          <button
            className="icon-button"
            aria-label={full ? "Exit expanded world" : "Expand world"}
            onClick={() => setFull(!full)}
          >
            {full ? <X size={13} /> : <Maximize2 size={13} />}
          </button>
        </span>
      </div>
      <svg
        viewBox="0 0 500 500"
        className="world-svg"
        aria-label="Top-down world, evaluator ground truth"
      >
        <defs>
          <pattern
            id="small-grid"
            width={scale / 5}
            height={scale / 5}
            patternUnits="userSpaceOnUse"
            x={ox}
            y={oy}
          >
            <path
              d={`M ${scale / 5} 0 L 0 0 0 ${scale / 5}`}
              fill="none"
              stroke="#1c2a39"
              strokeWidth=".45"
            />
          </pattern>
          <pattern
            id="grid"
            width={scale}
            height={scale}
            patternUnits="userSpaceOnUse"
            x={ox}
            y={oy}
          >
            <rect width={scale} height={scale} fill="url(#small-grid)" />
            <path
              d={`M ${scale} 0 L 0 0 0 ${scale}`}
              fill="none"
              stroke="#354355"
              strokeWidth=".65"
            />
          </pattern>
        </defs>
        <rect
          x={ox}
          y={oy}
          width={s.size[0] * scale}
          height={s.size[1] * scale}
          fill="url(#grid)"
          stroke="#465368"
        />
        <circle
          cx={Xp(s.target[0])}
          cy={Yp(s.target[1])}
          r={s.success_distance * scale}
          fill="#45d7830b"
          stroke="#45d78370"
          strokeDasharray="3 4"
        />
        <polyline
          points={trail}
          fill="none"
          stroke="#99a9bf"
          strokeWidth="1.5"
          strokeDasharray="5 4"
        />
        {s.obstacles.map((o, i) => (
          <g
            key={i}
            onClick={click(
              `Obstacle ${i + 1}: (${fmt(o[0])}, ${fmt(o[1])}) m, radius ${fmt(o[2])} m`,
            )}
          >
            <circle
              cx={Xp(o[0])}
              cy={Yp(o[1])}
              r={o[2] * scale}
              fill="#a68c59"
              stroke="#e0be7a"
            />
            <circle
              cx={Xp(o[0])}
              cy={Yp(o[1])}
              r={Math.max(12, o[2] * scale)}
              fill="transparent"
            />
          </g>
        ))}
        <g
          role="button"
          tabIndex={0}
          aria-label="Inspect target"
          onClick={click(
            `Target: (${fmt(s.target[0])}, ${fmt(s.target[1])}) m`,
          )}
          onKeyDown={(e) => e.key === "Enter" && click("Target red ball")()}
        >
          <circle
            cx={Xp(s.target[0])}
            cy={Yp(s.target[1])}
            r={Math.max(6, s.target[2] * scale)}
            fill="#ff4b62"
            stroke="#ff7d87"
          />
          <circle
            cx={Xp(s.target[0])}
            cy={Yp(s.target[1])}
            r="14"
            fill="transparent"
          />
        </g>
        <g transform={`translate(${Xp(v.x)} ${Yp(v.y)}) rotate(${a})`}>
          {fov && (
            <path
              d={`M 0 0 L ${len * Math.cos(half)} ${-len * Math.sin(half)} A ${len} ${len} 0 0 1 ${len * Math.cos(half)} ${len * Math.sin(half)} Z`}
              fill="#438ffa12"
              stroke="#438ffa50"
              strokeWidth=".8"
            />
          )}
          <g
            role="button"
            tabIndex={0}
            aria-label="Inspect vehicle"
            onClick={click(
              `Vehicle: (${fmt(v.x)}, ${fmt(v.y)}) m · heading ${fmt(a, 1)}°`,
            )}
          >
            <rect
              x="-7"
              y="-5"
              width="14"
              height="10"
              rx="2"
              fill="#2689fa"
              stroke="#88c4ff"
            />
            <path d="M 4 -4 L 12 0 L 4 4" fill="#8cccff" />
            <circle r="15" fill="transparent" />
          </g>
        </g>
        <path d={`M ${ox} 481 h ${scale * 2}`} stroke="#8390a4" />
        <text x={ox} y="494" fill="#8c9bb0" fontSize="9">
          0
        </text>
        <text x={ox + scale * 2} y="494" fill="#8c9bb0" fontSize="9">
          2 m
        </text>
      </svg>
      {selected && (
        <div className="world-inspector">
          <Crosshair size={12} />
          {selected}
          <button
            className="icon-button"
            aria-label="Close inspection"
            onClick={() => setSelected(null)}
          >
            <X size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

export function VehicleDrawing({ steering = 0 }: { steering?: number }) {
  return (
    <svg
      viewBox="0 0 90 110"
      className="vehicle-drawing"
      aria-label="Vehicle steering diagram"
    >
      <defs>
        <marker
          id="arrow"
          markerWidth="5"
          markerHeight="5"
          refX="3"
          refY="2.5"
          orient="auto"
        >
          <path d="M0 0 L5 2.5 L0 5" fill="#42cc8d" />
        </marker>
      </defs>
      <g transform="translate(45 55) rotate(12)">
        <path d="M0 32 V-44" stroke="#42cc8d" markerEnd="url(#arrow)" />
        <path d="M-28 0 H33" stroke="#c95570" />
        <rect
          x="-16"
          y="-26"
          width="32"
          height="57"
          rx="6"
          fill="#152f48"
          stroke="#5a9ddd"
        />
        <path d="M-12 -13 H12 M-12 18 H12" stroke="#71c8ee" />
        {[-21, 15].map((x) =>
          [-23, 21].map((y) => (
            <rect
              key={`${x},${y}`}
              x={x}
              y={y}
              width="6"
              height="14"
              rx="1"
              fill="#101b2c"
              stroke="#72b3ef"
              transform={
                y < 0
                  ? `rotate(${(steering * 180) / Math.PI} ${x + 3} ${y + 7})`
                  : undefined
              }
            />
          )),
        )}
        <circle r="3" fill="#78cbff" />
      </g>
    </svg>
  );
}

export function Chart({
  history,
  frame,
  onSeek,
}: {
  history: Snapshot[];
  frame: Snapshot;
  onSeek: (index: number) => void;
}) {
  const end = Math.max(0.1, ...history.map((h) => h.sim_time)),
    x = (t: number) => 42 + (t / end) * 680;
  const maxDistance = Math.max(
    1,
    ...history.map((h) => h.result.final_target_distance),
  );
  const series = [
    {
      name: "Speed (m/s)",
      color: "#4fa8ff",
      value: (h: Snapshot) => h.vehicle.speed / 1.5,
    },
    {
      name: "Steering (normalized)",
      color: "#edc15b",
      value: (h: Snapshot) => h.command.steering,
    },
    {
      name: `Distance (0–${fmt(maxDistance, 1)} m)`,
      color: "#57cf89",
      value: (h: Snapshot) => h.result.final_target_distance / maxDistance,
    },
  ];
  return (
    <div className="chart">
      <svg
        viewBox="0 0 750 155"
        role="img"
        aria-label="Synchronized speed, steering, and distance timeline"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const t =
            ((((e.clientX - rect.left) / rect.width) * 750 - 42) / 680) * end;
          const closest = history.reduce(
            (a, b) =>
              Math.abs(b.sim_time - t) < Math.abs(a.sim_time - t) ? b : a,
            history[0],
          );
          if (closest) onSeek(closest.index);
        }}
      >
        {[-1, -0.5, 0, 0.5, 1].map((y) => (
          <g key={y}>
            <path
              d={`M42 ${67 - y * 45} H722`}
              stroke="#283548"
              strokeDasharray="2 3"
            />
            <text x="11" y={71 - y * 45} fill="#7f8fa6" fontSize="10">
              {y.toFixed(1)}
            </text>
          </g>
        ))}
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <g key={i}>
            <path d={`M${42 + i * 136} 20 V115`} stroke="#233043" />
            <text x={38 + i * 136} y="135" fill="#7f8fa6" fontSize="10">
              {fmt((i * end) / 5, 1)}
            </text>
          </g>
        ))}
        {series.map((s) => (
          <polyline
            key={s.name}
            points={history
              .map((h) => `${x(h.sim_time)},${67 - s.value(h) * 45}`)
              .join(" ")}
            fill="none"
            stroke={s.color}
            strokeWidth="1.5"
          />
        ))}
        <line
          x1={x(frame.sim_time)}
          x2={x(frame.sim_time)}
          y1="13"
          y2="117"
          stroke="#c1d1e7"
          strokeDasharray="3 3"
        />
        <text
          x={Math.min(670, x(frame.sim_time) + 5)}
          y="15"
          fontSize="10"
          fill="#dbe8fa"
        >
          {fmt(frame.sim_time, 1)} s
        </text>
        <text x="345" y="152" fontSize="9" fill="#8997ab">
          SIMULATION TIME (s)
        </text>
      </svg>
      <div className="chart-legend">
        {series.map((s) => (
          <span key={s.name}>
            <i style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}
