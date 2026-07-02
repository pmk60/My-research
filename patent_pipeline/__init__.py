"""특허 작성 파이프라인.

KIPRIS 선행문헌과 특허/논문을 기반으로, 사용자가 떠올린 아이디어가
특허로 출원·등록될 수 있는지 검토하고 명세서 초안을 작성하며,
모든 과정을 Obsidian 위키로 남기는 파이프라인.
"""

from .config import Config, load_config
from .pipeline import PatentPipeline
from . import models

__all__ = ["Config", "load_config", "PatentPipeline", "models"]

__version__ = "0.1.0"
