# ---------------------------
# SGR: Agent actions & messaging
# ---------------------------

from typing import Any, Dict, Optional, Union, Literal
from pydantic import BaseModel, Field

class AskAgent(BaseModel):
    """
    Действие: отправить сообщение другому агенту.

    Поля:
        action  – тип действия, всегда "ask_agent".
        target  – имя агента, которому адресовано сообщение
                  (planner, coder, tester, reviewer).
        message – текст сообщения, передаваемый целевому агенту.

    Назначение:
        Используется для межагентной коммуникации в рамках шины сообщений (MessageBus).
    """
    action: Literal["ask_agent"] = "ask_agent"
    target: Literal["planner", "coder", "tester", "reviewer"]
    message: str


class UseTool(BaseModel):
    """
    Действие: запросить выполнение инструмента (tool).

    Поля:
        action    – тип действия, всегда "use_tool".
        tool_name – имя инструмента, который должен быть вызван (например: store_code, run_tests).
        args      – параметры, необходимые инструменту для выполнения (словарь).

    Назначение:
        Позволяет агентам вызывать внешние инструменты через Orchestrator.
    """
    action: Literal["use_tool"] = "use_tool"
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class Reply(BaseModel):
    """
    Действие: вернуть текстовый ответ.

    Поля:
        action  – тип действия, всегда "reply".
        content – текст ответа.

    Назначение:
        Используется, когда агент должен вернуть результат,
        не инициируя вызовы инструментов и не отправляя сообщений другим агентам.
    """
    action: Literal["reply"] = "reply"
    content: str


class Finish(BaseModel):
    """
    Действие: завершить работу агента, сообщив итог.

    Поля:
        action  – тип действия, всегда "finish".
        summary – краткое описание результата завершения.

    Назначение:
        Позволяет агенту сообщить о финальном состоянии (например: задача решена,
        тесты пройдены, работа завершена) и прекратить участие в текущей оркестрации.
    """
    action: Literal["finish"] = "finish"
    summary: str


class AgentStep(BaseModel):
    """
    Обёртка над единичным шагом агента.

    Поля:
        step – одно из возможных действий агента:
               AskAgent, UseTool, Reply или Finish.

    Назначение:
        Определяет структуру ответа агента, обеспечивая строгую типизацию его действий.
    """
    step: Union[AskAgent, UseTool, Reply, Finish]


class BusMessage(BaseModel):
    """
    Сообщение, передаваемое через MessageBus.

    Поля:
        sender    – имя агента, отправившего сообщение.
        recipient – имя агента-получателя или "broadcast" для глобальной рассылки.
        content   – текст сообщения.
        meta      – дополнительные служебные метаданные (опционально).

    Назначение:
        Используется инфраструктурой для маршрутизации коммуникаций между агентами.
    """
    sender: str
    recipient: str  # имя агента или "broadcast"
    content: str
    meta: Optional[Dict[str, Any]] = None