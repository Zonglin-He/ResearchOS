from __future__ import annotations

from pathlib import Path

from app.skills.exporter import export_provider_wrappers


def main() -> int:
    output_root = Path("provider_exports")
    written = export_provider_wrappers(output_root)
    print(f"exported {len(written)} provider wrapper files to {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
