import base64
from dataclasses import asdict
from pathlib import Path
import tempfile
import time
import unittest
from fastapi.testclient import TestClient
from cns_car.camera import Camera, png
from cns_car.controllers import BaselineController
from cns_car.runner import replay
from cns_car.scenario import Scenario
from cns_car.server import create_app
from cns_car.simulator import Simulator
from cns_car.workbench import Experiment, RunStore, Workbench, validate_config


class RecordingTests(unittest.TestCase):
    def test_capture_matches_world_and_replays_with_configured_geometry(self):
        with tempfile.TemporaryDirectory() as temp:
            config = validate_config({"scenario": Scenario(timeout=.5).to_dict(), "vehicle": {"wheelbase": .3}})
            store = RunStore(temp)
            experiment = Experiment(config, BaselineController, store)
            while not experiment.finished:
                experiment.tick()
            records = store.records(experiment.id)
            self.assertGreater(len(records), 3)
            for record in records:
                sim = Simulator(Scenario(**record['scenario']))
                for k, v in record['vehicle'].items():
                    setattr(sim.vehicle, k, v)
                sim.steps = round(record['sim_time']/sim.dt)
                expected = png(Camera(**record['sensor']).observe(sim))
                self.assertEqual((experiment.path/record['frame_path']).read_bytes(), expected)
                if record['decision']:
                    self.assertEqual(record['decision']['timestamp'], record['sim_time'])
                    self.assertGreater(record['decision']['outcome_time'], record['sim_time'])
                self.assertTrue(all(e['time'] <= record['sim_time'] for e in record['events']))
            self.assertEqual(replay(experiment.path)['result'], experiment.session.sim.result())
            self.assertTrue(store.list()[0]['finished'])

    def test_reset_and_empty_stopped_runs_are_replayable(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Scenario(), BaselineController, temp)
            old = bench.current
            bench.action('reset', {})
            self.assertEqual(replay(old.path)['result']['reason'], 'reset')
            self.assertNotEqual(old.id, bench.current.id)
            self.assertEqual(bench.current.latest['sim_time'], 0)

    def test_bad_config_does_not_end_existing_run(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Scenario(), BaselineController, temp)
            old = bench.current
            with self.assertRaises(ValueError):
                bench.action('configure', {'scenario': {'start': [-1, 2, 0]}})
            self.assertIs(bench.current, old)
            self.assertFalse(old.finished)
            with self.assertRaises(ValueError):
                bench.action('configure', {'sensor': {'fov': float('nan')}})

    def test_batch_matches_seeds_and_persists_results(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Scenario(timeout=.2), BaselineController, temp)
            bench.start_batch({'seed': 1000, 'count': 2, 'controllers': ['baseline']})
            bench.batch_thread.join(10)
            self.assertEqual(bench.batch['status'], 'complete')
            self.assertEqual([r['seed'] for r in bench.batch['runs']], [1000, 1001])
            for row in bench.batch['runs']:
                self.assertEqual(replay(bench.store.directory(row['id']))['result'], row['result'])


class ApiTests(unittest.TestCase):
    def test_controls_stream_persistence_and_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app(Scenario(), BaselineController, temp)
            with TestClient(app) as client:
                initial = client.get('/api/state').json()
                self.assertFalse(initial['running'])
                with client.websocket_connect('/api/stream') as ws:
                    state = ws.receive_json()
                    self.assertEqual(state['run_id'], initial['run_id'])
                    self.assertTrue(base64.b64decode(state['camera']).startswith(b'\x89PNG'))
                self.assertEqual(client.post('/api/run', json={}, headers={'Origin':'https://untrusted.example'}).status_code, 403)
                self.assertEqual(client.post('/api/speed', json={'value':99}).status_code, 400)
                self.assertEqual(client.post('/api/manual', json={'enabled':'false'}).status_code, 400)
                client.post('/api/run', json={})
                time.sleep(.35)
                paused = client.post('/api/pause', json={}).json()
                self.assertGreater(paused['frame_count'], 1)
                time.sleep(.15)
                self.assertEqual(client.get('/api/state').json()['frame_count'], paused['frame_count'])
                stopped = client.post('/api/stop', json={}).json()
                self.assertTrue(stopped['finished'])
                run_id = stopped['run_id']
                self.assertGreater(len(client.get(f'/api/runs/{run_id}/history').json()), 2)
                self.assertEqual(client.get(f'/api/runs/{run_id}/frames/99999').status_code, 400)
                self.assertEqual(client.get('/api/runs/invalid/history').status_code, 400)
                self.assertEqual(client.get(f'/api/runs/{run_id}/export').status_code, 200)
                self.assertEqual(client.post('/api/run', json={}).status_code, 400)
            self.assertTrue(RunStore(temp).list()[0]['finished'])

    def test_manual_watchdog_brakes_stale_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app(Scenario(), BaselineController, temp)
            with TestClient(app) as client:
                client.post('/api/manual', json={'enabled':True})
                client.post('/api/command', json={'steering':0, 'throttle':.2})
                client.post('/api/run', json={})
                time.sleep(.8)
                state = client.post('/api/pause', json={}).json()
                self.assertTrue(state['command']['brake'])
