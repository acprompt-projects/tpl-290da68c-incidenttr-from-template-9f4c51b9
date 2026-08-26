from .models import Incident


class IncidentStore:
    def __init__(self):
        self._by_id: dict[str, Incident] = {}
        self._by_dedupe: dict[str, Incident] = {}

    async def init(self):
        pass

    async def save(self, incident: Incident):
        self._by_id[incident.id] = incident
        if incident.dedupe_key:
            self._by_dedupe[incident.dedupe_key] = incident

    async def get(self, incident_id: str) -> Incident | None:
        return self._by_id.get(incident_id)

    async def find_by_dedupe(self, dedupe_key: str) -> Incident | None:
        return self._by_dedupe.get(dedupe_key)