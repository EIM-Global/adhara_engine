"""Output formatting helpers — rich tables or JSON."""

import json
import sys

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

_json_mode = False


def set_json_mode(enabled: bool):
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def print_json(data):
    """Print data as formatted JSON."""
    console.print_json(json.dumps(data, default=str))


def print_table(columns: list[tuple[str, str]], rows: list[dict], title: str | None = None):
    """Print a rich table. columns = [(key, header_label), ...]."""
    if _json_mode:
        print_json(rows)
        return

    table = Table(title=title, show_lines=False)
    for _, header in columns:
        table.add_column(header)
    for row in rows:
        table.add_row(*[str(row.get(k, "")) for k, _ in columns])
    console.print(table)


def print_detail(data: dict, title: str | None = None):
    """Print a single record as key-value pairs."""
    if _json_mode:
        print_json(data)
        return

    if title:
        console.print(f"\n[bold]{title}[/bold]")
    for key, value in data.items():
        console.print(f"  [cyan]{key}:[/cyan] {value}")
    console.print()


def print_success(message: str):
    if _json_mode:
        print_json({"status": "ok", "message": message})
    else:
        console.print(f"[green]{message}[/green]")


def print_error(message: str):
    if _json_mode:
        print_json({"status": "error", "message": message})
    else:
        err_console.print(f"[red]Error:[/red] {message}")
    sys.exit(1)
