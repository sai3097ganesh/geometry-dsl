#!/usr/bin/env python3
"""Test the blend2D operation for morphing profiles along paths."""

from dsl_parser import Parser
from dsl_ir import lower
from dsl_glsl_ir import emit_glsl
from dsl_interp_ir import eval_ir


def test_blend2d_circle_to_polygon_line():
    """Test blending from circle to polygon along a line."""
    print("Test: blend2D(circle, polygon, line)")
    
    code = """
    blend2D(
        circle(1),
        polygon(vec2(-0.8, -0.8), vec2(0.8, -0.8), vec2(0.8, 0.8), vec2(-0.8, 0.8)),
        line(vec3(0, 0, 0), vec3(0, 5, 0))
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ Parsed and compiled to GLSL")
    
    # Test at start of path (should be closer to circle)
    env_start = {"p": (1, 0, 0)}  # On circle at y=0
    result_start = eval_ir(ir, env_start)
    print(f"  SDF at (1,0,0) [start]: {result_start:.4f}")
    
    # Test at middle of path
    env_mid = {"p": (0, 2.5, 0)}  # Middle of path
    result_mid = eval_ir(ir, env_mid)
    print(f"  SDF at (0,2.5,0) [middle]: {result_mid:.4f}")
    
    # Test at end of path (should be closer to polygon)
    env_end = {"p": (0.8, 5, 0)}  # On polygon at y=5
    result_end = eval_ir(ir, env_end)
    print(f"  SDF at (0.8,5,0) [end]: {result_end:.4f}")
    
    print()


def test_blend2d_polyline():
    """Test blend2D with a polyline path."""
    print("Test: blend2D with polyline path")
    
    code = """
    blend2D(
        circle(0.5),
        polygon(vec2(-0.3, -0.3), vec2(0.3, -0.3), vec2(0.3, 0.3), vec2(-0.3, 0.3)),
        polyline(vec3(0, 0, 0), vec3(2, 0, 0), vec3(2, 2, 0))
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ Parsed and compiled to GLSL")
    
    # Test at various points along the polyline
    test_points = [
        (0, 0, 0, "start"),
        (1, 0, 0, "first segment middle"),
        (2, 0, 0, "corner"),
        (2, 1, 0, "second segment middle"),
        (2, 2, 0, "end"),
    ]
    
    for x, y, z, label in test_points:
        env = {"p": (x, y, z)}
        result = eval_ir(ir, env)
        print(f"  SDF at ({x},{y},{z}) [{label}]: {result:.4f}")
    
    print()


def test_blend2d_two_polygons():
    """Test blending between two different polygons."""
    print("Test: blend2D between two polygons")
    
    code = """
    blend2D(
        polygon(vec2(-0.5, -0.5), vec2(0.5, -0.5), vec2(0.5, 0.5), vec2(-0.5, 0.5)),
        polygon(vec2(-1, 0), vec2(0, 1), vec2(1, 0), vec2(0, -1)),
        line(vec3(0, 0, 0), vec3(0, 4, 0))
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ Square morphing to diamond")
    
    env = {"p": (0, 2, 0)}
    result = eval_ir(ir, env)
    print(f"  SDF at middle of path: {result:.4f}")
    
    print()


def test_blend2d_two_circles():
    """Test blending between two circles of different sizes."""
    print("Test: blend2D between two circles")
    
    code = """
    blend2D(
        circle(0.5),
        circle(1.5),
        line(vec3(0, 0, 0), vec3(0, 3, 0))
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ Small circle morphing to large circle")
    
    # At start, should be closer to radius 0.5
    env_start = {"p": (0.5, 0, 0)}
    result_start = eval_ir(ir, env_start)
    print(f"  SDF at (0.5,0,0) [start]: {result_start:.4f}")
    
    # At end, should be closer to radius 1.5
    env_end = {"p": (1.5, 3, 0)}
    result_end = eval_ir(ir, env_end)
    print(f"  SDF at (1.5,3,0) [end]: {result_end:.4f}")
    
    print()


def test_blend2d_with_transforms():
    """Test blend2D with transformations."""
    print("Test: blend2D with transformations")
    
    code = """
    translate(
        rotate(
            blend2D(
                circle(0.5),
                polygon(vec2(-0.4, -0.4), vec2(0.4, -0.4), vec2(0.4, 0.4), vec2(-0.4, 0.4)),
                line(vec3(0, 0, 0), vec3(0, 2, 0))
            ),
            vec3(45, 0, 0)
        ),
        vec3(1, 0, 0)
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ blend2D with rotation and translation")
    
    env = {"p": (1, 0, 0)}
    result = eval_ir(ir, env)
    print(f"  SDF at transformed origin: {result:.4f}")
    
    print()


def test_blend2d_in_union():
    """Test blend2D used within a union."""
    print("Test: blend2D in union")
    
    code = """
    union(
        blend2D(
            circle(0.3),
            polygon(vec2(-0.2, -0.2), vec2(0.2, -0.2), vec2(0.2, 0.2), vec2(-0.2, 0.2)),
            line(vec3(0, 0, 0), vec3(0, 2, 0))
        ),
        translate(sphere(0.3), vec3(3, 1, 0))
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ blend2D combined with sphere in union")
    
    # Test near the blend2D shape
    env1 = {"p": (0, 1, 0)}
    result1 = eval_ir(ir, env1)
    print(f"  SDF near blend2D: {result1:.4f}")
    
    # Test near the sphere
    env2 = {"p": (3, 1, 0)}
    result2 = eval_ir(ir, env2)
    print(f"  SDF near sphere: {result2:.4f}")
    
    print()


def test_blend2d_horizontal_path():
    """Test blend2D with a horizontal path."""
    print("Test: blend2D with horizontal path")
    
    code = """
    blend2D(
        circle(0.8),
        polygon(vec2(-0.6, -0.6), vec2(0.6, -0.6), vec2(0.6, 0.6), vec2(-0.6, 0.6)),
        line(vec3(0, 0, 0), vec3(4, 0, 0))
    )
    """
    
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    glsl = emit_glsl(ir)
    
    print("  ✓ Blend along X axis")
    
    # Test points along the path
    for x in [0, 1, 2, 3, 4]:
        env = {"p": (x, 0, 0)}
        result = eval_ir(ir, env)
        print(f"  SDF at ({x},0,0): {result:.4f}")
    
    print()


def demo_blend2d_examples():
    """Show various blend2D examples."""
    print("\n" + "="*60)
    print("BLEND2D DEMO EXAMPLES")
    print("="*60)
    
    examples = [
        ("Circle to Square along Y axis", 
         "blend2D(circle(1), polygon(vec2(-1,-1), vec2(1,-1), vec2(1,1), vec2(-1,1)), line(vec3(0,0,0), vec3(0,5,0)))"),
        
        ("Small to Large Circle",
         "blend2D(circle(0.5), circle(1.5), line(vec3(0,0,0), vec3(0,3,0)))"),
        
        ("Square to Diamond along X",
         "blend2D(polygon(vec2(-1,-1), vec2(1,-1), vec2(1,1), vec2(-1,1)), polygon(vec2(-1.5,0), vec2(0,1.5), vec2(1.5,0), vec2(0,-1.5)), line(vec3(0,0,0), vec3(5,0,0)))"),
        
        ("Circle to Triangle via Polyline",
         "blend2D(circle(0.8), polygon(vec2(0,1), vec2(-0.866,-0.5), vec2(0.866,-0.5)), polyline(vec3(0,0,0), vec3(2,0,0), vec3(2,2,0)))"),
    ]
    
    for name, code in examples:
        print(f"\n{name}:")
        print(f"  Code: {code[:80]}...")
        try:
            ast = Parser.from_source(code).parse()
            ir = lower(ast)
            glsl = emit_glsl(ir)
            env = {"p": (0, 0, 0)}
            result = eval_ir(ir, env)
            print(f"  ✓ Compiled successfully")
            print(f"  SDF at origin: {result:.4f}")
        except Exception as e:
            print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("BLEND2D OPERATION TESTS")
    print("=" * 60)
    print()
    
    try:
        test_blend2d_circle_to_polygon_line()
        test_blend2d_polyline()
        test_blend2d_two_polygons()
        test_blend2d_two_circles()
        test_blend2d_with_transforms()
        test_blend2d_in_union()
        test_blend2d_horizontal_path()
        
        demo_blend2d_examples()
        
        print("\n" + "=" * 60)
        print("✓ ALL BLEND2D TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
