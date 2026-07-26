#!/usr/bin/env python3
"""
ILMA Chart Generator v1.0  (2026-06-02)
=======================================
Free/offline data visualization (matplotlib, Agg backend) for ILMA writing.
Turns structured data (from the research manifest — NO fabricated numbers) into
publication-grade PNG charts with captions, for embedding in papers/reports/blogs.

API:
  bar_chart(labels, values, title, out_path, ylabel="", color=None) -> dict
  line_chart(x, series, title, out_path, xlabel="", ylabel="") -> dict
  pie_chart(labels, values, title, out_path) -> dict
  make_chart(spec, out_path) -> dict   # spec = {type,title,labels,values,...}

Returns {ok, path, type, error}.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# colorblind-safe palette
_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
plt.rcParams.update({"font.size": 11, "axes.titlesize": 13, "figure.dpi": 150})


def _save(fig, out_path: str) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    ok = os.path.exists(out_path) and os.path.getsize(out_path) > 1000
    return {"ok": ok, "path": out_path}


def bar_chart(labels: List[str], values: List[float], title: str, out_path: str,
              ylabel: str = "", color: Optional[str] = None) -> Dict[str, Any]:
    try:
        fig, ax = plt.subplots(figsize=(7, 4))
        colors = [color] * len(values) if color else _PALETTE[:len(values)] or _PALETTE
        bars = ax.bar(range(len(values)), values, color=colors)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title(title); ax.set_ylabel(ylabel)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:g}",
                    ha="center", va="bottom", fontsize=9)
        return {**_save(fig, out_path), "type": "bar"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "type": "bar"}


def line_chart(x: List[Any], series: Dict[str, List[float]], title: str, out_path: str,
               xlabel: str = "", ylabel: str = "") -> Dict[str, Any]:
    try:
        fig, ax = plt.subplots(figsize=(7, 4))
        for idx, (name, ys) in enumerate(series.items()):
            ax.plot(x, ys, marker="o", label=name, color=_PALETTE[idx % len(_PALETTE)])
        ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        if len(series) > 1:
            ax.legend()
        ax.grid(True, alpha=0.3)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        return {**_save(fig, out_path), "type": "line"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "type": "line"}


def pie_chart(labels: List[str], values: List[float], title: str, out_path: str) -> Dict[str, Any]:
    try:
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90,
               colors=_PALETTE[:len(values)], wedgeprops={"edgecolor": "white"})
        ax.set_title(title); ax.axis("equal")
        return {**_save(fig, out_path), "type": "pie"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "type": "pie"}


def make_chart(spec: Dict[str, Any], out_path: str) -> Dict[str, Any]:
    """spec = {type:bar|line|pie, title, labels, values | x+series, xlabel, ylabel}"""
    ct = (spec.get("type") or "bar").lower()
    title = spec.get("title", "Chart")
    if ct == "pie":
        return pie_chart(spec.get("labels", []), spec.get("values", []), title, out_path)
    if ct == "line":
        return line_chart(spec.get("x", []), spec.get("series", {}), title, out_path,
                          spec.get("xlabel", ""), spec.get("ylabel", ""))
    return bar_chart(spec.get("labels", []), spec.get("values", []), title, out_path,
                     spec.get("ylabel", ""))


if __name__ == "__main__":
    import json, sys
    r = bar_chart(["Surya", "Angin", "Hidro"], [3600, 1200, 800],
                  "Potensi EBT Indonesia (GW)", "/tmp/chart_test.png", ylabel="GW")
    print(json.dumps(r))
