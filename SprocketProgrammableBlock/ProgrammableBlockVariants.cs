using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Definitions;
using VRage.Game;
using VRage.Game.Components;

namespace SprocketProgrammableBlock
{
    /// <summary>Adds the mod's blocks to the game's programmable block variant group, beside Keen's own.</summary>
    [MySessionComponentDescriptor(MyUpdateOrder.NoUpdate)]
    public class ProgrammableBlockVariants : MySessionComponentBase
    {
        // The game's Data\BlockVariantGroups.sbc. A mod's definition of the group would replace it whole, dropping blocks
        // Keen adds later and other mods' changes, so the mod's blocks are added to the loaded group instead.
        const string GroupName = "ProgrammableBlockGroup";

        // Content\Data\CubeBlocks\SprocketProgrammableBlock.sbc; a subtype not defined is skipped.
        static readonly string[] Subtypes = { "SprocketProgrammableBlock", "SprocketProgrammableBlockInset" };

        /// <inheritdoc />
        public override void LoadData()
        {
            MyBlockVariantGroup group;
            if (!MyDefinitionManager.Static.GetBlockVariantGroupDefinitions().TryGetValue(GroupName, out group))
                return;
            var blocks = new List<MyCubeBlockDefinition>(group.Blocks);
            foreach (var subtype in Subtypes)
            {
                MyCubeBlockDefinition block;
                var id = new MyDefinitionId(typeof(MyObjectBuilder_MyProgrammableBlock), subtype);
                // The game can keep loaded definitions for the next world with the same mods, so a block may be in already.
                if (!MyDefinitionManager.Static.TryGetCubeBlockDefinition(id, out block) || blocks.Contains(block))
                    continue;
                blocks.Add(block);
                // MyDefinitionManager.InitBlockGroups: each block knows its group.
                block.BlockVariantsGroup = group;
            }
            if (blocks.Count == group.Blocks.Length)
                return;
            group.Blocks = blocks.ToArray();
            // Rebuilds what the game derives from the list once at load: the pairs, each size's variants, and which block shows.
            group.Postprocess();
        }
    }
}
