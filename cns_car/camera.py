"""Small RGB pinhole ray caster: room walls, ground, spheres, cylindrical obstacles.

Geometry is used only here and by the evaluator, never by a controller.
"""
import math
import struct
import zlib
from .protocol import Observation


class Camera:
    def __init__(self, width=96, height=72, fov=70):
        self.width, self.height = width, height
        self.focal = width/(2*math.tan(math.radians(fov)/2))
        self.rays = [[((x+.5-width/2)/self.focal,
                       (height/2-y-.5)/self.focal)
                      for x in range(width)] for y in range(height)]

    def observe(self, sim):
        v = sim.vehicle
        c, s = math.cos(v.heading), math.sin(v.heading)
        ox, oy, oz = v.x+0.1*c, v.y+0.1*s, 0.12
        w, h = sim.scenario.size
        tx, ty, radius = sim.scenario.target
        pixels = bytearray()
        # Horizontal intersections are reusable for all pixels in a column.
        columns = []
        for u, _ in self.rays[0]:
            dx, dy = c-u*s, s+u*c
            wall = min((w-ox)/dx if dx > 1e-9 else -ox/dx if dx < -1e-9 else math.inf,
                       (h-oy)/dy if dy > 1e-9 else -oy/dy if dy < -1e-9 else math.inf)
            cylinders = []
            a = dx*dx+dy*dy
            for bx, by, br in sim.scenario.obstacles:
                b = (ox-bx)*dx+(oy-by)*dy
                d = b*b-a*((ox-bx)**2+(oy-by)**2-br*br)
                if d >= 0:
                    near = (-b-math.sqrt(d))/a
                    if near > 0:
                        cylinders.append(near)
            columns.append((dx, dy, wall, cylinders))
        for row in self.rays:
            for x, (u, dz) in enumerate(row):
                dx, dy, wall, cylinders = columns[x]
                dist = -oz/dz if dz < -1e-9 else math.inf
                color = (72, 82, 91) if dz < 0 else (137, 163, 184)
                if wall < dist and 0 <= oz+wall*dz <= 1.5:
                    dist, color = wall, (111, 127, 141)
                for near in cylinders:
                    if near < dist and 0 <= oz+near*dz <= 0.6:
                        dist, color = near, (178, 137, 78)
                # Sphere centre is one radius above the floor.
                ax, ay, az = ox-tx, oy-ty, oz-radius
                a = dx*dx+dy*dy+dz*dz
                b = ax*dx+ay*dy+az*dz
                disc = b*b-a*(ax*ax+ay*ay+az*az-radius*radius)
                if disc >= 0:
                    near = (-b-math.sqrt(disc))/a
                    if 0 < near < dist:
                        color = (230, 35, 45)
                pixels.extend(color)
        return Observation(bytes(pixels), self.width, self.height, sim.time)


def png(obs):
    def chunk(kind, data):
        return struct.pack("!I", len(data))+kind+data+struct.pack("!I", zlib.crc32(kind+data))
    rows = b"".join(b"\0"+obs.rgb[y*obs.width*3:(y+1)*obs.width*3] for y in range(obs.height))
    return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack("!2I5B", obs.width, obs.height, 8, 2, 0, 0, 0))
            +chunk(b"IDAT", zlib.compress(rows))+chunk(b"IEND", b""))
