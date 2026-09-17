import math
from pathlib import Path
import tempfile
import unittest
from cns_car.camera import Camera, png
from cns_car.controllers import BaselineController
from cns_car.protocol import Observation, VehicleCommand
from cns_car.runner import Session, run, replay
from cns_car.scenario import Scenario, randomized
from cns_car.simulator import Simulator


class PhysicsTests(unittest.TestCase):
    def test_cannot_rotate_in_place(self):
        sim = Simulator(Scenario())
        sim.submit(VehicleCommand(1, 0))
        for _ in range(30):
            sim.step()
        self.assertEqual(sim.vehicle.heading, 0)

    def test_positive_steering_turns_right_and_reverse_inverts_turn(self):
        for throttle, sign in ((.3, 1), (-.3, -1)):
            sim = Simulator(Scenario(start=[5., 5., 0.], target=[8., 8., .15]))
            for i in range(40):
                if i % 10 == 0:
                    sim.submit(VehicleCommand(.5, throttle))
                sim.step()
            self.assertGreater(sim.vehicle.heading*sign, 0)

    def test_acceleration_limit_and_watchdog(self):
        sim = Simulator(Scenario())
        sim.submit(VehicleCommand(0, 1))
        previous = 0
        for _ in range(40):
            sim.step()
            self.assertLessEqual(sim.vehicle.speed-previous, 1.5*sim.dt+1e-9)
            previous = sim.vehicle.speed
        for _ in range(120):
            sim.step()
        self.assertLess(sim.vehicle.speed, .001)

    def test_collision_is_terminal(self):
        sim = Simulator(Scenario(start=[.21, 5., 180.], target=[8., 8., .15]))
        sim.submit(VehicleCommand(0, 1))
        for _ in range(50):
            sim.step()
        self.assertEqual(sim.reason, "collision")
        self.assertEqual(sim.collisions, 1)
        self.assertEqual(sim.vehicle.speed, 0)
        self.assertGreaterEqual(sim.vehicle.x, sim.radius)

    def test_emergency_stop_latches(self):
        sim = Simulator(Scenario())
        sim.stop()
        sim.submit(VehicleCommand(0, 1))
        sim.step()
        self.assertEqual(sim.vehicle.speed, 0)
        self.assertEqual(sim.status, "failed")

    def test_success_requires_stopped_hold(self):
        sim = Simulator(Scenario(start=[5., 5., 0.], target=[5.45, 5., .15]))
        sim.submit(VehicleCommand(brake=True))
        for _ in range(49):
            sim.step()
        self.assertEqual(sim.status, "running")
        sim.step()
        self.assertEqual(sim.status, "success")

    def test_invalid_commands(self):
        for x in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                VehicleCommand(x, 0)
        self.assertEqual(VehicleCommand(3, -2).limited(), VehicleCommand(1, -1))

    def test_scenario_validation_and_seeds(self):
        self.assertEqual(randomized(4).to_dict(), randomized(4).to_dict())
        with self.assertRaises(ValueError):
            Scenario(start=[-1, 2, 0])
        with self.assertRaises(ValueError):
            Scenario(obstacles=[[6., 3., .4]])
        with self.assertRaises(ValueError):
            Scenario(timeout=math.nan)


class CameraTests(unittest.TestCase):
    def red_pixels(self, obs):
        return sum(obs.rgb[i] > 150 and obs.rgb[i+1] < 80 and obs.rgb[i+2] < 80
                   for i in range(0, len(obs.rgb), 3))

    def test_rgb_contract_and_png(self):
        obs = Camera().observe(Simulator(Scenario()))
        self.assertEqual(len(obs.rgb), obs.width*obs.height*3)
        self.assertEqual(set(Observation.__dataclass_fields__), {"rgb", "width", "height", "timestamp"})
        self.assertTrue(png(obs).startswith(b"\x89PNG\r\n\x1a\n"))

    def test_occlusion_and_behind(self):
        clear = Scenario(start=[2., 5., 0.], target=[7., 5., .15])
        occluded = Scenario(start=[2., 5., 0.], target=[7., 5., .15], obstacles=[[4., 5., .45]])
        camera = Camera()
        self.assertGreater(self.red_pixels(camera.observe(Simulator(clear))), 0)
        self.assertEqual(self.red_pixels(camera.observe(Simulator(occluded))), 0)
        clear.start[2] = 180
        self.assertEqual(self.red_pixels(camera.observe(Simulator(clear))), 0)


class IntegrationTests(unittest.TestCase):
    def test_success_and_exact_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"run"
            result = run(Scenario(), BaselineController(), path, frames=True)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["collisions"], 0)
            self.assertLessEqual(result["final_target_distance"], .5)
            self.assertEqual(replay(path)["result"], result)
            self.assertTrue(list((path/"frames").glob("*.png")))

    def test_controller_failure_stops_vehicle(self):
        class Broken:
            def reset(self, task): pass
            def act(self, obs): raise ValueError("broken")
        session = Session(Scenario(), Broken())
        with self.assertRaises(RuntimeError):
            session.tick()
        self.assertEqual(session.sim.reason, "controller_error")
        self.assertEqual(session.sim.vehicle.speed, 0)
