from app.memory.project_memory import ProjectMemory


class ProjectMemoryRetrieval:
    def __init__(self, memory: ProjectMemory) -> None:
        self.memory = memory

    def search_notes(self, query: str) -> list[str]:
        query_lower = query.lower()
        return [note for note in self.memory.notes if query_lower in note.lower()]
