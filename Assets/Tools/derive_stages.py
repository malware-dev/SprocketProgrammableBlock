"""Derives LOD and build-stage models from a finished SEUT blend, as if an artist had handed it over.

    blender.exe <finished>.blend --python derive_stages.py [-- --stages <list> --out <folder>]

Run windowed (not -b): SEUT's export needs a 3D viewport. The blend itself is left alone; the
result is saved in the output folder (Derived/ beside the blend unless given) as <blend>Derived.blend and
exported to its Content folder. The build stages come from stages.txt beside the blend unless given.

    blender.exe -b <finished>.blend --python derive_stages.py -- --list-parts

lists the parts as the stage list names them, and does nothing else.

Nothing here knows how the models were made. It looks only at what is in each scene's main collection:
object sizes, materials and the meshes themselves. An object made of several loose pieces is taken apart
into them, named <object>/<n>, numbered from the bottom up and then around.

LODs (every scene, main and subparts), each made fresh from the full model:
  - parts too small to read at the LOD's distance are dropped, by the area of their largest side, and thin
    relief (trims, grooves, plates a few millimetres proud) goes sooner than solid parts. Lights and screens
    are kept longer, and a model's biggest parts are never dropped;
  - bevelled boxes become plain boxes, keeping their texture scale, or their atlas region;
  - other detailed parts (cylinders) are decimated;
  - every face that cannot be seen from anywhere at the LOD's distance is deleted, found by casting rays to
    viewpoints all around the block. Subparts are left out of the test, so a doorway counts as open;
  - what is left is joined into one mesh.

Build stages (main scenes only) are not derived: they take judgement about what a part is and the order
things are built in, which sizes and materials do not tell. They are chosen by a person (or by Claude, looking
at the model) in a stage list, and only built here: a "frame" line makes thin beams along a part's edges with
a cross over its top, parts cut off at a height have the cut closed, and each stage gets a LOD1 by the rules
above. As in the game's own blocks, every stage is painted in the Construction material, unless
--real-materials is given.

A copy of the se-block-stages skill's script, as of 2026-11-07 14:23, the version these models' LODs and build stages
were derived with.
"""

import fnmatch
import math
import os
import shutil
import sys
import time
import traceback

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

SEUT = "space-engineers-utilities"
seut_collections = sys.modules[SEUT + ".seut_collections"]

HERE = os.path.dirname(bpy.path.abspath(bpy.data.filepath))   # the blend's folder: defaults sit beside it


def option(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


OUTPUT = option("--out", os.path.join(HERE, "Derived"))
CONTENT = os.path.join(OUTPUT, "Content")
EXPORT = os.path.join(CONTENT, "Models", "Cubes", "large")
EXPORT_SMALL = os.path.join(CONTENT, "Models", "Cubes", "small")
BLEND = os.path.join(OUTPUT, os.path.splitext(os.path.basename(bpy.data.filepath))[0] + "Derived.blend")
LOG = os.path.join(OUTPUT, "derive_stages.log")


class Lod:
    """How much one LOD keeps. Areas are of a part's largest side, in square metres."""

    def __init__(self, index, distance, min_area, relief_depth, relief_area, lit_area, ratio):
        self.index = index
        self.distance = distance
        self.min_area = min_area            # smaller parts are dropped
        self.relief_depth = relief_depth    # parts thinner than this...
        self.relief_area = relief_area      # ...and smaller than this are dropped too
        self.lit_area = lit_area            # lights and screens are kept down to this
        self.ratio = ratio                  # the most a detailed part is decimated to, if its shape allows

    def at(self, distance):
        """This LOD moved to another distance: what reads on screen shrinks with distance, so the areas
        scale with its square and the depths with it."""
        k = distance / self.distance
        return Lod(self.index, distance, self.min_area * k * k, self.relief_depth * k, self.relief_area * k * k,
                   self.lit_area * k * k, self.ratio)

    @property
    def tolerance(self):
        """How far a decimated part may stray from the original: PIXELS of a 1080p screen at this distance."""
        return PIXELS * 2 * self.distance * math.tan(math.radians(35)) / 1080


LODS = [
    Lod(1, 25, 0.01, 0.007, 0.10, 0.001, 0.5),
    Lod(2, 50, 0.05, 0.020, 0.30, 0.010, 0.25),
    Lod(3, 100, 0.25, 0.030, 0.30, 0.030, 0.12),
]

KEEP_SHARE = 0.25       # parts at least this share of a model's largest part's area are never dropped
VIEWS = 400             # viewpoints around the block for the visibility test
PIXELS = 1.5            # how far, in screen pixels at a LOD's distance, decimation may move a part's surface
RATIOS = (0.12, 0.18, 0.25, 0.35, 0.5, 0.7, 0.85)   # decimation ratios tried, the strongest first
STAGES_FILE = option("--stages", os.path.join(HERE, "stages.txt"))   # the build stages, chosen by a person
BEVEL = 0.03            # a box whose corners are all this close to its surface has only bevels to lose
FRAME = "frame"         # a stage list entry built as a frame of beams, not as the part
CAGE = "cage"           # a stage list entry: a designed frame around the whole block
BOX = "box"             # a stage list entry: one designed member, an axis-aligned box
RING = "ring"           # a stage list entry: a level regular polygon loop, for framing round parts
LOOP = "loop"           # a stage list entry: a level loop of members round any convex outline
STRUT = "strut"         # a stage list entry: a square member between two points
LODS_LINE = "lods"      # a stage list entry: the scene's LOD distances
DESIGNED = (CAGE, BOX, RING, LOOP, STRUT)   # entries that build members of their own rather than show a part
CAGE_BEAM = 0.06        # a cage's posts and beams; its floor braces are three quarters of it
FRAME_BEAM = 0.04       # a frame beam's thickness
FRAME_EDGE = math.radians(30)   # edges sharper than this get a beam
FRAME_MIN = 0.1         # straight runs of edge shorter than this get none: a frame outlines, it does not trace
CONSTRUCTION = None if "--real-materials" in sys.argv else "Construction"   # what build stages are painted in

# With --tint-lods, every LOD is painted one loud colour by its number, so the game's switching between them
# can be seen. Only for testing: the tinted models replace the real ones in Derived/.
TINT = {1: "PaintedMetal_Yellow", 2: "PlasticPink", 3: "PlasticWhite"} if "--tint-lods" in sys.argv else None
if TINT:
    # Close enough to see each switch with a short walk, whatever the game scales the distances by.
    for lod, distance in zip(LODS, (5, 10, 20)):
        lod.distance = distance


def log(line):
    print(line)
    if os.path.isdir(OUTPUT):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# --- Looking at a part ---------------------------------------------------------------------------

class Part:
    """A piece of a model, measured in the scene's coordinates: a mesh object, or one loose piece of it."""

    def __init__(self, obj, name, faces=None, placement=None):
        self.obj = obj
        self.name = name
        self.face_ids = faces
        # A subpart's parts are placed where its empty puts them in the main scene.
        self.matrix = obj.matrix_world if placement is None else placement @ obj.matrix_world
        mesh = obj.data
        polygons = list(mesh.polygons) if faces is None else [mesh.polygons[i] for i in faces]
        verts = {i for poly in polygons for i in poly.vertices}
        points = [self.matrix @ mesh.vertices[i].co for i in verts]
        self.low = Vector([min(p[i] for p in points) for i in range(3)])
        self.high = Vector([max(p[i] for p in points) for i in range(3)])
        self.centre = (self.low + self.high) / 2
        size = self.high - self.low
        self.size = size
        d = sorted(size)
        self.thin, self.middle, self.long = d
        self.area = self.long * self.middle
        # The object's material slots, empty ones as None, so face material indices keep pointing right.
        self.materials = [slot.material.name if slot.material else None for slot in obj.material_slots]
        used = {self.materials[poly.material_index] for poly in polygons if poly.material_index < len(self.materials)}
        self.used = sorted(m for m in used if m)
        # Lights, screens and keypads glow, so they read from further away than their size suggests.
        self.lit = any(m.startswith("Emissive") or "Screen" in m or m == "Terminal" for m in self.used)
        self.faces = len(polygons)


def parts_of(obj, placement=None, prefix=""):
    """An object as parts: itself, or its loose pieces when it has several. A subpart's objects are given the
    placement of its empty and their names a prefix."""
    mesh = obj.data
    if obj.type != "MESH" or not mesh.polygons:
        return []
    root = list(range(len(mesh.vertices)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    for poly in mesh.polygons:
        first = find(poly.vertices[0])
        for v in poly.vertices[1:]:
            root[find(v)] = first
    groups = {}
    for poly in mesh.polygons:
        groups.setdefault(find(poly.vertices[0]), []).append(poly.index)
    if len(groups) == 1:
        return [Part(obj, prefix + obj.name, placement=placement)]
    pieces = [Part(obj, None, faces, placement) for faces in groups.values()]
    pieces.sort(key=lambda p: (round(p.centre.z, 2), round(math.atan2(p.centre.y, p.centre.x), 2), round(p.centre.x, 2)))
    for i, piece in enumerate(pieces):
        piece.name = "%s%s/%d" % (prefix, obj.name, i + 1)
    return pieces


def subpart_parts(scene, main):
    """The parts of every subpart the main collection places, named <subpart>:<part>, where its empty puts
    them. A build stage can show a subpart's parts as fixed geometry: subparts themselves do not exist in
    build stages."""
    placed = []
    for empty in main.objects:
        name = empty.get("file")
        if empty.type != "EMPTY" or not empty.name.startswith("subpart_") or name not in bpy.data.scenes:
            continue
        sub_main = seut_collections.get_cols_by_type(bpy.data.scenes[name], "main")[0]
        # Blender numbers a second empty of the same name (subpart_Disk.001); the subpart's name is without it.
        prefix = empty.name[len("subpart_"):].split(".")[0] + ":"
        for o in sub_main.objects:
            placed.extend(parts_of(o, empty.matrix_world, prefix))
    return placed


def world_bmesh(part):
    bm = bmesh.new()
    bm.from_mesh(part.obj.data)
    if part.face_ids is not None:
        keep = set(part.face_ids)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.transform(bm, matrix=part.matrix, verts=bm.verts)
    bm.normal_update()
    return bm


def uv_area(face, uv):
    pts = [l[uv].uv for l in face.loops]
    return abs(sum(pts[i].x * pts[i - 1].y - pts[i - 1].x * pts[i].y for i in range(len(pts)))) / 2


def texture_mapping(bm):
    """How a part's faces are textured: ('atlas', (u0, v0, u1, v1)) when every face is fitted into the same
    part of the texture, or ('tiled', uv units per metre)."""
    uv = bm.loops.layers.uv.active
    regions = []
    ratios = []
    for f in bm.faces:
        us = [l[uv].uv.x for l in f.loops]
        vs = [l[uv].uv.y for l in f.loops]
        regions.append((min(us), min(vs), max(us), max(vs)))
        area = f.calc_area()
        a = uv_area(f, uv)
        if area > 1e-6 and a > 0:
            ratios.append(math.sqrt(a / area))
    first = regions[0]
    if all(max(abs(r[i] - first[i]) for i in range(4)) < 1e-4 for r in regions):
        return ("atlas", first)
    ratios.sort()
    return ("tiled", ratios[len(ratios) // 2] if ratios else 0.4)


def map_faces(bm, faces, mapping):
    """Gives faces UVs in the manner of a part's mapping: box-projected at its scale, or fitted to its region."""
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    kind, value = mapping
    for f in faces:
        n = f.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        a, b = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
        coords = [(l.vert.co[a], l.vert.co[b]) for l in f.loops]
        if kind == "tiled":
            for loop, (x, y) in zip(f.loops, coords):
                loop[uv].uv = (x * value, y * value)
            continue
        x0, x1 = min(c[0] for c in coords), max(c[0] for c in coords)
        y0, y1 = min(c[1] for c in coords), max(c[1] for c in coords)
        for loop, (x, y) in zip(f.loops, coords):
            fx = (x - x0) / (x1 - x0) if x1 > x0 else 0.5
            fy = (y - y0) / (y1 - y0) if y1 > y0 else 0.5
            loop[uv].uv = (value[0] + fx * (value[2] - value[0]), value[1] + fy * (value[3] - value[1]))


def boxlike(part, bm):
    """A bevelled box: a closed part of one material, with more than a box's corners, that fills nearly all of
    its bounding box and reaches within BEVEL of each of its corners. Larger chamfers and notches are shape,
    not bevels, and are kept."""
    if len(bm.verts) <= 8 or len(part.used) != 1 or not all(e.is_manifold for e in bm.edges):
        return False
    volume = part.size.x * part.size.y * part.size.z
    if volume <= 0 or abs(bm.calc_volume()) / volume < 0.85:
        return False
    # Every vertex near the box's surface: a recess (an inset block's well) fills little volume but is shape.
    for v in bm.verts:
        if min(min(v.co[i] - part.low[i], part.high[i] - v.co[i]) for i in range(3)) > BEVEL:
            return False
    tree = BVHTree.FromBMesh(bm)
    for corner in range(8):
        point = Vector([part.high[i] if corner >> i & 1 else part.low[i] for i in range(3)])
        nearest = tree.find_nearest(point)
        if nearest[0] is None or nearest[3] > BEVEL:
            return False
    return True


def plain_box(part, src):
    mapping = texture_mapping(src)
    material = next(iter(src.faces)).material_index
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=part.size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=(part.low + part.high) / 2, verts=bm.verts)
    bm.normal_update()
    bm.loops.layers.uv.new(src.loops.layers.uv.active.name)
    map_faces(bm, bm.faces, mapping)
    for f in bm.faces:
        f.material_index = material
    return bm


def triangles_by_face(bm):
    """Each face's triangles, as corner positions. A face's own middle is no use for sampling it: on a face
    with a hole, such as a ring's flat top, it lies in the hole."""
    by_face = {}
    for tri in bm.calc_loop_triangles():
        by_face.setdefault(tri[0].face, []).append([loop.vert.co for loop in tri])
    return by_face


def surface_error(a, b):
    """The furthest the surface of either mesh strays from the other's, sampled over every triangle; infinite
    when any face of b is turned against a's surface there, as decimation sometimes turns faces inside out."""
    a.normal_update()
    b.normal_update()
    worst = 0.0
    for one, other in ((a, b), (b, a)):
        tree = BVHTree.FromBMesh(other)
        for face, tris in triangles_by_face(one).items():
            for point in [v.co for v in face.verts] + samples(tris):
                nearest = tree.find_nearest(point)
                if nearest[0] is None:
                    return float("inf")
                if one is b and nearest[3] < 0.01 and face.normal.dot(nearest[1]) < -0.5:
                    return float("inf")
                worst = max(worst, nearest[3])
    return worst


def sharpen(bm, angle=math.radians(35)):
    """Marks edges sharper than angle as sharp, as the original's were, so decimation does not smooth its
    shading across corners."""
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > angle:
            e.smooth = False


def simplified(src, lod, scene):
    """The part decimated as far as the LOD's ratio allows while its surface stays within the LOD's tolerance;
    the part itself when no decimation does."""
    for ratio in RATIOS:
        if ratio < lod.ratio:
            continue
        bm = decimated(src, ratio, scene)
        if surface_error(src, bm) <= lod.tolerance:
            sharpen(bm)
            return bm
        bm.free()
    return src


def decimated(src, ratio, scene):
    """The part's mesh through a collapse decimation, evaluated on a scratch object in the scene. The scene's
    own view layer evaluates it: the context's may belong to another scene, which knows nothing of the object
    and hands back stale data."""
    mesh = bpy.data.meshes.new("DeriveScratch")
    src.to_mesh(mesh)
    obj = bpy.data.objects.new("DeriveScratch", mesh)
    scene.collection.objects.link(obj)
    modifier = obj.modifiers.new("Decimate", "DECIMATE")
    modifier.ratio = ratio
    depsgraph = scene.view_layers[0].depsgraph
    depsgraph.update()
    evaluated = obj.evaluated_get(depsgraph)
    if evaluated.data is mesh:
        raise RuntimeError("the decimation was not evaluated")
    out = bmesh.new()
    out.from_mesh(evaluated.to_mesh())
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    return out


# --- Joining parts into one mesh -------------------------------------------------------------------

class Joined:
    """One mesh built from many parts, with their materials gathered into one list."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.materials = []

    def add(self, src, materials):
        uv = src.loops.layers.uv.active
        index = []
        for m in materials:
            if m not in self.materials:
                self.materials.append(m)
            index.append(self.materials.index(m))
        verts = {v: self.bm.verts.new(v.co) for v in src.verts}
        for f in src.faces:
            try:
                face = self.bm.faces.new([verts[v] for v in f.verts])
            except ValueError:
                continue
            face.material_index = index[f.material_index] if f.material_index < len(index) else index[0]
            face.smooth = f.smooth
            for new, old in zip(face.loops, f.loops):
                new[self.uv].uv = old[uv].uv if uv is not None else (0, 0)
        for e in src.edges:
            edge = self.bm.edges.get([verts[v] for v in e.verts])
            if edge is not None:
                edge.smooth = e.smooth

    def finish(self, name, collection):
        if len(self.bm.faces) == 0:
            self.bm.free()
            return None
        mesh = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.materials:
            mesh.materials.append(bpy.data.materials[m] if m else None)
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        return obj


def triangles(obj):
    return 0 if obj is None else sum(len(p.vertices) - 2 for p in obj.data.polygons)


# --- Seeing what can be seen ------------------------------------------------------------------------

def sphere(count):
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(count):
        z = 1 - 2 * (i + 0.5) / count
        r = math.sqrt(1 - z * z)
        yield Vector((math.cos(golden * i) * r, math.sin(golden * i) * r, z))


def samples(tris):
    """Points spread over a face, from its triangles: each one's middle and points near its corners, and a
    grid over large ones. Up to 40, the triangles' middles first."""
    middles = []
    corners = []
    grid = []
    for a, b, c in tris:
        m = (a + b + c) / 3
        middles.append(m)
        corners.extend(m.lerp(v, 0.92) for v in (a, b, c))
        k = min(4, int(math.ceil(math.sqrt((b - a).cross(c - a).length / 2 / 0.02))))
        for i in range(1, k):
            for j in range(1, k - i):
                grid.append(a + (b - a) * (i / k) + (c - a) * (j / k))
    return (middles + corners + grid)[:40]


def cull_hidden(bm, distance):
    """Deletes every face no viewpoint at this distance can see. A face is seen when a ray from a point on it
    reaches a viewpoint in front of it; faces turned away from the ray do not block it, as the game draws
    one side only."""
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    normals = [f.normal.copy() for f in bm.faces]
    by_face = triangles_by_face(bm)
    views = [d * distance for d in sphere(VIEWS)]
    hidden = []
    for f in bm.faces:
        n = f.normal
        c = f.calc_center_median()
        points = None
        seen = False
        for p in views:
            if (p - c).dot(n) <= 0:
                continue
            if points is None:
                points = samples(by_face.get(f, []))
            for s in points:
                if reaches(tree, normals, s + n * 2e-4, p):
                    seen = True
                    break
            if seen:
                break
        if not seen:
            hidden.append(f)
    bmesh.ops.delete(bm, geom=hidden, context="FACES")
    return len(hidden)


def reaches(tree, normals, origin, target):
    for _ in range(16):
        d = target - origin
        length = d.length
        d /= length
        hit, _, index, along = tree.ray_cast(origin, d, length)
        if hit is None:
            return True
        if normals[index].dot(d) <= 0:
            return False
        origin = hit + d * 1e-4
    return False


# --- LODs and build stages ----------------------------------------------------------------------------

def make_lod(parts, lod, scene, collection, name, cull=True, extra=(), material=None):
    """A LOD of parts, with extra (part, bmesh) pairs added as they are, all painted material if given."""
    largest = max([p.area for p in parts] or [0])
    joined = Joined()
    kept = 0
    for part in parts:
        keep_always = part.area >= KEEP_SHARE * largest
        if not keep_always:
            if part.lit:
                if part.area < lod.lit_area:
                    continue
            elif part.area < lod.min_area or (part.thin < lod.relief_depth and part.area < lod.relief_area):
                continue
        src = world_bmesh(part)
        if boxlike(part, src):
            bm = plain_box(part, src)
            src.free()
        elif part.faces > 14:
            bm = simplified(src, lod, scene)
            if bm is not src:
                src.free()
        else:
            bm = src
        joined.add(bm, part.materials)
        bm.free()
        kept += 1
    for part, bm in extra:
        joined.add(bm, part.materials)
        bm.free()
    culled = cull_hidden(joined.bm, lod.distance) if cull else 0
    if material:
        paint(joined, material)
    if TINT:
        joined.materials = [TINT[lod.index]]
        for f in joined.bm.faces:
            f.material_index = 0
    obj = joined.finish(name, collection)
    log("  %s: %d of %d parts, %d faces culled, %d triangles" % (name, kept, len(parts), culled, triangles(obj)))
    return obj


def clipped(part, height):
    """A part cut off at a height, its cut closed with a cap textured like the rest of it."""
    src = world_bmesh(part)
    mapping = texture_mapping(src)
    material = next(iter(src.faces)).material_index
    geom = src.verts[:] + src.edges[:] + src.faces[:]
    bmesh.ops.bisect_plane(src, geom=geom, plane_co=(0, 0, height), plane_no=(0, 0, 1), clear_outer=True)
    boundary = [e for e in src.edges if e.is_boundary]
    if boundary:
        caps = bmesh.ops.holes_fill(src, edges=boundary, sides=0)["faces"]
        src.normal_update()
        for f in caps:
            f.smooth = False
            f.material_index = material
        map_faces(src, caps, mapping)
    return src


def read_stages(path):
    """The build stages a person chose, from a list (see stages.txt): for each scene, a list of stages, each
    (title, [(pattern, height or None)]), and for each scene that names them, its LOD distances. Each stage adds
    to the one before it."""
    scenes = {}
    distances = {}
    stages = None
    scene = None
    if not os.path.exists(path):
        return scenes, distances
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("scene "):
                scene = line[6:].strip()
                stages = scenes.setdefault(scene, [])
            elif line.startswith(LODS_LINE + " "):
                distances[scene] = [float(v) for v in line[len(LODS_LINE):].split()]
                if len(distances[scene]) != len(LODS):
                    raise ValueError("%s: lods needs %d distances" % (scene, len(LODS)))
            elif line.startswith(RING + " "):
                stages[-1][1].append((RING, tuple(float(v) for v in line[len(RING):].split())))
            elif line.startswith(LOOP + " "):
                words = line[len(LOOP):].split()
                axis = words.pop(0) if words[0] in AXES else "z"
                stages[-1][1].append((LOOP, (axis, tuple(float(v) for v in words))))
            elif line.startswith(STRUT + " "):
                stages[-1][1].append((STRUT, tuple(float(v) for v in line[len(STRUT):].split())))
            elif line.startswith("["):
                stages.append((line[line.index("]") + 1:].strip(), []))
            elif line.startswith("frame "):
                stages[-1][1].append((line[6:].strip(), FRAME))
            elif line == CAGE or line.startswith(CAGE + " "):
                size = line[len(CAGE):].split()
                stages[-1][1].append((CAGE, float(size[0]) if size else CAGE_BEAM))
            elif line.startswith(BOX + " "):
                stages[-1][1].append((BOX, tuple(float(v) for v in line[len(BOX):].split())))
            else:
                pattern, _, height = line.partition("@")
                stages[-1][1].append((pattern.strip(), float(height) if height.strip() else None))
    return scenes, distances


def stage_contents(parts, stages, index):
    """What build stage index (from 0) holds: each part with the height it is built to, None for whole, or
    FRAME. A later stage's entry for a part replaces an earlier one's, so a frame can become the part."""
    built = {}
    for title, entries in stages[:index + 1]:
        for pattern, height in entries:
            if pattern in DESIGNED:
                continue
            matched = [p for p in parts if fnmatch.fnmatchcase(p.name, pattern)]
            if not matched:
                log("  warning: %r matches no part" % pattern)
            for part in matched:
                built[part] = height
    return built


def block(bm, low, high):
    """An axis-aligned box from low to high, capped all round."""
    size = high - low
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((low + high) / 2) @ Matrix.Diagonal((*size, 1.0)))


def bar(bm, a, b, width, height):
    """A bar of exactly the length from a to b, capped, with its sides upright and its top level."""
    d = (b - a).normalized()
    side = Vector((0, 0, 1)).cross(d).normalized()
    up = d.cross(side)
    turn = Matrix((d, side, up)).transposed().to_4x4()
    scale = Matrix.Diagonal(((b - a).length, width, height, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((a + b) / 2) @ turn @ scale)


def cage(bm, low, high, w):
    """A frame around a box, built like fabricated steelwork: corner posts the full height, flush with the
    box's faces; beams top and bottom cut to butt square against the posts; and a cross over the floor of
    slimmer braces set within the beams' depth, so no two faces overlap in one plane. One brace runs corner to
    corner; the other is two halves butting square against its sides. Brace ends are lost inside the posts."""
    for x in (low.x, high.x - w):
        for y in (low.y, high.y - w):
            block(bm, Vector((x, y, low.z)), Vector((x + w, y + w, high.z)))
    for z in (low.z, high.z - w):
        for y in (low.y, high.y - w):
            block(bm, Vector((low.x + w, y, z)), Vector((high.x - w, y + w, z + w)))
        for x in (low.x, high.x - w):
            block(bm, Vector((x, low.y + w, z)), Vector((x + w, high.y - w, z + w)))
    d = 0.75 * w
    z = low.z + w / 2
    c1, c3 = Vector((low.x + w / 2, low.y + w / 2, z)), Vector((high.x - w / 2, high.y - w / 2, z))
    c2, c4 = Vector((high.x - w / 2, low.y + w / 2, z)), Vector((low.x + w / 2, high.y - w / 2, z))
    bar(bm, c1, c3, d, d)
    middle = (c2 + c4) / 2
    for end in (c2, c4):
        bar(bm, end, middle - (middle - end).normalized() * d / 2, d, d)


AXES = {"x": lambda a, b, h: Vector((h, a, b)), "y": lambda a, b, h: Vector((a, h, b)),
        "z": lambda a, b, h: Vector((a, b, h))}   # a loop's plane: (a, b) in it, h along the axis


def loop(bm, z, w, outline, axis="z"):
    """A closed loop of straight members, square in section w and centred on z along axis, mitred at the
    corners into one tube. Its outer faces are flush with outline, a convex polygon of points in the other two
    coordinates (x y for axis z, x z for y, y z for x), and it lies inside it."""
    first = len(bm.verts)
    _loop(bm, z, w, outline)
    bm.verts.ensure_lookup_table()
    for v in bm.verts[first:]:
        v.co = AXES[axis](v.co.x, v.co.y, v.co.z)


def _loop(bm, z, w, outline):
    points = [Vector((x, y, 0)) for x, y in outline]
    if sum(a.x * b.y - b.x * a.y for a, b in zip(points, points[1:] + points[:1])) < 0:
        points.reverse()   # counter-clockwise, so each edge's outward side is to its right
    corners = []
    for i, p in enumerate(points):
        d0 = (p - points[i - 1]).normalized()
        d1 = (points[(i + 1) % len(points)] - p).normalized()
        n0, n1 = Vector((d0.y, -d0.x, 0)), Vector((d1.y, -d1.x, 0))
        mitre = (n0 + n1).normalized()
        inward = -mitre * (w / mitre.dot(n0))
        corners.append([bm.verts.new(p + Vector((0, 0, z)) + offset)
                        for offset in (inward + Vector((0, 0, -w / 2)), Vector((0, 0, -w / 2)),
                                       Vector((0, 0, w / 2)), inward + Vector((0, 0, w / 2)))])
    for i in range(len(points)):
        a, b = corners[i], corners[(i + 1) % len(points)]
        for k in range(4):
            bm.faces.new((a[k], b[k], b[(k + 1) % 4], a[(k + 1) % 4]))


def ring(bm, centre, radius, sides, w):
    """A loop round a regular polygon of sides, its outer faces radius from centre, one face towards +X."""
    step = 2 * math.pi / sides
    reach = radius / math.cos(step / 2)
    outline = [(centre.x + reach * math.cos(step * (i + 0.5)), centre.y + reach * math.sin(step * (i + 0.5)))
               for i in range(sides)]
    loop(bm, centre.z, w, outline)


def strut(bm, a, b, w):
    """A capped member of square section w from a to b."""
    d = b - a
    if abs(d.normalized().z) > 0.999:
        block(bm, Vector((a.x - w / 2, a.y - w / 2, min(a.z, b.z))), Vector((a.x + w / 2, a.y + w / 2, max(a.z, b.z))))
    else:
        bar(bm, a, b, w, w)


def members_part(built):
    """What designed members are painted in: Construction, or the first material of the model."""
    if CONSTRUCTION:
        return Designed(CONSTRUCTION)
    first = next((m for part in built for m in part.materials if m), None)
    return Designed(first)


class Designed:
    """Stands in for a part in what is joined: designed members have no part of their own."""

    def __init__(self, material):
        self.materials = [material]


def designed(entries, parts):
    """The designed members a stage lists (cage, boxes) as one mesh, or None. They belong to that stage
    alone: a later stage's real parts take their place."""
    members = [(kind, value) for kind, value in entries if kind in DESIGNED]
    if not members:
        return None
    low = Vector([min(p.low[i] for p in parts) for i in range(3)])
    high = Vector([max(p.high[i] for p in parts) for i in range(3)])
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    for kind, value in members:
        if kind == CAGE:
            cage(bm, low, high, value)
        elif kind == RING:
            ring(bm, Vector(value[:3]), value[3], int(value[4]), value[5])
        elif kind == LOOP:
            axis, numbers = value
            loop(bm, numbers[0], numbers[1], list(zip(numbers[2::2], numbers[3::2])), axis)
        elif kind == STRUT:
            strut(bm, Vector(value[:3]), Vector(value[3:6]), value[6])
        else:
            block(bm, Vector(value[:3]), Vector(value[3:]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    map_faces(bm, bm.faces, ("tiled", 0.4))
    for f in bm.faces:
        f.material_index = 0
    return bm


def beam(bm, a, b, size):
    """A square beam from a to b, its ends overlapping by half its thickness so corners close. It has no end
    caps: the joints hide them, and four sides are 8 triangles instead of 12."""
    d = b - a
    length = d.length
    if length < 1e-4:
        return
    verts = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    caps = [f for f in {f for v in verts for f in v.link_faces} if abs(f.normal.z) > 0.9]
    bmesh.ops.delete(bm, geom=caps, context="FACES_ONLY")
    bmesh.ops.scale(bm, vec=(size, size, length + size), verts=verts)
    rotation = Vector((0, 0, 1)).rotation_difference(d / length).to_matrix()
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=rotation, verts=verts)
    bmesh.ops.translate(bm, vec=(a + b) / 2, verts=verts)


def straight_runs(edges):
    """Edges joined into straight runs: through every vertex where exactly two of them meet in a line."""
    meeting = {}
    for e in edges:
        for v in e.verts:
            meeting.setdefault(v, []).append(e)

    def straight_through(v):
        pair = meeting[v]
        if len(pair) != 2:
            return False
        a = (pair[0].other_vert(v).co - v.co).normalized()
        b = (pair[1].other_vert(v).co - v.co).normalized()
        return a.dot(b) < -0.996

    done = set()
    runs = []
    for e in edges:
        if e in done:
            continue
        done.add(e)
        ends = []
        for v in e.verts:
            came = e
            while straight_through(v):
                onward = meeting[v][0] if meeting[v][1] is came else meeting[v][1]
                if onward in done:
                    break
                done.add(onward)
                v = onward.other_vert(v)
                came = onward
            ends.append(v.co.copy())
        runs.append(tuple(ends))
    return runs


def framed(part):
    """The frame a part is built on: a beam along each straight run of its sharp edges that is long enough to
    matter, and a cross over its top. A beam is 12 triangles, so a frame stays a small share of the model."""
    src = world_bmesh(part)
    # The part's main top surface: the height with the most upward-facing area. The frame outlines the body
    # up to it and lays its cross there; whatever stands on top of it is not framed.
    tops = {}
    for f in src.faces:
        if f.normal.z > 0.9:
            height = round(f.calc_center_median().z, 3)
            tops[height] = tops.get(height, 0) + f.calc_area()
    top = max(tops, key=tops.get) if tops else part.high.z
    sharp = [e for e in src.edges if (len(e.link_faces) != 2 or e.calc_face_angle(0) > FRAME_EDGE)
             and max(v.co.z for v in e.verts) <= top + 0.005]
    segments = [(a, b) for a, b in straight_runs(sharp) if (b - a).length >= FRAME_MIN]
    src.free()
    lo, hi, z = part.low, part.high, top - FRAME_BEAM / 2
    inset = FRAME_BEAM
    segments.append((Vector((lo.x + inset, lo.y + inset, z)), Vector((hi.x - inset, hi.y - inset, z))))
    segments.append((Vector((hi.x - inset, lo.y + inset, z)), Vector((lo.x + inset, hi.y - inset, z))))
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    for a, b in segments:
        beam(bm, a, b, FRAME_BEAM)
    bm.normal_update()
    map_faces(bm, bm.faces, ("tiled", 0.4))
    for f in bm.faces:
        f.material_index = 0
    return bm


def paint(joined, material):
    """Paints everything joined in one material."""
    joined.materials = [material]
    for f in joined.bm.faces:
        f.material_index = 0


def build_stage(built, members, collection, name, finished):
    joined = Joined()
    if members is not None:
        joined.add(members, members_part(built).materials)
    for part, height in built.items():
        if height == FRAME:
            bm = framed(part)
        elif height is not None and part.high.z > height:
            if part.low.z >= height:
                continue
            bm = clipped(part, height)
        else:
            bm = world_bmesh(part)
        joined.add(bm, part.materials)
        bm.free()
    if CONSTRUCTION:
        paint(joined, CONSTRUCTION)
    obj = joined.finish(name, collection)
    count = triangles(obj)
    log("  %s: %d parts, %d triangles (%d%% of the finished model)" % (name, len(built), count, 100 * count / max(finished, 1)))
    if count > finished:
        log("  warning: %s costs more than the finished model; build stages should not" % name)
    return obj


# --- Running ------------------------------------------------------------------------------------------

def export_path(scene):
    """Where a scene exports to: its own folder under the blend's Content, moved under this script's, so a component's
    model stays with the components; by grid size when the scene's folder is not under a Content."""
    own = os.path.normpath(bpy.path.abspath(scene.seut.export_exportPath or ""))
    parts = own.split(os.sep)
    if "Content" in parts:
        return os.path.join(CONTENT, *parts[parts.index("Content") + 1:])
    return EXPORT_SMALL if scene.seut.gridScale == "small" else EXPORT


def derive(scene):
    bpy.context.window.scene = scene
    scene.seut.mod_path = CONTENT + "\\"
    scene.seut.export_exportPath = export_path(scene)
    os.makedirs(scene.seut.export_exportPath, exist_ok=True)
    main = seut_collections.get_cols_by_type(scene, "main")[0]
    parts = [part for o in main.objects for part in parts_of(o)]
    source = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in main.objects if o.type == "MESH")
    log("%s (%s): %d parts, %d triangles" % (scene.name, scene.seut.sceneType, len(parts), source))

    all_stages, all_distances = read_stages(STAGES_FILE)
    distances = all_distances.get(scene.name)
    scene_lods = [lod.at(d) for lod, d in zip(LODS, distances)] if distances and not TINT else LODS
    lods = seut_collections.get_cols_by_type(scene, "lod", main)
    for lod in scene_lods:
        collection = lods.get(lod.index) or seut_collections.create_seut_collection(scene, "lod", lod.index, main)
        collection.seut.lod_distance = int(round(lod.distance))
        make_lod(parts, lod, scene, collection, "%s_LOD%d" % (scene.seut.subtypeId, lod.index))

    stages = all_stages.get(scene.name)
    if scene.seut.sceneType != "mainScene" or not stages:
        return
    # Stages may also show a subpart's parts, by <subpart>:<part> names, as fixed geometry. The finished block
    # draws its subparts too, so a stage's cost is measured against both.
    placed = subpart_parts(scene, main)
    finished = source + sum(len(p.obj.data.polygons[i].vertices) - 2 for p in placed
                            for i in (p.face_ids if p.face_ids is not None else range(len(p.obj.data.polygons))))
    designed_bounds = parts
    parts = parts + placed
    collections = seut_collections.get_cols_by_type(scene, "bs")
    for i, (title, entries) in enumerate(stages):
        index = i + 1
        collection = collections.get(index) or seut_collections.create_seut_collection(scene, "bs", index)
        log("  BS%d: %s" % (index, title))
        built = stage_contents(parts, stages, i)
        members = designed(entries, designed_bounds)
        build_stage(built, members, collection, "%s_BS%d" % (scene.seut.subtypeId, index), finished)
        lod_collection = seut_collections.get_cols_by_type(scene, "lod", collection).get(1) \
            or seut_collections.create_seut_collection(scene, "lod", 1, collection)
        lod_collection.seut.lod_distance = int(round(scene_lods[0].distance))
        # A stage's LOD is made from its whole parts and its frames; a half-built part is left out.
        whole = [p for p, height in built.items() if height is None]
        frames = [(p, framed(p)) for p, height in built.items() if height == FRAME]
        if members is not None:
            frames.append((members_part(built), members))
        if whole or frames:
            make_lod(whole, scene_lods[0], scene, lod_collection, "%s_BS%d_LOD1" % (scene.seut.subtypeId, index),
                     extra=frames, material=CONSTRUCTION)
    for index in range(len(stages) + 1, 4):
        # Stages the list doesn't have are emptied, so the game is not told of them.
        stale = collections.get(index)
        if stale is not None:
            for obj in list(stale.objects):
                bpy.data.objects.remove(obj)


def export(scene):
    bpy.context.window.scene = scene
    result = bpy.ops.scene.export()
    log("export %s: %s" % (scene.name, result))
    return result == {"FINISHED"}


def link_materials(names):
    """Links materials from SEUT's asset library; a finished blend keeps only the materials it uses."""
    missing = [m for m in names if m not in bpy.data.materials]
    if not missing:
        return
    preferences = bpy.context.preferences.addons[SEUT].preferences
    library = os.path.join(bpy.path.abspath(preferences.asset_path), "Materials", "Materials.blend")
    with bpy.data.libraries.load(library, link=True) as (source, target):
        target.materials = missing


def build():
    # Everything under Content is this script's output; clearing it keeps files from an earlier list, such as
    # a build stage since removed, from being picked up.
    if os.path.exists(CONTENT):
        shutil.rmtree(CONTENT)
    os.makedirs(EXPORT, exist_ok=True)
    os.makedirs(EXPORT_SMALL, exist_ok=True)
    if os.path.exists(LOG):
        os.remove(LOG)
    link_materials(list(TINT.values() if TINT else []) + ([CONSTRUCTION] if CONSTRUCTION else []))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    scenes = [s for s in bpy.data.scenes if s.seut.sceneType in ("mainScene", "subpart")]
    for scene in scenes:
        started = time.time()
        derive(scene)
        log("  (%.1f s)" % (time.time() - started))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    log("saved %s" % BLEND)
    if "--no-export" in sys.argv:
        return True
    return all([export(scene) for scene in scenes])


def view_3d(window):
    for area in window.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    return area, region
    raise RuntimeError("No 3D viewport in the window")


def run():
    window = bpy.context.window_manager.windows[0]
    area, region = view_3d(window)
    ok = False
    with bpy.context.temp_override(window=window, area=area, region=region):
        try:
            ok = build()
        except Exception:
            log(traceback.format_exc())
        log("RESULT %s" % ("OK" if ok else "FAILED"))
        if "--keep-open" not in sys.argv:
            bpy.ops.wm.quit_blender()
    return None


def list_parts():
    for scene in bpy.data.scenes:
        if scene.seut.sceneType not in ("mainScene", "subpart"):
            continue
        main = seut_collections.get_cols_by_type(scene, "main")[0]
        print("scene %s" % scene.name)
        for o in main.objects:
            for part in parts_of(o):
                print("  %-28s %.3f x %.3f x %.3f  from (%6.3f, %6.3f, %6.3f) to (%6.3f, %6.3f, %6.3f)  %4d faces  %s" % (
                    part.name, part.size.x, part.size.y, part.size.z, part.low.x, part.low.y, part.low.z,
                    part.high.x, part.high.y, part.high.z, part.faces, ", ".join(part.used)))


if __name__ == "__main__":
    if "--list-parts" in sys.argv:
        list_parts()
    else:
        bpy.app.timers.register(run, first_interval=1.0)
