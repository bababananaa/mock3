class ServiceError(Exception):
    status_code = 500

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ValidationError(ServiceError):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409
