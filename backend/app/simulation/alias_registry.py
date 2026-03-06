"""Deterministic alias registry for resolving partial agent names to agent IDs."""
import re


# Recognized title prefixes (lowercase, with trailing dot if applicable)
_TITLES = {
    "dr.", "prof.", "professor", "officer", "captain", "chief",
    "mayor", "coach", "pastor", "father", "sister", "brother",
    "reverend", "rev.", "sgt.", "sergeant", "lt.", "lieutenant",
    "col.", "colonel", "gen.", "general", "mr.", "mrs.", "ms.", "miss",
    "sir", "dame", "lord", "lady", "judge",
}


class AliasRegistry:
    """
    Maps display names to a set of lowercase aliases, enabling deterministic
    resolution of partial/informal names (e.g. "Dr. Chen") back to agent IDs.

    If an alias maps to multiple agents it is considered ambiguous and
    resolve() returns None for that alias.
    """

    def __init__(self):
        # alias (lowercase str) -> set of agent_ids that own it
        self._alias_to_agents: dict[str, set[str]] = {}
        # agent_id -> set of aliases registered for it
        self._agent_aliases: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, agent_id: str, display_name: str) -> None:
        """Register an agent and auto-generate aliases from its display name."""
        aliases = self._generate_aliases(display_name)
        self._agent_aliases[agent_id] = aliases
        for alias in aliases:
            if alias not in self._alias_to_agents:
                self._alias_to_agents[alias] = set()
            self._alias_to_agents[alias].add(agent_id)

    def unregister(self, agent_id: str) -> None:
        """Remove an agent and all its aliases."""
        aliases = self._agent_aliases.pop(agent_id, set())
        for alias in aliases:
            owners = self._alias_to_agents.get(alias)
            if owners:
                owners.discard(agent_id)
                if not owners:
                    del self._alias_to_agents[alias]

    def resolve(self, name: str) -> str | None:
        """
        Resolve a name to an agent_id.
        Returns None if the name is unknown or ambiguous (maps to >1 agent).
        """
        key = name.strip().lower()
        owners = self._alias_to_agents.get(key)
        if owners and len(owners) == 1:
            return next(iter(owners))
        return None

    def resolve_or_fallback(self, name: str) -> tuple[str | None, bool]:
        """
        Resolve a name, also indicating ambiguity.
        Returns (agent_id, False) on unique match,
                (None, True) if ambiguous,
                (None, False) if unknown.
        """
        key = name.strip().lower()
        owners = self._alias_to_agents.get(key)
        if not owners:
            return None, False
        if len(owners) == 1:
            return next(iter(owners)), False
        return None, True

    # ------------------------------------------------------------------
    # Alias generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_aliases(display_name: str) -> set[str]:
        """Generate all plausible aliases from a display name."""
        aliases: set[str] = set()
        raw = display_name.strip()

        # Always add the full original display name (lowercased)
        aliases.add(raw.lower())

        # Strip trailing #N numbering
        stripped = re.sub(r'\s*#\d+\s*$', '', raw).strip()
        aliases.add(stripped.lower())

        # Extract quoted nicknames: 'Bobby' or "Tommy"
        nicknames: list[str] = re.findall(r"""['"]([^'"]+)['"]""", stripped)

        # Remove nickname tokens from the name for part extraction
        clean = re.sub(r"""['"][^'"]+['"]\s*""", '', stripped).strip()

        # Identify title prefix
        title: str | None = None
        parts = clean.split()
        if parts and parts[0].lower() in _TITLES:
            title = parts[0].lower()
            name_parts = parts[1:]
        else:
            name_parts = parts

        # Add individual name parts
        for part in name_parts:
            aliases.add(part.lower())

        # Add full name without title
        if name_parts:
            aliases.add(' '.join(name_parts).lower())

        # Add full name with title
        if title and name_parts:
            aliases.add(f"{title} {' '.join(name_parts)}".lower())

        # Title + last name (e.g., "dr. chen")
        if title and len(name_parts) >= 1:
            aliases.add(f"{title} {name_parts[-1]}".lower())

        # First + last (when there are at least 2 name parts)
        if len(name_parts) >= 2:
            aliases.add(f"{name_parts[0]} {name_parts[-1]}".lower())

        # Nicknames
        for nick in nicknames:
            aliases.add(nick.lower())
            # Nickname + last name
            if name_parts:
                aliases.add(f"{nick} {name_parts[-1]}".lower())

        return aliases
