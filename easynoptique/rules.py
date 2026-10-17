"""Fichier de règles ``<projet>.easynoptique.yaml`` : corrections manuelles de la détection.

Exemple ::

    hub: mcu                    # bloc central (sinon : bloc le plus connecté)
    components:
      U5: {block: usb}          # force le bloc d'un composant
    blocks:
      capteurs: {name: "Capteurs env.", category: sensors}
      debug: {hide: true}
    nets:
      FLASH_CS: spi             # force le type de bus d'un net
    ignore_nets: [NRST]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Rules:
    hub: str = ""
    components: dict[str, dict] = field(default_factory=dict)
    blocks: dict[str, dict] = field(default_factory=dict)
    nets: dict[str, str] = field(default_factory=dict)
    ignore_nets: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path | None) -> Rules:
        if not path:
            return cls()
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            import yaml
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("PyYAML est nécessaire pour lire le fichier de règles (pip install pyyaml)") from e
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls(
            hub=str(data.get("hub", "") or ""),
            components={str(k): dict(v or {}) for k, v in (data.get("components") or {}).items()},
            blocks={str(k): dict(v or {}) for k, v in (data.get("blocks") or {}).items()},
            nets={str(k): str(v).lower() for k, v in (data.get("nets") or {}).items()},
            ignore_nets=[str(x) for x in (data.get("ignore_nets") or [])],
        )

    @staticmethod
    def default_path(project: str | Path) -> Path:
        p = Path(project)
        base = p if p.is_dir() else p.parent
        stem = p.stem if not p.is_dir() else p.name
        return base / f"{stem}.easynoptique.yaml"
