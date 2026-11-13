"""Puts Keen's atlas stamps and panel lines on a model from a Blender build script.

    import sys; sys.path.append(<this folder>)
    import se_stamps

    se_stamps.stamp("Atlas3", "Slim Vent", at=(0, -1.25, 0.5), normal=(0, -1, 0), up=(0, 0, 1),
                    scale=0.3, material="Atlas3_Darker", collection=col)
    se_stamps.panel_line("Panel Line Creased", [(-1, -1.25, 0), (1, -1.25, 0)], normal=(0, -1, 0),
                         material="PanelingColorable", collection=col)

Coordinates are metres in the object's parent space, as the caller's other geometry. The materials must already
be in the blend, linked from SEUT's Materials.blend so that SEUT exports them as references to the game's own.
A stamp is a flat mesh, so put it on a flat face, or give panel_line a normal per point on a curved one.

A copy of the se-block-texturing skill's library, as of 2026-11-07, the version these models were built with. The stamp
coordinates in stamps/ were read from SEUT's decal library (Models/Decals/*.blend in its assets).
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Vector

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stamps")

# Metres one atlas covers at scale 1, as in SEUT's library.
ATLAS_METRES = 2.5
# Keen's overlays sit 0.3 to 3 mm off the surface on a large block. Less z-fights at a distance.
LIFT = 0.001

_catalogues = {}


def _find(atlas, name):
    if atlas not in _catalogues:
        with open(os.path.join(FOLDER, atlas + ".json")) as f:
            _catalogues[atlas] = {s["name"]: s for s in json.load(f)}
    return _catalogues[atlas][name]


def _material(name):
    found = bpy.data.materials.get(name)
    if found is None:
        raise KeyError("material %s is not in the blend: link it from Materials.blend first" % name)
    return found


def _finish(name, mesh_name, faces_build, material, collection):
    """Builds a triangulated mesh object. SEUT's route to the game takes triangles, and stamp outlines are concave."""
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    faces_build(bm, uv_layer)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(_material(material))
    obj = bpy.data.objects.new(name, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def stamp(atlas, name, at, normal, up, scale=0.3, material=None, lift=LIFT, mirror=False, collection=None):
    """Adds one stamp, its centre at `at` plus `lift` along `normal`, with the atlas's up toward `up`.

    `scale` is against SEUT's 2.5 m atlas. Keen's median for Atlas3 on large blocks is 0.3, about 0.75 m per atlas.
    """
    entry = _find(atlas, name)
    metres = ATLAS_METRES * scale
    n = Vector(normal).normalized()
    v_axis = (Vector(up) - n * Vector(up).dot(n)).normalized()
    u_axis = v_axis.cross(n)
    if mirror:
        u_axis = -u_axis
    points = [p for outline in entry["outlines"] for p in outline]
    mid_u = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    mid_v = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
    origin = Vector(at) + n * lift

    def build(bm, uv_layer):
        for outline in entry["outlines"]:
            verts = [bm.verts.new(origin + u_axis * ((u - mid_u) * metres) + v_axis * ((v - mid_v) * metres))
                     for u, v in outline]
            face = bm.faces.new(verts if not mirror else list(reversed(verts)))
            for loop in face.loops:
                index = verts.index(loop.vert)
                loop[uv_layer].uv = outline[index]

    return _finish("stamp " + name, "stamp " + name, build, material or entry["material"], collection)


def rect(material, uv, at, normal, up, size, lift=LIFT, collection=None):
    """Adds a plain quad showing `uv` (u0, v0, u1, v1), for atlas art SEUT has no stamp for. `size` is (width, height)."""
    n = Vector(normal).normalized()
    v_axis = (Vector(up) - n * Vector(up).dot(n)).normalized()
    u_axis = v_axis.cross(n)
    origin = Vector(at) + n * lift
    u0, v0, u1, v1 = uv
    corners = [(-1, -1, u0, v0), (1, -1, u1, v0), (1, 1, u1, v1), (-1, 1, u0, v1)]

    def build(bm, uv_layer):
        verts = [bm.verts.new(origin + u_axis * (x * size[0] / 2) + v_axis * (y * size[1] / 2)) for x, y, _, _ in corners]
        face = bm.faces.new(verts)
        for loop, corner in zip(face.loops, corners):
            loop[uv_layer].uv = corner[2:]

    return _finish("rect " + material, "rect " + material, build, material, collection)


def panel_line(style, points, normal, scale=0.5, material=None, closed=False, lift=LIFT, atlas="Paneling", collection=None):
    """Runs a tiling seam strip along `points`, mitred at the corners.

    `normal` is the surface's normal, or a list with one per point for a line round a curve. Keen's seams use the
    two thin styles, Creased and Rubber, at a median scale of 0.5. The strip's U tiles, so it can be any length.
    Any full-width stamp tiles this way: pass atlas="Atlas4" for its Line trims, or atlas="Atlas1" for Rubber Dark.
    """
    entry = _find(atlas, style)
    outline = entry["outlines"][0]
    v0 = min(p[1] for p in outline)
    v1 = max(p[1] for p in outline)
    half = (v1 - v0) * ATLAS_METRES * scale / 2
    count = len(points)
    pts = [Vector(p) for p in points]
    normals = [Vector(n).normalized() for n in normal] if isinstance(normal[0], (tuple, list, Vector)) else [Vector(normal).normalized()] * count

    def side(i):
        """The offset at point i: along the mitre, stretched so the strip keeps its width round the corner."""
        before = pts[(i - 1) % count] if closed or i > 0 else None
        after = pts[(i + 1) % count] if closed or i < count - 1 else None
        d_in = (pts[i] - before).normalized() if before is not None else None
        d_out = (after - pts[i]).normalized() if after is not None else None
        a = normals[i].cross(d_in or d_out).normalized()
        b = normals[i].cross(d_out or d_in).normalized()
        mitre = (a + b).normalized()
        return mitre * (half / max(mitre.dot(a), 0.3))

    def build(bm, uv_layer):
        left, right, along = [], [], [0.0]
        for i in range(count):
            offset = side(i)
            lifted = pts[i] + normals[i] * lift
            left.append(bm.verts.new(lifted + offset))
            right.append(bm.verts.new(lifted - offset))
            if i:
                along.append(along[-1] + (pts[i] - pts[i - 1]).length)
        spans = list(range(count - 1))
        if closed:
            spans.append(count - 1)
            along.append(along[-1] + (pts[0] - pts[-1]).length)
        per_metre = 1 / (ATLAS_METRES * scale)
        for i in spans:
            j = (i + 1) % count
            face = bm.faces.new((right[i], right[j], left[j], left[i]))
            u_start = along[i] * per_metre
            u_end = along[i + 1] * per_metre
            for loop, uv in zip(face.loops, ((u_start, v0), (u_end, v0), (u_end, v1), (u_start, v1))):
                loop[uv_layer].uv = uv

    return _finish("line " + style, "line " + style, build, material or entry["material"], collection)


def circle_points(centre, radius, normal, count=48):
    """Returns the points of a circle for a closed panel_line."""
    n = Vector(normal).normalized()
    a = n.orthogonal().normalized()
    b = n.cross(a)
    return [Vector(centre) + (a * math.cos(i * math.tau / count) + b * math.sin(i * math.tau / count)) * radius
            for i in range(count)]
