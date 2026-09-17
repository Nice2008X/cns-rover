import argparse
import json
from pathlib import Path
from .scenario import Scenario, randomized
from .controllers import load_controller
from .runner import run, replay


def main():
    parser = argparse.ArgumentParser(description="CNS car simulation and connectome experiments")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("run", "serve", "benchmark"):
        p = sub.add_parser(name)
        p.add_argument("--controller", default="baseline", help="baseline, malecns, malecns-ablated, connectome, ablated, or module:Class")
        p.add_argument("--model", default=None, help="Model file for connectome; circuit directory for malecns")
        if name != "benchmark":
            p.add_argument("--scenario", help="Scenario JSON; omitted uses visible-ball default")
        if name == "run":
            p.add_argument("--output")
            p.add_argument("--frames", action="store_true")
        elif name == "serve":
            p.add_argument("--port", type=int, default=8765)
        else:
            p.add_argument("--count", type=int, default=10)
            p.add_argument("--seed", type=int, default=100)
            p.add_argument("--output", default="runs/benchmark.json")
    p = sub.add_parser("replay")
    p.add_argument("directory")
    for name in ("fetch-brain", "inspect-brain", "train-brain"):
        p = sub.add_parser(name)
        p.add_argument("--data", default="data")
        if name == "train-brain":
            p.add_argument("--episodes", type=int, default=20)
            p.add_argument("--output", default="data/car-readout.npz")
    p = sub.add_parser("prepare-malecns", help="Build a fresh circuit from original MaleCNS v1.0 data")
    p.add_argument("--source", default="data/malecns-raw", help="Official Feather files or vendored R CSV export")
    p.add_argument("--output", default="data/malecns-car")
    p.add_argument("--vendor", default="vendor/malecns")
    p.add_argument("--download", action="store_true", help="Fetch original public snapshot (~1.1 GB)")
    args = parser.parse_args()
    if args.action == "prepare-malecns":
        from .malecns_data import fetch_snapshot, build_circuit, train_readout
        if args.download:
            fetch_snapshot(args.source)
        info = build_circuit(args.source, args.output, args.vendor)
        training = train_readout(args.output)
        print(json.dumps({"circuit": info, "training": training}, indent=2))
        return
    if hasattr(args, "model") and args.model is None:
        args.model = "data/malecns-car" if args.controller in ("malecns", "malecns-ablated") else "data/car-readout.npz"
    if args.action in ("fetch-brain", "inspect-brain", "train-brain"):
        from .brain import fetch_assets, inspect_graph, train
        if args.action == "fetch-brain":
            result = fetch_assets(Path(args.data))
        elif args.action == "inspect-brain":
            result = inspect_graph(Path(args.data))
        else:
            if args.episodes < 1:
                parser.error("episodes must be positive")
            result = train(Path(args.data), args.episodes, Path(args.output))
    elif args.action == "replay":
        result = replay(args.directory)
    else:
        def factory():
            if args.controller in ("malecns", "malecns-ablated"):
                from .malecns_controller import MaleCNSController
                return MaleCNSController(args.model, ablated=args.controller == "malecns-ablated")
            if args.controller in ("connectome", "ablated"):
                from .brain import ConnectomeController
                return ConnectomeController(Path(args.model), ablated=args.controller == "ablated")
            return load_controller(args.controller)
        if args.action == "benchmark":
            if args.count < 1:
                parser.error("count must be positive")
            results = []
            for seed in range(args.seed, args.seed+args.count):
                row = run(randomized(seed), factory())
                results.append({"seed": seed, **row})
                print(f"seed={seed}: {row['status']} ({row['reason']})", flush=True)
            result = {"controller": args.controller, "success_rate": sum(r["status"] == "success" for r in results)/len(results), "runs": results}
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2))
        else:
            scenario = Scenario.load(args.scenario) if args.scenario else Scenario()
            if args.action == "serve":
                from .server import serve
                return serve(scenario, factory, args.port, args.controller if args.controller in ("baseline", "connectome", "ablated", "malecns", "malecns-ablated") else "custom", args.model)
            result = run(scenario, factory(), args.output, args.frames)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
