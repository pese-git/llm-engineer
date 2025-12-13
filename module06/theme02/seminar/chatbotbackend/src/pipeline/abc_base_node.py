from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from src.pipeline.context import Context


class BaseNode(ABC):
    name: str

    async def execute(self, context: Context) -> Context:
        return await self._execute(context)

    @abstractmethod
    async def _execute(self, context: Context) -> Context:
        pass


class BaseDescisionEnum(StrEnum): ...


T = TypeVar("T", bound=BaseDescisionEnum)


class BaseDescisionNode(BaseNode, Generic[T], ABC):
    available_decisions: type[T]
