from collections import deque

class Bus:
    """
    Простейшая message bus-шина для мультиагентных взаимодействий.
    Позволяет отправлять сообщения (steps), забирать сообщения для конкретного агента,
    и хранит историю взаимодействий.
    """
    def __init__(self):
        self._messages = deque()
        self._history = []

    def publish(self, message: dict):
        """
        Положить сообщение в очередь (step).
        """
        self._messages.append(message)
        self._history.append(message)

    def get_next_for(self, agent_name: str):
        """
        Забрать следующее сообщение для данного агента.
        Возвращает None, если нет сообщений для агента.
        """
        for idx, msg in enumerate(self._messages):
            if msg.get("to") == agent_name:
                found = msg
                # удаляем по индексу через list(self._messages)
                self._messages = deque([m for i, m in enumerate(self._messages) if i != idx])
                return found
        return None

    def get_history(self):
        return list(self._history)

    def is_empty(self):
        return not self._messages
