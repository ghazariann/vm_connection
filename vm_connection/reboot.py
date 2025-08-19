from dataclasses import dataclass
from typing import Optional
from .exceptions import UnexpectedRebootError


@dataclass(frozen=True)
class BootIdentity:
    boot_id: Optional[str]
    btime: Optional[int]

    def known(self) -> bool:
        return (self.boot_id is not None) or (self.btime is not None)


def compare_boot_identities(before: BootIdentity, after: BootIdentity) -> None:
    """
    Raise UnexpectedRebootError if the identity has changed.
    Uses the same tiered logic:
      - If before.boot_id exists, compare boot_id only.
      - Else if before.btime exists, compare btime only.
      - Else do nothing.
    """
    if before.boot_id is not None:
        if after.boot_id is None:
            return
        if before.boot_id != after.boot_id:
            raise UnexpectedRebootError(
                f"Reboot detected via boot_id: {before.boot_id} -> {after.boot_id}"
            )
        return

    if before.btime is not None:
        if after.btime is None:
            return
        if before.btime != after.btime:
            raise UnexpectedRebootError(
                f"Reboot detected via btime: {before.btime} -> {after.btime}"
            )
        return
