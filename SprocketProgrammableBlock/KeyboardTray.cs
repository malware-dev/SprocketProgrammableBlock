using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace SprocketProgrammableBlock
{
    /// <summary>Opens the block's keyboard tray for a player standing at it or using its terminal, and folds it after they leave.</summary>
    /// <remarks>Runs on clients only: the tray is drawn, and the server keeps no state for it.</remarks>
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_MyProgrammableBlock), false, "SprocketProgrammableBlock", "SprocketProgrammableBlockInset")]
    public class KeyboardTray : MyGameLogicComponent
    {
        // The mod's CLAUDE.md: the tray opens for a player within 3 m, and folds about 2 s after they leave.
        const double ReachSquared = 3.0 * 3.0;
        const int FoldDelayChecks = 12;

        // Players are looked for every 10 ticks, and only while the camera is this close; 100-tick checks keep watch for it.
        const double WatchedSquared = 30.0 * 30.0;

        readonly List<IMyPlayer> _players = new List<IMyPlayer>();
        IMyCubeBlock _block;
        TrayHinge _hinge;
        KeysScreen _keys;
        bool _isWatched;
        int _checksSinceWanted = FoldDelayChecks;

        /// <inheritdoc />
        public override void Init(MyObjectBuilder_EntityBase objectBuilder)
        {
            if (MyAPIGateway.Utilities.IsDedicated)
                return;
            _block = (IMyCubeBlock)Entity;
            _hinge = new TrayHinge(Entity);
            _keys = new KeysScreen((IMyTerminalBlock)Entity);
            NeedsUpdate = MyEntityUpdateEnum.EACH_100TH_FRAME;
        }

        /// <inheritdoc />
        public override void Close()
        {
            _hinge?.Close();
            base.Close();
        }

        /// <inheritdoc />
        public override void UpdateBeforeSimulation100()
        {
            var camera = MyAPIGateway.Session.Camera;
            var isWatched = camera != null && Vector3D.DistanceSquared(camera.Position, BlockWorld().Translation) < WatchedSquared;
            if (isWatched == _isWatched)
                return;
            _isWatched = isWatched;
            if (isWatched)
            {
                NeedsUpdate |= MyEntityUpdateEnum.EACH_10TH_FRAME;
                return;
            }
            NeedsUpdate &= ~(MyEntityUpdateEnum.EACH_10TH_FRAME | MyEntityUpdateEnum.EACH_FRAME);
            _checksSinceWanted = FoldDelayChecks;
            _hinge.Fold();
        }

        /// <inheritdoc />
        public override void UpdateBeforeSimulation10()
        {
            if (IsWanted())
                _checksSinceWanted = 0;
            else if (_checksSinceWanted < FoldDelayChecks)
                _checksSinceWanted++;
            if (_hinge.Swing(_checksSinceWanted < FoldDelayChecks))
                NeedsUpdate |= MyEntityUpdateEnum.EACH_FRAME;
            // The surface raises no event when its content changes, and this check already runs while anyone could see it.
            _keys.Refresh(_hinge.Tray);
        }

        /// <inheritdoc />
        /// <remarks>Runs every tick only while the tray swings or its sound plays, for a smooth swing and a sound that follows a moving grid.</remarks>
        public override void UpdateBeforeSimulation()
        {
            if (!_hinge.Step())
                NeedsUpdate &= ~MyEntityUpdateEnum.EACH_FRAME;
        }

        bool IsWanted()
        {
            // A projected block has no physics, and is no device yet.
            if (!_block.IsFunctional || _block.CubeGrid.Physics == null)
                return false;
            // Only the local player's terminal is known to this client.
            if (MyAPIGateway.Gui.InteractedEntity == Entity)
                return true;
            return IsPlayerInFront();
        }

        // Measured from the tray's hinge, at the device's foot: the wall variant's device is at the back of its cell and
        // the inset's at the front. A player in the room behind the device is close, and is not standing at it.
        bool IsPlayerInFront()
        {
            var tray = _hinge.Tray;
            if (tray == null)
                return false;
            var world = BlockWorld();
            var hinge = Vector3D.Transform(tray.PositionComp.LocalMatrixRef.Translation, world);
            var forward = world.Forward;
            _players.Clear();
            MyAPIGateway.Players.GetPlayers(_players);
            foreach (var player in _players)
            {
                var character = player.Character;
                if (character == null || character.IsDead)
                    continue;
                var position = character.GetPosition();
                if (Vector3D.DistanceSquared(position, hinge) < ReachSquared && Vector3D.Dot(position - hinge, forward) > 0)
                    return true;
            }
            return false;
        }

        // From the grid's world matrix, which the game keeps current: a block's, and its folded tray's, are only updated
        // on a moving grid while something needs them (NeedsWorldMatrix).
        MatrixD BlockWorld() => (MatrixD)_block.LocalMatrix * _block.CubeGrid.WorldMatrix;
    }
}
