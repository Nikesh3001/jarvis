import json
import os
from pathlib import Path


MEMORY_DIR = Path(__file__).parent.parent / "memory_store"


class VectorStore:
    def __init__(self):
        self._chroma = None
        self._collection = None
        MEMORY_DIR.mkdir(exist_ok=True)

    @property
    def chroma(self):
        if self._chroma is None:
            try:
                import chromadb
            except ImportError:
                raise ImportError("chromadb is not installed. Run: pip install chromadb")
            self._chroma = chromadb.PersistentClient(path=str(MEMORY_DIR))
        return self._chroma

    @property
    def collection(self):
        if self._collection is None:
            try:
                self._collection = self.chroma.get_collection("friday_memory")
            except Exception:
                self._collection = self.chroma.create_collection("friday_memory")
        return self._collection

    def add(self, key, value, metadata=None):
        try:
            doc_id = key.replace(" ", "_").lower()[:64]
            self.collection.upsert(
                ids=[doc_id],
                documents=[str(value)],
                metadatas=[{"key": key, **(metadata or {})}]
            )
            return f"Remembered: {key}"
        except Exception as e:
            return f"Memory add error: {e}"

    def search(self, query, n_results=3, filter_metadata=None):
        try:
            kwargs = {
                "query_texts": [query],
                "n_results": n_results,
            }
            if filter_metadata:
                kwargs["where"] = filter_metadata
            results = self.collection.query(**kwargs)
            if not results["documents"] or not results["documents"][0]:
                return "No memories found."
            lines = []
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )):
                key = meta.get("key", "unknown")
                lines.append(f"{i+1}. [{key}] {doc[:300]}")
            return "Memories:\n" + "\n".join(lines)
        except Exception as e:
            return f"Memory search error: {e}"

    def get_all_keys(self, filter_metadata=None):
        try:
            kwargs = {}
            if filter_metadata:
                kwargs["where"] = filter_metadata
            results = self.collection.get(**kwargs)
            if not results["metadatas"]:
                return "No memories stored."
            keys = [m.get("key", "?") for m in results["metadatas"]]
            return f"Stored memories: {', '.join(keys)}"
        except Exception as e:
            return f"Memory list error: {e}"

    def delete(self, key):
        try:
            doc_id = key.replace(" ", "_").lower()[:64]
            self.collection.delete(ids=[doc_id])
            return f"Forgot: {key}"
        except Exception as e:
            return f"Memory delete error: {e}"

    def count(self):
        try:
            return self.collection.count()
        except Exception:
            return 0
