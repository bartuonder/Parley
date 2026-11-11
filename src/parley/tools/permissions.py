from enum import StrEnum


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    RISKY = "risky"


ALL_PERMISSIONS = frozenset(Permission)
MUTATING = frozenset({Permission.WRITE, Permission.RISKY})
