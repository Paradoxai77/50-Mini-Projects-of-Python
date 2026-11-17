#!/usr/bin/env python3
"""
Projectile Motion Simulator
============================
Project #13 of 50 Mini Projects

A complete physics engine for modelling and visualising projectile motion
across all three canonical cases:

  Case 1 — Horizontal launch from height h (e.g. food-drop from aircraft)
  Case 2 — Inclined launch on level ground (single angle or multi-angle sweep)
  Case 3 — Inclined launch with launch/landing height difference

Dependencies: numpy, matplotlib

Usage:
    python Projectile_Motion.py --case 1 --height 900 --velocity 140
    python Projectile_Motion.py --case 2 --velocity 50 --angle 45
    python Projectile_Motion.py --case 2 --velocity 40 --multi-angle
    python Projectile_Motion.py --case 3 --velocity 100 --angle 45 --height 100
    python Projectile_Motion.py --all --velocity 50 --save
    python Projectile_Motion.py --interactive
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ─── Constants ────────────────────────────────────────────────────────────────

G: float = 9.81          # m s⁻²  (standard gravity)

# ANSI (terminal output)
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"


# ─── Physics Data Models ──────────────────────────────────────────────────────

@dataclass
class HorizontalResult:
    """Results for a horizontal launch from height h."""
    h:        float    # initial height (m)
    u:        float    # horizontal velocity (m/s)
    g:        float    # gravity (m/s²)
    t_flight: float    # time of flight (s)
    R:        float    # horizontal range (m)
    v_impact: float    # impact speed (m/s)
    angle_impact: float  # impact angle below horizontal (°)


@dataclass
class InclinedResult:
    """Results for an inclined launch on level ground."""
    u:        float    # initial velocity (m/s)
    alpha:    float    # launch angle (°)
    g:        float    # gravity (m/s²)
    T:        float    # time of flight (s)
    R:        float    # horizontal range (m)
    h_max:    float    # maximum height (m)
    t_apex:   float    # time to reach apex (s)
    x_apex:   float    # horizontal distance at apex (m)


@dataclass
class HeightDiffResult:
    """Results for inclined launch with height difference."""
    u:        float    # initial velocity (m/s)
    alpha:    float    # launch angle (°)
    y0:       float    # height of launch above landing (m)
    g:        float    # gravity (m/s²)
    t_flight: float    # time of flight (s)
    R:        float    # horizontal range (m)
    h_max_abs: float   # max height above landing level (m)
    h_max_rel: float   # max height above launch point (m)


# ─── Physics Engine ───────────────────────────────────────────────────────────

def case1_horizontal(
    h: float, u: float, g: float = G
) -> HorizontalResult:
    """
    Case 1: Object launched horizontally from height h.

    Equations:
        h = ½ g t²   →   t = √(2h/g)
        R = u t
        v_y_impact = g t
        v_impact   = √(u² + v_y²)
    """
    if h <= 0:
        raise ValueError("Height h must be positive.")
    if u <= 0:
        raise ValueError("Initial velocity u must be positive.")

    t = math.sqrt(2 * h / g)
    R = u * t
    v_y = g * t
    v_impact = math.sqrt(u**2 + v_y**2)
    angle_impact = math.degrees(math.atan(v_y / u))
    return HorizontalResult(h=h, u=u, g=g, t_flight=t, R=R,
                            v_impact=v_impact, angle_impact=angle_impact)


def case2_inclined(
    u: float, alpha_deg: float, g: float = G
) -> InclinedResult:
    """
    Case 2: Inclined launch on level ground.

    Equations:
        T     = 2u sin(α) / g
        R     = u² sin(2α) / g
        h_max = u² sin²(α) / (2g)
        t_apex = u sin(α) / g  (= T/2)
        x_apex = u cos(α) · t_apex
    """
    if u <= 0:
        raise ValueError("Initial velocity u must be positive.")
    if not (0 < alpha_deg < 90):
        raise ValueError("Launch angle must be between 0° and 90° (exclusive).")

    alpha = math.radians(alpha_deg)
    T     = 2 * u * math.sin(alpha) / g
    R     = u**2 * math.sin(2 * alpha) / g
    h_max = u**2 * math.sin(alpha)**2 / (2 * g)
    t_apex = T / 2
    x_apex = u * math.cos(alpha) * t_apex
    return InclinedResult(u=u, alpha=alpha_deg, g=g, T=T, R=R,
                          h_max=h_max, t_apex=t_apex, x_apex=x_apex)


def case3_height_diff(
    u: float, alpha_deg: float, y0: float, g: float = G
) -> HeightDiffResult:
    """
    Case 3: Inclined launch with launch height y0 above landing level.

    Solve quadratic: g t² − 2u sin(α) t − 2 y0 = 0

    Taking the physically meaningful (positive) root.
    """
    if u <= 0:
        raise ValueError("Initial velocity u must be positive.")
    if not (0 < alpha_deg < 90):
        raise ValueError("Launch angle must be between 0° and 90° (exclusive).")

    alpha = math.radians(alpha_deg)
    # Quadratic coefficients: g t² − 2u sin(α) t − 2 y0 = 0
    a =  g
    b = -2 * u * math.sin(alpha)
    c = -2 * y0
    disc = b**2 - 4 * a * c
    if disc < 0:
        raise ValueError("No real solution — projectile never reaches landing level.")

    t1 = (-b + math.sqrt(disc)) / (2 * a)
    t2 = (-b - math.sqrt(disc)) / (2 * a)
    t_flight = max(t1, t2)   # positive root

    R = u * math.cos(alpha) * t_flight
    h_max_rel = u**2 * math.sin(alpha)**2 / (2 * g)   # above launch
    h_max_abs = h_max_rel + y0                          # above landing

    return HeightDiffResult(u=u, alpha=alpha_deg, y0=y0, g=g,
                            t_flight=t_flight, R=R,
                            h_max_abs=h_max_abs, h_max_rel=h_max_rel)


# ─── Trajectory Arrays ────────────────────────────────────────────────────────

def trajectory_horizontal(
    res: HorizontalResult, points: int = 200
) -> tuple[np.ndarray, np.ndarray]:
    """Return (x, y) arrays for a horizontal launch trajectory."""
    t_arr = np.linspace(0, res.t_flight, points)
    x = res.u * t_arr
    y = res.h - 0.5 * res.g * t_arr**2
    return x, y


def trajectory_inclined(
    u: float, alpha_deg: float, R: float,
    g: float = G, points: int = 300
) -> tuple[np.ndarray, np.ndarray]:
    """Return (x, y) arrays for an inclined-launch trajectory on level ground."""
    alpha = np.radians(alpha_deg)
    x = np.linspace(0, R, points)
    y = x * np.tan(alpha) - (g * x**2) / (2 * u**2 * np.cos(alpha)**2)
    return x, np.maximum(y, 0)   # clip below-ground artifacts


def trajectory_height_diff(
    u: float, alpha_deg: float, R: float, y0: float,
    g: float = G, points: int = 300
) -> tuple[np.ndarray, np.ndarray]:
    """Return (x, y) arrays for height-difference trajectory (y relative to landing)."""
    alpha = np.radians(alpha_deg)
    x = np.linspace(0, R, points)
    # y measured from launch height, then shift up by y0
    y_launch = x * np.tan(alpha) - (g * x**2) / (2 * u**2 * np.cos(alpha)**2)
    y_landing = y_launch + y0   # shift to landing-level reference
    return x, y_landing


# ─── Plots ────────────────────────────────────────────────────────────────────

STYLE = {
    "figure.facecolor":  "#0f172a",
    "axes.facecolor":    "#1e293b",
    "axes.edgecolor":    "#334155",
    "axes.labelcolor":   "#cbd5e1",
    "axes.titlecolor":   "#f8fafc",
    "xtick.color":       "#94a3b8",
    "ytick.color":       "#94a3b8",
    "grid.color":        "#334155",
    "grid.alpha":        0.6,
    "legend.facecolor":  "#0f172a",
    "legend.edgecolor":  "#334155",
    "legend.labelcolor": "#cbd5e1",
    "text.color":        "#f8fafc",
}

PALETTE = ["#38bdf8", "#a78bfa", "#34d399", "#fb923c",
           "#f472b6", "#facc15", "#60a5fa", "#4ade80"]


def apply_style() -> None:
    plt.rcParams.update(STYLE)


def _annotate_point(ax, x, y, label, color="#facc15") -> None:
    ax.plot(x, y, "o", markersize=8, color=color, zorder=5)
    ax.annotate(
        label, (x, y),
        xytext=(10, 10), textcoords="offset points",
        color=color, fontsize=9,
        arrowprops=dict(arrowstyle="->", color=color, lw=1),
    )


def plot_case1(res: HorizontalResult, save_path: Path | None = None) -> None:
    """Plot Case 1: horizontal launch from height."""
    apply_style()
    x, y = trajectory_horizontal(res)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Case 1 — Horizontal Projectile Launch", fontsize=14,
                 fontweight="bold", color="#f8fafc")

    # ── Left: trajectory ──
    ax = axes[0]
    ax.plot(x, y, color="#38bdf8", linewidth=2.5, label="Trajectory")
    ax.fill_between(x, y, alpha=0.15, color="#38bdf8")

    # Ground
    ax.axhline(0, color="#94a3b8", linewidth=1, linestyle="--", alpha=0.5)
    # Launch point
    _annotate_point(ax, 0, res.h, f"Launch\n(0, {res.h:.0f} m)", "#34d399")
    # Impact
    _annotate_point(ax, res.R, 0, f"Impact\n({res.R:.1f} m)", "#fb923c")

    # Dashed height guide
    ax.plot([0, 0], [0, res.h], color="#34d399", linestyle=":", alpha=0.6, lw=1)
    ax.text(-res.R * 0.03, res.h / 2, f"h = {res.h:.0f} m",
            color="#34d399", fontsize=9, ha="right")

    ax.set_xlabel("Horizontal Distance (m)")
    ax.set_ylabel("Height (m)")
    ax.set_title("Trajectory")
    ax.legend()
    ax.grid(True)
    ax.set_xlim(-res.R * 0.05, res.R * 1.1)
    ax.set_ylim(-res.h * 0.05, res.h * 1.15)

    # ── Right: velocity components over time ──
    ax2 = axes[1]
    t_arr = np.linspace(0, res.t_flight, 200)
    v_x = np.full_like(t_arr, res.u)
    v_y = res.g * t_arr
    v_total = np.sqrt(v_x**2 + v_y**2)

    ax2.plot(t_arr, v_x,     color="#38bdf8", lw=2, label="vₓ (horizontal)")
    ax2.plot(t_arr, v_y,     color="#fb923c", lw=2, label="vᵧ (vertical ↓)")
    ax2.plot(t_arr, v_total, color="#34d399", lw=2, linestyle="--",
             label="v (resultant)")
    ax2.axvline(res.t_flight, color="#facc15", linestyle=":", lw=1,
                label=f"Impact at t = {res.t_flight:.2f} s")

    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Speed (m/s)")
    ax2.set_title("Velocity Components vs Time")
    ax2.legend(fontsize=8)
    ax2.grid(True)

    plt.tight_layout()
    _save_or_show(fig, save_path, "case1_horizontal.png")


def plot_case2_single(res: InclinedResult, save_path: Path | None = None) -> None:
    """Plot Case 2: single-angle inclined launch."""
    apply_style()
    x, y = trajectory_inclined(res.u, res.alpha, res.R)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f"Case 2 — Inclined Launch  (u = {res.u} m/s, α = {res.alpha}°)",
        fontsize=14, fontweight="bold", color="#f8fafc",
    )

    # ── Left: trajectory ──
    ax = axes[0]
    ax.plot(x, y, color="#a78bfa", linewidth=2.5, label=f"α = {res.alpha}°")
    ax.fill_between(x, y, alpha=0.15, color="#a78bfa")

    # Apex
    _annotate_point(ax, res.x_apex, res.h_max,
                    f"Apex ({res.x_apex:.1f} m, {res.h_max:.1f} m)", "#facc15")
    # Ground decorations
    ax.axhline(0, color="#94a3b8", linewidth=1, linestyle="--", alpha=0.5)
    _annotate_point(ax, 0, 0, "Launch", "#34d399")
    _annotate_point(ax, res.R, 0, f"Landing\n({res.R:.1f} m)", "#fb923c")

    # h_max guide
    ax.plot([res.x_apex, res.x_apex], [0, res.h_max],
            color="#facc15", linestyle=":", alpha=0.5, lw=1)
    ax.text(res.x_apex + res.R * 0.01, res.h_max / 2,
            f"h_max = {res.h_max:.1f} m", color="#facc15", fontsize=9)

    # Range arrow
    ax.annotate("", xy=(res.R, -res.h_max * 0.07), xytext=(0, -res.h_max * 0.07),
                 arrowprops=dict(arrowstyle="<->", color="#38bdf8", lw=1.5))
    ax.text(res.R / 2, -res.h_max * 0.12, f"R = {res.R:.1f} m",
            ha="center", color="#38bdf8", fontsize=9)

    ax.set_xlabel("Horizontal Distance (m)")
    ax.set_ylabel("Height (m)")
    ax.set_title("Trajectory")
    ax.legend()
    ax.grid(True)
    ax.set_ylim(-res.h_max * 0.18, res.h_max * 1.2)

    # ── Right: parametric motion ──
    ax2 = axes[1]
    alpha_r = math.radians(res.alpha)
    t_arr = np.linspace(0, res.T, 300)
    x_t = res.u * np.cos(alpha_r) * t_arr
    y_t = res.u * np.sin(alpha_r) * t_arr - 0.5 * G * t_arr**2

    ax2.plot(t_arr, x_t, color="#38bdf8", lw=2, label="x(t) — horizontal")
    ax2.plot(t_arr, y_t, color="#fb923c", lw=2, label="y(t) — vertical")
    ax2.axhline(0, color="#94a3b8", lw=1, linestyle="--", alpha=0.5)
    ax2.axvline(res.t_apex, color="#facc15", linestyle=":", lw=1,
                label=f"Apex at t = {res.t_apex:.2f} s")

    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Distance (m)")
    ax2.set_title("Position Components vs Time")
    ax2.legend(fontsize=8)
    ax2.grid(True)

    plt.tight_layout()
    _save_or_show(fig, save_path, "case2_single.png")


def plot_case2_multi(
    u: float,
    angles: Sequence[float] = (15, 30, 45, 60, 75),
    save_path: Path | None = None,
) -> None:
    """Plot Case 2: multiple launch angles on one chart."""
    apply_style()
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.suptitle(
        f"Case 2 — Multi-Angle Trajectory Comparison  (u = {u} m/s)",
        fontsize=14, fontweight="bold", color="#f8fafc",
    )

    max_R = 0.0
    max_H = 0.0
    for i, angle in enumerate(angles):
        res = case2_inclined(u, angle)
        x, y = trajectory_inclined(u, angle, res.R)
        color = PALETTE[i % len(PALETTE)]
        ax.plot(x, y, color=color, linewidth=2.2,
                label=f"{angle}°  R={res.R:.1f} m  h_max={res.h_max:.1f} m")
        ax.fill_between(x, y, alpha=0.07, color=color)
        # Mark apex
        ax.plot(res.x_apex, res.h_max, "o", color=color, markersize=5, zorder=5)
        max_R = max(max_R, res.R)
        max_H = max(max_H, res.h_max)

    ax.axhline(0, color="#94a3b8", linewidth=1.5, alpha=0.6)
    ax.set_xlabel("Horizontal Distance (m)", fontsize=11)
    ax.set_ylabel("Height (m)", fontsize=11)
    ax.set_title(f"Trajectories for angles: {list(angles)}", fontsize=10)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True)
    ax.set_xlim(-max_R * 0.03, max_R * 1.05)
    ax.set_ylim(-max_H * 0.08, max_H * 1.15)

    # Symmetry note (45° gives max range)
    ax.text(max_R * 0.5, max_H * 1.05,
            "⟵  45° gives maximum range  ⟶",
            ha="center", color="#facc15", fontsize=9, style="italic")

    plt.tight_layout()
    _save_or_show(fig, save_path, "case2_multi.png")


def plot_case3(res: HeightDiffResult, save_path: Path | None = None) -> None:
    """Plot Case 3: inclined launch with height difference."""
    apply_style()
    x, y = trajectory_height_diff(res.u, res.alpha, res.R, res.y0)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f"Case 3 — Launch with Height Difference  "
        f"(u={res.u} m/s, α={res.alpha}°, h={res.y0} m)",
        fontsize=13, fontweight="bold", color="#f8fafc",
    )

    # ── Left: trajectory ──
    ax = axes[0]
    # Ground level (landing)
    ax.axhline(0, color="#94a3b8", lw=1.5, linestyle="--",
               alpha=0.7, label="Landing level")
    # Launch platform
    ax.plot([-res.R * 0.05, res.R * 0.05], [res.y0, res.y0],
            color="#34d399", lw=3, label=f"Launch platform (h={res.y0:.0f} m)")

    # Terrain fill
    ax.fill_between([0, res.R], [-res.h_max_abs * 0.1, -res.h_max_abs * 0.1],
                    [0, 0], color="#78350f", alpha=0.4)

    ax.plot(x, y, color="#f472b6", linewidth=2.5, label="Trajectory")
    ax.fill_between(x, 0, y, where=(y > 0), alpha=0.12, color="#f472b6")

    _annotate_point(ax, 0, res.y0, f"Launch\n(0, {res.y0:.0f} m)", "#34d399")
    _annotate_point(ax, res.R, 0, f"Landing\n({res.R:.1f} m, 0)", "#fb923c")

    apex_t = res.u * math.sin(math.radians(res.alpha)) / G
    apex_x = res.u * math.cos(math.radians(res.alpha)) * apex_t
    apex_y = res.h_max_abs
    _annotate_point(ax, apex_x, apex_y,
                    f"Apex\n({apex_x:.1f} m, {apex_y:.1f} m)", "#facc15")

    ax.set_xlabel("Horizontal Distance (m)")
    ax.set_ylabel("Height above landing (m)")
    ax.set_title("Trajectory")
    ax.legend(fontsize=8)
    ax.grid(True)
    ylim = max(res.h_max_abs * 1.2, res.y0 * 1.3)
    ax.set_ylim(-ylim * 0.1, ylim)
    ax.set_xlim(-res.R * 0.06, res.R * 1.08)

    # ── Right: height vs time ──
    ax2 = axes[1]
    alpha_r = math.radians(res.alpha)
    t_arr = np.linspace(0, res.t_flight, 300)
    y_t = (res.y0
           + res.u * np.sin(alpha_r) * t_arr
           - 0.5 * G * t_arr**2)

    ax2.plot(t_arr, y_t, color="#f472b6", lw=2.5, label="Height above landing")
    ax2.axhline(0, color="#94a3b8", lw=1, linestyle="--", alpha=0.6, label="Landing level")
    ax2.axhline(res.y0, color="#34d399", lw=1, linestyle=":", alpha=0.6, label="Launch height")

    apex_t_val = res.u * math.sin(alpha_r) / G
    ax2.plot(apex_t_val, res.h_max_abs, "o", color="#facc15", markersize=8,
             zorder=5, label=f"Apex: {res.h_max_abs:.1f} m")
    ax2.axvline(res.t_flight, color="#fb923c", linestyle=":", lw=1,
                label=f"Landing: t={res.t_flight:.2f} s")

    ax2.fill_between(t_arr, y_t, where=(y_t >= 0), alpha=0.15, color="#f472b6")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Height above landing (m)")
    ax2.set_title("Height vs Time")
    ax2.legend(fontsize=8)
    ax2.grid(True)

    plt.tight_layout()
    _save_or_show(fig, save_path, "case3_height_diff.png")


def plot_range_vs_angle(
    u: float, save_path: Path | None = None
) -> None:
    """Plot Range and h_max vs launch angle — the classic optimisation curve."""
    apply_style()
    angles = np.linspace(1, 89, 500)
    R_vals = u**2 * np.sin(np.radians(2 * angles)) / G
    H_vals = u**2 * np.sin(np.radians(angles))**2 / (2 * G)

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle(f"Range & Height vs Launch Angle  (u = {u} m/s)",
                 fontsize=14, fontweight="bold", color="#f8fafc")

    ax2 = ax.twinx()
    l1, = ax.plot(angles, R_vals, color="#38bdf8", lw=2.5, label="Range R (m)")
    l2, = ax2.plot(angles, H_vals, color="#fb923c", lw=2.5, linestyle="--",
                   label="Max Height h_max (m)")

    # Mark 45° maximum range
    ax.axvline(45, color="#facc15", linestyle=":", lw=1.5, alpha=0.8)
    max_R_val = u**2 / G
    ax.plot(45, max_R_val, "★", markersize=14, color="#facc15",
            label=f"Max Range at 45° = {max_R_val:.1f} m", zorder=5)

    # Complementary angle pairs
    for a1, a2 in [(30, 60), (20, 70), (15, 75)]:
        r1 = u**2 * math.sin(math.radians(2 * a1)) / G
        ax.plot([a1, a2], [r1, r1], "s", color="#a78bfa", markersize=7, zorder=4)
        ax.annotate(f"{a1}° & {a2}°\nsame R",
                    xy=(a2, r1), xytext=(5, 5), textcoords="offset points",
                    color="#a78bfa", fontsize=7)

    ax.set_xlabel("Launch Angle (°)", fontsize=11)
    ax.set_ylabel("Range (m)", color="#38bdf8", fontsize=11)
    ax2.set_ylabel("Max Height (m)", color="#fb923c", fontsize=11)
    ax.set_xlim(0, 90)

    lines = [l1, l2]
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc="upper right", fontsize=9)
    ax.grid(True)

    plt.tight_layout()
    _save_or_show(fig, save_path, "range_vs_angle.png")


def _save_or_show(fig: plt.Figure, save_path: Path | None, filename: str) -> None:
    if save_path:
        out = save_path / filename
        fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"  {GREEN}✔  Saved → {out}{RESET}")
        plt.close(fig)
    else:
        plt.show()
        plt.close(fig)


# ─── Terminal Report Formatters ───────────────────────────────────────────────

def _header(title: str) -> None:
    border = "═" * 64
    print(f"\n{CYAN}{border}{RESET}")
    print(f"{CYAN}  🚀  {BOLD}{title}{RESET}")
    print(f"{CYAN}{border}{RESET}\n")


def _row(label: str, value: str, unit: str = "") -> None:
    print(f"  {DIM}{label:<30}{RESET} {YELLOW}{BOLD}{value}{RESET} {DIM}{unit}{RESET}")


def report_case1(res: HorizontalResult) -> None:
    _header("Case 1 — Horizontal Launch from Height")
    _row("Initial height (h)",       f"{res.h:.3f}", "m")
    _row("Horizontal velocity (u)",  f"{res.u:.3f}", "m/s")
    _row("Gravity (g)",              f"{res.g:.2f}",  "m/s²")
    print()
    _row("Time of flight (t)",       f"{res.t_flight:.4f}", "s")
    _row("Horizontal range (R)",     f"{res.R:.4f}",        "m")
    _row("Impact speed (v)",         f"{res.v_impact:.4f}", "m/s")
    _row("Impact angle (below hor.)",f"{res.angle_impact:.2f}", "°")
    print()


def report_case2(res: InclinedResult) -> None:
    _header(f"Case 2 — Inclined Launch (α = {res.alpha}°)")
    _row("Initial velocity (u)",     f"{res.u:.3f}", "m/s")
    _row("Launch angle (α)",         f"{res.alpha:.1f}", "°")
    _row("Gravity (g)",              f"{res.g:.2f}",  "m/s²")
    print()
    _row("Time of flight (T)",       f"{res.T:.4f}",     "s")
    _row("Horizontal range (R)",     f"{res.R:.4f}",     "m")
    _row("Maximum height (h_max)",   f"{res.h_max:.4f}", "m")
    _row("Time to apex",             f"{res.t_apex:.4f}","s")
    _row("Horizontal dist. at apex", f"{res.x_apex:.4f}","m")
    print()


def report_case3(res: HeightDiffResult) -> None:
    _header(f"Case 3 — Height-Difference Launch (y₀ = {res.y0} m)")
    _row("Initial velocity (u)",      f"{res.u:.3f}",  "m/s")
    _row("Launch angle (α)",          f"{res.alpha:.1f}", "°")
    _row("Launch height (y₀)",        f"{res.y0:.3f}", "m")
    _row("Gravity (g)",               f"{res.g:.2f}",  "m/s²")
    print()
    _row("Time of flight",            f"{res.t_flight:.4f}", "s")
    _row("Range (R)",                 f"{res.R:.4f}",        "m")
    _row("Max height above landing",  f"{res.h_max_abs:.4f}", "m")
    _row("Max height above launch",   f"{res.h_max_rel:.4f}", "m")
    print()


# ─── Interactive Mode ─────────────────────────────────────────────────────────

def _prompt(text: str, cast=float, default=None):
    dflt_str = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"  {CYAN}{text}{dflt_str}: {RESET}").strip()
        if not raw and default is not None:
            return default
        try:
            return cast(raw)
        except ValueError:
            print(f"  {RED}Invalid input. Please enter a valid {cast.__name__}.{RESET}")


def interactive_mode(save_path: Path | None = None) -> None:
    _header("Interactive Projectile Motion Simulator")
    print(f"  {'1'} — Case 1: Horizontal launch from height")
    print(f"  {'2'} — Case 2: Inclined launch on level ground")
    print(f"  {'3'} — Case 3: Inclined launch with height difference")
    print(f"  {'4'} — Multi-angle comparison")
    print(f"  {'5'} — Range vs angle optimisation plot")
    print()

    choice = _prompt("Select case (1-5)", cast=int)

    if choice == 1:
        h = _prompt("Height h (m)", default=900.0)
        u = _prompt("Horizontal velocity u (m/s)", default=140.0)
        res = case1_horizontal(h, u)
        report_case1(res)
        plot_case1(res, save_path)

    elif choice == 2:
        u     = _prompt("Initial velocity u (m/s)", default=50.0)
        alpha = _prompt("Launch angle α (°)", default=45.0)
        res   = case2_inclined(u, alpha)
        report_case2(res)
        plot_case2_single(res, save_path)

    elif choice == 3:
        u     = _prompt("Initial velocity u (m/s)", default=100.0)
        alpha = _prompt("Launch angle α (°)", default=45.0)
        y0    = _prompt("Launch height above landing y₀ (m)", default=100.0)
        res   = case3_height_diff(u, alpha, y0)
        report_case3(res)
        plot_case3(res, save_path)

    elif choice == 4:
        u = _prompt("Initial velocity u (m/s)", default=40.0)
        angles_str = _prompt("Angles (comma-separated)", cast=str,
                              default="15,30,45,60,75")
        angles = [float(a.strip()) for a in angles_str.split(",")]
        plot_case2_multi(u, angles, save_path)

    elif choice == 5:
        u = _prompt("Initial velocity u (m/s)", default=50.0)
        plot_range_vs_angle(u, save_path)

    else:
        print(f"  {RED}Invalid choice.{RESET}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Projectile_Motion",
        description="🚀  Projectile Motion Simulator — all three canonical cases.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            cases:
              1  Horizontal launch from height h (e.g. food-drop from aircraft)
              2  Inclined launch on level ground (single angle or multi-angle sweep)
              3  Inclined launch with launch/landing height difference

            examples:
              python Projectile_Motion.py --case 1 --height 900 --velocity 140
              python Projectile_Motion.py --case 2 --velocity 50 --angle 45
              python Projectile_Motion.py --case 2 --velocity 40 --multi-angle
              python Projectile_Motion.py --case 3 --velocity 100 --angle 45 --height 100
              python Projectile_Motion.py --all --velocity 50 --save
              python Projectile_Motion.py --range-plot --velocity 60
              python Projectile_Motion.py --interactive
        """),
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--case", type=int, choices=[1, 2, 3], metavar="N",
                      help="run a specific case (1, 2, or 3)")
    mode.add_argument("--all", action="store_true",
                      help="run all three cases and the range-vs-angle plot")
    mode.add_argument("--range-plot", action="store_true",
                      help="plot Range and h_max vs launch angle")
    mode.add_argument("--interactive", action="store_true",
                      help="interactive guided mode")

    parser.add_argument("--velocity", "-u", type=float, default=50.0,
                        metavar="U", help="initial velocity m/s (default: 50)")
    parser.add_argument("--angle", "-a", type=float, default=45.0,
                        metavar="A", help="launch angle in degrees (default: 45)")
    parser.add_argument("--height", "-H", type=float, default=100.0,
                        metavar="H",
                        help="height for case 1 (launch height) or case 3 (y₀) (default: 100)")
    parser.add_argument("--gravity", "-g", type=float, default=G,
                        metavar="G", help=f"gravity m/s² (default: {G})")
    parser.add_argument("--multi-angle", action="store_true",
                        help="case 2: plot multiple angles (15 30 45 60 75)")
    parser.add_argument("--angles", nargs="+", type=float,
                        default=[15, 30, 45, 60, 75], metavar="A",
                        help="angles for --multi-angle (default: 15 30 45 60 75)")
    parser.add_argument("--save", action="store_true",
                        help="save plots to PNG files instead of displaying")
    parser.add_argument("--output-dir", type=Path, default=Path("."),
                        metavar="DIR", help="directory for saved PNGs (default: .)")
    parser.add_argument("--points", type=int, default=300,
                        help="trajectory sample points (default: 300)")
    parser.add_argument("--no-colour", action="store_true",
                        help="disable ANSI colour output")
    return parser


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    if args.no_colour:
        global RESET, BOLD, DIM, CYAN, GREEN, YELLOW, RED, MAGENTA, WHITE
        RESET = BOLD = DIM = CYAN = GREEN = YELLOW = RED = MAGENTA = WHITE = ""

    save_path = args.output_dir if args.save else None
    if save_path:
        save_path.mkdir(parents=True, exist_ok=True)
        print(f"  Plots will be saved to: {CYAN}{save_path.resolve()}{RESET}\n")

    try:
        if args.interactive:
            interactive_mode(save_path)

        elif args.range_plot:
            print_header = _header
            _header(f"Range & Height vs Angle  (u = {args.velocity} m/s)")
            plot_range_vs_angle(args.velocity, save_path)

        elif args.all:
            # Case 1
            r1 = case1_horizontal(args.height, args.velocity, args.gravity)
            report_case1(r1)
            plot_case1(r1, save_path)
            # Case 2 single
            r2 = case2_inclined(args.velocity, args.angle, args.gravity)
            report_case2(r2)
            plot_case2_single(r2, save_path)
            # Case 2 multi
            plot_case2_multi(args.velocity, args.angles, save_path)
            # Case 3
            r3 = case3_height_diff(args.velocity, args.angle, args.height, args.gravity)
            report_case3(r3)
            plot_case3(r3, save_path)
            # Range vs angle
            plot_range_vs_angle(args.velocity, save_path)

        elif args.case == 1:
            res = case1_horizontal(args.height, args.velocity, args.gravity)
            report_case1(res)
            plot_case1(res, save_path)

        elif args.case == 2:
            if args.multi_angle:
                plot_case2_multi(args.velocity, args.angles, save_path)
            else:
                res = case2_inclined(args.velocity, args.angle, args.gravity)
                report_case2(res)
                plot_case2_single(res, save_path)

        elif args.case == 3:
            res = case3_height_diff(args.velocity, args.angle, args.height,
                                    args.gravity)
            report_case3(res)
            plot_case3(res, save_path)

        else:
            parser.print_help()
            return 1

    except ValueError as exc:
        print(f"{RED}Error:{RESET} {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
