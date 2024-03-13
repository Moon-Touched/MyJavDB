class DatabaseConnectionError(Exception):
    def __init__(self, message):
        super().__init__(message)


class CookieUnavailableError(Exception):
    def __init__(self, message):
        super().__init__(message)


class UrlRequestFailedError(Exception):
    def __init__(self, message):
        super().__init__(message)


class NoneObjectError(Exception):
    def __init__(self, message):
        super().__init__(message)
