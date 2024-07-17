"""Utilities for adding versions when building the documentation."""

import sys
from pathlib import Path


def add_version_to_selector_page(version: str) -> None:
    """Add the newly built version to the version selection overview.

    Args:
        version: The version that should be added.
    """
    indent = "        "
    new_line = (
        f"{indent}<li><a href="
        f'"https://avhopp.github.io/baybe_dev/{version}/">{version}'
        "</a></li>\n"
    )
    file = Path("versions.html")
    modified_lines = []
    with file.open(mode="r") as f:
        lines = f.readlines()
        for line in lines:
            modified_lines.append(line)
            # Add new line at correct position which is in the first line after stable
            if "Stable" in line:
                modified_lines.append(new_line)
    with file.open(mode="w") as f:
        f.writelines(modified_lines)


def adjust_version_in_sidebar(version: str) -> None:
    """Adjust the shown version in the sidebar.

    Args:
        version: The version that should be injected into the sidebar.
    """
    prefix = '<li class="toctree-l1">'
    link = "https://avhopp.github.io/baybe_dev/versions"
    line_to_replace = (
        f'{prefix}<a class="reference external" href="{link}">Versions</a></li>'
    )
    new_line = (
        f'{prefix}<a class="reference external" href="{link}">V: {version}</a></li>'
    )
    path = Path(version)
    if path.exists():
        # Recursively check all HTML files
        for file in path.rglob("*.html"):
            modified_lines = []
            with file.open(mode="r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.strip() == line_to_replace:
                        modified_lines.append(new_line)
                    else:
                        modified_lines.append(line)
            with file.open(mode="w") as f:
                f.writelines(modified_lines)


if __name__ == "__main__":
    chosen_method = sys.argv[1]
    version = sys.argv[2]
    if chosen_method == "selector_page":
        print(f"Adding {version=} to version selector page")
        add_version_to_selector_page(version)
    elif chosen_method == "sidebar":
        adjust_version_in_sidebar(version)
        print(f"Adding {version=} to sidebar")
    else:
        print(f"Invalid arguments {sys.argv} were chosen!")
