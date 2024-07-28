"""Small test file for playing around with versions and tags."""

import sys

from packaging.version import Version


def main():
    """Test the main function."""
    tags = sys.argv[1].split("\n")
    current_version = sys.argv[2]
    tags.sort(key=Version)
    print("false" if tags[-1] == current_version else "true")


if __name__ == "__main__":
    main()
