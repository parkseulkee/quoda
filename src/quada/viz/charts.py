"""CLI chart rendering with Plotext."""

import plotext as plt


def render_bar_chart(data: dict[str, float], title: str = "") -> str:
    """Render a bar chart in the terminal and return the string output."""
    plt.clear_figure()
    plt.bar(list(data.keys()), list(data.values()))
    if title:
        plt.title(title)
    plt.theme("dark")
    return plt.build()


def render_line_chart(x: list, y: list, title: str = "") -> str:
    """Render a line chart in the terminal and return the string output."""
    plt.clear_figure()
    plt.plot(x, y)
    if title:
        plt.title(title)
    plt.theme("dark")
    return plt.build()
