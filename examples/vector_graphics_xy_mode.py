"""Vector Graphics on Oscilloscope using XY Mode

This example demonstrates how to use the oscilloscope as a vector display
by generating waveforms for XY mode.

REQUIREMENTS:
    - Install fun extras: pip install "Siglent-Oscilloscope[fun]"
    - External AWG/DAC to feed signals into scope channels
      OR use scope's built-in AWG if available
    - Oscilloscope channels connected to AWG outputs

SETUP:
    1. Connect AWG CH1 output → Scope CH1 (X axis)
    2. Connect AWG CH2 output → Scope CH2 (Y axis)
    3. Enable XY mode on oscilloscope (Display → XY Mode → ON)
    4. Adjust voltage scales to see full pattern

WHAT THIS DOES:
    - Generates X/Y waveform data for various shapes
    - Saves waveform files that can be loaded into an AWG
    - Creates animations by rotating and transforming shapes
"""

import time

import numpy as np

from siglent import Oscilloscope
from siglent.vector_graphics import Shape, VectorDisplay

# Configuration
SCOPE_IP = "192.168.1.100"
SAMPLE_RATE = 1e6  # 1 MSa/s for AWG
DURATION = 0.1  # 100ms per frame
OUTPUT_DIR = "vector_waveforms"


def main():
    """Main demonstration of vector graphics features."""

    print("=" * 60)
    print("  Oscilloscope Vector Graphics Demo")
    print("=" * 60)
    print()
    print("This demo generates waveform data for XY mode display.")
    print("Load the generated files into your AWG to see the shapes!")
    print()

    # Connect to oscilloscope
    print(f"Connecting to {SCOPE_IP}...")
    scope = Oscilloscope(SCOPE_IP)
    scope.connect()
    print(f"Connected: {scope.identify()}")
    print()

    # Initialize vector display
    print("Initializing vector display (CH1=X, CH2=Y)...")
    display = scope.vector_display
    display.enable_xy_mode(voltage_scale=1.0)
    print("✓ XY mode configured")
    print()

    # Create output directory
    import os

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ==========================================
    # Demo 1: Basic Shapes
    # ==========================================
    print("Demo 1: Basic Shapes")
    print("-" * 40)

    # Circle
    print("  Generating circle...")
    circle = Shape.circle(radius=0.8, points=1000)
    display.save_waveforms(circle, f"{OUTPUT_DIR}/01_circle", sample_rate=SAMPLE_RATE, duration=DURATION)

    # Square
    print("  Generating square...")
    square = Shape.rectangle(width=1.6, height=1.6, points_per_side=250)
    display.save_waveforms(square, f"{OUTPUT_DIR}/02_square", sample_rate=SAMPLE_RATE, duration=DURATION)

    # Star
    print("  Generating star...")
    star = Shape.star(num_points=5, outer_radius=0.9, inner_radius=0.4)
    display.save_waveforms(star, f"{OUTPUT_DIR}/03_star", sample_rate=SAMPLE_RATE, duration=DURATION)

    # Triangle
    print("  Generating triangle...")
    triangle = Shape.polygon(
        [
            (0, 0.8),  # Top
            (-0.7, -0.4),  # Bottom left
            (0.7, -0.4),  # Bottom right
        ],
        points_per_side=300,
    )
    display.save_waveforms(triangle, f"{OUTPUT_DIR}/04_triangle", sample_rate=SAMPLE_RATE, duration=DURATION)

    print("✓ Basic shapes generated\n")

    # ==========================================
    # Demo 2: Lissajous Figures
    # ==========================================
    print("Demo 2: Lissajous Figures")
    print("-" * 40)

    lissajous_patterns = [
        (3, 2, np.pi / 2, "3_2"),
        (5, 4, 0, "5_4"),
        (7, 5, np.pi / 4, "7_5"),
    ]

    for a, b, delta, name in lissajous_patterns:
        print(f"  Generating Lissajous {a}:{b}...")
        lissajous = Shape.lissajous(a=a, b=b, delta=delta, points=2000)
        display.save_waveforms(lissajous, f"{OUTPUT_DIR}/lissajous_{name}", sample_rate=SAMPLE_RATE, duration=DURATION)

    print("✓ Lissajous figures generated\n")

    # ==========================================
    # Demo 3: Text
    # ==========================================
    print("Demo 3: Text Rendering")
    print("-" * 40)
    print("  Generating text 'HELLO'...")

    try:
        text = Shape.text("HELLO", font_size=0.6)
        display.save_waveforms(text, f"{OUTPUT_DIR}/text_hello", sample_rate=SAMPLE_RATE, duration=DURATION)
        print("✓ Text generated")
    except Exception as e:
        print(f"  ⚠ Text generation skipped: {e}")

    print()

    # ==========================================
    # Demo 4: Animations (Rotating Star)
    # ==========================================
    print("Demo 4: Animation Frames (Rotating Star)")
    print("-" * 40)

    star_base = Shape.star(num_points=5, outer_radius=0.8, inner_radius=0.3)

    for i, angle in enumerate(range(0, 360, 15)):
        rotated_star = star_base.rotate(angle)
        display.save_waveforms(
            rotated_star,
            f"{OUTPUT_DIR}/anim_star_frame_{i:02d}",
            sample_rate=SAMPLE_RATE,
            duration=DURATION / 10,
        )  # Faster frames
        print(f"  Frame {i+1}/24 (angle={angle}°)")

    print("✓ Animation frames generated\n")

    # ==========================================
    # Demo 5: Composite Shapes
    # ==========================================
    print("Demo 5: Composite Shapes")
    print("-" * 40)

    # Smiley face (circle + eyes + mouth)
    print("  Generating smiley face...")
    face_outer = Shape.circle(radius=0.9, points=500)
    eye_left = Shape.circle(radius=0.1, center=(-0.3, 0.3), points=100)
    eye_right = Shape.circle(radius=0.1, center=(0.3, 0.3), points=100)

    # Mouth as an arc (half circle)
    t = np.linspace(0, np.pi, 200)
    mouth_x = 0.5 * np.cos(t)
    mouth_y = -0.2 + 0.3 * np.sin(t)
    from siglent.vector_graphics import VectorPath

    mouth = VectorPath(x=mouth_x, y=mouth_y, connected=False)

    # Combine all parts
    smiley = face_outer.combine(eye_left).combine(eye_right).combine(mouth)
    display.save_waveforms(smiley, f"{OUTPUT_DIR}/composite_smiley", sample_rate=SAMPLE_RATE, duration=DURATION)
    print("✓ Smiley face generated\n")

    # ==========================================
    # Summary
    # ==========================================
    print("=" * 60)
    print("  Demo Complete!")
    print("=" * 60)
    print()
    print(f"Waveform files saved to: {OUTPUT_DIR}/")
    print()
    print("Next Steps:")
    print("  1. Load the .csv files into your AWG")
    print("     - Load *_x.csv → AWG Channel 1")
    print("     - Load *_y.csv → AWG Channel 2")
    print("  2. Enable XY mode on the oscilloscope")
    print("  3. Start the AWG output")
    print("  4. Adjust timebase and voltage scales to see the pattern")
    print()
    print("Tips:")
    print("  - Use CSV format for most AWGs")
    print("  - Adjust sample rate to match your AWG capabilities")
    print("  - Connect AWG outputs directly to scope inputs")
    print("  - Set scope to DC coupling for best results")
    print()

    # Cleanup
    scope.disconnect()


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        if "fun" in str(e):
            print()
            print("=" * 60)
            print("  ERROR: Missing 'fun' extras")
            print("=" * 60)
            print()
            print("Vector graphics features require additional packages.")
            print()
            print("Install with:")
            print('  pip install "Siglent-Oscilloscope[fun]"')
            print()
            print("This will install:")
            print("  - shapely (geometric operations)")
            print("  - Pillow (text rendering)")
            print("  - svgpathtools (SVG path support)")
            print()
        else:
            raise
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        raise
