from memory.vector_store import VectorStore


class ConversationMemory:
    def __init__(self):
        self.store = VectorStore()

    def remember(self, key, value):
        return self.store.add(key, value)

    def recall(self, query):
        return self.store.search(query)

    def list_memories(self):
        return self.store.get_all_keys()

    def forget(self, key):
        return self.store.delete(key)

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "remember",
                    "description": "Store a fact or piece of information in long-term memory for later recall",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "A unique label/name for this memory"},
                            "value": {"type": "string", "description": "The content to remember"}
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "recall",
                    "description": "Search long-term memory for information matching a query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "What to search for in memory"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_memories",
                    "description": "List all stored memory keys/labels",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "forget",
                    "description": "Delete a specific memory by key",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "The key/label of the memory to delete"}
                        },
                        "required": ["key"]
                    }
                }
            }
        ]

    def get_handler(self, name):
        handlers = {
            "remember": self.remember,
            "recall": self.recall,
            "list_memories": self.list_memories,
            "forget": self.forget,
        }
        return handlers.get(name)
