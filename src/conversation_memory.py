"""
Conversation Memory manager for CivicAssist.
Tracks the last 5 conversation turns and extracts contextual entities (zones, events, permits).
"""

from typing import List, Dict, Any, Optional
import re

class ConversationMemory:
    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.messages: List[Dict[str, str]] = []
        self.last_referenced_zone: Optional[str] = None
        self.last_referenced_event: Optional[Dict[str, Any]] = None
        self.last_referenced_permit: Optional[Dict[str, Any]] = None

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a message turn. Role is 'user' or 'assistant'.
        """
        self.messages.append({
            "role": role,
            "content": content
        })

        # Trim to last 5 turns (each turn is a user+assistant pair, so up to 10 messages)
        max_messages = self.max_turns * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

        # Extract entities to maintain active state
        self._extract_entities(content, metadata)

    def _extract_entities(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        if metadata:
            if "zone" in metadata:
                self.last_referenced_zone = metadata["zone"]
            if "event" in metadata:
                self.last_referenced_event = metadata["event"]
            if "permit" in metadata:
                self.last_referenced_permit = metadata["permit"]

        # Regex scan for zone mentions dynamically
        zone_match = re.search(r"\b(zone\s+[a-z0-9_-]+)\b", text, re.IGNORECASE)
        if zone_match:
            self.last_referenced_zone = zone_match.group(1).title()

    def get_recent_history(self, limit: int = 5) -> List[Dict[str, str]]:
        """
        Returns recent messages (up to limit turns).
        """
        return self.messages[-(limit * 2):]

    def get_context(self) -> str:
        """
        Returns a formatted text string summarizing recent dialogue and entities.
        """
        if not self.messages:
            return ""

        lines = []
        for msg in self.messages[-6:]:
            role_label = "Citizen" if msg["role"] == "user" else "CivicAssist"
            lines.append(f"{role_label}: {msg['content']}")

        context_str = "\n".join(lines)
        entity_notes = []
        if self.last_referenced_zone:
            entity_notes.append(f"Active Zone Focus: {self.last_referenced_zone}")
        if self.last_referenced_event:
            entity_notes.append(f"Active Event Focus: {self.last_referenced_event.get('name')}")
        if self.last_referenced_permit:
            entity_notes.append(f"Active Permit Focus: {self.last_referenced_permit.get('name')}")

        if entity_notes:
            context_str += "\n[Active Entities: " + "; ".join(entity_notes) + "]"

        return context_str

    def clear(self):
        """
        Resets memory state.
        """
        self.messages.clear()
        self.last_referenced_zone = None
        self.last_referenced_event = None
        self.last_referenced_permit = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_turns": self.max_turns,
            "messages": self.messages,
            "last_referenced_zone": self.last_referenced_zone,
            "last_referenced_event": self.last_referenced_event,
            "last_referenced_permit": self.last_referenced_permit
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMemory":
        mem = cls(max_turns=data.get("max_turns", 5))
        mem.messages = data.get("messages", [])
        mem.last_referenced_zone = data.get("last_referenced_zone")
        mem.last_referenced_event = data.get("last_referenced_event")
        mem.last_referenced_permit = data.get("last_referenced_permit")
        return mem

