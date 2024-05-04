class CustomAPIResponseError(Exception):
    """Исключение для неуспешного статуса ответа API."""
    pass


class JSONDecodeError(Exception):
    """Исключение для ошибок при декодировании JSON."""
    pass
