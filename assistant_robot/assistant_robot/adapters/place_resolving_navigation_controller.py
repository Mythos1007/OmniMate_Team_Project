from __future__ import annotations

from typing import Any

from assistant_robot.interfaces.navigation_controller import BaseNavigationController, NavigationHandle
from assistant_robot.services.place_catalog import PlaceCatalog


class PlaceResolvingNavigationController(BaseNavigationController):
    """Resolve aliases and normalize place names before delegating navigation."""

    def __init__(
        self,
        delegate: BaseNavigationController,
        *,
        place_catalog: PlaceCatalog | None = None,
    ) -> None:
        self._delegate = delegate
        self._place_catalog = place_catalog or PlaceCatalog()
        self._alias_map = self._build_alias_map()
        self._metadata_map = self._build_metadata_map()

    def start_navigation(self, target_location: str, *, metadata: dict[str, Any] | None = None) -> NavigationHandle:
        resolved_target = self._resolve_target(target_location)
        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("requested_target", target_location)
        merged_metadata.setdefault("resolved_target", resolved_target)
        extra_metadata = self._metadata_map.get(resolved_target, {})
        if extra_metadata:
            merged_metadata.setdefault("resolved_place_metadata", extra_metadata)
        handle = self._delegate.start_navigation(resolved_target, metadata=merged_metadata)
        handle.target_location = resolved_target
        handle.metadata.update(merged_metadata)
        return handle

    def poll_navigation(self, handle: NavigationHandle) -> NavigationHandle:
        return self._delegate.poll_navigation(handle)

    def cancel_navigation(self, handle: NavigationHandle) -> None:
        self._delegate.cancel_navigation(handle)

    def get_current_location(self) -> str:
        return self._delegate.get_current_location()

    def _resolve_target(self, target_location: str) -> str:
        compact = self._compact(target_location)
        if not compact:
            return target_location
        resolved = self._alias_map.get(compact)
        if resolved:
            return resolved
        for alias, canonical in self._alias_map.items():
            if alias and alias in compact:
                return canonical
        return target_location

    def _build_alias_map(self) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for name, place in self._place_catalog.named_places().items():
            alias_map[self._compact(name)] = str(name)
            for alias in place.aliases:
                alias_map[self._compact(alias)] = str(name)
        return alias_map

    def _build_metadata_map(self) -> dict[str, dict[str, Any]]:
        return self._place_catalog.place_metadata()

    @staticmethod
    def _compact(value: str) -> str:
        return "".join(str(value or "").lower().split())
