"""Engineering baseline; no claim to emulate the MaleCNS connectome."""
from .protocol import VehicleCommand


class BaselineController:
    def reset(self, task):
        if "red ball" not in task.lower():
            raise ValueError("Baseline supports only the red-ball task")
        self.debug = {"mode": "SEARCH", "visible": False}

    def act(self, observation):
        points = []
        rgb, width = observation.rgb, observation.width
        for i in range(0, len(rgb), 3):
            r, g, b = rgb[i:i+3]
            if r > 150 and r > 2*g and r > 2*b:
                points.append((i//3 % width, i//3//width))
        if len(points) < 2:
            self.debug = {"mode": "SEARCH", "visible": False}
            # Ackermann vehicles cannot turn in place. A slow circle scans the room.
            return VehicleCommand(1, .18)
        center = sum(x for x, _ in points)/len(points)
        error = (center-(width-1)/2)/(width/2)
        diameter = max(x for x, _ in points)-min(x for x, _ in points)+1
        fraction = diameter/width
        self.debug = {"mode": "APPROACH", "visible": True,
                      "image_error": error, "apparent_width": fraction}
        # Calibrated for the default ball and camera, not a general depth estimator.
        if fraction >= .62:
            self.debug["mode"] = "STOP"
            return VehicleCommand(brake=True)
        throttle = max(.06, min(.42, (.62-fraction)*.9))
        return VehicleCommand(max(-1, min(1, error*1.6)), throttle)


def load_controller(spec="baseline"):
    if spec == "baseline":
        controller = BaselineController()
    elif spec in ("malecns", "malecns-ablated"):
        from .malecns_controller import MaleCNSController
        controller = MaleCNSController(ablated=spec == "malecns-ablated")
    else:
        import importlib
        module, name = spec.split(":", 1)
        controller = getattr(importlib.import_module(module), name)()
    return controller
