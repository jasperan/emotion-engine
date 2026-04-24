import pytest
from emotionsim.simulation.goal_tree import GoalTree, GoalNode, GoalLevel, GoalStatus


class TestGoalNode:
    def test_create_mission_goal(self):
        node = GoalNode(
            description="Ensure maximum survival",
            level=GoalLevel.MISSION,
            owner_ids=[],
            created_at_step=0,
        )
        assert node.level == GoalLevel.MISSION
        assert node.parent_id is None
        assert node.status == GoalStatus.ACTIVE
        assert node.id

    def test_create_agent_goal_with_parent(self):
        node = GoalNode(
            description="Find rope",
            level=GoalLevel.INDIVIDUAL,
            parent_id="mission-1",
            owner_ids=["agent-marcus"],
            created_at_step=5,
            priority=7,
        )
        assert node.parent_id == "mission-1"
        assert node.priority == 7

    def test_goal_serialization_roundtrip(self):
        node = GoalNode(
            description="Test goal",
            level=GoalLevel.GROUP,
            owner_ids=["a1", "a2"],
            created_at_step=3,
            alignment_score=0.8,
            conflict_with=["g5"],
        )
        data = node.to_dict()
        restored = GoalNode.from_dict(data)
        assert restored.description == node.description
        assert restored.level == GoalLevel.GROUP
        assert restored.alignment_score == 0.8
        assert restored.conflict_with == ["g5"]


class TestGoalTree:
    def _make_tree(self) -> GoalTree:
        tree = GoalTree()
        tree.set_mission("Ensure maximum survival", step=0)
        return tree

    def test_set_mission(self):
        tree = self._make_tree()
        assert tree.mission is not None
        assert tree.mission.level == GoalLevel.MISSION

    def test_add_group_goal(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate basement", ["a1", "a2"], step=3)
        goal = tree.get_goal(gid)
        assert goal.level == GoalLevel.GROUP
        assert goal.parent_id == tree.mission.id

    def test_add_agent_goal_under_group(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        aid = tree.add_agent_goal("Find rope", "a1", gid, step=2)
        goal = tree.get_goal(aid)
        assert goal.level == GoalLevel.INDIVIDUAL
        assert goal.parent_id == gid

    def test_get_agent_goals(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1", "a2"], step=1)
        tree.add_agent_goal("Find rope", "a1", gid, step=2)
        tree.add_agent_goal("Triage", "a2", gid, step=2)
        tree.add_agent_goal("Scout", "a1", gid, step=3)
        a1_goals = tree.get_agent_goals("a1")
        assert len(a1_goals) == 2

    def test_get_goal_ancestry(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        aid = tree.add_agent_goal("Find rope", "a1", gid, step=2)
        ancestry = tree.get_ancestry(aid)
        assert len(ancestry) == 3
        assert ancestry[0].level == GoalLevel.MISSION
        assert ancestry[1].level == GoalLevel.GROUP
        assert ancestry[2].level == GoalLevel.INDIVIDUAL

    def test_complete_goal(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.complete_goal(gid, step=5)
        assert tree.get_goal(gid).status == GoalStatus.COMPLETED

    def test_fail_goal(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.fail_goal(gid, step=5)
        assert tree.get_goal(gid).status == GoalStatus.FAILED

    def test_abandon_goal(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.abandon_goal(gid, step=5)
        assert tree.get_goal(gid).status == GoalStatus.ABANDONED

    def test_propagate_completions(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1", "a2"], step=1)
        a1 = tree.add_agent_goal("Find rope", "a1", gid, step=2)
        a2 = tree.add_agent_goal("Triage", "a2", gid, step=2)
        tree.complete_goal(a1, step=5)
        tree.complete_goal(a2, step=6)
        tree.propagate_completions(step=6)
        assert tree.get_goal(gid).status == GoalStatus.COMPLETED

    def test_propagate_does_not_complete_partial(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1", "a2"], step=1)
        a1 = tree.add_agent_goal("Find rope", "a1", gid, step=2)
        tree.add_agent_goal("Triage", "a2", gid, step=2)
        tree.complete_goal(a1, step=5)
        tree.propagate_completions(step=5)
        assert tree.get_goal(gid).status == GoalStatus.ACTIVE

    def test_get_active_goals_for_agent(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.add_agent_goal("Find rope", "a1", gid, step=2)
        tree.add_agent_goal("Scout", "a1", gid, step=3)
        active = tree.get_active_goals("a1")
        assert len(active) == 2

    def test_get_highest_priority_goal(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.add_agent_goal("Find rope", "a1", gid, step=2, priority=5)
        tree.add_agent_goal("Save child", "a1", gid, step=3, priority=9)
        top = tree.get_highest_priority_goal("a1")
        assert top.description == "Save child"
        assert top.priority == 9

    def test_set_alignment_score(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        aid = tree.add_agent_goal("Hoard supplies", "a1", gid, step=2)
        tree.set_alignment(aid, -0.6)
        assert tree.get_goal(aid).alignment_score == -0.6

    def test_add_conflict(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1", "a2"], step=1)
        a1 = tree.add_agent_goal("Hoard", "a1", gid, step=2)
        a2 = tree.add_agent_goal("Share", "a2", gid, step=2)
        tree.add_conflict(a1, a2)
        assert a2 in tree.get_goal(a1).conflict_with
        assert a1 in tree.get_goal(a2).conflict_with

    def test_get_context_string(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate basement", ["a1"], step=1)
        tree.add_agent_goal("Find rope", "a1", gid, step=2)
        context = tree.get_context_string("a1")
        assert "Ensure maximum survival" in context
        assert "Evacuate basement" in context
        assert "Find rope" in context

    def test_tree_serialization_roundtrip(self):
        tree = self._make_tree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.add_agent_goal("Find rope", "a1", gid, step=2)
        data = tree.to_dict()
        restored = GoalTree.from_dict(data)
        assert restored.mission.description == tree.mission.description
        assert len(restored._goals) == len(tree._goals)
