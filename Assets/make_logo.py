"""Renders the logo panel's texture and converts it for the game.

    python make_logo.py

Chrome renders Design/logo_texture.html, which is mockup.html's logo panel. The colour map is that picture; the panel is
black glass, so the normal map is flat and glossy, and the extensions map neither paints nor glows: the logo keeps its
own colours on any paint. Sources go to Textures/Models/Cubes beside this script, where SEUT finds them, and the
converted maps to the mod's Content/Textures/Models/Cubes.
"""
import os
import subprocess

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
# Set CHROME and TEXCONV in the environment where they are installed elsewhere; texconv comes with the ModSDK.
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
TEXCONV = os.environ.get("TEXCONV", r"E:\Steam\steamapps\common\SpaceEngineersModSDK\Tools\TexturePacking\Tools\texconv.exe")
SOURCES = os.path.join(HERE, "Textures", "Models", "Cubes")
TARGET = os.path.join(HERE, "..", "SprocketProgrammableBlock", "Content", "Textures", "Models", "Cubes")
NAME = "SprocketAutomationLogo"
SIZE = (2048, 512)
GLOSS = 180             # black glass, as Keen's cockpit glass (CockpitIndustrialGlassOutside_ng: 180)


def main():
    os.makedirs(SOURCES, exist_ok=True)
    os.makedirs(TARGET, exist_ok=True)
    shot = os.path.join(SOURCES, NAME + "_shot.png")
    page = "file:///" + os.path.join(HERE, "Design", "logo_texture.html").replace("\\", "/")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=%d,%d" % SIZE, "--screenshot=" + shot, page], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    picture = Image.open(shot).convert("RGB").crop((0, 0) + SIZE)
    os.remove(shot)

    colour = picture.copy()
    colour.putalpha(0)                                                      # metalness: none
    maps = {
        "cm": colour,
        "ng": Image.new("RGBA", SIZE, (128, 128, 255, GLOSS)),             # flat, glossy
        "add": Image.new("RGBA", SIZE, (255, 0, 255, 0)),                   # full AO, no glow, no paint
    }
    write_maps(NAME, maps)
    # The black glass round the screen, on the tray and on the logo panel's edge: the logo panel's own ground, at its darkest.
    write_maps("SprocketBlackGlass", {
        "cm": Image.new("RGBA", (64, 64), (14, 16, 20, 0)),
        "ng": Image.new("RGBA", (64, 64), (128, 128, 255, GLOSS)),
        "add": Image.new("RGBA", (64, 64), (255, 0, 255, 0)),
    })
    print("logo and glass written to", TARGET)


def write_maps(name, maps):
    """Saves a material's maps as sources and converts each to the game's DDS, with mips.

    The alpha channels are data (metalness, gloss, paint), not coverage: without -sepalpha, texconv weights colour by
    alpha when it makes the mips, and a map whose alpha is 0 comes out black below full size.
    """
    formats = {"cm": "BC7_UNORM_SRGB", "ng": "BC7_UNORM", "add": "BC7_UNORM"}
    for kind, image in maps.items():
        source = os.path.join(SOURCES, "%s_%s.png" % (name, kind))
        image.save(source)
        subprocess.run([TEXCONV, "-nologo", "-y", "-sepalpha", "-ft", "dds", "-f", formats[kind], "-o", TARGET, source],
                       check=True, stdout=subprocess.DEVNULL)
        written = os.path.join(TARGET, "%s_%s.DDS" % (name, kind))
        if os.path.exists(written):
            os.replace(written, os.path.join(TARGET, "%s_%s.dds" % (name, kind)))


main()
