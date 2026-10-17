"""Trusted in-process transport, not network authentication or policy authority."""

from witness_fleet.domain import DispatchEvent


class LocalSimulatorAdapter:
    """Thin exact-ID adapter; missing records remain unknown, never resend proof."""

    def __init__(self, service):
        self.service = service

    def deliver(self, event: DispatchEvent):
        if not isinstance(event, DispatchEvent):
            raise ValueError('a typed hash-bound dispatch event is required')
        validated = DispatchEvent.model_validate(event.model_dump(mode='json'))
        return self.service.receive(validated)

    def event(self, event_id):
        return self.service.journal.event(event_id)

    def receipt(self, command_id):
        return self.service.journal.receipt(command_id)

    def status(self):
        return self.service.status()
