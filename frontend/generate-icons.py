"""Generate PWA icons from SVG"""
import subprocess, os

# Try to use cairosvg or Pillow to convert
try:
    from cairosvg import svg2png
    for size in [192, 512]:
        svg2png(url="icons/icon.svg", write_to=f"icons/icon-{size}.png", output_width=size, output_height=size)
        print(f"Created icon-{size}.png")
except ImportError:
    try:
        # Fallback: use system rsvg-convert
        for size in [192, 512]:
            subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-o", f"icons/icon-{size}.png", "icons/icon.svg"])
            print(f"Created icon-{size}.png via rsvg-convert")
    except:
        print("No SVG converter available. Install: pip install cairosvg")
        print("Or: apt install librsvg2-bin")
