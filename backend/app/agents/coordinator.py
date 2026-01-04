"""Cooperation coordinator for agent task delegation and loop detection"""
from typing import Any
from collections import defaultdict, deque
from datetime import datetime


class Task:
    """Represents a task that can be assigned to agents"""
    
    def __init__(
        self,
        task_id: str,
        description: str,
        priority: int = 5,
        assigned_to: str | None = None,
        status: str = "pending",
    ):
        self.id = task_id
        self.description = description
        self.priority = priority  # 1-10, higher is more urgent
        self.assigned_to = assigned_to
        self.status = status  # pending, in_progress, completed, failed
        self.created_at = datetime.utcnow()
        self.completed_at: datetime | None = None
        self.progress: float = 0.0  # 0.0 to 1.0


class CooperationCoordinator:
    """
    Coordinates agent cooperation by tracking shared goals, detecting loops,
    and managing task delegation.
    """
    
    def __init__(self):
        # Shared goals across all agents
        self.shared_goals: list[str] = []
        self.goal_progress: dict[str, float] = {}  # goal -> progress (0.0 to 1.0)
        
        # Task management
        self.tasks: dict[str, Task] = {}
        self.agent_tasks: dict[str, list[str]] = defaultdict(list)  # agent_id -> task_ids
        
        # Loop detection
        self.conversation_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
        self.action_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
        self.staleness_scores: dict[str, float] = {}  # agent_id -> staleness (0.0 to 1.0)
        
        # Cooperation metrics
        self.cooperation_score: float = 0.5  # Overall cooperation level (0.0 to 1.0)
        self.agent_cooperation: dict[str, float] = {}  # agent_id -> cooperation score
        
    def add_shared_goal(self, goal: str) -> None:
        """Add a shared goal for all agents"""
        if goal not in self.shared_goals:
            self.shared_goals.append(goal)
            self.goal_progress[goal] = 0.0
    
    def update_goal_progress(self, goal: str, progress: float) -> None:
        """Update progress toward a goal (0.0 to 1.0)"""
        if goal in self.goal_progress:
            self.goal_progress[goal] = max(0.0, min(1.0, progress))
    
    def create_task(
        self,
        description: str,
        priority: int = 5,
        assigned_to: str | None = None,
    ) -> str:
        """Create a new task and return its ID"""
        import uuid
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            description=description,
            priority=priority,
            assigned_to=assigned_to,
        )
        self.tasks[task_id] = task
        if assigned_to:
            self.agent_tasks[assigned_to].append(task_id)
        return task_id
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        # Remove from previous assignee if any
        if task.assigned_to:
            self.agent_tasks[task.assigned_to].remove(task_id)
        
        task.assigned_to = agent_id
        task.status = "in_progress"
        self.agent_tasks[agent_id].append(task_id)
        return True
    
    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = "completed"
        task.progress = 1.0
        task.completed_at = datetime.utcnow()
        return True
    
    def track_conversation(self, agent_id: str, topic: str) -> None:
        """Track conversation topics for loop detection"""
        self.conversation_history[agent_id].append({
            "topic": topic,
            "timestamp": datetime.utcnow(),
        })
        self._update_staleness(agent_id)
    
    def track_action(self, agent_id: str, action_type: str, target: str | None) -> None:
        """Track agent actions for diversity detection"""
        self.action_history[agent_id].append({
            "action_type": action_type,
            "target": target,
            "timestamp": datetime.utcnow(),
        })
        self._update_staleness(agent_id)
    
    def _update_staleness(self, agent_id: str) -> None:
        """Calculate how stale/repetitive an agent's behavior is"""
        conversations = list(self.conversation_history[agent_id])
        actions = list(self.action_history[agent_id])
        
        if len(conversations) < 3 and len(actions) < 3:
            self.staleness_scores[agent_id] = 0.0
            return
        
        # Check for repetitive conversations
        conversation_staleness = 0.0
        if len(conversations) >= 3:
            recent_topics = [c["topic"] for c in conversations[-3:]]
            if len(set(recent_topics)) == 1:  # All same topic
                conversation_staleness = 0.8
            elif len(set(recent_topics)) == 2:  # Mostly same
                conversation_staleness = 0.5
        
        # Check for repetitive actions
        action_staleness = 0.0
        if len(actions) >= 3:
            recent_actions = [(a["action_type"], a["target"]) for a in actions[-3:]]
            if len(set(recent_actions)) == 1:  # All same action
                action_staleness = 0.8
            elif len(set(recent_actions)) == 2:  # Mostly same
                action_staleness = 0.5
        
        # Combined staleness score
        self.staleness_scores[agent_id] = max(conversation_staleness, action_staleness)
    
    def is_stuck_in_loop(self, agent_id: str, threshold: float = 0.7) -> bool:
        """Check if an agent is stuck in a repetitive loop"""
        staleness = self.staleness_scores.get(agent_id, 0.0)
        return staleness >= threshold
    
    def get_suggestions_for_agent(self, agent_id: str) -> list[str]:
        """Get suggestions for an agent to break out of loops"""
        suggestions = []
        
        if self.is_stuck_in_loop(agent_id):
            suggestions.append("You seem to be repeating the same actions. Try a different approach.")
            
            # Suggest based on shared goals
            if self.shared_goals:
                incomplete_goals = [
                    goal for goal in self.shared_goals
                    if self.goal_progress.get(goal, 0.0) < 0.8
                ]
                if incomplete_goals:
                    suggestions.append(f"Consider working toward: {incomplete_goals[0]}")
            
            # Suggest available tasks
            available_tasks = [
                task for task in self.tasks.values()
                if task.status == "pending" and task.assigned_to != agent_id
            ]
            if available_tasks:
                suggestions.append(f"Available task: {available_tasks[0].description}")
        
        return suggestions
    
    def update_cooperation_score(self) -> None:
        """Update overall cooperation score based on task completion and goal progress"""
        if not self.tasks:
            self.cooperation_score = 0.5
            return
        
        # Task completion rate
        completed_tasks = sum(1 for t in self.tasks.values() if t.status == "completed")
        total_tasks = len(self.tasks)
        task_score = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        
        # Goal progress
        if self.goal_progress:
            avg_goal_progress = sum(self.goal_progress.values()) / len(self.goal_progress)
        else:
            avg_goal_progress = 0.0
        
        # Combined score
        self.cooperation_score = (task_score * 0.6 + avg_goal_progress * 0.4)
    
    def get_cooperation_context(self) -> dict[str, Any]:
        """Get context about cooperation state for agents"""
        self.update_cooperation_score()
        
        return {
            "shared_goals": self.shared_goals,
            "goal_progress": self.goal_progress.copy(),
            "cooperation_score": self.cooperation_score,
            "pending_tasks": [
                {
                    "id": task.id,
                    "description": task.description,
                    "priority": task.priority,
                }
                for task in self.tasks.values()
                if task.status == "pending"
            ],
            "agent_staleness": self.staleness_scores.copy(),
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize coordinator state"""
        return {
            "shared_goals": self.shared_goals,
            "goal_progress": self.goal_progress,
            "tasks": {
                task_id: {
                    "id": task.id,
                    "description": task.description,
                    "priority": task.priority,
                    "assigned_to": task.assigned_to,
                    "status": task.status,
                    "progress": task.progress,
                }
                for task_id, task in self.tasks.items()
            },
            "cooperation_score": self.cooperation_score,
        }

