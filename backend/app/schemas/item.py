"""Item and WorldObject Pydantic schemas"""
from typing import Any, Literal
from pydantic import BaseModel, Field


class ItemEffect(BaseModel):
    """Effect of using an item"""
    target_attribute: str = Field(..., description="Attribute to modify (health, stress, etc.)")
    value: float = Field(..., description="Value to add/subtract")
    duration: int | None = Field(None, description="Duration in ticks (None for instant/permanent)")


class WorldObject(BaseModel):
    """Base class for objects in the world"""
    id: str = Field(..., description="Unique ID of the object")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Description for agents")
    type: Literal["item", "interactable", "structure"] = Field("item")
    location: str | None = Field(None, description="Current location ID")
    is_visible: bool = Field(True, description="Whether agents can see it without searching")
    properties: dict[str, Any] = Field(default_factory=dict, description="Custom properties (locked, open, etc.)")


class Item(WorldObject):
    """Pickable item that can be used"""
    type: Literal["item"] = "item"
    weight: float = Field(1.0, description="Weight/Size for inventory limits")
    can_pick_up: bool = Field(True, description="Whether it can be added to inventory")
    is_consumable: bool = Field(True, description="Whether it is removed after use")
    effects: list[ItemEffect] = Field(default_factory=list, description="Effects when used")


class Interactable(WorldObject):
    """Object that can be interacted with but not picked up (doors, terminals)"""
    type: Literal["interactable"] = "interactable"
    interaction_type: str = Field("generic", description="Type of interaction (open, hack, search)")
    required_item: str | None = Field(None, description="Item ID needed to interact (e.g. key)")
    state: str = Field("default", description="Current state (closed, open, locked)")
    state_transitions: dict[str, str] = Field(default_factory=dict, description="Map of current_state -> next_state on interaction")
