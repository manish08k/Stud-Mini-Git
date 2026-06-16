class StudError(Exception):
    """Base exception for all Stud errors."""
    exit_code = 1


class ConfigError(StudError):
    exit_code = 2


class ObjectStoreError(StudError):
    exit_code = 3


class HashMismatchError(ObjectStoreError):
    pass


class ObjectNotFoundError(ObjectStoreError):
    pass


class IgnoreError(StudError):
    exit_code = 4


class LockError(StudError):
    exit_code = 5


class LockAcquisitionError(LockError):
    pass


class LockTimeoutError(LockError):
    pass


class EventError(StudError):
    exit_code = 6
