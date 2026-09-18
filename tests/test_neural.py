import importlib.util
from pathlib import Path
import unittest
from cns_rover.camera import Camera
from cns_rover.scenario import Scenario
from cns_rover.simulator import Simulator

AVAILABLE = importlib.util.find_spec("numpy") is not None and importlib.util.find_spec("scipy") is not None and Path("data/rover-readout.npz").exists()


@unittest.skipUnless(AVAILABLE, "Requires local trained model and NumPy/SciPy")
class NeuralTests(unittest.TestCase):
    def test_reset_is_deterministic_and_output_finite(self):
        import math
        from cns_rover.brain import LegacyConnectomeRoverController
        controller = LegacyConnectomeRoverController(Path("data/rover-readout.npz"))
        obs = Camera().observe(Simulator(Scenario()))
        controller.reset("Find the red ball")
        first = controller.act(obs)
        for _ in range(3):
            controller.act(obs)
        controller.reset("Find the red ball")
        self.assertEqual(first, controller.act(obs))
        self.assertTrue(math.isfinite(first.steering) and math.isfinite(first.throttle))

    def test_ablation_removes_visual_activity(self):
        import numpy as np
        from cns_rover.brain import LegacyConnectomeRoverController
        obs = Camera().observe(Simulator(Scenario(start=[5.,5.,0.], target=[6.,5.,.15])))
        active = LegacyConnectomeRoverController(Path("data/rover-readout.npz"))
        ablated = LegacyConnectomeRoverController(Path("data/rover-readout.npz"), ablated=True)
        active.reset("Find the red ball")
        ablated.reset("Find the red ball")
        self.assertTrue(np.any(active.encoder.features(obs)))
        self.assertFalse(np.any(ablated.encoder.features(obs)))
