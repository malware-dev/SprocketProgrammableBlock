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
        readonly TraySound _sound;
        MyEntitySubpart _tray;
        Matrix _rest;
        float _openness;
        float _target;
        float _heardTarget;
        bool _hasTurnedOnWorldMatrix;

        /// <summary>Initializes the hinge of <paramref name="block" />'s tray.</summary>
        public TrayHinge(IMyEntity block)
        {
            _block = block;
            _sound = new TraySound(block);
        }

        /// <summary>Gets the tray, or null while the block's model has none.</summary>
        public MyEntitySubpart Tray => FindTray() ? _tray : null;

        /// <summary>Sets whether the tray is to be open, and returns true if it has to move to get there.</summary>
        /// <remarks>A swing toward a new target plays its sound here, as it starts.</remarks>
        public bool Swing(bool isOpen)
        {
            _target = isOpen ? 1f : 0f;
            var mustMove = FindTray() && _openness != _target;
            if (mustMove && _heardTarget != _target)
            {
                _sound.Play(isOpen);
                _heardTarget = _target;
            }
            return mustMove;
        }

        /// <summary>Moves the tray one tick toward where it is to be, and returns true if it is still moving or heard.</summary>
        public bool Step()
        {
            if (!FindTray())
            {
                // A new tray resumes the swing; this lets that swing play its sound again.
                _heardTarget = -1f;
                _sound.Stop();
                KeepWorldMatrix(false);
                return false;
            }
            _sound.Update();
            if (_openness != _target)
            {
                _openness = _target > _openness ? Math.Min(_target, _openness + OpenStep) : Math.Max(_target, _openness - FoldStep);
                Place();
                if (_openness != _target)
                    return true;
            }
            // Playback ends on its own, between any two reads: one read decides both the world matrix and the ticks.
            var isPlaying = _sound.IsPlaying;
            KeepWorldMatrix(_openness > 0f || isPlaying);
            return isPlaying;
        }

        /// <summary>Folds the tray at once, without a swing or a sound.</summary>
        public void Fold()
        {
            _target = 0f;
            _heardTarget = 0f;
            _openness = 0f;
            _sound.Stop();
            if (_tray != null && !_tray.Closed)
                Place();
            else
                KeepWorldMatrix(false);
        }

        /// <summary>Stops the tray's sound for good, as its block closes.</summary>
        public void Close()
        {
            _sound.Close();
        }

        // The sound plays from the block, so its position must follow a moving grid until the fold's tap has ended.
        bool IsWorldMatrixNeeded => _openness > 0f || _sound.IsPlaying;

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
            KeepWorldMatrix(IsWorldMatrixNeeded);
        }

        // An unfolded tray, or a sound, on a moving grid needs its block's world matrix kept current, as Keen's door does
        // on clients.
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
