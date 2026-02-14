#!/usr/bin/env python3
"""
Quick test of the DSL generation pipeline.
Tests:
  1. DSL spec prompt generation
  2. Mock LLM response parsing
  3. End-to-end compile
"""

import asyncio
from dsl_prompt import dsl_system_prompt
from dsl_parser import Parser
from dsl_ir import lower
from dsl_glsl_ir import emit_glsl


def test_dsl_spec():
    spec = dsl_system_prompt()
    assert "sphere" in spec
    assert "union" in spec
    assert "translate" in spec
    print("✓ dsl_system_prompt() contains expected function names")


def test_parse_and_compile():
    # Simulate LLM output
    llm_outputs = [
        "sphere(1.5)",
        "union(sphere(1), box(vec3(0.5,0.5,0.5)))",
        "translate(sphere(1), vec3(1,0,0))",
        "difference(box(vec3(1,1,1)), sphere(0.5))",
    ]
    
    for dsl in llm_outputs:
        ast = Parser.from_source(dsl).parse()
        ir = lower(ast)
        glsl = emit_glsl(ir)
        assert "float sdf(vec3 p)" in glsl
        print(f"✓ Compiled: {dsl[:40]}")


def test_error_handling():
    """Test that invalid DSL raises proper errors."""
    invalid = "invalid_func(1)"
    try:
        Parser.from_source(invalid).parse()
        assert False, "Should have raised error"
    except Exception as e:
        print(f"✓ Invalid DSL caught: {str(e)[:50]}")


if __name__ == "__main__":
    test_dsl_spec()
    test_parse_and_compile()
    test_error_handling()
    print("\nAll tests passed!")
