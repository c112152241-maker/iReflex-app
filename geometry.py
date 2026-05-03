import math
from typing import Tuple


Point = Tuple[float, float]


def calculate_angle(p1: Point, p2: Point, p3: Point) -> float:
    """
    計算三點夾角，p2 是中間點。
    例如 hip-knee-ankle，p2=knee。
    """

    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3

    v1 = (x1 - x2, y1 - y2)
    v2 = (x3 - x2, y3 - y2)

    dot = v1[0] * v2[0] + v1[1] * v2[1]

    norm1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    norm2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    cos_theta = dot / (norm1 * norm2)
    cos_theta = max(-1.0, min(1.0, cos_theta))

    angle = math.degrees(math.acos(cos_theta))

    return float(angle)