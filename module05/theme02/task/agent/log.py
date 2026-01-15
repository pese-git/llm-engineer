# ---------------------------
# Цветное логирование с timestamp
# ---------------------------
import datetime

class Log:
    """
    Утилита для цветного логирования сообщений в консоль с временной меткой.

    Особенности:
    ------------
    - Поддерживает уровни сообщений: INFO, WARN, ERROR, DEBUG.
    - Цветовое оформление помогает быстро различать тип сообщения.
    - Каждое сообщение содержит временную метку (timestamp).
    - Методы статические — можно вызывать без создания экземпляра.

    Атрибуты:
    ----------
    COLORS : Dict[str, str]
        Словарь соответствия уровням сообщений ANSI-кодов цветов:
        - INFO: синий
        - WARN: жёлтый
        - ERROR: красный
        - DEBUG: зелёный
        - TIME: серый (для timestamp)
        - RESET: сброс цвета
    """

    COLORS = {
        "INFO": "\033[94m",   # синий
        "WARN": "\033[93m",   # жёлтый
        "ERROR": "\033[91m",  # красный
        "DEBUG": "\033[92m",  # зелёный
        "TIME": "\033[90m",   # серый для timestamp
        "RESET": "\033[0m"    # сброс цвета
    }

    @staticmethod
    def _get_timestamp():
        """
        Возвращает текущую временную метку в формате [ЧЧ:ММ:СС.ммм].
        
        Возвращает:
        -----------
        str:
            Строка с текущим временем в формате [ЧЧ:ММ:СС.ммм].
        """
        now = datetime.datetime.now()
        return f"[{now.strftime('%H:%M:%S')}.{now.microsecond//1000:03d}]"

    @staticmethod
    def info(msg: str):
        """
        Логирует информационное сообщение (INFO) с синим цветом и временной меткой.

        Параметры:
        -----------
        msg : str
            Текст сообщения.
        """
        timestamp = Log._get_timestamp()
        print(f"{Log.COLORS['TIME']}{timestamp}{Log.COLORS['RESET']} {Log.COLORS['INFO']}[INFO]{Log.COLORS['RESET']} {msg}")

    @staticmethod
    def warn(msg: str):
        """
        Логирует предупреждение (WARN) с жёлтым цветом и временной меткой.

        Параметры:
        -----------
        msg : str
            Текст предупреждения.
        """
        timestamp = Log._get_timestamp()
        print(f"{Log.COLORS['TIME']}{timestamp}{Log.COLORS['RESET']} {Log.COLORS['WARN']}[WARN]{Log.COLORS['RESET']} {msg}")

    @staticmethod
    def error(msg: str):
        """
        Логирует сообщение об ошибке (ERROR) с красным цветом и временной меткой.

        Параметры:
        -----------
        msg : str
            Текст ошибки.
        """
        timestamp = Log._get_timestamp()
        print(f"{Log.COLORS['TIME']}{timestamp}{Log.COLORS['RESET']} {Log.COLORS['ERROR']}[ERROR]{Log.COLORS['RESET']} {msg}")

    @staticmethod
    def debug(msg: str):
        """
        Логирует отладочное сообщение (DEBUG) с зелёным цветом и временной меткой.

        Параметры:
        -----------
        msg : str
            Текст отладочной информации.
        """
        timestamp = Log._get_timestamp()
        print(f"{Log.COLORS['TIME']}{timestamp}{Log.COLORS['RESET']} {Log.COLORS['DEBUG']}[DEBUG]{Log.COLORS['RESET']} {msg}")