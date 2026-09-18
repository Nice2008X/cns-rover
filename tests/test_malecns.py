"""Regression tests for the independently sourced MaleCNS rover controller."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from cns_rover.camera import Camera
from cns_rover.protocol import Observation
from cns_rover.runner import Session, replay, run
from cns_rover.scenario import Scenario
from cns_rover.simulator import Simulator

AVAILABLE = (importlib.util.find_spec('numpy') is not None
             and importlib.util.find_spec('scipy') is not None
             and Path('data/malecns-rover/readout.npz').exists())


@unittest.skipUnless(AVAILABLE, 'Requires the independent MaleCNS rover circuit and NumPy/SciPy')
class MaleCNSTests(unittest.TestCase):
    def controller(self, **kwargs):
        from cns_rover.malecns_controller import MaleCNSRoverController
        c = MaleCNSRoverController(**kwargs)
        c.reset('Find the red ball')
        return c

    def test_anatomy_is_original_and_nontrivial(self):
        import numpy as np
        c = self.controller()
        m = c.circuit.manifest
        self.assertEqual(m['dataset'], 'male-cns:v1.0')
        self.assertEqual(m['provenance']['source'], 'Janelia public flat snapshot')
        self.assertGreater(m['anatomical_edges'], 10000)
        self.assertIn('R/neuprint.R', m['vendor_sha256'])
        with np.load('data/malecns-rover/anatomy.npz', allow_pickle=False) as a:
            self.assertEqual(len(a['pre']), m['anatomical_edges'])
            self.assertTrue((a['synapses'] >= 5).all())
            self.assertEqual(len(set(a['body_ids'])), len(a['body_ids']))

    def test_neural_drive_and_edge_lesion_change_output(self):
        import numpy as np
        c = self.controller()
        left, right = np.zeros(14), np.zeros(14)
        left[0], right[6] = 1, 1
        l, _ = c.circuit.decide(left)
        r, _ = c.circuit.decide(right)
        self.assertLess(l[0], -.8)
        self.assertGreater(r[0], .8)
        obstacle_left, obstacle_right = np.zeros(14), np.zeros(14)
        obstacle_left[7], obstacle_right[13] = 1, 1
        self.assertGreater(c.circuit.decide(obstacle_left)[0][1], .2)
        self.assertLess(c.circuit.decide(obstacle_right)[0][1], -.2)
        c.circuit.feed.data[:] = 0
        self.assertTrue(np.array_equal(c.circuit.features(left), np.zeros(384)))
        np.testing.assert_array_equal(c.circuit.decide(left)[0], c.circuit.decide(right)[0])

    def test_reset_and_ablation_are_deterministic(self):
        obs = Camera().observe(Simulator(Scenario(target=[4, 2.5, .15])))
        c = self.controller()
        first = c.act(obs)
        c.act(Observation(obs.rgb, obs.width, obs.height, .1))
        c.reset('Find the red ball')
        self.assertEqual(c.act(obs), first)
        ablated = self.controller(ablated=True)
        ablated.act(obs)
        self.assertEqual(ablated.debug['active_neurons'], 0)
        self.assertGreater(c.debug['active_neurons'], 0)

    def test_bad_frame_and_backwards_time_fail_closed(self):
        c = self.controller()
        obs = Camera().observe(Simulator(Scenario()))
        c.act(obs)
        with self.assertRaises(ValueError):
            c.act(Observation(obs.rgb, obs.width, obs.height, -1))
        with self.assertRaises(ValueError):
            c.act(Observation(b'bad', 96, 72, .1))

    def test_missing_corrupt_and_mismatched_models_are_rejected(self):
        from cns_rover.malecns_controller import RateCircuit
        from cns_rover.malecns_data import digest
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'prepare-malecns'):
                RateCircuit(temp)
            shutil.copytree('data/malecns-rover', temp, dirs_exist_ok=True)
            path = Path(temp) / 'manifest.json'
            m = json.loads(path.read_text())
            m['files']['feed.npz'] = '0' * 64
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, 'checksum'):
                RateCircuit(temp)
            m['files']['feed.npz'] = digest(Path(temp) / 'feed.npz')
            m['selection'] = 'different circuit metadata'
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, 'identity'):
                RateCircuit(temp)

    def test_camera_obstacles_change_neural_proximity(self):
        clear = Scenario(start=[2, 5, 0], target=[7, 5, .15])
        blocked = Scenario(start=[2, 5, 0], target=[7, 5, .15], obstacles=[[3.2, 5, .35]])
        a, b = self.controller(), self.controller()
        a.act(Camera().observe(Simulator(clear)))
        b.act(Camera().observe(Simulator(blocked)))
        self.assertGreater(b.debug['neural_proximity'], a.debug['neural_proximity'] + .1)
        self.assertGreater(b.debug['local_obstacle_points'], 0)

    def test_avoidance_passes_on_both_sides(self):
        for y in (4.6, 5.4):
            with self.subTest(obstacle_y=y):
                scenario = Scenario(start=[2, 5, 0], target=[7, 5, .15],
                                    obstacles=[[4, y, .4]], timeout=40)
                session = Session(scenario, self.controller())
                avoided = False
                while session.sim.status == 'running':
                    record = session.tick()
                    avoided |= record['debug']['mode'] == 'AVOID'
                self.assertEqual(session.sim.status, 'success')
                self.assertEqual(session.sim.collisions, 0)
                self.assertTrue(avoided)

    def test_occluded_target_and_exact_replay(self):
        scenario = Scenario(start=[2, 5, 0], target=[7, 5, .15],
                            obstacles=[[4, 5, .45]], timeout=45)
        with tempfile.TemporaryDirectory() as temp:
            result = run(scenario, self.controller(), Path(temp) / 'run')
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['collisions'], 0)
            self.assertEqual(replay(Path(temp) / 'run')['result'], result)

    def test_near_wall_brakes_without_contact(self):
        scenario = Scenario(start=[.35, 5, 180], target=[8, 5, .15], timeout=2)
        c = self.controller()
        session = Session(scenario, c)
        first = session.tick()
        self.assertTrue(first['command']['brake'])
        while session.sim.status == 'running':
            session.tick()
        self.assertEqual(session.sim.collisions, 0)
        self.assertLess(session.sim.distance, .01)

    def test_observed_target_remains_safe_after_leaving_camera(self):
        # Development case that previously clipped the ball from the blind side
        # after ~28 seconds with neural drive disabled.
        scenario = Scenario(start=[1.5, 6.054146481708747, -10.478319195063374],
                            target=[8, 5.998512539010646, .15],
                            obstacles=[[3.934855964146153, 6.597319917735397, .4052889591499192]],
                            timeout=35)
        result = run(scenario, self.controller(ablated=True))
        self.assertEqual(result['collisions'], 0)

    def test_workbench_selection_calibration_and_recording(self):
        from cns_rover.controllers import BaselineRoverController
        from cns_rover.workbench import Workbench
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Scenario(), BaselineRoverController, temp)
            bench.action('configure', {'controller': 'malecns',
                                      'sensor': {'width': 160, 'height': 120, 'fov': 90},
                                      'vehicle': {'wheelbase': .3, 'max_steering_degrees': 25}})
            experiment = bench.current
            self.assertEqual(experiment.session.controller.fov, 90)
            self.assertEqual(experiment.session.controller.wheelbase, .3)
            experiment.tick()
            self.assertEqual(experiment.latest['controller'], 'malecns')
            self.assertIn('neural_proximity', experiment.latest['debug'])
            metadata = json.loads((experiment.path / 'controller.json').read_text())
            self.assertIn('readout_sha256', metadata['config'])
            bench.action('configure', {'controller': 'malecns-ablated'})
            bench.current.tick()
            self.assertEqual(bench.current.latest['debug']['active_neurons'], 0)


class SnapshotDownloadTests(unittest.TestCase):
    def test_partial_download_is_not_promoted_and_cache_is_verified(self):
        import hashlib
        import io
        from unittest.mock import patch
        from cns_rover import malecns_data as data
        good = b'original-source-data'
        class Response(io.BytesIO):
            headers = {'Content-Length': str(len(good))}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(data, 'FILES', {'weights.feather': ('weights.feather', len(good))}), \
             patch.object(data, 'SNAPSHOT_SHA256', {'weights.feather': hashlib.sha256(good).hexdigest()}):
            with patch.object(data, 'urlopen', return_value=Response(good[:-2])):
                with self.assertRaises(ValueError):
                    data.fetch_snapshot(temp)
            self.assertFalse((Path(temp) / 'weights.feather').exists())
            self.assertFalse((Path(temp) / 'weights.part').exists())
            with patch.object(data, 'urlopen', return_value=Response(good)):
                data.fetch_snapshot(temp)
            self.assertEqual((Path(temp) / 'weights.feather').read_bytes(), good)
            (Path(temp) / 'weights.feather').write_bytes(b'x' * len(good))
            with self.assertRaises(ValueError):
                data.fetch_snapshot(temp)


@unittest.skipUnless(AVAILABLE, 'Requires independent model for export round-trip fixture')
class ExportImportTests(unittest.TestCase):
    def test_csv_export_schema_preserves_circuit_weights(self):
        import csv
        import numpy as np
        from scipy import sparse
        from cns_rover.malecns_data import build_circuit
        # This checks the R exporter file contract; it does not execute R.
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / 'export', Path(temp) / 'model'
            source.mkdir()
            (source / 'export.json').write_text(json.dumps({'dataset': 'male-cns:v1.0', 'source': 'natverse/malecns'}))
            neurons = json.loads(Path('data/malecns-rover/neurons.json').read_text())
            with (source / 'neurons.csv').open('w') as f:
                writer = csv.DictWriter(f, fieldnames=['bodyId', 'type', 'somaSide', 'superclass'])
                writer.writeheader()
                writer.writerows(neurons)
            with np.load('data/malecns-rover/anatomy.npz', allow_pickle=False) as a:
                with (source / 'edges.csv').open('w') as f:
                    writer = csv.writer(f)
                    writer.writerow(['body_pre', 'body_post', 'weight'])
                    writer.writerows(zip(a['body_ids'][a['pre']], a['body_ids'][a['post']], a['synapses']))
            info = build_circuit(source, output)
            self.assertEqual(info['anatomical_edges'], 29583)
            for name in ['feed.npz', 'recurrent.npz']:
                np.testing.assert_allclose(sparse.load_npz(output / name).toarray(),
                                           sparse.load_npz(Path('data/malecns-rover') / name).toarray())
