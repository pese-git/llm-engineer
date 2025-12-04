from collections import deque
from sgr import BusMessage

class Bus:
    """
    Message bus: публикует и отдаёт только объекты BusMessage
    """
    def __init__(self):
        self._messages = deque()  # только BusMessage
        self._history = []

    def publish(self, message: BusMessage):
        """
        Положить строго BusMessage в очередь. Только BusMessage, иначе ошибка.
        """
        if not isinstance(message, BusMessage):
            raise TypeError("Bus.publish принимает только BusMessage!")
        self._messages.append(message)
        self._history.append(message)

    def get_next_for(self, agent_name: str):
        """
        Забрать следующее сообщение для агента. Возвращает BusMessage или None.
        """
        for idx, msg in enumerate(self._messages):
            if msg.recipient == agent_name:
                found = msg
                self._messages = deque([m for i, m in enumerate(self._messages) if i != idx])
                return found
        return None

    def get_history(self):
        return list(self._history)

    def is_empty(self):
        return not self._messages
