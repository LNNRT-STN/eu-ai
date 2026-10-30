"""One visual system for every static chart (src/build_charts.py, notebooks/report_charts.py).

EU navy carries the data; black ink carries the words; yellow is kept for the one thing to look at.
Meaning never rests on colour alone: every series is also labelled in words."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAVY = "#003399"      # EU flag blue: the main series
NAVY_MID = "#5A7FD6"  # second series in a stack
NAVY_PALE = "#D6DFF2" # 'fine' / covered: context, not the story
YELLOW = "#FFCC00"    # EU flag yellow: highlight only
WATER = "#2A78D6"     # flood extent on maps, distinct from the navy classes
RED = "#B8202F"
INK, MUTED, RULE, PAPER = "#14213D", "#5B6577", "#C7CCD6", "#FFFFFF"
HATCH = "////"        # modelled, not observed

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 10,
    "text.color": INK, "ytick.color": INK, "axes.facecolor": PAPER, "figure.facecolor": PAPER,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.spines.bottom": False,
    "xtick.bottom": False, "xtick.labelbottom": False, "ytick.major.size": 0, "legend.frameon": False,
    "savefig.dpi": 300, "svg.fonttype": "none", "hatch.linewidth": 0.8, "hatch.color": NAVY,  # SVG text stays editable
})


def heading(fig, title, subtitle, height):
    """Message title and one-line subtitle, placed in inches so every chart shares the same top rhythm."""
    fig.text(0.25 / fig.get_figwidth(), 1 - 0.28 / height, title, fontsize=14, weight="bold", va="top")
    fig.text(0.25 / fig.get_figwidth(), 1 - 0.62 / height, subtitle, fontsize=10, color=MUTED, va="top")


def note(fig, text, height):
    """Notes and source, bottom-left, one muted size."""
    fig.text(0.25 / fig.get_figwidth(), 0.14 / height, text, fontsize=7.5, color=MUTED, linespacing=1.6)


def save(fig, out, name):
    out.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(out / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", out / f"{name}.png")
