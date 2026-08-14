from abc import ABC, abstractmethod
from typing import List
from entity import Entity


class BaseDetector(ABC):

    @abstractmethod
    def detect(self, text: str, block_id: str) -> List[Entity]:
        """
        Takes a text block and its block_id.
        Returns a list of Entity objects found in that text.
        """
        pass

    def normalize_label(self, raw_label: str) -> str:
        from config import LABEL_MAP
        return LABEL_MAP.get(raw_label, raw_label.upper())