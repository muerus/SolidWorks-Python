"""Units. Everything in swpy is SI internally (metres, radians, kg) - the SOLIDWORKS API is too.

    50 * mm          -> 0.05
    to(0.05, mm)     -> 50.0
"""
import math

m = 1.0
cm = 0.01
mm = 0.001
um = 1e-6
inch = 0.0254
ft = 0.3048
rad = 1.0
deg = math.pi / 180.0
kg = 1.0
g = 0.001
lb = 0.45359237

# unit suffixes accepted in SOLIDWORKS equations -> SI factor
EQUATION_UNITS = {"mm": mm, "cm": cm, "m": m, "in": inch, "ft": ft, "deg": deg, "rad": rad, "um": um}


def to(value, unit):
    """Convert an SI value to `unit`:  to(0.05, mm) -> 50.0"""
    return value / unit
