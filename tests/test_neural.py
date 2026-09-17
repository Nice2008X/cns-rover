import importlib.util
from pathlib import Path
import unittest
from cns_car.camera import Camera
from cns_car.scenario import Scenario
from cns_car.simulator import Simulator

AVAILABLE = importlib.util.find_spec("numpy") is not None and importlib.util.find_spec("scipy") is not None and Path("data/car-readout.npz").exists()


@unittest.skipUnless(AVAILABLE, "Requires local trained model and NumPy/SciPy")
class NeuralTests(unittest.TestCase):
    def test_reset_is_deterministic_and_output_finite(self):
        import math
        from cns_car.brain import ConnectomeController
        controller = ConnectomeController(Path("data/car-readout.npz"))
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
        from cns_car.brain import ConnectomeController
        obs = Camera().observe(Simulator(Scenario(start=[5.,5.,0.], target=[6.,5.,.15])))
        active = ConnectomeController(Path("data/car-readout.npz"))
        ablated = ConnectomeController(Path("data/car-readout.npz"), ablated=True)
        active.reset("Find the red ball")
        ablated.reset("Find the red ball")
        self.assertTrue(np.any(active.encoder.features(obs)))
        self.assertFalse(np.any(ablated.encoder.features(obs)))
