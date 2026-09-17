"""Built-in role names and SUPERADMIN aliases (ТЗ-08)."""

from typing import Optional

BUILTIN_ROLE_NAMES = frozenset({
    'USER', 'ADMIN', 'SUPERADMIN', 'OPERATOR', 'MANAGER',
})

# Transitional alias after OWNER → SUPERADMIN rename.
_SUPERADMIN_ALIASES = frozenset({'SUPERADMIN', 'OWNER'})


def is_superadmin_role(name: Optional[str]) -> bool:
    return name in _SUPERADMIN_ALIASES
