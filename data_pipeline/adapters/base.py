from abc import ABC, abstractmethod
from typing import Generic, TypeVar


T = TypeVar("T")


class BaseAdapter(ABC, Generic[T]):
    @abstractmethod
    def fetch(self) -> T:
        """Return normalized records from a data source."""

