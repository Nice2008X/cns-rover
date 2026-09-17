"""100 Hz kinematic bicycle dynamics, 10 Hz observations, simulated-time watchdog."""
from dataclasses import dataclass, asdict
import math
from .protocol import VehicleCommand
from .scenario import Scenario


@dataclass
class Vehicle:
    x: float
    y: float
    heading: float  # radians; clockwise in screen/world coordinates, y points down
    speed: float = 0.0
    steering: float = 0.0  # radians


def approach(value, target, delta):
    return value + max(-delta, min(delta, target-value))


class Simulator:
    dt = 0.01
    camera_steps = 10
    wheelbase = 0.20
    radius = 0.20  # conservative circular collision envelope at rear axle
    max_steering = math.radians(30)
    watchdog = 0.5

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        x, y, heading = scenario.start
        self.vehicle = Vehicle(x, y, math.radians(heading))
        self.steps = 0
        self.command = VehicleCommand(brake=True)
        self.last_command = -math.inf
        self.emergency = False
        self.status = "running"
        self.reason = None
        self.distance = 0.0
        self.collisions = 0
        self.decisions = 0
        self.reversals = 0
        self.last_direction = 0
        self.max_speed = 0.0
        self.steering_variation = 0.0
        self.stopped_for = 0.0

    @property
    def time(self):
        return self.steps*self.dt

    @property
    def target_distance(self):
        return math.hypot(self.vehicle.x-self.scenario.target[0],
                          self.vehicle.y-self.scenario.target[1])

    def submit(self, command):
        if not isinstance(command, VehicleCommand):
            raise TypeError("Controller must return VehicleCommand")
        self.command = command.limited()
        self.last_command = self.time
        self.decisions += 1

    def stop(self, reason="emergency_stop"):
        self.emergency = True
        self.command = VehicleCommand(brake=True)
        self.vehicle.speed = 0.0
        self.status = "failed"
        self.reason = reason

    def collides(self, x, y):
        r = self.radius
        w, h = self.scenario.size
        if not (r <= x <= w-r and r <= y <= h-r):
            return True
        return any(math.hypot(x-ox, y-oy) <= r+radius
                   for ox, oy, radius in [self.scenario.target]+self.scenario.obstacles)

    def step(self):
        if self.status != "running":
            return
        v = self.vehicle
        cmd = self.command
        stale = self.time-self.last_command >= self.watchdog
        # First-order actuator response plus explicit acceleration/servo slew limits.
        desired_steer = cmd.steering*self.max_steering
        old_steer = v.steering
        v.steering = approach(v.steering, desired_steer,
            min(math.radians(240)*self.dt, abs(desired_steer-v.steering)*self.dt/0.08))
        self.steering_variation += abs(v.steering-old_steer)
        brake = stale or cmd.brake or self.emergency
        target_speed = 0 if brake else cmd.throttle*(1.5 if cmd.throttle >= 0 else 0.7)
        slowing = brake or v.speed*target_speed < 0 or abs(target_speed) < abs(v.speed)
        accel = 3.0 if slowing else 1.5
        v.speed = approach(v.speed, target_speed, min(accel*self.dt,
            abs(target_speed-v.speed)*self.dt/0.10))
        omega = v.speed/self.wheelbase*math.tan(v.steering)
        mid = v.heading+omega*self.dt/2
        nx = v.x+v.speed*math.cos(mid)*self.dt
        ny = v.y+v.speed*math.sin(mid)*self.dt
        self.steps += 1
        if self.collides(nx, ny):
            self.collisions += 1
            self.stop("collision")
            return
        self.distance += math.hypot(nx-v.x, ny-v.y)
        v.x, v.y = nx, ny
        v.heading = (v.heading+omega*self.dt+math.pi) % (2*math.pi)-math.pi
        self.max_speed = max(self.max_speed, abs(v.speed))
        direction = 1 if v.speed > .03 else -1 if v.speed < -.03 else 0
        if direction:
            if self.last_direction and direction != self.last_direction:
                self.reversals += 1
            self.last_direction = direction
        if self.target_distance <= self.scenario.success_distance and abs(v.speed) <= self.scenario.stop_speed:
            self.stopped_for += self.dt
        else:
            self.stopped_for = 0
        if self.stopped_for+1e-9 >= self.scenario.stop_duration:
            self.status, self.reason = "success", "target_reached_and_stopped"
            self.vehicle.speed = 0
        elif self.time+1e-9 >= self.scenario.timeout:
            self.stop("timeout")

    def result(self):
        return dict(status=self.status, reason=self.reason, time=round(self.time, 6),
                    distance=self.distance, collisions=self.collisions, decisions=self.decisions,
                    reversals=self.reversals, maximum_speed=self.max_speed,
                    average_speed=self.distance/max(self.time, self.dt),
                    steering_variation=self.steering_variation,
                    final_target_distance=self.target_distance)

    def state(self):
        return dict(vehicle=asdict(self.vehicle), scenario=self.scenario.to_dict(),
                    result=self.result(), command=asdict(self.command))
