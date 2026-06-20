#!/usr/bin/env python3
"""
ILMA Image Optimizer
==================
Image optimization scripts.
"""

import subprocess
from pathlib import Path

def optimize_image(input_path, output_path, quality=85):
    """Optimize image using various tools. SECURITY: Converted from shell=True (Phase 15B)"""
    from pathlib import Path
    ext = Path(input_path).suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        cmd = ["convert", input_path, "-quality", str(quality), output_path]
    elif ext == ".png":
        cmd = ["optipng", input_path, "-out", output_path]
    elif ext == ".gif":
        cmd = ["gifsicle", "-O3", input_path, "-o", output_path]
    else:
        cmd = ["cp", input_path, output_path]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Optimized: {output_path}")
    else:
        print(f"⚠️ Optimization failed: {result.stderr}")

def batch_optimize(dir_path, quality=85):
    """Batch optimize images in directory."""
    for img in Path(dir_path).glob("*"):
        if img.suffix.lower() in [".jpg", ".png", ".gif"]:
            output = img.parent / f"opt_{img.name}"
            optimize_image(str(img), str(output), quality)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input")
    p.add_argument("--output")
    p.add_argument("--quality", type=int, default=85)
    p.add_argument("--batch")
    args = p.parse_args()
    if args.input and args.output:
        optimize_image(args.input, args.output, args.quality)
    elif args.batch:
        batch_optimize(args.batch, args.quality)

if __name__ == "__main__": main()