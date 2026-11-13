using System.Collections.Generic;
using Sandbox.Game.Components;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using IMyTextSurface = Sandbox.ModAPI.Ingame.IMyTextSurface;
using IMyTextSurfaceProvider = Sandbox.ModAPI.Ingame.IMyTextSurfaceProvider;
using VRage.Game.Entity;
using VRage.Game.GUI.TextPanel;
using VRage.ModAPI;
using VRage.Utils;
using VRageRender.Messages;

namespace SprocketProgrammableBlock
{
    /// <summary>Gives the keyboard's screen the surface's drawn texture, and hides it while it has no content, so the keyboard art behind it shows.</summary>
    public class KeysScreen
    {
        // Assets/build_models.py: the tray's dummy subpart_KeysScreen, holding only the keyboard's screen quad.
        const string SubpartName = "KeysScreen";

        // The block's ScreenAreas: surface 1 is the keyboard, drawn on CockpitScreen_01.
        const int SurfaceIndex = 1;
        const string ScreenMaterial = "CockpitScreen_01";

        const uint Unassigned = 0xFFFFFFFF;     // MyRenderProxy.RENDER_ID_UNASSIGNED

        readonly IMyTerminalBlock _block;
        IMyTextSurface _surface;
        MyEntitySubpart _screen;
        bool _isShown = true;
        uint _boundTo = Unassigned;
        Dictionary<MyStringId, MyTextureChange> _given;

        /// <summary>Initializes the keyboard screen of <paramref name="block" />.</summary>
        public KeysScreen(IMyTerminalBlock block)
        {
            _block = block;
        }

        /// <summary>Binds and shows or hides the screen on <paramref name="tray" /> by the surface's content, as the game does its own.</summary>
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
            Bind();
            // MyTextPanelComponent: a working block's surface with no content is hidden; otherwise it shows its content,
            // or the Offline image while the block is not working.
            var isShown = !(_block.IsWorking && _surface.ContentType == ContentType.NONE);
            if (isShown == _isShown)
                return;
            _isShown = isShown;
            ((IMyEntity)_screen).Visible = isShown;
        }

        void Bind()
        {
            // The game gives a screen its drawn texture on the block's own render objects only
            // (MyRenderComponentScreenAreas.ChangeTexture), and the renderer applies a change to the one object named
            // (MyTextureChangeManager.ChangeMaterialTexture). The subpart's render component is told instead, as the game
            // passes a skin to subparts (MyRenderComponentBase.UpdateRenderTextureChanges). A new subpart, or a skin
            // replacing the changes, needs binding again.
            var block = (MyCubeBlock)_block;
            var screens = block.Render as MyRenderComponentScreenAreas;
            if (screens == null || !block.InScene || block.Closed)
                return;
            var id = _screen.Render.GetRenderObjectID();
            if (id == Unassigned || (id == _boundTo && _screen.Render.TextureChanges == _given))
                return;
            // The block's own changes (a skin) come along. A new dictionary each bind: the render component keeps it, and
            // the renderer reads it later.
            var skin = block.Render.TextureChanges;
            var changes = skin == null ? new Dictionary<MyStringId, MyTextureChange>() : new Dictionary<MyStringId, MyTextureChange>(skin);
            changes[MyStringId.GetOrCompute(ScreenMaterial)] = new MyTextureChange
            {
                ColorMetalFileName = screens.GenerateOffscreenTextureName(block.EntityId, SurfaceIndex)
            };
            _screen.Render.UpdateRenderTextureChanges(changes);
            _boundTo = id;
            _given = changes;
        }
    }
}
