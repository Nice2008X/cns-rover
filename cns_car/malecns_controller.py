"""New MaleCNS rate-circuit car policy and camera-only local avoidance.

Geometry is reconstructed from RGB and configured camera calibration only.
The short-lived local map uses command-based odometry, never simulator pose.
"""
import json
import math
from pathlib import Path

from .protocol import VehicleCommand
from .malecns_data import BINS, digest


class RateCircuit:
    def __init__(self, directory, readout=True):
        import numpy as np
        from scipy import sparse
        self.np = np
        directory = Path(directory)
        if not (directory / 'manifest.json').exists():
            raise ValueError('MaleCNS car circuit missing. Run: python -m cns_car prepare-malecns')
        self.manifest = json.loads((directory / 'manifest.json').read_text())
        if self.manifest.get('schema') != 'malecns-car-circuit-v1':
            raise ValueError('Unsupported MaleCNS circuit schema')
        required = {'feed.npz', 'recurrent.npz', 'anatomy.npz', 'neurons.json'}
        if set(self.manifest.get('files', {})) != required:
            raise ValueError('Incomplete MaleCNS circuit manifest')
        for name in required:
            if digest(directory / name) != self.manifest['files'][name]:
                raise ValueError(f'MaleCNS circuit checksum mismatch: {name}')
        self.feed = sparse.load_npz(directory / 'feed.npz').tocsr()
        self.recurrent = sparse.load_npz(directory / 'recurrent.npz').tocsr()
        n = self.feed.shape[0]
        if self.feed.shape != (n, 2 * BINS) or self.recurrent.shape != (n, n) or n < 1:
            raise ValueError('Invalid MaleCNS matrix dimensions')
        if any(not np.isfinite(m.data).all() or (m.data < 0).any()
               for m in (self.feed, self.recurrent)):
            raise ValueError('Invalid MaleCNS rate weights')
        self.config = {}
        if readout:
            with np.load(directory / 'readout.npz', allow_pickle=False) as data:
                self.weights = data['weights'].copy()
                self.mean = data['mean'].copy()
                self.scale = data['scale'].copy()
                self.config = json.loads(str(data['config']))
            if (self.config.get('schema') != 'malecns-car-readout-v1'
                    or self.config.get('circuit_sha256') != digest(directory / 'manifest.json')):
                raise ValueError('MaleCNS readout/circuit identity mismatch')
            if (self.weights.shape != (n + 1, 3) or self.mean.shape != (n,)
                    or self.scale.shape != (n,) or (self.scale <= 0).any()
                    or any(not np.isfinite(a).all() for a in (self.weights, self.mean, self.scale))):
                raise ValueError('Invalid MaleCNS readout parameters')
            self.config = {**self.config, 'readout_sha256': digest(directory / 'readout.npz')}

    def features(self, signals):
        np = self.np
        signals = np.asarray(signals, dtype=float)
        if signals.shape != (2 * BINS,) or not np.isfinite(signals).all():
            raise ValueError('Expected fourteen finite visual signals')
        drive = self.feed @ np.clip(signals, 0, 1)
        state = np.zeros(self.feed.shape[0])
        for _ in range(4):
            state = np.tanh(1.5 * drive + .35 * (self.recurrent @ state))
        return state

    def decide(self, signals):
        np = self.np
        state = self.features(signals)
        result = np.r_[(state - self.mean) / self.scale, 1.] @ self.weights
        if not np.isfinite(result).all():
            raise ValueError('Non-finite MaleCNS output')
        return np.clip(result, [-1, -1, 0], [1, 1, 1]), int(np.count_nonzero(state > 1e-5))


class MaleCNSController:
    def __init__(self, model='data/malecns-car', ablated=False):
        import numpy as np
        self.np = np
        self.circuit = RateCircuit(model)
        self.ablated = ablated
        self.config = {**self.circuit.config, 'controller': 'native-malecns-car-v1',
                       'ablated': ablated, 'safety': 'RGB ground-plane local arc planner',
                       'dataset': self.circuit.manifest['dataset']}
        self.configure()

    def configure(self, sensor=None, vehicle=None):
        sensor, vehicle = sensor or {}, vehicle or {}
        self.fov = float(sensor.get('fov', 70))
        self.wheelbase = float(vehicle.get('wheelbase', .2))
        self.max_steering = math.radians(float(vehicle.get('max_steering_degrees', 30)))
        if not (40 <= self.fov <= 110 and .1 <= self.wheelbase <= 1
                and math.radians(5) <= self.max_steering <= math.radians(45)):
            raise ValueError('Unsupported MaleCNS camera/vehicle calibration')
        self.config['calibration'] = {'fov': self.fov, 'wheelbase': self.wheelbase,
                                      'max_steering_degrees': math.degrees(self.max_steering),
                                      'camera_height': .12, 'camera_offset': .1,
                                      'target_radius': .15, 'vehicle_radius': .2}

    def reset(self, task):
        if 'red ball' not in task.lower():
            raise ValueError('MaleCNS car currently supports the red-ball task')
        np = self.np
        self.points = np.empty((0, 4))  # x forward, y right, observation time, target flag
        self.last_time = None
        self.speed = 0.
        self.servo = 0.
        self.command = VehicleCommand(brake=True)
        self.turn = 1.
        self.search_started = None
        self.debug = {'mode': 'SEARCH', 'biologically_validated': False}

    def _advance_map(self, timestamp):
        """Predict ego motion using only our last command and elapsed time."""
        np = self.np
        dt = 0 if self.last_time is None else timestamp - self.last_time
        if not math.isfinite(timestamp) or dt < 0:
            raise ValueError('Camera timestamps must be finite and monotonic')
        if dt > .5:
            # Cannot safely reconstruct motion across missing decisions.
            self.points = np.empty((0, 4))
            self.speed = self.servo = 0.
        else:
            x = y = heading = 0.
            left = dt
            while left > 1e-9:
                step = min(.01, left)
                cmd = self.command
                desired = cmd.steering * self.max_steering
                delta = min(math.radians(240) * step, abs(desired - self.servo) * step / .08)
                self.servo += max(-delta, min(delta, desired - self.servo))
                target = 0 if cmd.brake else cmd.throttle * (1.5 if cmd.throttle >= 0 else .7)
                accel = 3 if cmd.brake or self.speed * target < 0 or abs(target) < abs(self.speed) else 1.5
                delta = min(accel * step, abs(target - self.speed) * step / .1)
                self.speed += max(-delta, min(delta, target - self.speed))
                omega = self.speed / self.wheelbase * math.tan(self.servo)
                x += self.speed * math.cos(heading + omega * step / 2) * step
                y += self.speed * math.sin(heading + omega * step / 2) * step
                heading += omega * step
                left -= step
            if len(self.points):
                p = self.points[:, :2] - [x, y]
                c, s = math.cos(heading), math.sin(heading)
                self.points[:, :2] = p @ np.array([[c, -s], [s, c]])
        self.last_time = timestamp
        if len(self.points):
            self.points = self.points[(timestamp - self.points[:, 2] < np.where(self.points[:, 3] == 1, 30, 5))
                                      & (np.linalg.norm(self.points[:, :2], axis=1) < 4)]

    def _perceive(self, observation):
        np = self.np
        w, h = observation.width, observation.height
        if w < 16 or h < 16 or len(observation.rgb) != w * h * 3:
            raise ValueError('Invalid RGB camera frame')
        rgb = np.frombuffer(observation.rgb, dtype=np.uint8).reshape(h, w, 3).astype(float)
        focal = w / (2 * math.tan(math.radians(self.fov) / 2))
        red = (rgb[:, :, 0] > 150) & (rgb[:, :, 0] > 2 * rgb[:, :, 1]) & (rgb[:, :, 0] > 2 * rgb[:, :, 2])
        # Renderer-specific semantic colors, with tolerance; not general vision.
        solid = (np.max(abs(rgb - [178, 137, 78]), axis=2) < 15) | (np.max(abs(rgb - [111, 127, 141]), axis=2) < 12)
        floor = np.max(abs(rgb - [72, 82, 91]), axis=2) < 12
        new = []
        hazards = np.zeros(BINS)
        for col in range(w):
            ys = np.flatnonzero(solid[:, col] & (np.arange(h) > h / 2))
            if not len(ys):
                continue
            bottom = int(ys[-1])
            # A visible ground contact is required. An obstacle extending below
            # the image is conservatively treated as very close.
            depth = .12 * focal / (bottom + 1.5 - h / 2)
            if bottom + 1 < h and not floor[bottom + 1, col]:
                continue  # ground contact occluded by another object
            lateral = depth * (col + .5 - w / 2) / focal
            if depth < 4:
                new.append([depth + .1, lateral, observation.timestamp, 0])
            sector = min(BINS - 1, int(col / w * BINS))
            hazards[sector] = max(hazards[sector], max(0, 1 - depth / 2.5))
        rows, cols = np.nonzero(red)
        target = np.zeros(BINS)
        distance = None
        visible = len(cols) >= 2
        if visible:
            center = float(cols.mean())
            bearing_bin = np.clip((center + .5) / w * BINS - .5, 0, BINS - 1)
            target = np.exp(-((np.arange(BINS) - bearing_bin) / .65) ** 2)
            target /= target.sum()
            # Sphere angular silhouette, calibrated for the known 15 cm ball.
            half_angle = (math.atan((float(cols.max()) + 1 - w / 2) / focal)
                          - math.atan((float(cols.min()) - w / 2) / focal)) / 2
            distance = .15 / max(math.sin(half_angle), 1e-5) + .1
            # Replace old target estimates: tiny far-away blobs give noisy
            # ranges and must not leave phantom obstacles along the approach.
            # A silhouette clipped by the image edge overestimates range.
            # Preserve the last complete view instead of replacing it with that.
            reliable = (cols.min() > 0 and cols.max() < w - 1
                        and rows.min() > 0 and rows.max() < h - 1)
            # Keep the target in the collision map too: after it leaves the
            # forward FOV, a turning car can otherwise clip it from the side.
            raw_angle = math.atan((center + .5 - w / 2) / focal)
            center_xy = [(distance - .1) * math.cos(raw_angle) + .1,
                         (distance - .1) * math.sin(raw_angle)]
            if reliable and distance < 4:
                self.points = self.points[self.points[:, 3] == 0]
                for a in np.linspace(0, 2 * math.pi, 32, endpoint=False):
                    new.append([center_xy[0] + .16 * math.cos(a),
                                center_xy[1] + .16 * math.sin(a), observation.timestamp, 1])
        if new:
            self.points = np.vstack((self.points, np.asarray(new)))
            # Keep newest observation in each 4 cm cell, limiting old map density.
            cells = np.floor(self.points[:, :2] / .04).astype(int)
            _, reverse_indices = np.unique(cells[::-1], axis=0, return_index=True)
            self.points = self.points[len(self.points) - 1 - reverse_indices]
        return np.r_[target, hazards], visible, distance

    def _path(self, steering, length):
        np = self.np
        distances = np.linspace(0, length, 25)
        curvature = math.tan(steering * self.max_steering) / self.wheelbase
        if abs(curvature) < 1e-6:
            return np.column_stack((distances, np.zeros(len(distances))))
        return np.column_stack((np.sin(distances * curvature) / curvature,
                                (1 - np.cos(distances * curvature)) / curvature))

    def act(self, observation):
        np = self.np
        self._advance_map(observation.timestamp)
        signals, visible, distance = self._perceive(observation)
        neural, active = self.circuit.decide(np.zeros_like(signals) if self.ablated else signals)
        bearing, avoidance_bias, proximity = map(float, neural)
        # Approximate image bearing decoded by the anatomical rate circuit.
        angle = bearing * math.radians(self.fov) / 2
        if visible:
            self.search_started = None
            desired = max(-1., min(1., angle * 2.8))
        else:
            if self.search_started is None:
                self.search_started = observation.timestamp
            phase = (observation.timestamp - self.search_started) % 14
            desired = self.turn * (.12 if phase < 8 else .65)
        stop = visible and distance is not None and distance <= .465
        mode = 'STOP' if stop else 'APPROACH' if visible else 'SEARCH'
        length = min(1.1, max(.01, (distance or 2) - .47))
        points = self.points[:, :2]
        candidates = []
        for steering in sorted(set(np.linspace(-1, 1, 21).tolist() + [desired])):
            path = self._path(steering, length)
            clearance = float(np.min(np.linalg.norm(path[:, None, :] - points[None, :, :], axis=2))) if len(points) else 4.
            if clearance < .28:
                continue
            # Follow neural steering when clear. Clearance breaks near ties.
            cost = abs(steering - desired) + .08 * abs(steering - self.command.steering)
            cost -= .10 * min(clearance, 1) + .12 * avoidance_bias * steering
            candidates.append((cost, steering, clearance))
        override = False
        clearance = 0.
        if stop:
            action = VehicleCommand(brake=True)
        elif not candidates:
            mode = 'BLOCKED'
            action = VehicleCommand(brake=True)
            override = True
        else:
            _, steering, clearance = min(candidates)
            override = abs(steering - desired) > .15
            if override:
                mode = 'AVOID'
                self.turn = 1 if steering >= 0 else -1
            throttle = .24 * (1 - .25 * proximity)
            if visible:
                throttle = min(throttle, max(.055, ((distance or 1) - .45) * .45))
            throttle = min(throttle, .14 + max(0, clearance - .28) * .4)
            # Account for command latency and residual motion before braking.
            stopping_distance = abs(self.speed) * .2 + self.speed ** 2 / 6 + .03
            immediate = self._path(self.command.steering, stopping_distance)
            imminent = (len(points) and float(np.min(np.linalg.norm(immediate[:, None, :] - points[None, :, :], axis=2))) < .23)
            if imminent:
                mode = 'BRAKE'
                action = VehicleCommand(brake=True)
                override = True
            else:
                action = VehicleCommand(float(steering), float(throttle))
        self.command = action
        self.debug = {'mode': mode, 'visible': visible, 'estimated_distance': distance,
                      'neural_bearing': bearing, 'neural_avoidance_bias': avoidance_bias,
                      'neural_proximity': proximity, 'active_neurons': active,
                      'local_obstacle_points': len(points), 'path_clearance': clearance,
                      'safety_override': override, 'ablated': self.ablated,
                      'biologically_validated': False}
        return action
