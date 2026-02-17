#!/usr/bin/env python3
"""
Simple example demonstrating blend2D operation.
This can be used to test in the web viewer.
"""

from dsl_parser import Parser
from dsl_ir import lower
from dsl_glsl_ir import emit_glsl

# Example 1: Circle morphing to square
example1 = """
blend2D(
    circle(1),
    polygon(vec2(-1,-1), vec2(1,-1), vec2(1,1), vec2(-1,1)),
    line(vec3(0, -2, 0), vec3(0, 2, 0))
)
"""

# Example 2: Small circle to large circle with offset
example2 = """
blend2D(
    circle(0.5),
    circle(1.5),
    line(vec3(0, 0, 0), vec3(0, 4, 0))
)
"""

# Example 3: Morphing along a bent path
example3 = """
blend2D(
    circle(0.8),
    polygon(vec2(-0.6,-0.6), vec2(0.6,-0.6), vec2(0.6,0.6), vec2(-0.6,0.6)),
    polyline(vec3(0, 0, 0), vec3(2, 0, 0), vec3(2, 2, 0))
)
"""

# Example 4: Union of blend2D with other shapes
example4 = """
union(
    blend2D(
        circle(0.5),
        polygon(vec2(-0.4,-0.4), vec2(0.4,-0.4), vec2(0.4,0.4), vec2(-0.4,0.4)),
        line(vec3(0, -1.5, 0), vec3(0, 1.5, 0))
    ),
    translate(sphere(0.6), vec3(3, 0, 0))
)
"""

# Example 5: Complex morphing shape
example5 = """
translate(
    blend2D(
        polygon(vec2(-1,-1), vec2(1,-1), vec2(1,1), vec2(-1,1)),
        polygon(vec2(-1.2,0), vec2(0,1.2), vec2(1.2,0), vec2(0,-1.2)),
        line(vec3(0, 0, 0), vec3(0, 3, 0))
    ),
    vec3(0, -1.5, 0)
)
"""

if __name__ == "__main__":
    examples = [
        ("Circle to Square", example1),
        ("Growing Circle", example2),
        ("Morphing along Polyline", example3),
        ("Union with Sphere", example4),
        ("Square to Diamond", example5),
    ]
    
    print("BLEND2D EXAMPLES")
    print("="*60)
    print()
    
    for name, code in examples:
        print(f"{name}:")
        print(f"{code.strip()}")
        print()
        
        # Compile and show it works
        ast = Parser.from_source(code).parse()
        ir = lower(ast)
        glsl = emit_glsl(ir)
        
        print(f"✓ Compiles to {len(glsl)} chars of GLSL")
        print("-"*60)
        print()
    
    print("\nTo test in the web viewer:")
    print("1. Start the server: uvicorn server:app --reload")
    print("2. Open index.html in a browser")
    print("3. Paste any example above into the DSL editor")
    print("4. Click 'Render' to visualize")
