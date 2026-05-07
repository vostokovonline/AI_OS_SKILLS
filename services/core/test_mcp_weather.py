#!/usr/bin/env python3
"""
Test MCP generation with simple weather skill
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from mcp_skill_generator import mcp_skill_generator
from logging_config import get_logger

logger = get_logger(__name__)


async def test_weather_skill():
    """Test generating a simple weather skill"""
    print("\n=== Weather Skill Generation Test ===")

    missing_caps = ["weather_api", "temperature_check"]
    requirements = {
        "input_type": "text",
        "output_type": "text",
        "artifacts": ["KNOWLEDGE"]
    }
    goal_context = {
        "title": "Check weather in London",
        "description": "Get current temperature for London"
    }

    try:
        print(f"\nGenerating skill for: {missing_caps}")

        plugin_id = await mcp_skill_generator.generate_skill(
            missing_capabilities=missing_caps,
            requirements=requirements,
            goal_context=goal_context
        )

        print(f"\n✓ Skill generated successfully!")
        print(f"  Plugin ID: {plugin_id}")

        # Get the plugin
        plugin = await mcp_skill_generator.get_plugin(plugin_id)

        if plugin:
            print(f"\n✓ Plugin registered in MCP:")
            print(f"  ID: {plugin.plugin_id}")
            print(f"  Version: {plugin.version}")
            print(f"  Status: {plugin.status}")
            print(f"  Capabilities: {plugin.capabilities}")

        # Check file
        plugin_path = mcp_skill_generator.plugins_dir / f"{plugin_id}.py"
        if plugin_path.exists():
            print(f"\n✓ Plugin file created: {plugin_path}")
            with open(plugin_path, 'r') as f:
                code = f.read()
                lines = code.count('\n')
                print(f"  Lines of code: {lines}")
                print(f"\n  First 20 lines:")
                print('  ' + '\n  '.join(code.split('\n')[:20]))

        return True

    except Exception as e:
        print(f"\n✗ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    result = await test_weather_skill()
    print("\n" + "=" * 60)
    if result:
        print("✓ MCP WEATHER SKILL TEST PASSED")
    else:
        print("✗ MCP WEATHER SKILL TEST FAILED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
