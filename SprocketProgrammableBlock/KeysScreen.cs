using System.Collections.Generic;
using Sandbox.Definitions;
using Sandbox.Game.Components;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using IMyTextSurface = Sandbox.ModAPI.Ingame.IMyTextSurface;
using IMyTextSurfaceProvider = Sandbox.ModAPI.Ingame.IMyTextSurfaceProvider;
using VRage.Game.Entity;
using VRage.Game.GUI.TextPanel;
using VRage.ModAPI;
using VRage.Utils;
using VRageMath;
using VRageRender.Messages;

namespace SprocketProgrammableBlock
{
    /// <summary>Gives the keyboard's screen the picture the game shows on the surface, and hides it while the game would, so the keyboard art behind it shows.</summary>
    public class KeysScreen
    {
        // Assets/build_models.py: the tray's dummy subpart_KeysScreen, holding only the keyboard's screen quad.
        const string SubpartName = "KeysScreen";

        // The block's ScreenAreas: surface 1 is the keyboard, drawn on CockpitScreen_01.
        const int SurfaceIndex = 1;
        const string ScreenMaterial = "CockpitScreen_01";

        const uint Unassigned = 0xFFFFFFFF;     // MyRenderProxy.RENDER_ID_UNASSIGNED

        // MyTextPanelComponent: the stock image of a surface whose block is not working, and the wide one for a surface
        // more than four times wider than tall.
        const string OfflineImage = "Offline";
        const string OfflineWideImage = "Offline_wide";

        // MyGeneratedTexture: the renderer's transparent black 1x1 texture, which the game gives a surface with nothing to draw.
        const string EmptyTexture = "EMPTY";

        readonly IMyTerminalBlock _block;
        IMyTextSurface _surface;
        MyEntitySubpart _screen;
        bool _isShown = true;
        uint _boundTo = Unassigned;
        string _boundPicture;
        string _drawnTexture;
        Dictionary<MyStringId, MyTextureChange> _given;

        /// <summary>Initializes the keyboard screen of <paramref name="block" />.</summary>
        public KeysScreen(IMyTerminalBlock block)
        {
            _block = block;
        }

        /// <summary>Gives the screen on <paramref name="tray" /> the surface's picture, and shows or hides it, as the game does its own.</summary>
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
            var picture = Picture();
            if (picture != null)
                Bind(picture);
            var isShown = picture != null;
            if (isShown == _isShown)
                return;
            _isShown = isShown;
            ((IMyEntity)_screen).Visible = isShown;
        }

        // The texture the game puts on the surface's own material, or null where it shows none and hides the screen.
        // MyTextPanelComponent: a block that is not working shows the Offline image; a working surface with no content
        // shows nothing. Text and images with no text on a black background shows the current image's file when the image
        // is stretched, and the renderer's empty texture when no image is selected; everything else is drawn into the
        // surface's generated texture.
        string Picture()
        {
            if (!_block.IsWorking)
            {
                var size = _surface.SurfaceSize;
                return ImagePath(size.X > size.Y * 4 ? OfflineWideImage : OfflineImage);
            }
            var content = _surface.ContentType;
            if (content == ContentType.NONE)
                return null;
            if (content == ContentType.TEXT_AND_IMAGE && _surface.BackgroundColor == Color.Black && string.IsNullOrEmpty(_surface.GetText()))
            {
                var image = _surface.CurrentlyShownImage;
                if (string.IsNullOrEmpty(image))
                    return EmptyTexture;
                if (!_surface.PreserveAspectRatio)
                    return ImagePath(image);
            }
            return DrawnTexture();
        }

        // The name depends only on the block and the surface, so it is made once.
        string DrawnTexture()
        {
            if (_drawnTexture != null)
                return _drawnTexture;
            var render = ((MyCubeBlock)_block).Render as MyRenderComponentScreenAreas;
            _drawnTexture = render?.GenerateOffscreenTextureName(_block.EntityId, SurfaceIndex);
            return _drawnTexture;
        }

        // MyTextPanelComponent.GetPathForID: an LCD texture's file, by its id.
        static string ImagePath(string id)
        {
            if (string.IsNullOrEmpty(id))
                return null;
            var definition = MyDefinitionManager.Static.GetDefinition<MyLCDTextureDefinition>(id);
            return definition?.TexturePath;
        }

        void Bind(string picture)
        {
            // The game gives a surface's picture to the block's own render objects only
            // (MyRenderComponentScreenAreas.ChangeTexture), and the renderer applies a change to the one object named
            // (MyTextureChangeManager.ChangeMaterialTexture). The subpart's render component is told instead, as the game
            // passes a skin to subparts (MyRenderComponentBase.UpdateRenderTextureChanges). A new subpart, a skin
            // replacing the changes, or a new picture needs binding again.
            var block = (MyCubeBlock)_block;
            if (!block.InScene || block.Closed)
                return;
            var id = _screen.Render.GetRenderObjectID();
            if (id == Unassigned || (id == _boundTo && picture == _boundPicture && _screen.Render.TextureChanges == _given))
                return;
            // The block's own changes (a skin) come along. A new dictionary each bind: the render component keeps it, and
            // the renderer reads it later.
            var skin = block.Render.TextureChanges;
            var changes = skin == null ? new Dictionary<MyStringId, MyTextureChange>() : new Dictionary<MyStringId, MyTextureChange>(skin);
            changes[MyStringId.GetOrCompute(ScreenMaterial)] = new MyTextureChange { ColorMetalFileName = picture };
            _screen.Render.UpdateRenderTextureChanges(changes);
            _boundTo = id;
            _boundPicture = picture;
            _given = changes;
        }
    }
}
