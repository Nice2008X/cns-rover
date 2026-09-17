import React from "react";
import type { LucideIcon } from "lucide-react";
import { fmt } from "./types";
export function Panel({
  title: label,
  icon: Icon,
  children,
  className = "",
  aside,
}: {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
  className?: string;
  aside?: React.ReactNode;
}) {
  return (
    <section className={"panel " + className}>
      <div className="panel-heading">
        <h2>
          <Icon size={14} />
          {label}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
export function Row({
  label,
  value,
  good = false,
}: {
  label: string;
  value: React.ReactNode;
  good?: boolean;
}) {
  return (
    <div className="data-row">
      <span>{label}</span>
      <strong className={good ? "green" : ""}>{value}</strong>
    </div>
  );
}
export function Button({
  icon: Icon,
  children,
  onClick,
  disabled = false,
  primary = false,
  danger = false,
}: {
  icon: LucideIcon;
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={(primary ? "primary " : "") + (danger ? "danger" : "")}
    >
      <Icon size={14} />
      {children}
    </button>
  );
}
export function GaugeBar({
  value,
  label,
  left,
  right,
}: {
  value: number;
  label: string;
  left: string;
  right: string;
}) {
  return (
    <div className="gauge">
      <Row label={label} value={fmt(value)} />
      <div className="gauge-track">
        <i style={{ left: `${50 + value * 50}%` }} />
        <b />
      </div>
      <div className="gauge-labels">
        <span>{left}</span>
        <span>0</span>
        <span>{right}</span>
      </div>
    </div>
  );
}
