from __future__ import annotations

from assistant_commands import CanonicalCommand
from assistant_brain.dispatch_types import DispatchResult
from assistant_brain.service_registry import InMemoryServiceRegistry


class NavigationHandler:
    def __init__(self, registry: InMemoryServiceRegistry) -> None:
        self._registry = registry

    def handle_guide_to_location(self, command: CanonicalCommand) -> DispatchResult:
        location = str(command.args.get('location', '미지정 위치'))
        self._registry.record_guidance(location)
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Guidance requested to {location}',
            speak_text=f'{location}까지 안내를 시작할게요.',
        )

    def handle_deliver_mail(self, command: CanonicalCommand) -> DispatchResult:
        item = str(command.args.get('item', '우편물'))
        destination = str(command.args.get('destination', '미지정 목적지'))
        self._registry.add_delivery_request(item=item, destination=destination)
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Delivery queued: {item} -> {destination}',
            speak_text=f'{destination}으로 {item} 배달 요청을 저장했어요.',
        )
