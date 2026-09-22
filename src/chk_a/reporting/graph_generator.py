"""Graph generation for monthly reports using matplotlib.

This module creates publication-quality charts for the monthly DNS resolver
report, including:
- Availability bar chart (per resolver)
- Availability heatmap (hourly per resolver)
- Integrity score chart (per resolver)
- Latency distribution (box plots)
- IP stability / diversity charts
- MTR path visualization

Modern styling with colorblind-safe palettes, high DPI, and clean aesthetics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import matplotlib.font_manager as fm
import numpy as np
import seaborn as sns

matplotlib.use("Agg")  # Non-interactive backend

log = logging.getLogger(__name__)

# ============================================================================
# MODERN STYLE CONFIGURATION
# ============================================================================

# Modern color palette - colorblind-safe, professional
COLORS = {
    # Primary brand colors
    "primary": "#2563EB",      # Blue-600
    "primary_light": "#3B82F6", # Blue-500
    "primary_dark": "#1D4ED8",  # Blue-700
    # Semantic colors (colorblind-safe)
    "success": "#059669",      # Emerald-600
    "success_light": "#10B981", # Emerald-500
    "warning": "#D97706",      # Amber-600
    "warning_light": "#F59E0B", # Amber-500
    "danger": "#DC2626",       # Red-600
    "danger_light": "#EF4444",  # Red-500
    "info": "#0891B2",         # Cyan-600
    # Neutrals
    "dark": "#111827",         # Gray-900
    "dark_muted": "#374151",    # Gray-700
    "medium": "#6B7280",       # Gray-500
    "light": "#F3F4F6",        # Gray-100
    "lighter": "#F9FAFB",      # Gray-50
    "white": "#FFFFFF",
    # Grid & borders
    "grid": "#E5E7EB",         # Gray-200
    "border": "#D1D5DB",       # Gray-300
}

# Heatmap colormaps (colorblind-safe)
HEATMAP_CMAP = "viridis"       # Perceptually uniform, colorblind-safe
HEATMAP_CMAP_DIVERGING = "RdYlGn"  # For availability (red-yellow-green is standard)

# Modern matplotlib rcParams
MODERN_RCPARAMS = {
    # Fonts
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Sarabun", "Noto Sans Thai", "Loma", "DejaVu Sans", "Arial"],
    "font.size": 11,
    # Figure
    "figure.facecolor": COLORS["white"],
    "figure.edgecolor": "none",
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.facecolor": COLORS["white"],
    "savefig.edgecolor": "none",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.1,
    # Axes
    "axes.facecolor": COLORS["white"],
    "axes.edgecolor": COLORS["border"],
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "axes.grid.axis": "both",
    "axes.grid.which": "major",
    "axes.axisbelow": True,
    "axes.titlesize": 14,
    "axes.titleweight": "600",
    "axes.titlecolor": COLORS["dark"],
    "axes.labelsize": 11,
    "axes.labelweight": "500",
    "axes.labelcolor": COLORS["dark_muted"],
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": True,
    "axes.spines.bottom": True,
    # Grid
    "grid.color": COLORS["grid"],
    "grid.linewidth": 0.6,
    "grid.linestyle": "-",
    "grid.alpha": 1.0,
    # Ticks
    "xtick.color": COLORS["medium"],
    "ytick.color": COLORS["medium"],
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    # Legend
    "legend.frameon": True,
    "legend.framealpha": 0.95,
    "legend.facecolor": COLORS["white"],
    "legend.edgecolor": COLORS["border"],
    "legend.fancybox": True,
    "legend.fontsize": 9,
    "legend.title_fontsize": 10,
    # Lines
    "lines.linewidth": 2,
    "lines.markersize": 6,
    # Animation (not used but good defaults)
    "animation.html": "none",
}

# Apply modern style
plt.style.use("seaborn-v0_8-whitegrid")
for key, value in MODERN_RCPARAMS.items():
    matplotlib.rcParams[key] = value

# Seaborn palette for categorical data
sns.set_palette("colorblind")  # Colorblind-safe categorical palette

# ============================================================================
# THAI FONT SUPPORT (bundled with package)
# ============================================================================

try:
    from importlib import resources

    # Use bundled Loma fonts from package
    thai_fonts = []
    font_dir = None

    # Modern importlib.resources approach (Python 3.9+)
    try:
        font_dir = resources.files("chk_a.fonts")
        thai_fonts = [f for f in font_dir.iterdir() if f.name.startswith("Loma") and f.name.endswith(".otf")]
    except Exception:
        pass

    # Fallback for older Python / pkg_resources
    if not thai_fonts:
        try:
            import pkg_resources
            font_dir = Path(pkg_resources.resource_filename("chk_a", "fonts"))
            thai_fonts = list(font_dir.glob("Loma*.otf"))
        except Exception:
            pass

    if thai_fonts:
        font_path = None
        try:
            font_path = str(Path(thai_fonts[0]))
            if not Path(font_path).exists():
                raise ValueError("Path does not exist")
        except Exception:
            with resources.as_file(thai_fonts[0]) as p:
                font_path = str(p)
                THAI_FONT = fm.FontProperties(fname=font_path)
                THAI_FONT_SMALL = fm.FontProperties(fname=font_path, size=8)
                THAI_FONT_NORMAL = fm.FontProperties(fname=font_path, size=10)
                THAI_FONT_LARGE = fm.FontProperties(fname=font_path, size=12)
                THAI_FONT_TITLE = fm.FontProperties(fname=font_path, size=14, weight="bold")
                THAI_FONT_BOLD = fm.FontProperties(fname=font_path, size=11, weight="bold")
                log.info(f"Using bundled Thai font: {thai_fonts[0].name}")
        else:
            THAI_FONT = fm.FontProperties(fname=font_path)
            THAI_FONT_SMALL = fm.FontProperties(fname=font_path, size=8)
            THAI_FONT_NORMAL = fm.FontProperties(fname=font_path, size=10)
            THAI_FONT_LARGE = fm.FontProperties(fname=font_path, size=12)
            THAI_FONT_TITLE = fm.FontProperties(fname=font_path, size=14, weight="bold")
            THAI_FONT_BOLD = fm.FontProperties(fname=font_path, size=11, weight="bold")
            log.info(f"Using bundled Thai font: {thai_fonts[0].name}")
    else:
        # Fallback to system fonts
        system_thai_fonts = [
            f
            for f in fm.findSystemFonts()
            if any(x in f.lower() for x in ["thai", "sarabun", "noto", "tahoma", "tlwg", "loma"])
        ]
        if system_thai_fonts:
            THAI_FONT = fm.FontProperties(fname=system_thai_fonts[0])
            THAI_FONT_SMALL = fm.FontProperties(fname=system_thai_fonts[0], size=8)
            THAI_FONT_NORMAL = fm.FontProperties(fname=system_thai_fonts[0], size=10)
            THAI_FONT_LARGE = fm.FontProperties(fname=system_thai_fonts[0], size=12)
            THAI_FONT_TITLE = fm.FontProperties(fname=system_thai_fonts[0], size=14, weight="bold")
            THAI_FONT_BOLD = fm.FontProperties(fname=system_thai_fonts[0], size=11, weight="bold")
            log.info(f"Using system Thai font: {system_thai_fonts[0]}")
        else:
            THAI_FONT = None
            THAI_FONT_SMALL = None
            THAI_FONT_NORMAL = None
            THAI_FONT_LARGE = None
            THAI_FONT_TITLE = None
            THAI_FONT_BOLD = None
            log.warning("No Thai font found - Thai text may not render correctly")
except Exception as e:
    log.warning(f"Could not load Thai font: {e}")
    THAI_FONT = None
    THAI_FONT_SMALL = None
    THAI_FONT_NORMAL = None
    THAI_FONT_LARGE = None
    THAI_FONT_TITLE = None
    THAI_FONT_BOLD = None


def _get_font_props(size: int = 10, weight: str = "normal", lang: str = "en"):
    """Get appropriate font properties for the given language."""
    if lang == "th" and THAI_FONT:
        if size <= 8:
            return THAI_FONT_SMALL
        elif size <= 10:
            return THAI_FONT_NORMAL
        elif size <= 12:
            return THAI_FONT_LARGE
        elif weight == "bold":
            return THAI_FONT_BOLD
        else:
            return THAI_FONT_TITLE
    return {"fontsize": size, "fontweight": weight}


def _add_header_footer(
    fig: plt.Figure,
    ax: plt.Axes,
    title: str,
    hostname: str | None = None,
    lang: str = "en",
    version: str | None = None,
) -> None:
    """Add standardized header (title) and footer (hostname + last update) to figure.

    Footer language follows lang parameter: Thai for lang='th', English for lang='en'.
    Left: hostname, Center: version, Right: timestamp
    Title supports newline (\\n) for multi-line headers.
    """
    hostname = hostname or "unknown-host"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version_str = f"v{version}" if version else ""

    # Footer language follows lang parameter - split left/center/right
    if lang == "th":
        left_text = f"ตรวจสอบจากเครื่อง : \"{hostname}\""
        center_text = version_str
        right_text = f"อัปเดตล่าสุด : {timestamp}"
        font_props = THAI_FONT if THAI_FONT else None
        title_font = THAI_FONT_TITLE if THAI_FONT else None
    else:
        left_text = f"Checked from host : \"{hostname}\""
        center_text = version_str
        right_text = f"Last Update : {timestamp}"
        font_props = None
        title_font = None

    # Title (header) - centered at top, supports newline
    fig.text(
        0.5, 0.94, title,
        ha="center", va="top",
        fontsize=14, fontweight="600",
        color=COLORS["dark"],
        fontproperties=title_font,
    )

    # Left footer - hostname (bottom-left)
    fig.text(
        0.015, 0.015, left_text,
        ha="left", va="bottom",
        fontsize=7, fontweight="normal",
        color=COLORS["medium"],
        fontproperties=font_props,
    )

    # Center footer - version (bottom-center)
    if center_text:
        fig.text(
            0.5, 0.015, center_text,
            ha="center", va="bottom",
            fontsize=7, fontweight="500",
            color=COLORS["primary"],
            fontproperties=font_props,
        )

    # Right footer - timestamp (bottom-right)
    fig.text(
        0.985, 0.015, right_text,
        ha="right", va="bottom",
        fontsize=7, fontweight="normal",
        color=COLORS["medium"],
        fontproperties=font_props,
    )

    # Adjust layout to make room for header and footer
    fig.subplots_adjust(top=0.86, bottom=0.08)


def _apply_thai_fonts(fig: plt.Figure, ax: plt.Axes, lang: str = "en") -> None:
    """Apply Thai font to all text elements in the figure when lang='th'."""
    if lang != "th" or not THAI_FONT:
        return

    # Translation map for common English labels
    thai_translations = {
        "Latency (ms)": "ความหน่วง (มิลลิวินาที)",
        "Packet Loss (%)": "การสูญเสียแพ็กเกต (%)",
        "Path Availability (% of hops with <10% loss)": "ความพร้อมใช้งานเส้นทาง (% hop ที่ loss <10%)",
        "Unique IP Sets Returned": "ชุด IP ที่ได้รับ (ไม่ซ้ำ)",
        "IP Stability (%)": "ความเสถียรของ IP (%)",
        "Stability Threshold (80%)": "เกณฑ์ความเสถียร (80%)",
        "No Loss": "ไม่มีการสูญเสีย",
        "10% Warning": "เตือน 10%",
        "50% Critical": "วิกฤต 50%",
        "Healthy (90%)": "ปกติ (90%)",
        "Degraded (70%)": "ลดประสิทธิภาพ (70%)",
        "Availability (%)": "ความพร้อมใช้งาน (%)",
        "Resolvers": "Resolver",
        "Hour of Day (Local)": "ชั่วโมงในวัน (เวลาท้องถิ่น)",
        "Resolver Latency Distribution (ms)": "การกระจายความหน่วงของ Resolver (มิลลิวินาที)",
        "Resolver IP Stability & Diversity": "ความเสถียรและความหลากหลายของ IP Resolver",
        "MTR Network Path Visualization": "การแสดงเส้นทางเครือข่าย MTR",
        "Network Path Availability (ML-based)": "ความพร้อมใช้งานเส้นทางเครือข่าย (จาก ML)",
        "Resolver Availability": "ความพร้อมใช้งานของ Resolver",
        "Integrity": "ความสมบูรณ์",
        "Anomaly": "ผิดปกติ",
        "Normal": "ปกติ",
    }

    # Axis labels and title - apply Thai font
    if ax.get_xlabel():
        ax.set_xlabel(ax.get_xlabel(), fontproperties=THAI_FONT_NORMAL)
    if ax.get_ylabel():
        ax.set_ylabel(ax.get_ylabel(), fontproperties=THAI_FONT_NORMAL)
    if ax.get_title():
        ax.set_title(ax.get_title(), fontproperties=THAI_FONT_TITLE)

    # Tick labels
    for label in ax.get_xticklabels():
        label.set_fontproperties(THAI_FONT_SMALL)
        text = label.get_text()
        if text in thai_translations:
            label.set_text(thai_translations[text])
    for label in ax.get_yticklabels():
        label.set_fontproperties(THAI_FONT_SMALL)
        text = label.get_text()
        if text in thai_translations:
            label.set_text(thai_translations[text])

    # Legend
    legend = ax.get_legend()
    if legend:
        for text in legend.get_texts():
            text.set_fontproperties(THAI_FONT_SMALL)
            txt = text.get_text()
            if txt in thai_translations:
                text.set_text(thai_translations[txt])

    # Text annotations (value labels on bars, etc.)
    for text in ax.texts:
        text.set_fontproperties(THAI_FONT_SMALL)
        txt = text.get_text()
        for eng, thai in thai_translations.items():
            if eng in txt:
                txt = txt.replace(eng, thai)
        text.set_text(txt)

    # Figure-level texts (header/footer already handled separately)
    for text in fig.texts:
        if text.get_position()[1] > 0.85 or text.get_position()[1] < 0.05:
            # Skip header/footer (already set with Thai font)
            continue
        text.set_fontproperties(THAI_FONT_SMALL)
        txt = text.get_text()
        for eng, thai in thai_translations.items():
            if eng in txt:
                txt = txt.replace(eng, thai)
        text.set_text(txt)


def _save_figure(fig: plt.Figure, output_path: Path, dpi: int = 200) -> None:
    """Save figure with tight layout and logging."""
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=COLORS["white"])
    plt.close(fig)
    log.debug("Saved graph: %s", output_path)


def generate_availability_bar_chart(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Resolver Availability (%)",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate horizontal bar chart of resolver availability."""
    if not availability_data:
        return

    resolvers = list(availability_data.keys())
    availabilities = [availability_data[r]["availability_pct"] for r in resolvers]

    # Sort by availability
    sorted_pairs = sorted(zip(resolvers, availabilities), key=lambda x: x[1], reverse=True)
    resolvers = [p[0] for p in sorted_pairs]
    availabilities = [p[1] for p in sorted_pairs]

    fig, ax = plt.subplots(figsize=(10, max(6, len(resolvers) * 0.4)))

    # Color bars by availability
    colors = [
        COLORS["success"] if a >= 99 else COLORS["warning"] if a >= 95 else COLORS["danger"]
        for a in availabilities
    ]

    bars = ax.barh(resolvers, availabilities, color=colors, edgecolor="white", height=0.6)

    # Add value labels
    for bar, val in zip(bars, availabilities):
        ax.text(
            val + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.2f}%",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_xlim(0, 105)
    ax.set_xlabel("Availability (%)", fontsize=12)
    ax.axvline(x=99, color=COLORS["success"], linestyle="--", alpha=0.5, label="99% SLA")
    ax.axvline(x=95, color=COLORS["warning"], linestyle="--", alpha=0.5, label="95% SLA")
    ax.legend(loc="lower right")

    # Invert y-axis so best is at top
    ax.invert_yaxis()

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_availability_heatmap(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Hourly Availability Heatmap",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate heatmap of hourly availability per resolver."""
    if not availability_data:
        return

    resolvers = list(availability_data.keys())
    hours = list(range(24))

    # Build matrix
    matrix = np.full((len(resolvers), 24), np.nan)
    for i, resolver in enumerate(resolvers):
        hourly = availability_data[resolver].get("hourly_availability", {})
        for h in hours:
            val = hourly.get(h)
            if val is not None:
                matrix[i, h] = val

    fig, ax = plt.subplots(figsize=(14, max(6, len(resolvers) * 0.35)))

    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100, interpolation="nearest")

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Availability (%)", fontsize=11)

    # Ticks
    ax.set_yticks(range(len(resolvers)))
    ax.set_yticklabels(resolvers, fontsize=9)
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], fontsize=9, rotation=45)

    # Hour axis is local time (Asia/Bangkok +07) per project convention
    xlabel = "ชั่วโมงในวัน (เวลาท้องถิ่น)" if lang == "th" else "Hour of Day (Local)"
    ax.set_xlabel(xlabel, fontsize=11)

    # Add text annotations for non-NaN values
    for i in range(len(resolvers)):
        for h in hours:
            val = matrix[i, h]
            if not np.isnan(val):
                color = "white" if val < 50 else "black"
                ax.text(h, i, f"{val:.0f}%", ha="center", va="center", fontsize=7, color=color)

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_availability_daily_heatmap(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Daily Availability Heatmap",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate heatmap of daily availability per resolver (for monthly reports)."""
    if not availability_data:
        return

    resolvers = list(availability_data.keys())
    # Get all unique dates across all resolvers
    all_dates = set()
    for resolver in resolvers:
        daily = availability_data[resolver].get("daily_availability", {})
        all_dates.update(daily.keys())

    if not all_dates:
        return

    # Sort dates
    sorted_dates = sorted(all_dates)
    date_labels = [d[-5:] for d in sorted_dates]  # MM-DD format

    # Build matrix
    matrix = np.full((len(resolvers), len(sorted_dates)), np.nan)
    for i, resolver in enumerate(resolvers):
        daily = availability_data[resolver].get("daily_availability", {})
        for j, date in enumerate(sorted_dates):
            val = daily.get(date)
            if val is not None:
                matrix[i, j] = val

    fig, ax = plt.subplots(figsize=(max(12, len(sorted_dates) * 0.4), max(6, len(resolvers) * 0.35)))

    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100, interpolation="nearest")

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Availability (%)", fontsize=11)

    # Ticks
    ax.set_yticks(range(len(resolvers)))
    ax.set_yticklabels(resolvers, fontsize=9)
    ax.set_xticks(range(len(sorted_dates)))
    ax.set_xticklabels(date_labels, fontsize=8, rotation=45)

    # X axis label (local time per project convention)
    xlabel = "วันในเดือน" if lang == "th" else "Day of Month"
    ax.set_xlabel(xlabel, fontsize=11)

    # Add text annotations for non-NaN values
    for i in range(len(resolvers)):
        for j in range(len(sorted_dates)):
            val = matrix[i, j]
            if not np.isnan(val):
                color = "white" if val < 50 else "black"
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center", fontsize=7, color=color)

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_integrity_chart(
    integrity_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Resolver Integrity Score (ML-based)",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate horizontal bar chart of ML-based integrity scores."""
    if not integrity_data:
        return

    resolvers = list(integrity_data.keys())
    scores = [integrity_data[r]["integrity_score"] for r in resolvers]
    # Use .get() for is_anomaly to support both IsolationForest and baseline-based integrity data
    anomalies = [integrity_data[r].get("is_anomaly", scores[i] < 50.0) for i, r in enumerate(resolvers)]

    # Sort by integrity score
    sorted_pairs = sorted(zip(resolvers, scores, anomalies), key=lambda x: x[1], reverse=True)
    resolvers = [p[0] for p in sorted_pairs]
    scores = [p[1] for p in sorted_pairs]
    anomalies = [p[2] for p in sorted_pairs]

    fig, ax = plt.subplots(figsize=(10, max(6, len(resolvers) * 0.4)))

    colors = [COLORS["danger"] if a else COLORS["primary"] for a in anomalies]

    bars = ax.barh(resolvers, scores, color=colors, edgecolor="white", height=0.6)

    # Add value labels and anomaly markers
    for bar, val, is_anomaly in zip(bars, scores, anomalies):
        label = f"{val:.1f}"
        if is_anomaly:
            label += " ⚠"
        ax.text(
            val + 1,
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            fontsize=10,
            fontweight="bold",
            color=COLORS["danger"] if is_anomaly else COLORS["dark"],
        )

    ax.set_xlim(0, 110)
    ax.set_xlabel("Integrity Score (0-100, higher = more consistent)", fontsize=12)
    ax.axvline(x=50, color=COLORS["warning"], linestyle="--", alpha=0.5, label="Median")
    ax.legend(loc="lower right")
    ax.invert_yaxis()

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_latency_boxplot(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Resolver Latency Distribution (ms)",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate box plot of latency distributions per resolver.

    Resolvers are sorted by median latency ASC (fastest on top).
    """
    if not availability_data:
        return

    # We need raw latency data - this is a simplified version using summary stats
    # In practice, you'd pass the raw DataFrame
    resolver_stats = []

    for resolver, data in availability_data.items():
        if "median_latency_ms" in data:
            resolver_stats.append({
                "resolver": resolver,
                "median": data["median_latency_ms"],
                "p25": data.get("p25_latency_ms", data["median_latency_ms"] * 0.7),
                "p75": data.get("p75_latency_ms", data["median_latency_ms"] * 1.3),
                "min": data.get("min_latency_ms", 0),
                "max": data.get("max_latency_ms", data["median_latency_ms"] * 2),
            })

    if not resolver_stats:
        return

    # Sort by median latency ASC (fastest on top)
    resolver_stats.sort(key=lambda x: x["median"])

    resolvers = [s["resolver"] for s in resolver_stats]
    medians = [s["median"] for s in resolver_stats]
    p25s = [s["p25"] for s in resolver_stats]
    p75s = [s["p75"] for s in resolver_stats]
    mins = [s["min"] for s in resolver_stats]
    maxs = [s["max"] for s in resolver_stats]

    fig, ax = plt.subplots(figsize=(12, max(6, len(resolvers) * 0.35)))

    # Create box plot data structure
    box_data = []
    for i in range(len(resolvers)):
        # Simulate box plot from summary stats
        box_data.append([mins[i], p25s[i], medians[i], p75s[i], maxs[i]])

    bp = ax.boxplot(
        box_data,
        vert=False,
        tick_labels=resolvers,
        patch_artist=True,
        showfliers=False,
        widths=0.6,
    )

    for patch in bp["boxes"]:
        patch.set_facecolor(COLORS["primary"])
        patch.set_alpha(0.7)
    for median in bp["medians"]:
        median.set_color(COLORS["dark"])
        median.set_linewidth(2)

    ax.set_xlabel("Latency (ms)", fontsize=12)
    ax.set_xscale("log")  # Log scale often better for latency

    # Invert y-axis so fastest (lowest median) is at top (matching availability bar chart)
    ax.invert_yaxis()

    # Add sort order indicator to title
    if "median" not in title.lower():
        title = f"{title}\n(sorted by median latency, fastest first)"

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_ip_stability_chart(
    integrity_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Resolver IP Stability & Diversity",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate scatter plot of IP stability vs unique IP count."""
    if not integrity_data:
        return

    resolvers = []
    stability = []
    unique_ips = []
    anomalies = []

    for resolver, data in integrity_data.items():
        raw = data.get("raw_features", {})
        if "ip_stability" in raw and "unique_ip_count" in raw:
            resolvers.append(resolver)
            stability.append(raw["ip_stability"] * 100)  # Convert to percentage
            unique_ips.append(raw["unique_ip_count"])
            anomalies.append(data.get("is_anomaly", False))

    if not resolvers:
        return

    fig, ax = plt.subplots(figsize=(10, 8))

    colors = [COLORS["danger"] if a else COLORS["primary"] for a in anomalies]
    sizes = [100 + u * 20 for u in unique_ips]  # Size by unique IP count

    ax.scatter(unique_ips, stability, c=colors, s=sizes, alpha=0.7, edgecolors="white", linewidth=1)

    # Add labels
    for i, resolver in enumerate(resolvers):
        ax.annotate(
            resolver,
            (unique_ips[i], stability[i]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_xlabel("Unique IP Sets Returned", fontsize=12)
    ax.set_ylabel("IP Stability (%)", fontsize=12)
    ax.set_ylim(0, 105)
    ax.axhline(
        y=80, color=COLORS["warning"], linestyle="--", alpha=0.5, label="Stability Threshold (80%)"
    )
    ax.legend(loc="lower right")

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_mtr_path_visualization(
    mtr_data: dict[str, Any],
    output_path: Path,
    title: str = "MTR Network Path Visualization",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate a visual representation of MTR network path with loss% and latency per hop.

    Creates a horizontal bar chart showing each hop with color-coded loss percentage
    and latency statistics. Suitable for identifying problematic network segments.
    """
    if not mtr_data:
        return

    fig, ax = plt.subplots(figsize=(14, max(8, len(mtr_data) * 0.8)))

    for resolver_name, trace in mtr_data.items():
        hops = trace.get("hops", [])
        if not hops:
            continue

        # Extract data for plotting
        hop_nums = [h["hop_num"] for h in hops]
        hosts = [h["host"] for h in hops]
        loss_pcts = [h["loss_pct"] for h in hops]
        avg_latencies = [h["avg_ms"] for h in hops]
        worst_latencies = [h["worst_ms"] for h in hops]

        # Create y-positions for each hop
        y_positions = [f"Hop {h}" for h in hop_nums]

        # Color by loss percentage: green < yellow < red
        colors = []
        for loss in loss_pcts:
            if loss == 0:
                colors.append(COLORS["success"])
            elif loss < 10:
                colors.append(COLORS["warning"])
            elif loss < 50:
                colors.append("#E67E22")  # Orange
            else:
                colors.append(COLORS["danger"])

        # Plot loss% as horizontal bars
        bars = ax.barh(
            y_positions,
            loss_pcts,
            color=colors,
            edgecolor="white",
            height=0.6,
            alpha=0.8,
            label=f"{resolver_name} Loss%" if resolver_name == list(mtr_data.keys())[0] else "",
        )

        # Add value labels on bars
        for bar, loss, host, avg_lat, worst_lat in zip(
            bars, loss_pcts, hosts, avg_latencies, worst_latencies
        ):
            label = f"{loss:.1f}% | {host}"
            if avg_lat > 0:
                label += f" | Avg: {avg_lat:.1f}ms"
            if worst_lat > 0:
                label += f" | Max: {worst_lat:.1f}ms"

            ax.text(
                loss + 1,
                bar.get_y() + bar.get_height() / 2,
                label,
                va="center",
                fontsize=9,
                fontweight="bold" if loss > 10 else "normal",
            )

    ax.set_xlabel("Packet Loss (%)", fontsize=12)
    ax.set_xlim(
        0,
        max(
            105,
            max(
                (max(h["loss_pct"] for h in trace.get("hops", [])) for trace in mtr_data.values()),
                default=100,
            )
        )
        + 20,
    )

    # Add threshold lines
    ax.axvline(x=0, color=COLORS["success"], linestyle="--", alpha=0.3, label="No Loss")
    ax.axvline(x=10, color=COLORS["warning"], linestyle="--", alpha=0.5, label="10% Warning")
    ax.axvline(x=50, color=COLORS["danger"], linestyle="--", alpha=0.5, label="50% Critical")
    ax.legend(loc="lower right")

    ax.invert_yaxis()
    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_path_availability_chart(
    path_availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    title: str = "Network Path Availability (ML-based)",
    lang: str = "en",
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Generate horizontal bar chart of network path availability with ML health scores.

    Shows:
    - Path availability % (hops with <10% loss)
    - ML-based path health score (0-100)
    - Bottleneck hop info
    """
    if not path_availability_data:
        return

    resolvers = list(path_availability_data.keys())
    availabilities = [path_availability_data[r]["path_availability_pct"] for r in resolvers]
    health_scores = [path_availability_data[r].get("path_health_score", 50.0) for r in resolvers]
    bottleneck_info = []
    for r in resolvers:
        bn = path_availability_data[r].get("bottleneck_hop")
        if bn:
            bottleneck_info.append(f"Hop {bn['hop_num']}: {bn['loss_pct']:.1f}% loss")
        else:
            bottleneck_info.append("N/A")

    # Sort by path availability
    sorted_data = sorted(
        zip(resolvers, availabilities, health_scores, bottleneck_info),
        key=lambda x: x[1],
        reverse=True,
    )
    resolvers = [d[0] for d in sorted_data]
    availabilities = [d[1] for d in sorted_data]
    health_scores = [d[2] for d in sorted_data]
    bottleneck_info = [d[3] for d in sorted_data]

    fig, ax = plt.subplots(figsize=(12, max(6, len(resolvers) * 0.5)))

    # Color by path availability
    colors = [
        COLORS["success"] if a >= 90 else COLORS["warning"] if a >= 70 else COLORS["danger"]
        for a in availabilities
    ]

    bars = ax.barh(
        resolvers, availabilities, color=colors, edgecolor="white", height=0.6, alpha=0.8
    )

    # Add value labels with health score
    for bar, avail, health, bn in zip(bars, availabilities, health_scores, bottleneck_info):
        label = f"{avail:.1f}%  |  Health: {health:.0f}  |  {bn}"
        ax.text(
            avail + 1,
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            fontsize=9,
            fontweight="bold" if avail < 70 else "normal",
            color=COLORS["danger"] if avail < 70 else COLORS["dark"],
        )

    ax.set_xlim(0, 110)
    ax.set_xlabel("Path Availability (% of hops with <10% loss)", fontsize=12)
    ax.axvline(x=90, color=COLORS["success"], linestyle="--", alpha=0.5, label="Healthy (90%)")
    ax.axvline(x=70, color=COLORS["warning"], linestyle="--", alpha=0.5, label="Degraded (70%)")
    ax.legend(loc="lower right")

    # Invert y-axis so best is at top
    ax.invert_yaxis()

    _add_header_footer(fig, ax, title, hostname, lang, version)
    _apply_thai_fonts(fig, ax, lang)
    _save_figure(fig, output_path)


def generate_summary_dashboard(
    ml_insights: dict[str, Any],
    output_dir: Path,
    lang: str = "en",
    hostname: str | None = None,
    report_date_context: str | None = None,
    version: str | None = None,
) -> list[Path]:
    """Generate all graphs and return list of generated file paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    generated = []

    # Add language suffix to filename for filtering (e.g., -th.png for Thai)
    lang_suffix = f"-{lang}" if lang != "en" else ""

    availability = ml_insights.get("availability", {})
    integrity = ml_insights.get("integrity", {})

    # Build titles with date context if provided
    if lang == "th":
        base_titles = {
            "availability_bar": "ความพร้อมใช้งานของ Resolver (%)",
            "availability_heatmap": "Heatmap ความพร้อมใช้งานรายชั่วโมง",
            "availability_daily_heatmap": "Heatmap ความพร้อมใช้งานรายวัน",
            "integrity": "คะแนนความสมบูรณ์ของ Resolver (ML-based)",
            "latency": "การกระจายตัวของ Latency (ms)",
            "ip_stability": "ความเสถียรและความหลากหลายของ IP",
            "mtr_path": "การแสดงเส้นทางเครือข่าย MTR",
            "path_availability": "ความพร้อมใช้งานของเส้นทางเครือข่าย (ML-based)",
        }
    else:
        base_titles = {
            "availability_bar": "Resolver Availability (%)",
            "availability_heatmap": "Hourly Availability Heatmap",
            "availability_daily_heatmap": "Daily Availability Heatmap",
            "integrity": "Resolver Integrity Score (ML-based)",
            "latency": "Resolver Latency Distribution (ms)",
            "ip_stability": "Resolver IP Stability & Diversity",
            "mtr_path": "MTR Network Path Visualization",
            "path_availability": "Network Path Availability (ML-based)",
        }

    if report_date_context:
        for k in base_titles:
            base_titles[k] = f"{base_titles[k]}\n{report_date_context}"

    # 1. Availability bar chart
    path = output_dir / f"availability-bar{timestamp}{lang_suffix}.png"
    generate_availability_bar_chart(availability, path, title=base_titles["availability_bar"], lang=lang, hostname=hostname, version=version)
    generated.append(path)

    # 2. Availability heatmap (hourly)
    path = output_dir / f"availability-heatmap{timestamp}{lang_suffix}.png"
    generate_availability_heatmap(availability, path, title=base_titles["availability_heatmap"], lang=lang, hostname=hostname, version=version)
    generated.append(path)

    # 3. Availability daily heatmap (NEW - for monthly reports)
    path = output_dir / f"availability-daily-heatmap{timestamp}{lang_suffix}.png"
    # Check if daily_availability has month-range data (more than 1 day)
    has_month_data = False
    for resolver_data in availability.values():
        daily = resolver_data.get("daily_availability", {})
        if len(daily) > 1:
            has_month_data = True
            break
    
    if has_month_data:
        # Use month-context title for daily heatmap
        if lang == "th":
            daily_heatmap_title = f"Heatmap ความพร้อมใช้งานรายวัน (วันที่ 1 ถึง {now.day})"
            if report_date_context:
                daily_heatmap_title = f"{daily_heatmap_title}\n{report_date_context}"
        else:
            daily_heatmap_title = f"Daily Availability Heatmap (Days 1 to {now.day})"
            if report_date_context:
                daily_heatmap_title = f"{daily_heatmap_title}\n{report_date_context}"
    else:
        daily_heatmap_title = base_titles["availability_daily_heatmap"]
        if report_date_context:
            daily_heatmap_title = f"{daily_heatmap_title}\n{report_date_context}"
    
    generate_availability_daily_heatmap(availability, path, title=daily_heatmap_title, lang=lang, hostname=hostname, version=version)
    generated.append(path)

    # 4. Integrity chart
    path = output_dir / f"integrity-score{timestamp}{lang_suffix}.png"
    generate_integrity_chart(integrity, path, title=base_titles["integrity"], lang=lang, hostname=hostname, version=version)
    generated.append(path)

    # 4. Latency boxplot
    path = output_dir / f"latency-boxplot{timestamp}{lang_suffix}.png"
    generate_latency_boxplot(availability, path, title=base_titles["latency"], lang=lang, hostname=hostname, version=version)
    generated.append(path)

    # 5. IP stability chart
    path = output_dir / f"ip-stability{timestamp}{lang_suffix}.png"
    generate_ip_stability_chart(integrity, path, title=base_titles["ip_stability"], lang=lang, hostname=hostname, version=version)
    generated.append(path)

    # 6. MTR path visualization (if MTR data available)
    mtr_data = ml_insights.get("mtr", {})
    if mtr_data:
        path = output_dir / f"mtr-path{timestamp}{lang_suffix}.png"
        generate_mtr_path_visualization(mtr_data, path, title=base_titles["mtr_path"], lang=lang, hostname=hostname, version=version)
        generated.append(path)

    # 7. Path availability chart (ML-based)
    path_availability = ml_insights.get("path_availability", {})
    if path_availability:
        path = output_dir / f"path-availability{timestamp}{lang_suffix}.png"
        generate_path_availability_chart(path_availability, path, title=base_titles["path_availability"], lang=lang, hostname=hostname, version=version)
        generated.append(path)

    log.info("Generated %d graphs in %s", len(generated), output_dir)
    return generated


# Thai language versions
def generate_availability_bar_chart_th(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of availability bar chart."""
    generate_availability_bar_chart(
        availability_data,
        output_path,
        title="ความพร้อมใช้งานของ Resolver (%)",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_availability_heatmap_th(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of availability heatmap."""
    generate_availability_heatmap(
        availability_data,
        output_path,
        title="Heatmap ความพร้อมใช้งานรายชั่วโมง",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_availability_daily_heatmap_th(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of daily availability heatmap."""
    generate_availability_daily_heatmap(
        availability_data,
        output_path,
        title="Heatmap ความพร้อมใช้งานรายวัน",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_integrity_chart_th(
    integrity_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of integrity chart."""
    generate_integrity_chart(
        integrity_data,
        output_path,
        title="คะแนนความสมบูรณ์ของ Resolver (ML-based)",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_latency_boxplot_th(
    availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of latency boxplot."""
    generate_latency_boxplot(
        availability_data,
        output_path,
        title="การกระจายตัวของ Latency (ms)",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_ip_stability_chart_th(
    integrity_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of IP stability chart."""
    generate_ip_stability_chart(
        integrity_data,
        output_path,
        title="ความเสถียรและความหลากหลายของ IP",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_summary_dashboard_th(
    ml_insights: dict[str, Any],
    output_dir: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> list[Path]:
    """Thai version of summary dashboard."""
    return generate_summary_dashboard(ml_insights, output_dir, lang="th", hostname=hostname, version=version)


def generate_mtr_path_visualization_th(
    mtr_data: dict[str, Any],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of MTR path visualization."""
    generate_mtr_path_visualization(
        mtr_data,
        output_path,
        title="การแสดงเส้นทางเครือข่าย MTR",
        lang="th",
        hostname=hostname,
        version=version,
    )


def generate_path_availability_chart_th(
    path_availability_data: dict[str, dict[str, Any]],
    output_path: Path,
    hostname: str | None = None,
    version: str | None = None,
) -> None:
    """Thai version of path availability chart."""
    generate_path_availability_chart(
        path_availability_data,
        output_path,
        title="ความพร้อมใช้งานของเส้นทางเครือข่าย (ML-based)",
        lang="th",
        hostname=hostname,
        version=version,
    )
