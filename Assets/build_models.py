"""Builds the Sprocket Automation Programmable Block's models and exports them through SEUT.

Run from a normal Blender, which SEUT's export needs, kept behind other windows:

    blender.exe --no-window-focus --window-geometry 0 0 800 600 --python build_models.py [-- --no-export]

Everything is drawn in Blender's own axes, in metres from the block's centre: the block's Front is -Y, its Up is +Z and,
seen from the front, +X is to the right. The device is 1.2 m wide, with the screen's middle at a standing person's eye
height, about 1.6 m above the floor of its cell; its height follows from the screen's. See the mod's CLAUDE.md for the
design.

The screen is 16:10, as Keen's programmable block's; `--square` builds the near-square screen instead, to compare.

The wall variant stands on the cell's Back face. The inset variant is a full cube with the same device in a well in its
Front. The keyboard tray is a subpart hinged at the device's foot; it is drawn folded up.

Both screens are made as Keen makes the programmable block's (ProgrammingBlock.fbx in the ModSDK): one quad of the
screen material with UVs 0 to 1, and half a millimetre behind it a placeholder from the fighter cockpit's interior atlas,
which shows while the screen has no content (the game hides a functional block's screen then).
"""

import math
import os
import sys
import traceback

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tools"))
import se_stamps  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "Build")
CONTENT = os.path.join(HERE, "..", "SprocketProgrammableBlock", "Content")
BLEND = os.path.join(OUTPUT, "SprocketProgrammableBlock.blend")
LOG = os.path.join(OUTPUT, "build_models.log")
EXPORT = os.path.join(OUTPUT, "Content", "Models", "Cubes", "large")
TEXTURES = os.path.join(HERE, "Textures", "Models", "Cubes")
SEUT = "space-engineers-utilities"

# --- Materials --------------------------------------------------------------------------------------------

SHELL = "PaintedMetal_Clean"            # the white shell: takes the player's paint everywhere, and has no scratches or wear
ARMOUR = "PaintedMetal_Colorable"       # the inset variant's cube, as Keen's armour-like blocks
INSIDE = "PaintedMetal_VeryDark"        # the inset variant's well, still to be built
SCREEN = "CockpitScreen_02"             # the programmable block's surface 0, as on Keen's
KEYS = "CockpitScreen_01"               # its surface 1, on the tray
STATUS = "Emissive"                     # the status line; the programmable block drives it itself
GLASS = "SprocketBlackGlass"            # made by make_logo.py
LOGO = "SprocketAutomationLogo"         # made by make_logo.py
PLACEHOLDER = "CockpitFighter_Interior"  # the atlas holding the art behind Keen's programmable block's screens
SEAM = "PanelingColorable"              # Keen's seams on painted metal
BUTTON = "ButtonsAtlas_Colorable"       # the power button, painted with the shell
KIT = "Atlas3_Colorable"                # the back's screws, vent and connector, painted with the shell
VENT = "Atlas3_Darker"                  # the vent in the tray's well, dark on any paint

LINKED = [SHELL, ARMOUR, INSIDE, SCREEN, KEYS, STATUS, PLACEHOLDER, SEAM, BUTTON, KIT, VENT]
LOCAL = [GLASS, LOGO]
TRAY_MODEL = "SprocketProgrammableBlock_Tray"   # one tray model for both variants: it is drawn about its own hinge
TILE = 2.5

# --- The device, in Blender axes. --------------------------------------------------------------------------

CELL = 1.25
WIDTH = 1.2
CORNER = 0.1            # the radius of the device's corners, seen from the front
DEPTH = 0.11            # the device's depth at its top, where it is thinnest
LEAN = math.radians(6)  # the face leans back, its top toward the wall
CURVE_DROP = 0.07       # the one curve: the top rolls this far down into the face,
CURVE_RUN = 0.07        # over this much of the device's depth, so it starts 4 cm off the wall

EYE_Z = 0.35            # the screen's middle, about 1.6 m above the cell's floor
SCREEN_HALF = 0.495     # the screen's half width, 0.99 m
SQUARE = "--square" in sys.argv
SCREEN_HEIGHT = 0.98 if SQUARE else 2 * SCREEN_HALF * 10 / 16    # 16:10, as Keen's programmable block's ScreenArea
SCREEN_TOP = EYE_Z + SCREEN_HEIGHT / 2
SCREEN_BOTTOM = EYE_Z - SCREEN_HEIGHT / 2
TOP = SCREEN_TOP + 0.1  # the face's top edge, after the curve, is 3 cm above the glass
STATUS_Z = SCREEN_BOTTOM - 0.03
SEAM_Z = STATUS_Z - 0.035               # the tray's top edge, folded

# ProgrammingBlock.fbx: the keyboard surface is 0.4423 x 0.1745 m, 5:2 as its ScreenArea.
KEYBOARD = (0.4423, 0.1745)
TRAY_BORDER = 0.03
TRAY_HALF = KEYBOARD[0] / 2 + TRAY_BORDER
TRAY_TOP = SEAM_Z - 0.01
TRAY_BOTTOM = TRAY_TOP - KEYBOARD[1] - 2 * TRAY_BORDER
HINGE_Z = TRAY_BOTTOM + 0.015           # the tray's hinge, near the device's foot
BOTTOM = TRAY_BOTTOM - 0.005            # the device's foot
TRAY_THICK = 0.03
TRAY_CLEAR = 0.008      # from the well's floor to the folded tray: the logo panel stands 5 mm off the floor
WELL_DEPTH = TRAY_CLEAR + TRAY_THICK    # the folded tray's back is flush with the face
WELL_GAP = 0.005        # between the folded tray and the well's walls
LOGO_SIZE = (0.4, 0.4 * 0.09 / 0.59)    # the logo texture's panel, 0.59 x 0.09 m in the mockup, scaled to the tray
LOGO_CORNER = LOGO_SIZE[1] * 40 / 136   # Design/logo_texture.html: the rim's outer corner, r 40 on a panel 136 high
# The well's floor holds the logo at the top and the vent under it. The strip of tray below the hinge swings back into
# the well, 21 mm round the hinge, so both stay above that.
LOGO_Z = TRAY_TOP - 0.042
VENT_SCALE = 0.35       # Atlas3's Slim Vent, laid across: 0.22 x 0.105 m
VENT_Z = LOGO_Z - LOGO_SIZE[1] / 2 - 0.012 - 0.301 * VENT_SCALE / 2

# ProgrammingBlock.fbx's placeholders in the CockpitFighter_Interior atlas, as (u, v) at the near or bottom left corner
# and the change in each across the surface (to the right) and up it (away from a typist on the keyboard).
SCREEN_ART = ((0.8552, 0.2178), (0.0, -0.2106), (0.1312, 0.0))
KEYBOARD_ART = ((0.0353, 0.5987), (0.0, -0.5806), (0.2250, 0.0))
ART_PROUD = 0.0012      # the placeholder stands this far off what is behind it,
SCREEN_PROUD = 0.0024   # and the screen as far again in front of it. An .mwm stores positions as half floats, in
                        # steps of 0.98 mm between 1 and 2 m from the block's centre: Keen's 0.5 mm gap is one step where
                        # their screen sits (0.99 m), and rounded away where ours does (1.06 to 1.13 m), so the two flickered.
SCREEN_POCKET = 0.0048  # the pocket in the glass the screen sits in: the screen 2.4 mm below the glass's front
SCREEN_CORNER = 0.025   # the pocket's corners, concentric with the glass's 50 mm corners round its 25 mm border


def log(line):
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def link_materials():
    library = os.path.join(bpy.path.abspath(bpy.context.preferences.addons[SEUT].preferences.asset_path), "Materials", "Materials.blend")
    with bpy.data.libraries.load(library, link=True) as (source, target):
        missing = [m for m in LINKED if m not in source.materials]
        if missing:
            raise RuntimeError("Not in %s: %s" % (library, ", ".join(missing)))
        target.materials = list(LINKED)
    for name in LOCAL:
        local_material(name)


def local_material(name):
    """A material of the mod's own, from the maps make_logo.py made. SEUT writes its entry from the image nodes' names."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    for kind in ("CM", "NG", "ADD"):
        node = nodes.new("ShaderNodeTexImage")
        node.name = node.label = kind
        node.image = bpy.data.images.load(os.path.join(TEXTURES, "%s_%s.png" % (name, kind.lower())))
        if kind == "CM":
            mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            node.image.colorspace_settings.name = "Non-Color"
    mat.seut.technique = "MESH"
    return mat


# --- Geometry -------------------------------------------------------------------------------------------------

class Part:
    """Where a scene's shapes go. Objects after the first parent to the first, as SEUT wants one root."""

    def __init__(self, collection, origin=(0, 0, 0)):
        self.collection = collection
        self.origin = Vector(origin)
        self.root = None
        self.overlays = 0

    def add(self, name, bm, material, region=None, smooth=True):
        bmesh.ops.translate(bm, verts=bm.verts, vec=-self.origin)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
        for face in bm.faces:
            n = face.normal
            axis = max(range(3), key=lambda i: abs(n[i]))
            u, v = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
            coords = [(loop.vert.co[u], loop.vert.co[v]) for loop in face.loops]
            if region is None:
                for loop, (a, b) in zip(face.loops, coords):
                    loop[uv].uv = (a / TILE, b / TILE)
                continue
            a0, a1 = min(c[0] for c in coords), max(c[0] for c in coords)
            b0, b1 = min(c[1] for c in coords), max(c[1] for c in coords)
            flip = axis == 1 and n[1] > 0      # a face seen from +Y reads mirrored
            for loop, (a, b) in zip(face.loops, coords):
                fa = (a - a0) / (a1 - a0) if a1 > a0 else 0.5
                fb = (b - b0) / (b1 - b0) if b1 > b0 else 0.5
                if flip:
                    fa = 1 - fa
                loop[uv].uv = (region[0] + fa * (region[2] - region[0]), region[1] + fb * (region[3] - region[1]))
        return self.place(name, bm, material, smooth)

    def quad(self, name, corners, uvs, material):
        """One flat face, its corners counter-clockwise seen from the side it shows, with the UV given for each corner."""
        bm = bmesh.new()
        face = bm.faces.new([bm.verts.new(Vector(c) - self.origin) for c in corners])
        uv = bm.loops.layers.uv.new("UVMap")
        for loop, coord in zip(face.loops, uvs):
            loop[uv].uv = coord
        return self.place(name, bm, material, smooth=False)

    def place(self, name, bm, material, smooth):
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(bpy.data.materials[material])
        if smooth:
            mesh.shade_smooth()
            mesh.set_sharp_from_angle(angle=math.radians(35))
            keep_flat(mesh)
        obj = bpy.data.objects.new(name, mesh)
        self.collection.objects.link(obj)
        if self.root is None:
            self.root = obj
        else:
            obj.parent = self.root
        return obj

    def empty(self, name, location, display="ARROWS", size=0.1):
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = display
        obj.empty_display_size = size
        obj.location = Vector(location) - self.origin
        self.collection.objects.link(obj)
        obj.parent = self.root
        return obj

    def adopt(self, overlay):
        self.overlays += 1
        overlay.name = "Overlay%d" % self.overlays
        overlay.parent = self.root

    def rect(self, material, uv, at, normal, up, size):
        self.adopt(se_stamps.rect(material, uv, Vector(at) - self.origin, normal, up, size, collection=self.collection))


FLAT_FACE = 0.1         # m2: a face this large keeps its own normal


def keep_flat(mesh):
    """Marks every edge of a large face sharp, so its normal is not smoothed into its neighbours. A large n-gon is
    exported as long thin triangles, which spread a smoothed vertex's lean across the whole face as a streak."""
    sharp = mesh.attributes.get("sharp_edge") or mesh.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    for poly in mesh.polygons:
        if poly.area >= FLAT_FACE:
            for i in poly.loop_indices:
                sharp.data[mesh.loops[i].edge_index].value = True


def solid(verts, faces):
    bm = bmesh.new()
    made = [bm.verts.new(v) for v in verts]
    for face in faces:
        bm.faces.new([made[i] for i in face])
    return bm


def chamfered(low, high, width):
    x0, y0, z0 = low
    x1, y1, z1 = high
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    bm = solid(verts, [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    if width > 0:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=width, offset_type="OFFSET", segments=2, profile=0.5, affect="EDGES")
    return bm


def rounded_outline(left, right, bottom, top, radius, steps=6):
    """A rectangle with rounded corners, as (x, z) points counter-clockwise from the bottom right, seen from the front.
    Where a side is all corner (twice the radius long), its two ends are one point, kept once: a repeated point makes
    a face with no area, whose zero normal makes MwmBuilder throw away the normals of its whole mesh part (found on
    the LCD Corridors mod)."""
    points = []
    for cx, cz, start in ((right - radius, bottom + radius, -90), (right - radius, top - radius, 0),
                          (left + radius, top - radius, 90), (left + radius, bottom + radius, 180)):
        for k in range(steps + 1):
            a = math.radians(start + 90 * k / steps)
            point = (cx + radius * math.cos(a), cz + radius * math.sin(a))
            if not points or math.dist(point, points[-1]) > 1e-6:
                points.append(point)
    if math.dist(points[0], points[-1]) <= 1e-6:
        points.pop()
    return points


def plate(outline, plane, thickness, sink=0.002):
    """A flat plate of an outline, (x, z) points, laid on a plane function (x, z) -> point, standing `thickness` off it
    toward the viewer, its back `sink` behind it. The plane's normal is that of the device's face. A plate standing on
    another is sunk less than it, or their hidden backs share a plane and flicker."""
    n = len(outline)
    front = [plane(x, z) + FACE_NORMAL * thickness for x, z in outline]
    back = [plane(x, z) - FACE_NORMAL * sink for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return solid(back + front, faces)


# --- The device's face is a plane leaning back, its top toward the wall. -----------------------------------------

BACK_Y = CELL           # the wall the device stands on, for the wall variant
FACE_NORMAL = Vector((0, -math.cos(LEAN), math.sin(LEAN)))
FACE_UP = Vector((0, math.sin(LEAN), math.cos(LEAN)))


def face_y(z, back):
    """Where the device's face is at height z, for a device standing on a wall at `back`."""
    return back - DEPTH - (TOP - z) * math.tan(LEAN)


def on_face(back, depth=0.0):
    """The device's face as a plane function (x, z) -> point, or a plane parallel to it `depth` behind it."""
    return lambda x, z: Vector((x, face_y(z, back), z)) - FACE_NORMAL * depth


def carved(bm, cutter):
    """A solid less another, by Blender's exact boolean, as a new bmesh. Both are freed."""
    scene = bpy.context.scene
    objects = []
    for name, part in (("Carved", bm), ("Cutter", cutter)):
        bmesh.ops.recalc_face_normals(part, faces=part.faces)
        mesh = bpy.data.meshes.new(name)
        part.to_mesh(mesh)
        part.free()
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        objects.append(obj)
    target, tool = objects
    cut = target.modifiers.new("Cut", "BOOLEAN")
    cut.operation = "DIFFERENCE"
    cut.solver = "EXACT"
    cut.object = tool
    result = bmesh.new()
    result.from_object(target, bpy.context.evaluated_depsgraph_get())
    for obj in objects:
        mesh = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
    return result


def well_cutter(back):
    """The tray's well: from just past the face to the well's floor, a gap wider than the folded tray, and open
    through the device's foot so nothing stands below the hinge as the tray swings."""
    corner = 0.03 + WELL_GAP
    outline = rounded_outline(-TRAY_HALF - WELL_GAP, TRAY_HALF + WELL_GAP, BOTTOM - 0.1, SEAM_Z - 0.01 + WELL_GAP, corner)
    # plate() stands its back 2 mm behind its plane.
    return plate(outline, on_face(back, WELL_DEPTH - 0.002), WELL_DEPTH + 0.05)


def shell(back, curve_steps=10):
    """The shell: the device's outline from the front, carried from the wall to its face, with its top running down into
    the face over one curve."""
    outline_steps = 6
    start = 1 - CURVE_RUN / DEPTH
    layers = [(0.0, rounded_outline(-WIDTH / 2, WIDTH / 2, BOTTOM, TOP, CORNER, outline_steps))]
    # Over the curve the top comes down on a quarter ellipse, in steps of its angle that shrink toward the face, so the
    # face, kept flat, meets the last step at under a degree and shows no edge.
    for k in range(curve_steps + 1):
        angle = math.radians(90 * math.sin(math.pi / 2 * k / curve_steps))
        t = start + math.sin(angle) * (1 - start)
        lift = CURVE_DROP * (1 - math.cos(angle))
        layers.append((t, rounded_outline(-WIDTH / 2, WIDTH / 2, BOTTOM, TOP - lift, CORNER, outline_steps)))
    rings = len(layers) - 1
    verts = []
    for t, outline in layers:
        for x, z in outline:
            verts.append((x, back - t * (back - face_y(z, back)), z))
    n = len(layers[0][1])
    faces = [tuple(range(n)), tuple(rings * n + i for i in range(n - 1, -1, -1))]
    for k in range(rings):
        a, b = k * n, (k + 1) * n
        faces += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]
    return solid(verts, faces)


def build_device(main, back):
    """The device on a wall at y = `back`: shell, screen, status line, logo and vent. Returns the tray's hinge and the
    screen's glass, for the detector."""
    face = on_face(back)
    floor = on_face(back, WELL_DEPTH)
    main.add("Shell", carved(shell(back), well_cutter(back)), SHELL)
    # The black glass, filling the face's width, and the screen set into a pocket in it, below the glass's front.
    glass_thickness = 0.006
    pocket_floor = lambda x, z: face(x, z) + FACE_NORMAL * (glass_thickness - SCREEN_POCKET)
    # A plane function takes heights in world z; the screen's height runs up the leaning face.
    # The pocket's corners are rounded and the screen's are not: its corners run into the glass, which hides them, as
    # the Survival Kit's frame hides its screen's (SurvivalKit_Reskin.fbx: a frame 6.3 mm in front, inner corners r 15 mm).
    pocket = [(x, EYE_Z + z * math.cos(LEAN)) for x, z in
              rounded_outline(-SCREEN_HALF, SCREEN_HALF, -SCREEN_HEIGHT / 2, SCREEN_HEIGHT / 2, SCREEN_CORNER)]
    slab = plate(rounded_outline(-SCREEN_HALF - 0.025, SCREEN_HALF + 0.025, SCREEN_BOTTOM - 0.025, SCREEN_TOP + 0.025, 0.05), face, glass_thickness)
    glass = main.add("ScreenGlass_section", carved(slab, plate(pocket, pocket_floor, 0.01, sink=0)), GLASS)
    # The square screen's own standby image is still to be made; until then it shows the glass behind it.
    add_surface(main, "Screen", pocket_floor(0, EYE_Z), Vector((1, 0, 0)), FACE_UP,
                (2 * SCREEN_HALF, SCREEN_HEIGHT), SCREEN, None if SQUARE else SCREEN_ART)
    main.add("Status", plate(rounded_outline(-0.13, 0.13, STATUS_Z - 0.006, STATUS_Z + 0.006, 0.006, 2), face, 0.004), STATUS, (0.40, 0.14, 0.50, 0.24))
    # On the floor of the tray's well: the logo on its glass panel, and a vent under it.
    w, h = LOGO_SIZE
    main.add("LogoPanel", plate(rounded_outline(-w / 2, w / 2, LOGO_Z - h / 2, LOGO_Z + h / 2, LOGO_CORNER), floor, 0.005), LOGO, (0, 0, 1, 1), smooth=False)
    main.adopt(se_stamps.stamp("Atlas3", "Slim Vent", at=floor(0, VENT_Z), normal=FACE_NORMAL, up=Vector((1, 0, 0)),
                               scale=VENT_SCALE, material=VENT, collection=main.collection))
    hinge = tray_hinge(back)
    tray = main.empty("subpart_Keyboard", hinge)
    return tray, glass


def add_details(main, back):
    """The overlay: one seam round the shell where its back housing meets the front cover, and a power button in the
    face's lower right corner, clear of the tray's well."""
    housing = 0.03      # the back housing's depth, from the wall: short of where the top's curve starts
    points = [(x, back - housing, z) for x, z in rounded_outline(-WIDTH / 2, WIDTH / 2, BOTTOM, TOP, CORNER)]
    normals = []
    for i, point in enumerate(points):
        before, after = Vector(points[i - 1]), Vector(points[(i + 1) % len(points)])
        along = after - before
        # The outline runs counter-clockwise seen from the front, so outward is its direction turned clockwise.
        normals.append(Vector((along.z, 0, -along.x)).normalized())
    # 1.5 mm off the shell: at the default 1 mm, parts of it rounded onto the shell in the .mwm's half floats.
    main.adopt(se_stamps.panel_line("Panel Line Creased", points, normals, material=SEAM, closed=True, lift=0.0015,
                                    collection=main.collection))
    button = on_face(back)(WIDTH / 2 - 0.13, BOTTOM + 0.06)
    main.adopt(se_stamps.stamp("ButtonsAtlas", "Metal Button", at=button, normal=FACE_NORMAL, up=FACE_UP, scale=0.3,
                               material=BUTTON, collection=main.collection))


def add_back(main, back):
    """The back, against the wall: a mounting plate screwed on at its corners, a vent and the connector. It shows only
    where the wall behind is not a full face, and faces into the wall, so the game culls it from the room's side."""
    normal, up = Vector((0, 1, 0)), Vector((0, 0, 1))
    inset = 0.06
    left, right, bottom, top = -WIDTH / 2 + inset, WIDTH / 2 - inset, BOTTOM + inset, TOP - inset
    points = [(x, back, z) for x, z in rounded_outline(left, right, bottom, top, CORNER - inset / 2, 3)]
    main.adopt(se_stamps.panel_line("Panel Line Creased", points, normal, material=SEAM, closed=True, collection=main.collection))
    screw = 0.045
    for x in (left + screw, right - screw):
        for z in (bottom + screw, top - screw):
            main.adopt(se_stamps.stamp("Atlas3", "Large Screw", at=(x, back, z), normal=normal, up=up, scale=0.13,
                                       material=KIT, collection=main.collection))
    middle = (bottom + top) / 2
    main.adopt(se_stamps.stamp("Atlas3", "Square Vent", at=(0, back, middle + 0.04), normal=normal, up=up, scale=0.5,
                               material=KIT, collection=main.collection))
    main.adopt(se_stamps.stamp("Atlas3", "Thin Plug Inset", at=(0, back, bottom + 0.09), normal=normal, up=Vector((1, 0, 0)),
                               scale=0.35, material=KIT, collection=main.collection))


def tray_hinge(back):
    """The tray's hinge: near the device's foot, in the middle of the folded tray's thickness."""
    return on_face(back, TRAY_THICK / 2)(0, HINGE_Z)


def add_surface(part, name, centre, right, up, size, material, art, screen_part=None):
    """A text surface as Keen makes one: a quad of the screen material, UVs 0 to 1 with V up, facing right x up, and half
    a millimetre behind it, given `art`, the placeholder quad of the cockpit atlas that shows while it has no content.
    `up` is up the screen, or away from a person typing on a keyboard. The screen quad goes to `screen_part` if given."""
    out = right.cross(up)
    w, h = size
    corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
    def at(proud):
        return [centre + out * proud + right * (a * w) + up * (b * h) for a, b in corners]
    (screen_part or part).quad(name, at(SCREEN_PROUD), [(a + 0.5, b + 0.5) for a, b in corners], material)
    if art is not None:
        (u0, v0), (du_right, dv_right), (du_up, dv_up) = art
        uvs = [(u0 + du_right * (a + 0.5) + du_up * (b + 0.5), v0 + dv_right * (a + 0.5) + dv_up * (b + 0.5)) for a, b in corners]
        part.quad(name + "Idle", at(ART_PROUD), uvs, PLACEHOLDER)


def add_detector(main, back, glass, tray):
    """The detector that opens the block's terminal on Use: a slab over the whole face, tilted with it, from the
    device's foot to the top of the glass. Aimed at, it outlines the glass and the tray, folded or open; the game reads
    a `subpart_` entry in the highlight list as that subpart."""
    bottom, top = BOTTOM, SCREEN_TOP + 0.025
    middle = (bottom + top) / 2
    detector = main.empty("detector_terminal_001", on_face(back)(0, middle) + FACE_NORMAL * 0.02, "CUBE", 1.0)
    detector.rotation_euler = (-LEAN, 0, 0)
    # A CUBE empty's half extents are its display size times its scale.
    detector.scale = (WIDTH / 2, 0.03, (top - bottom) / 2 / math.cos(LEAN))
    for target in (glass, tray):
        detector.seut.highlight_objects.add().obj = target
    detector["highlight"] = glass.name + ";" + tray.name


def build_wall(name):
    scene = new_scene(name, "mainScene")
    main = Part(collection(scene, "main"))
    tray, glass = build_device(main, BACK_Y)
    add_details(main, BACK_Y)
    add_back(main, BACK_Y)
    tray["file"] = TRAY_MODEL
    add_detector(main, BACK_Y, glass, tray)
    hkt = Part(collection(scene, "hkt"))
    hkt.add("Collision", chamfered((-WIDTH / 2, face_y(BOTTOM, BACK_Y), BOTTOM), (WIDTH / 2, BACK_Y, TOP), 0), SHELL)
    return scene


def prism(outline, near, far):
    """A solid of an outline, (x, z) points, running along Y from `near` to `far`."""
    n = len(outline)
    verts = [(x, near, z) for x, z in outline] + [(x, far, z) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return solid(verts, faces)


def build_inset(name):
    """The inset variant: a full cube, mounted on every side, with the same device in a dark well in its Front. The well
    is as deep as the device's foot and a centimetre more, so the device sits just inside the cube's face."""
    scene = new_scene(name, "mainScene")
    main = Part(collection(scene, "main"))
    front = -CELL
    back = front + DEPTH + (TOP - BOTTOM) * math.tan(LEAN) + 0.01
    gap = 0.03
    left, right, bottom, top = -WIDTH / 2 - gap, WIDTH / 2 + gap, BOTTOM - gap, TOP + gap
    well = prism(rounded_outline(left, right, bottom, top, CORNER + gap), front - 0.05, back)
    cube = main.add("Cube", carved(chamfered((-CELL, -CELL, -CELL), (CELL, CELL, CELL), 0.02), well), ARMOUR)
    # The well's walls and floor in the dark tone: faces between the cube's face and the well's floor, inside its outline.
    cube.data.materials.append(bpy.data.materials[INSIDE])
    for poly in cube.data.polygons:
        x, y, z = poly.center
        if front + 1e-4 < y <= back + 1e-4 and left - 1e-3 <= x <= right + 1e-3 and bottom - 1e-3 <= z <= top + 1e-3:
            poly.material_index = 1
    tray, glass = build_device(main, back)
    add_details(main, back)
    tray["file"] = TRAY_MODEL
    add_detector(main, back, glass, tray)
    add_armour_seams(main)
    hkt = Part(collection(scene, "hkt"))
    hkt.add("Collision", chamfered((-CELL, -CELL, -CELL), (CELL, CELL, CELL), 0), ARMOUR)
    return scene


def add_armour_seams(main):
    """One seam ring on each of the cube's faces, 10 cm in from its edges, as an armour plate's."""
    inner = CELL - 0.1
    ring = [(-inner, -inner), (inner, -inner), (inner, inner), (-inner, inner)]
    for axis in range(3):
        for sign in (-1, 1):
            normal = Vector([sign if i == axis else 0 for i in range(3)])
            others = [i for i in range(3) if i != axis]
            points = []
            for a, b in ring:
                point = [0.0, 0.0, 0.0]
                point[axis] = sign * CELL
                point[others[0]], point[others[1]] = a, b
                points.append(tuple(point))
            main.adopt(se_stamps.panel_line("Panel Line Creased", points, normal, material=SEAM, closed=True, collection=main.collection))


def build_tray(name, back):
    """The keyboard tray, folded: its face toward the device carries the keys, and its back the logo."""
    scene = new_scene(name, "subpart")
    face = on_face(back)
    part = Part(collection(scene, "main"), tray_hinge(back))
    outline = rounded_outline(-TRAY_HALF, TRAY_HALF, TRAY_BOTTOM, TRAY_TOP, 0.03)
    # Folded, the tray fills its well: its back is flush with the face. plate() stands its back 2 mm behind its plane.
    part.add("Tray", plate(outline, on_face(back, TRAY_THICK - 0.002), TRAY_THICK - 0.002), SHELL)
    w, h = LOGO_SIZE
    mid = (TRAY_BOTTOM + TRAY_TOP) / 2
    part.add("TrayLogo", plate(rounded_outline(-w / 2, w / 2, mid - h / 2, mid + h / 2, LOGO_CORNER), face, 0.001),
             LOGO, (0, 0, 1, 1), smooth=False)
    # The keys face the device while the tray is folded, and face up once it swings down: the hinge's edge is then the
    # far one, and the tray's top edge the near one. Their screen quad is a subpart of its own, for the mod's code to hide
    # while the surface has no content: the game hides an empty screen on the block's own model only.
    centre = on_face(back, TRAY_THICK)(0, mid)
    screen_scene = new_scene(name + "Keys", "subpart")
    screen = Part(collection(screen_scene, "main"), centre)
    add_surface(part, "Keys", centre, Vector((1, 0, 0)), -FACE_UP, KEYBOARD, KEYS, KEYBOARD_ART, screen)
    bpy.context.window.scene = scene
    part.empty("subpart_KeysScreen", centre)["file"] = name + "Keys"
    return [screen_scene, scene]


# --- Scenes -------------------------------------------------------------------------------------------------------

def new_scene(subtype_id, scene_type):
    scene = bpy.data.scenes.new(subtype_id)
    bpy.context.window.scene = scene
    scene.seut.sceneType = scene_type
    scene.seut.subtypeId = subtype_id
    scene.seut.subtypeBefore = subtype_id
    bpy.ops.scene.recreate_collections()
    scene.seut.gridScale = "large"
    scene.seut.export_largeGrid = True
    scene.seut.export_smallGrid = False
    scene.seut.export_sbc_type = "none"
    scene.seut.linkSubpartInstances = False
    scene.seut.mod_path = os.path.join(OUTPUT, "Content") + "\\"
    scene.seut.export_exportPath = EXPORT
    return scene


def collection(scene, col_type):
    for col in bpy.data.collections:
        if col.seut.scene is scene and col.seut.col_type == col_type:
            return col
    raise RuntimeError("Scene %s has no %s collection" % (scene.name, col_type))


def export(scene):
    bpy.context.window.scene = scene
    result = bpy.ops.scene.export()
    log("export %s: %s" % (scene.name, result))
    return result == {"FINISHED"}


def build():
    os.makedirs(EXPORT, exist_ok=True)
    if os.path.exists(LOG):
        os.remove(LOG)
    old_scenes = list(bpy.data.scenes)
    link_materials()
    scenes = build_tray(TRAY_MODEL, BACK_Y) + [build_wall("SprocketProgrammableBlock"), build_inset("SprocketProgrammableBlockInset")]
    for old in old_scenes:
        bpy.data.scenes.remove(old)
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
    """Timer callbacks get no window in their context, so everything runs inside one override."""
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


os.makedirs(OUTPUT, exist_ok=True)
bpy.app.timers.register(run, first_interval=1.0)
