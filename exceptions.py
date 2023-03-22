class TokenError(Exception):
    """Исключение при отсутствии или неверном формате переменных оружения."""

    pass


class DataError(Exception):
    """Исключение при получении данных по API в неустановленном формате."""

    pass


class StrangeStatus(Exception):
    """Исключение при получении неустановленного статуса домашней работы."""

    pass


class ApiNotAllow(Exception):
    """Исключение при невозможности подключиться к API."""

    pass


class StatusCodeError(Exception):
    """Исключение при получении статус кода, отличного от 200."""

    pass


class NoneHwName(Exception):
    """Исключение при отсутствии имени домашней работы среди ключей."""

    pass
