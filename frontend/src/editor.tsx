import { useRef, useState } from "react";
import { Car, Circle, Plus, Trash2 } from "lucide-react";
import type { Scenario } from "./types";

export function EnvironmentEditor({
  scenario,
  onChange,
}: {
  scenario: Scenario;
  onChange: (s: Scenario) => void;
}) {
  const [selected, setSelected] = useState("target");
  const svg = useRef<SVGSVGElement>(null),
    drag = useRef(false);
  const safe =
    scenario.size.every((n) => Number.isFinite(n) && n >= 2) &&
    [...scenario.start, ...scenario.target].every(Number.isFinite);
  if (!safe)
    return (
      <p className="form-note">
        Enter valid arena dimensions and coordinates to preview objects.
      </p>
    );
  const scale = 360 / Math.max(...scenario.size),
    [w, h] = scenario.size;
  const move = (e: React.PointerEvent) => {
    if (!drag.current || !svg.current) return;
    const matrix = svg.current.getScreenCTM();
    if (!matrix) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
      matrix.inverse(),
    );
    const x =
        Math.round(
          Math.max(0.25, Math.min(w - 0.25, (p.x - 20) / scale)) * 100,
        ) / 100,
      y =
        Math.round(
          Math.max(0.25, Math.min(h - 0.25, (p.y - 20) / scale)) * 100,
        ) / 100;
    if (selected === "vehicle")
      onChange({ ...scenario, start: [x, y, scenario.start[2]] });
    else if (selected === "target")
      onChange({ ...scenario, target: [x, y, scenario.target[2]] });
    else
      onChange({
        ...scenario,
        obstacles: scenario.obstacles.map((o, i) =>
          selected === `obstacle-${i}` ? [x, y, o[2]] : o,
        ),
      });
  };
  const select = (name: string) => (e: React.PointerEvent) => {
    e.stopPropagation();
    setSelected(name);
    drag.current = true;
    svg.current?.setPointerCapture(e.pointerId);
  };
  return (
    <div className="environment-editor">
      <div className="object-list">
        <h3>Objects</h3>
        <button
          type="button"
          className={selected === "vehicle" ? "selected" : ""}
          onClick={() => setSelected("vehicle")}
        >
          <Car size={14} />
          Vehicle
        </button>
        <button
          type="button"
          className={selected === "target" ? "selected" : ""}
          onClick={() => setSelected("target")}
        >
          <Circle size={13} color="#ff6070" />
          Red ball
        </button>
        {scenario.obstacles.map((_, i) => (
          <button
            type="button"
            key={i}
            className={selected === `obstacle-${i}` ? "selected" : ""}
            onClick={() => setSelected(`obstacle-${i}`)}
          >
            <Circle size={13} color="#c4a768" />
            Obstacle {i + 1}
          </button>
        ))}
        <button
          type="button"
          onClick={() => {
            onChange({
              ...scenario,
              obstacles: [...scenario.obstacles, [w / 2, h / 2, 0.3]],
            });
            setSelected(`obstacle-${scenario.obstacles.length}`);
          }}
        >
          <Plus size={13} />
          Add obstacle
        </button>
        {selected.startsWith("obstacle-") && (
          <button
            type="button"
            className="danger"
            onClick={() => {
              onChange({
                ...scenario,
                obstacles: scenario.obstacles.filter(
                  (_, i) => selected !== `obstacle-${i}`,
                ),
              });
              setSelected("target");
            }}
          >
            <Trash2 size={13} />
            Remove selected
          </button>
        )}
        <p>
          Drag an object in the arena to move it. Overlaps are checked when you
          apply.
        </p>
      </div>
      <svg
        ref={svg}
        viewBox="0 0 400 400"
        aria-label="Environment editor: drag vehicle, target, or obstacles"
        onPointerMove={move}
        onPointerUp={() => (drag.current = false)}
        onPointerCancel={() => (drag.current = false)}
      >
        <defs>
          <pattern
            id="editor-grid"
            width={scale}
            height={scale}
            patternUnits="userSpaceOnUse"
            x="20"
            y="20"
          >
            <path
              d={`M${scale} 0 H0 V${scale}`}
              stroke="#334259"
              fill="none"
              strokeWidth=".7"
            />
          </pattern>
        </defs>
        <rect
          x="20"
          y="20"
          width={w * scale}
          height={h * scale}
          fill="url(#editor-grid)"
          stroke="#465971"
        />
        <circle
          onPointerDown={select("target")}
          cx={20 + scenario.target[0] * scale}
          cy={20 + scenario.target[1] * scale}
          r={Math.max(7, scenario.target[2] * scale)}
          fill="#ec4e61"
          stroke={selected === "target" ? "white" : "#ff9aa5"}
          strokeWidth={selected === "target" ? 2 : 1}
        />
        {scenario.obstacles.map((o, i) => (
          <circle
            key={i}
            onPointerDown={select(`obstacle-${i}`)}
            cx={20 + o[0] * scale}
            cy={20 + o[1] * scale}
            r={Math.max(6, o[2] * scale)}
            fill="#a18a54"
            stroke={selected === `obstacle-${i}` ? "white" : "#dac896"}
            strokeWidth={selected === `obstacle-${i}` ? 2 : 1}
          />
        ))}
        <g
          onPointerDown={select("vehicle")}
          transform={`translate(${20 + scenario.start[0] * scale} ${20 + scenario.start[1] * scale}) rotate(${scenario.start[2]})`}
        >
          <path
            d="M-7 -6 L10 0 L-7 6 Z"
            fill="#489df8"
            stroke={selected === "vehicle" ? "white" : "#80b7f4"}
            strokeWidth={selected === "vehicle" ? 2 : 1}
          />
          <circle r="13" fill="transparent" />
        </g>
      </svg>
    </div>
  );
}
