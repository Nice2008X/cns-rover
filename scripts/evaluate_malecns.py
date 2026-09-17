#!/usr/bin/env python3
"""Matched seeded evaluation; reports navigation and safety separately.

Run from the repository root: .venv/bin/python scripts/evaluate_malecns.py
Seeds 9900+ and 10000+ are held out from readout training and development scenes.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cns_car.controllers import load_controller
from cns_car.runner import Session
from cns_car.scenario import Scenario, randomized
from cns_car.malecns_data import digest


def obstacle_scenario(seed):
    rng = random.Random(seed)
    lane = rng.uniform(3.5, 6.5)
    return Scenario(name=f'obstacle_{seed}', start=[1.5, lane, rng.uniform(-12, 12)],
                    target=[8, lane + rng.uniform(-.35, .35), .15],
                    obstacles=[[rng.uniform(3.5, 4.8), lane + rng.uniform(-.65, .65), rng.uniform(.3, .5)]],
                    timeout=60)


def evaluate(count=10, obstacle_seed=9900, empty_seed=10000):
    cases = [obstacle_scenario(obstacle_seed + i) for i in range(count)]
    for i in range(count):
        sc = randomized(empty_seed + i)
        sc.timeout = 60
        cases.append(sc)
    rows = []
    for spec in ('baseline', 'malecns', 'malecns-ablated'):
        for sc in cases:
            session = Session(sc, load_controller(spec))
            modes = Counter()
            inference = []
            while session.sim.status == 'running':
                record = session.tick()
                modes[record['debug']['mode']] += 1
                inference.append(session.inference_ms)
            row = {'controller': spec, 'scenario': sc.to_dict(), **session.sim.result(),
                   'modes': dict(modes), 'mean_inference_ms': sum(inference) / len(inference)}
            rows.append(row)
            print(spec, sc.name, row['status'], row['reason'], flush=True)
    summary = {}
    for spec in ('baseline', 'malecns', 'malecns-ablated'):
        summary[spec] = {}
        for suite in ('obstacle', 'random'):
            selected = [r for r in rows if r['controller'] == spec and r['scenario']['name'].startswith(suite)]
            summary[spec][suite] = {'runs': len(selected),
                'successes': sum(r['status'] == 'success' for r in selected),
                'collisions': sum(r['collisions'] for r in selected),
                'timeouts': sum(r['reason'] == 'timeout' for r in selected),
                'mean_inference_ms': sum(r['mean_inference_ms'] for r in selected) / len(selected)}
    return {'schema': 'malecns-car-evaluation-v1', 'summary': summary, 'runs': rows,
            'circuit_sha256': digest('data/malecns-car/manifest.json'),
            'readout_sha256': digest('data/malecns-car/readout.npz'),
            'controller_source_sha256': digest('cns_car/malecns_controller.py'),
            'notes': ['Synthetic simulator-specific perception; not a biological or hardware validation.',
                      'Visual ablation retains geometric safety, raw target visibility and stopping.',
                      'Collision-free timeout is not navigation success.',
                      'These comparisons do not establish an advantage over shuffled wiring.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--obstacle-seed', type=int, default=9900)
    parser.add_argument('--empty-seed', type=int, default=10000)
    parser.add_argument('--output', default='docs/malecns-evaluation.json')
    args = parser.parse_args()
    if args.count < 1:
        parser.error('count must be positive')
    started = time.perf_counter()
    report = evaluate(args.count, args.obstacle_seed, args.empty_seed)
    report['wall_seconds'] = time.perf_counter() - started
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(json.dumps(report['summary'], indent=2))
