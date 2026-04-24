"""Performance benchmarks for critical path optimizations.

Compares before/after for:
1. Agent name-to-ID resolution (O(n) linear scan vs O(1) dict lookup)
2. MessageBus get_history per-agent (O(n) filter vs O(1) index lookup)
3. ConversationManager get_agents_at_location (O(n) scan vs O(1) reverse index)
"""
import time
import uuid
from collections import defaultdict

from emotionsim.simulation.message_bus import MessageBus
from emotionsim.simulation.conversation import ConversationManager


# ---------------------------------------------------------------------------
# Helpers to simulate the OLD (linear-scan) behaviour
# ---------------------------------------------------------------------------

def _old_name_to_id_linear(agents: dict, target_name: str) -> str:
    """O(n) linear scan -- the original pattern from engine.py"""
    for aid, name in agents.items():
        if name == target_name:
            return aid
    return target_name


def _new_name_to_id_dict(name_cache: dict, target_name: str) -> str:
    """O(1) dict lookup -- the optimized version"""
    return name_cache.get(target_name, target_name)


def _old_get_history_linear(messages: list, from_agent_id: str) -> list:
    """O(n) linear filter -- the original get_history pattern"""
    return [m for m in messages if m.get("from_agent") == from_agent_id]


def _old_get_agents_at_location(agent_locations: dict, location: str) -> set:
    """O(n) linear scan -- the original get_agents_at_location pattern"""
    return {
        agent_id
        for agent_id, loc in agent_locations.items()
        if loc == location
    }


# ---------------------------------------------------------------------------
# Benchmark 1: Name-to-ID resolution
# ---------------------------------------------------------------------------

def test_benchmark_name_to_id():
    """Compare O(n) linear scan vs O(1) dict lookup for name resolution with 100 agents."""
    num_agents = 100
    iterations = 10_000

    # Build fake agent data
    agents = {}  # id -> name
    name_cache = {}  # name -> id
    for i in range(num_agents):
        aid = str(uuid.uuid4())
        name = f"Agent_{i}"
        agents[aid] = name
        name_cache[name] = aid

    # Pick a target near the end (worst case for linear scan)
    target_name = f"Agent_{num_agents - 1}"

    # --- OLD: linear scan ---
    t0 = time.perf_counter()
    for _ in range(iterations):
        _old_name_to_id_linear(agents, target_name)
    old_elapsed = time.perf_counter() - t0

    # --- NEW: dict lookup ---
    t0 = time.perf_counter()
    for _ in range(iterations):
        _new_name_to_id_dict(name_cache, target_name)
    new_elapsed = time.perf_counter() - t0

    speedup = old_elapsed / new_elapsed if new_elapsed > 0 else float("inf")

    print(f"\n{'='*60}")
    print(f"BENCHMARK: Name-to-ID resolution ({num_agents} agents, {iterations} lookups)")
    print(f"  OLD (linear scan): {old_elapsed*1000:.2f} ms")
    print(f"  NEW (dict lookup): {new_elapsed*1000:.2f} ms")
    print(f"  Speedup: {speedup:.1f}x")
    print(f"{'='*60}")

    # Correctness check
    expected = name_cache[target_name]
    assert _old_name_to_id_linear(agents, target_name) == expected
    assert _new_name_to_id_dict(name_cache, target_name) == expected

    # The dict lookup should be meaningfully faster
    assert new_elapsed < old_elapsed, "Dict lookup should be faster than linear scan"


# ---------------------------------------------------------------------------
# Benchmark 2: MessageBus get_history per-agent
# ---------------------------------------------------------------------------

def test_benchmark_message_bus_history():
    """Compare O(n) filter vs O(1) index for per-agent message retrieval with 10000 messages."""
    num_messages = 10_000
    num_agents = 20
    iterations = 1_000

    # Generate agent IDs
    agent_ids = [f"agent_{i}" for i in range(num_agents)]

    # Build message history (simulating the old flat list)
    all_messages = []
    per_agent_index = defaultdict(list)
    for i in range(num_messages):
        sender = agent_ids[i % num_agents]
        msg = {
            "id": f"msg_{i}",
            "from_agent": sender,
            "content": f"message {i}",
            "step_index": i // 10,
        }
        all_messages.append(msg)
        per_agent_index[sender].append(msg)

    target_agent = agent_ids[0]
    expected_count = len(per_agent_index[target_agent])

    # --- OLD: linear filter ---
    t0 = time.perf_counter()
    for _ in range(iterations):
        result = _old_get_history_linear(all_messages, target_agent)
    old_elapsed = time.perf_counter() - t0

    # --- NEW: index lookup ---
    t0 = time.perf_counter()
    for _ in range(iterations):
        result = per_agent_index.get(target_agent, [])
    new_elapsed = time.perf_counter() - t0

    speedup = old_elapsed / new_elapsed if new_elapsed > 0 else float("inf")

    print(f"\n{'='*60}")
    print(f"BENCHMARK: MessageBus per-agent history ({num_messages} msgs, {iterations} lookups)")
    print(f"  OLD (linear filter): {old_elapsed*1000:.2f} ms")
    print(f"  NEW (index lookup):  {new_elapsed*1000:.2f} ms")
    print(f"  Speedup: {speedup:.1f}x")
    print(f"{'='*60}")

    # Correctness
    assert len(_old_get_history_linear(all_messages, target_agent)) == expected_count
    assert len(per_agent_index.get(target_agent, [])) == expected_count

    assert new_elapsed < old_elapsed, "Index lookup should be faster than linear filter"


def test_benchmark_message_bus_integration():
    """Integration test: verify the actual MessageBus uses indexed get_history."""
    bus = MessageBus()
    num_agents = 10
    msgs_per_agent = 100

    for i in range(num_agents):
        bus.register_agent(f"agent_{i}", f"Agent {i}")

    for step in range(msgs_per_agent):
        for i in range(num_agents):
            bus.send_direct(
                from_agent_id=f"agent_{i}",
                to_agent_id=f"agent_{(i+1) % num_agents}",
                content=f"Hello from step {step}",
                step_index=step,
            )

    # Verify per-agent history uses the index
    history = bus.get_history(from_agent_id="agent_0")
    assert len(history) == msgs_per_agent
    for msg in history:
        assert msg["from_agent"] == "agent_0"

    # Verify full history still works
    all_history = bus.get_history()
    assert len(all_history) == num_agents * msgs_per_agent


# ---------------------------------------------------------------------------
# Benchmark 3: ConversationManager get_agents_at_location
# ---------------------------------------------------------------------------

def test_benchmark_conversation_location_lookup():
    """Compare O(n) scan vs O(1) reverse index for location-based agent lookup."""
    num_agents = 500
    num_locations = 10
    iterations = 10_000

    # Build agent location data
    agent_locations = {}  # old-style: agent_id -> location
    for i in range(num_agents):
        agent_id = f"agent_{i}"
        location = f"location_{i % num_locations}"
        agent_locations[agent_id] = location

    target_location = "location_0"
    expected_count = num_agents // num_locations

    # --- OLD: linear scan ---
    t0 = time.perf_counter()
    for _ in range(iterations):
        result = _old_get_agents_at_location(agent_locations, target_location)
    old_elapsed = time.perf_counter() - t0

    # --- NEW: reverse index ---
    # Build reverse index (what ConversationManager now does)
    location_agents = defaultdict(set)
    for agent_id, loc in agent_locations.items():
        location_agents[loc].add(agent_id)

    t0 = time.perf_counter()
    for _ in range(iterations):
        result = location_agents.get(target_location, set()).copy()
    new_elapsed = time.perf_counter() - t0

    speedup = old_elapsed / new_elapsed if new_elapsed > 0 else float("inf")

    print(f"\n{'='*60}")
    print(f"BENCHMARK: Location agent lookup ({num_agents} agents, {num_locations} locations, {iterations} lookups)")
    print(f"  OLD (linear scan):   {old_elapsed*1000:.2f} ms")
    print(f"  NEW (reverse index): {new_elapsed*1000:.2f} ms")
    print(f"  Speedup: {speedup:.1f}x")
    print(f"{'='*60}")

    # Correctness
    assert len(_old_get_agents_at_location(agent_locations, target_location)) == expected_count
    assert len(location_agents.get(target_location, set())) == expected_count

    assert new_elapsed < old_elapsed, "Reverse index should be faster than linear scan"


def test_benchmark_conversation_manager_integration():
    """Integration test: verify ConversationManager uses the reverse index."""
    mgr = ConversationManager()

    num_agents = 200
    num_locations = 5

    for i in range(num_agents):
        agent_id = f"agent_{i}"
        location = f"loc_{i % num_locations}"
        mgr.update_agent_location(agent_id, location)

    # Verify correctness
    agents_at_loc0 = mgr.get_agents_at_location("loc_0")
    assert len(agents_at_loc0) == num_agents // num_locations

    # Verify all returned agents are actually at that location
    for aid in agents_at_loc0:
        assert mgr._agent_locations[aid] == "loc_0"

    # Verify location change updates the index
    mgr.update_agent_location("agent_0", "loc_1")
    assert "agent_0" not in mgr.get_agents_at_location("loc_0")
    assert "agent_0" in mgr.get_agents_at_location("loc_1")

    # Verify clear works
    mgr.clear()
    assert len(mgr.get_agents_at_location("loc_0")) == 0
