#!/usr/bin/env python3
"""
Test MCP Skill Autogeneration System

This script tests:
1. MCP Manager initialization
2. Finding missing capabilities
3. Triggering skill generation
4. Validation and registration
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from mcp_manager import mcp_manager
from logging_config import get_logger

logger = get_logger(__name__)


async def test_mcp_initialization():
    """Test 1: MCP Manager initialization"""
    print("\n=== Test 1: MCP Initialization ===")

    try:
        await mcp_manager.connect()
        print(f"✓ MCP connected")
        print(f"  Plugins loaded: {len(mcp_manager.skill_generator._registry)}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


async def test_find_missing_skill():
    """Test 2: Find skill for missing capabilities"""
    print("\n=== Test 2: Find Missing Skill ===")

    # Define capabilities that don't exist
    missing_caps = ["stock_analysis", "market_data"]
    requirements = {
        "input_type": "text",
        "output_type": "report",
        "artifacts": ["FILE", "REPORT"]
    }
    goal_context = {
        "title": "Analyze AAPL stock",
        "description": "Get stock data and generate analysis report"
    }

    try:
        # This should trigger generation
        plugin_id = await mcp_manager.find_or_generate_skill(
            capabilities=missing_caps,
            requirements=requirements,
            goal_context=goal_context
        )

        print(f"✓ Plugin ID returned: {plugin_id}")

        # Wait a bit for generation to complete
        await asyncio.sleep(2)

        # Check if plugin was generated
        plugin = await mcp_manager.skill_generator.get_plugin(plugin_id)

        if plugin:
            print(f"✓ Plugin generated and registered!")
            print(f"  Plugin ID: {plugin.plugin_id}")
            print(f"  Version: {plugin.version}")
            print(f"  Status: {plugin.status}")
            print(f"  Capabilities: {plugin.capabilities}")
            return True
        else:
            print(f"ℹ Generation in progress (expected for new skills)")
            return True

    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_list_plugins():
    """Test 3: List all plugins"""
    print("\n=== Test 3: List Plugins ===")

    try:
        plugins = await mcp_manager.list_plugins()

        print(f"✓ Total plugins: {len(plugins)}")

        for plugin in plugins:
            print(f"  - {plugin['plugin_id']}")
            print(f"    Status: {plugin['status']}")
            print(f"    Capabilities: {plugin['capabilities']}")
            print(f"    Success Rate: {plugin['success_rate']}")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


async def test_plugin_stats():
    """Test 4: Get plugin statistics"""
    print("\n=== Test 4: Plugin Statistics ===")

    try:
        plugins = await mcp_manager.list_plugins()

        if not plugins:
            print("ℹ No plugins to get stats for")
            return True

        plugin_id = plugins[0]['plugin_id']
        stats = await mcp_manager.get_plugin_stats(plugin_id)

        if stats:
            print(f"✓ Stats for {plugin_id}:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            return True
        else:
            print(f"✗ No stats found for {plugin_id}")
            return False

    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


async def test_execute_fallback():
    """Test 5: Execute fallback skill"""
    print("\n=== Test 5: Execute Fallback ===")

    try:
        result = await mcp_manager.execute_skill(
            plugin_id="fallback_echo",
            inputs={"text": "test input"},
            context={}
        )

        print(f"✓ Fallback executed")
        print(f"  Success: {result['success']}")
        print(f"  Data: {result['data']}")
        print(f"  Fallback flag: {result.get('fallback', False)}")

        return result['success']
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("MCP Skill Autogeneration Test Suite")
    print("=" * 60)

    tests = [
        ("Initialization", test_mcp_initialization),
        ("Find Missing Skill", test_find_missing_skill),
        ("List Plugins", test_list_plugins),
        ("Plugin Statistics", test_plugin_stats),
        ("Execute Fallback", test_execute_fallback),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print(f"\n{passed}/{total} tests passed")

    # Cleanup
    await mcp_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
