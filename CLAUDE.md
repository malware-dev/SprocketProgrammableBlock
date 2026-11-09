# Sprocket Automation Programmable Block

A Space Engineers mod: a programmable block made by Sprocket Automation, the company in Sprocket's world. It is a true
companion of the Sprocket mod (`..\Sprocket`) and carries its name, and it works as a plain programmable block without
Sprocket.

## Layout

- `SprocketProgrammableBlock/` is the mod, an MDK2 mod project (`SprocketProgrammableBlock.csproj`). Code goes in that
  folder; `.sbc` definitions go under `SprocketProgrammableBlock/Content/Data/`, and anything else the mod ships
  (models, textures) in other folders under `SprocketProgrammableBlock/Content/`.
- `SprocketProgrammableBlock.slnx` is the solution.
- `Directory.Build.props` is the same as the other mods'. `.gitignore` is too, plus an Assets rule: the repository
  keeps `Assets/SprocketProgrammableBlock.blend` (the finished model with every LOD and build stage), `Assets/Textures`
  (the sources its own materials load) and `Assets/Design`. The scripts that build the models stay local, by Mal's rule.
- `Assets/Design/` holds the agreed design: `mockup.png`, drawn from `mockup.html`, and the logo's icon `icon.svg`.
- **License:** plain MIT, Mal's choice for this mod (2026-11-07), the same file as LCD Corridors'.

Any build of the mod deploys it to the game's Mods folder; `-p:MdkBuildConfiguration=none` compiles without deploying.

## The design Mal agreed

Large grid only, two variants: one mounted on a wall by its back, and one inset in a full cube's well, the way Keen's
refill station comes in two. The device is the same in both.

- **Who made it.** Sprocket Automation is proud of itself for a reason: the device works well and feels like a real
  computer of the future. The tone is Apple's competence with Cave Johnson's insanity. No Portal look and no jokes
  written on it.
- **Shell.** One white shell with one curve, 1.2 m wide and 1.03 m tall. It takes the player's paint like any
  block; white is only the showroom colour. No screws, labels or hardware keys on the front; the back, against the
  wall, shows how it is mounted.
- **Screen.** One sheet of black glass, filling the shell's width, 16:10 (0.99 x 0.62 m) as Keen's programmable
  block's, the face leaning back 6 degrees (Mal, 2026-11-07: tilted down looked odd). The device is then 1.2 x 1.03 m.
  `build_models.py --square` still builds the near-square screen to compare. Each surface is built as Keen builds
  them: one quad of `CockpitScreen_0x`, UVs 0 to 1, and one half-float step behind it (see "Gaps and half floats") the
  `CockpitFighter_Interior` placeholder Keen's programmable block shows while a screen has no content (the game hides
  a functional block's empty screen; it never shows the stock Online image).
- **Detail.** Even Apple has panel lines: one `Panel Line Creased` seam round the shell 3 cm off the wall, and a
  power button (ButtonsAtlas Metal Button) in the face's lower right corner. Both in the paintable variants.
- **Status.** A thin lit line under the glass: amber while asleep, green while running.
- **Logo.** `[gear] SPROCKET AUTOMATION` on one line, upper case, on a small black glass panel of its own, just above
  the vent. The logo keeps its own colours on any paint. Mal is still weighing the panel against the logo pressed
  into the shell in one tone.
- **Keyboard tray.** Sized round Keen's keyboard surface, 0.44 x 0.175 m (5:2), so their keyboard art fits: the tray
  is 0.5 m wide, centred, in a well of its own. A hinged subpart. Folded, it covers everything below a seam under the status line, and its back
  carries the same logo. When a player stands close, or opens the block's terminal, it swings down on its own to a
  typing angle, and folds back when they leave. Drawn on each client only; the check for a nearby player runs on a
  slow cadence and only near players.
- **Depth.** 11 cm at the top, about 22 cm at the foot with the lean (Mal halved it, 2026-11-07: the cowl was too much).
- **Vent.** The tray's well shows the logo and, under it, Atlas3's Slim Vent in `Atlas3_Darker` (Mal: the well must
  hold more than the logo). Both stay above the 21 mm the tray's strip below the hinge swings back into the well; the
  hand-built slotted vent looked faux and clipped the keyboard.
- **Back.** A mounting plate seam with a Large Screw in each corner, a Square Vent and a Thin Plug Inset connector, all
  `Atlas3_Colorable`, after Keen's LCDPanel3x3 back.

## Answers Mal gave on 2026-11-07

Through sprocket-main and in the HoverRepulsors session, where the first models were made.

- **Screens.** Surface 0 is the glass (material `CockpitScreen_02`), surface 1 the tray's keys (`CockpitScreen_01`), as on
  Keen's programmable block, so scripts that draw on either keep working.
- **Logo.** The black glass panel version. `Assets/Design/logo_texture.html` is mockup.html's `lockPanel`, rendered
  to the texture by `Assets/make_logo.py`: Bahnschrift SemiBold, the mockup's tighter tracking, the gear left of the
  wordmark at panel height, printed only (no glow). The tray's back carries the same panel. The logo spec from the
  reproduction sheet: never redraw the icon; brass top to bottom #8C6830, #EED296 .24, #C69E50 .44, #7A5826 .66,
  #DCBC7A .82, #86642E; silver #D6E1EC, #F6FAFD .4, #C4D1DF; amber #EAB256 to #D2963E.
- **Height.** The screen's middle at standing eye height, about 1.6 m above the cell's floor, not centred. Mal: "we'll
  try your way first".
- **Tray.** Swings down when a player is within 3 m or opens the terminal, folds back about 2 s after they leave.
- **Status line.** The programmable block's own `Emissive`, driven by the game. No code for it; only the tray needs code.
- **Shell.** `PaintedMetal_Clean`: paintable everywhere, with no scratches or wear. Mal agreed glossy; Clean was chosen
  after renders showed the glossy texture's scratches. Tell him.
- **Mounting.** The wall variant by its Back only; the inset cube on every side.
- **No DLC materials,** ever. Check with the se-block-texturing skill's `scripts/check_dlc.py` before any release.

## State on 2026-11-07

Finished, and seen in the game: both variants, their tray, keyboard, screens, outline, LODs and build stages. Deployed
to `E:\Data\sesaves\Mods` (the `output` in `mdk.local.ini`); Mal decides each deploy.

How it is made (the scripts are local only):

- `Assets/build_models.py` builds the wall variant (`SprocketProgrammableBlock`), the inset
  (`SprocketProgrammableBlockInset`), the shared tray (`SprocketProgrammableBlock_Tray`, dummy `subpart_Keyboard` at the
  hinge) and its keyboard screen (`SprocketProgrammableBlock_TrayKeys`), and exports through SEUT into `Assets/Build`.
  Run it windowed, behind other windows:
  `blender.exe --no-window-focus --window-geometry 0 0 800 600 --python build_models.py [-- --no-export]`.
  Then derive the stages and LODs (below); their models replace these.
- `Assets/export_preview.py` and the skill's `render_keen.py --extra Assets\Textures\Models\Cubes` render it with the
  game's textures and the mod's own. The tray turns about its dummy's X axis; 115 degrees is the typing angle.
- `Assets/make_logo.py` makes the logo and black glass maps: sources in `Assets/Textures/Models/Cubes` (where SEUT
  finds them), DDS in `Content/Textures/Models/Cubes`. It converts with texconv `-sepalpha`: the maps' alpha is data
  (metalness, gloss, paint), and without it texconv weighted colour by an alpha of 0 and made every mip below full size
  black. The glass's gloss is 180, Keen's cockpit glass.
- `Assets/make_icons.sh` renders both icons.
- `KeyboardTray.cs`: client-side game logic, a 100-tick camera check within 30 m, then 10-tick checks for a player
  within 3 m in front of the hinge or the local player's terminal open on this block, folding 2 s after. Positions come
  from the grid's world matrix, which stays current on a moving grid when the block's does not. `TrayHinge.cs` moves the
  `Keyboard` subpart, per tick only while it swings. The tray opens on a built, undamaged block, powered or not.
- **The tray's sound.** `TrayHinge` plays `SprocketPBTrayOpen` or `SprocketPBTrayFold` (`Content/Data/Audio.sbc`, an
  Arc and a Real pair each, 8 m) through `TraySound.cs` once, as a swing toward a new target starts, and keeps the
  block's world matrix current until the sound ends, so it follows a moving grid. A tray folded at once, as the camera
  leaves, is silent. Mal's brief: a tiny car-window motor, "duiii-i - duit" (the move, a small dip, a short correcting nudge),
  and on the fold a tap as the tray settles into its notch. `Assets/Audio/make_tray_sound.py` synthesizes both into
  `Content/Audio/SprocketProgrammableBlock`, its comments holding what Mal chose and why. The motor peaks 12 dB under
  the tap, the files are loud, and `Volume` in Audio.sbc (0.4) sets the level in the game: 0.15 was too quiet there.
- The folded tray sits flush in a well cut into the shell (open through the device's foot), with the logo panel and a
  vent on the well's floor. `detector_terminal_001` covers the face, tilted with it, and outlines
  `ScreenGlass_section;subpart_Keyboard`: the game reads a `subpart_` entry in a detector's highlight as that subpart.
  Stacked plates sink their hidden backs to different depths (`plate(..., sink)`).

Learned in the game:

- **The tray and its keyboard.** Content set on surface 1 reaches the tray (the renderer passes `ChangeMaterialTexture`
  on to subparts), but the game's hiding of an empty screen does not, and `MyRenderProxy` is forbidden to mods. So the
  keyboard's screen quad is a subpart of the tray's own (`SprocketProgrammableBlock_TrayKeys`, dummy
  `subpart_KeysScreen`), and `KeysScreen.cs` hides it while the block works with no content. A block's text surfaces
  exist only after its game logic's `Init`, so they are looked up on first use.
- **The variant group.** Mal will not redefine Keen's `ProgrammableBlockGroup` (a mod's definition replaces it whole).
  `ProgrammableBlockVariants.cs` appends the mod's blocks to the loaded group at `LoadData` and reruns its
  `Postprocess()`; the whitelist allows it, and the block shows as a variant of Keen's.

**Gaps and half floats.** An `.mwm` stores vertex positions as half floats: steps of 0.49 mm between 0.5 and 1 m from
the block's centre, 0.98 mm between 1 and 2 m. A gap smaller than a step rounds away. Keen's 0.5 mm between a screen
and its placeholder is one step where their screen sits (0.99 m); ours sits 1.06 to 1.21 m out, so it took 1.2 mm
(screen 1.2 mm off the placeholder, placeholder 1.2 mm off the glass) and the housing seam 1.5 mm. `find_zfighting.py`
reads exact positions and cannot see this; check the compiled positions (scratch `mwm_parts.py`) or a half-float copy.

**Workshop.** The page is `Workshop/description.txt`, in Mal's voice. Published 2026-11-07 as an unlisted item, id
3835340489, with Sprocket's se-workshop-publish skill (Sprocket's `.claude/skills`); its title is the folder's name
until Mal renames it on the page. The repository stays private until Mal makes the mod public, and its link on the
unlisted page 404s on purpose: https://github.com/malware-dev/SprocketProgrammableBlock.

Updating it, only when Mal asks, is Sprocket's se-workshop-publish skill with `--mods "SprocketProgrammableBlock"`.
What is this mod's own:

- Its changelog is `Workshop/changelog-next.txt`, not the skill's memory.
- Give `--description` and `--message` absolute paths: the tool looks for a relative one in `Bin64`. A `--message` file
  it cannot find is posted as text, so check the dry run says it read the file. The description file replaces the
  page's description on every update.
- The upload takes the deployed folder, `thumb.png` included, so it carries whatever was built last.
- Check the materials for DLC (`check_dlc.py`, see "Changing the model") before it.

Sprocket Automation's own Workshop link goes into the description's Sprocket section once Sprocket is released
(planned 2026-11-16). The thumbnail is Sprocket's Companion layout, owned by sprocket-main:
`..\Sprocket\art\thumbnail\build_companion_thumb.py Assets\Screenshots\01-both-variants.jpg "Programmable Block"
SprocketProgrammableBlock\thumb.png 0.07 0.19 0.93 0.83`. The blocks are named "Sprocket Programmable Block" and
"... Inset" (Mal: the full company name is too long); the subtypes keep their ids.

**The inset variant** (`SprocketProgrammableBlockInset`): a full `PaintedMetal_Colorable` cube with an armour seam on
each face, the device in a dark well in its Front just inside the face, mounted on every side, airtight like Keen's
inset refill station.

**Build stages and LODs** (se-block-stages skill; Mal: follow Keen's lead). `Assets/Stages/stages.txt` holds the list,
after Keen's refill station: three stages at 0.33/0.66/1.00, LODs at 8, 25 and 45 m. Wall: frame, frame and mounting
plate, housing with glass and logo panel. Inset: frame on every edge, the cube with its empty well, the device set in.
The overlay is in no stage (a decal in Construction paint is a solid quad). The derived models replace build_models.py's,
so after any model change: run build_models.py, copy its blend to `Assets/Stages/SprocketPB.blend`, run
`derive_stages.py` windowed on it with `--stages Assets/Stages/stages.txt --out Assets/Stages/out`, then copy
`Assets/Stages/out/Content/Models/Cubes/large/*.mwm` into the mod. Use the skill's script as of 2026-11-07 13:40 or
later: Hover Repulsors fixed its `lods` lines and its flattening of an inset cube's well in the LODs.

## Changing the model

Load the `se-block-texturing` skill (in `~/.claude/skills/se-block-texturing`) before touching the model: it holds how
Keen textures and details blocks, sizes from Keen's own models, the shared materials and atlases, emissives, icons,
the no-DLC rule, and the scripts:

- `render_keen.py`: renders a built model with the game's real textures; `--extra Assets\Textures\Models\Cubes` adds
  this mod's own materials, and `--icon 128` renders the block icon.
- `find_zfighting.py`: run on the built blend after every build; coplanar faces flicker in the game and no render
  shows it.
- `check_dlc.py`: every material must be used by base-game blocks.
- `se_stamps.py`: Keen's atlas stamps and panel lines; the build script imports it and has `Part.rect` for atlas art.

`D:\Space Engineers\Mods\HoverRepulsors\Assets\build_models.py` is the fuller example the build script came from: the
Hover Repulsor Controller there is the same wall slab and inset cube pair, after Keen's refill station, with a control
panel at a person's size and its terminal detector. Show Mal renders before anything goes into the game; he decides
when it is deployed.
