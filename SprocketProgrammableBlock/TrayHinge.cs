using System;
using VRage.Game.Entity;
using VRage.ModAPI;
using VRageMath;

namespace SprocketProgrammableBlock
{
    /// <summary>Swings a block's keyboard tray between folded and its typing angle.</summary>
    public class TrayHinge
    {
        // Assets/build_models.py: the dummy subpart_Keyboard sits on the hinge.
        const string SubpartName = "Keyboard";

        // The mod's CLAUDE.md: the tray turns about its dummy's X axis, 115 degrees to the typing angle. SEUT exports a
        // subpart with -Z forward, which keeps the model's X as the subpart's own X and the angle's sign.
        static readonly float TypingAngle = MathHelper.ToRadians(115f);

        // Shares of the full swing per tick: half a second down, 0.7 s back up.
        const float OpenStep = 1f / 30f;
        const float FoldStep = 1f / 42f;

        readonly IMyEntity _block;
        MyEntitySubpart _tray;
        Matrix _rest;
        float _openness;
        float _target;
        bool _hasTurnedOnWorldMatrix;

        /// <summary>Initializes the hinge of <paramref name="block" />'s tray.</summary>
        public TrayHinge(IMyEntity block)
        {
            _block = block;
        }

        /// <summary>Gets the tray, or null while the block's model has none.</summary>
        public MyEntitySubpart Tray => FindTray() ? _tray : null;

        /// <summary>Sets whether the tray is to be open, and returns true if it has to move to get there.</summary>
        public bool Swing(bool isOpen)
        {
            _target = isOpen ? 1f : 0f;
            return FindTray() && _openness != _target;
        }

        /// <summary>Moves the tray one tick toward where it is to be, and returns true if it is still moving.</summary>
        public bool Step()
        {
            if (!FindTray())
                return false;
            _openness = _target > _openness ? Math.Min(_target, _openness + OpenStep) : Math.Max(_target, _openness - FoldStep);
            Place();
            return _openness != _target;
        }

        /// <summary>Folds the tray at once, without a swing.</summary>
        public void Fold()
        {
            _target = 0f;
            _openness = 0f;
            if (_tray != null && !_tray.Closed)
                Place();
        }

        // A build stage, damage or repair replaces the block's model and its subparts with a new tray at rest.
        bool FindTray()
        {
            if (_tray != null && !_tray.Closed)
                return true;
            if (!_block.TryGetSubpart(SubpartName, out _tray))
                return false;
            _rest = _tray.PositionComp.LocalMatrixRef;
            Place();
            return true;
        }

        void Place()
        {
            // Smoothstep: the tray starts and stops gently.
            var eased = _openness * _openness * (3f - 2f * _openness);
            var matrix = Matrix.CreateRotationX(eased * TypingAngle) * _rest;
            _tray.PositionComp.SetLocalMatrix(ref matrix);
            KeepWorldMatrix(_openness > 0f);
        }

        // An unfolded tray on a moving grid needs its block's world matrix kept current, as Keen's door does on clients.
        void KeepWorldMatrix(bool isNeeded)
        {
            if (isNeeded == _hasTurnedOnWorldMatrix)
                return;
            if (isNeeded && _block.NeedsWorldMatrix)
                return;
            _block.NeedsWorldMatrix = isNeeded;
            _hasTurnedOnWorldMatrix = isNeeded;
        }
    }
}
