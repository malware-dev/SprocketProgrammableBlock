using Sandbox.Game.Entities;
using VRage.Game.Entity;
using VRage.ModAPI;

namespace SprocketProgrammableBlock
{
    /// <summary>Plays the keyboard tray's motor at its block as the tray starts to open or fold.</summary>
    public class TraySound
    {
        // Content/Data/Audio.sbc: each name is an Arc and a Real sound.
        readonly MySoundPair _open = new MySoundPair("SprocketPBTrayOpen");
        readonly MySoundPair _fold = new MySoundPair("SprocketPBTrayFold");
        readonly MyEntity3DSoundEmitter _emitter;

        /// <summary>Initializes the sound of <paramref name="block" />'s tray.</summary>
        public TraySound(IMyEntity block)
        {
            _emitter = new MyEntity3DSoundEmitter((MyEntity)block);
        }

        /// <summary>Gets whether a swing is still heard.</summary>
        public bool IsPlaying => _emitter.IsPlaying;

        /// <summary>Plays the tray opening if <paramref name="isOpening" />, otherwise folding, cutting off a swing still heard.</summary>
        public void Play(bool isOpening)
        {
            _emitter.PlaySound(isOpening ? _open : _fold, true);
        }

        /// <summary>Moves the sound to where its block is now.</summary>
        /// <remarks>Call every tick while <see cref="IsPlaying" />; Hover Repulsors' emitters need the same.</remarks>
        public void Update()
        {
            _emitter.Update();
        }

        /// <summary>Stops any swing still heard.</summary>
        public void Stop()
        {
            _emitter.StopSound(true);
        }

        /// <summary>Stops the sound and releases the emitter, as the block closes.</summary>
        public void Close()
        {
            Stop();
            _emitter.Cleanup();
        }
    }
}
