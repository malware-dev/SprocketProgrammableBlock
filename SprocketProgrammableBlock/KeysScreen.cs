using Sandbox.ModAPI;
using IMyTextSurface = Sandbox.ModAPI.Ingame.IMyTextSurface;
using IMyTextSurfaceProvider = Sandbox.ModAPI.Ingame.IMyTextSurfaceProvider;
using VRage.Game.Entity;
using VRage.Game.GUI.TextPanel;
using VRage.ModAPI;

namespace SprocketProgrammableBlock
{
    /// <summary>Hides the keyboard's screen while it has no content, so the keyboard art behind it shows.</summary>
    public class KeysScreen
    {
        // Assets/build_models.py: the tray's dummy subpart_KeysScreen, holding only the keyboard's screen quad. The game
        // hides an empty screen on the block's own model only (MyRenderComponentScreenAreas.ChangeTexture), and the mod
        // whitelist forbids MyRenderProxy, so a whole subpart is hidden instead.
        const string SubpartName = "KeysScreen";

        // The block's ScreenAreas: surface 1 is the keyboard.
        const int SurfaceIndex = 1;

        readonly IMyTerminalBlock _block;
        IMyTextSurface _surface;
        MyEntitySubpart _screen;
        bool _isShown = true;

        /// <summary>Initializes the keyboard screen of <paramref name="block" />.</summary>
        public KeysScreen(IMyTerminalBlock block)
        {
            _block = block;
        }

        /// <summary>Shows or hides the screen on <paramref name="tray" /> by the surface's content, as the game does its own.</summary>
        public void Refresh(MyEntitySubpart tray)
        {
            // The block makes its surfaces after its game logic's Init (MyMultiTextPanelComponent.OnAddedToContainer).
            if (_surface == null)
                _surface = ((IMyTextSurfaceProvider)_block).GetSurface(SurfaceIndex);
            if (tray == null || _surface == null)
                return;
            if (_screen == null || _screen.Closed)
            {
                if (!tray.TryGetSubpart(SubpartName, out _screen))
                    return;
                // A new tray's screen starts shown.
                _isShown = true;
            }
            // MyTextPanelComponent: a working block's surface with no content is hidden; otherwise it shows its content,
            // or the Offline image while the block is not working.
            var isShown = !(_block.IsWorking && _surface.ContentType == ContentType.NONE);
            if (isShown == _isShown)
                return;
            _isShown = isShown;
            ((IMyEntity)_screen).Visible = isShown;
        }
    }
}
