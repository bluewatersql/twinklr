from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from blinkb0t.core.formats.xlights.xsq.parser import XSQParser

if TYPE_CHECKING:
    from blinkb0t.core.formats.xlights.models.xsq import XSequence

root_path = Path(__file__).resolve().parents[1]
seq_path = root_path / "artifacts/need_a_favor/need_a_favor_blinkb0t_mh.xsq"

parser = XSQParser()
sequence: XSequence = parser.parse(seq_path)
sequence.optimize_and_validate()
