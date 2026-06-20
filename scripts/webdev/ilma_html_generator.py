#!/usr/bin/env python3
"""
ILMA HTML Generator
==================
Simple HTML generation utility.
"""

from pathlib import Path

def generate_html(title, body, css=None):
    """Generate HTML page."""
    css_style = f"<style>{css}</style>" if css else ""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {css_style}
</head>
<body>
    <header>
        <h1>{title}</h1>
    </header>
    <main>
        {body}
    </main>
</body>
</html>"""

def generate_table(headers, rows):
    """Generate HTML table."""
    header_html = "".join(f"<th>{h}</th>" for h in headers)
    rows_html = ""
    for row in rows:
        rows_html += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>"

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--title", default="Page")
    p.add_argument("--body")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    html = generate_html(args.title, args.body or "<p>Content</p>")
    if args.output:
        args.output.write_text(html)
        print(f"✅ Written: {args.output}")
    else:
        print(html)

if __name__ == "__main__": main()