class AppError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    pass


class BadRequestError(AppError):
    pass


class ConflictError(AppError):
    pass


class ForbiddenError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class InternalError(AppError):
    pass


class TooManyRequestsError(AppError):
    pass
