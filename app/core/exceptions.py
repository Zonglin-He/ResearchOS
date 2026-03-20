class ResearchOSError(Exception):
    pass


class EntityNotFoundError(ResearchOSError):
    pass


class InvalidTransitionError(ResearchOSError):
    pass
