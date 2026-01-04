"""Persona model for HumanAgent roleplay"""
from typing import Literal
from pydantic import BaseModel, Field


class Persona(BaseModel):
    """Rich persona for HumanAgent roleplay"""
    
    # Demographics
    name: str = Field(..., description="Character's full name")
    age: int = Field(..., ge=1, le=120, description="Age in years")
    sex: Literal["male", "female", "non-binary"] = Field(..., description="Biological sex/gender identity")
    occupation: str = Field(..., description="Current or former occupation")
    
    # Big Five personality traits (1-10 scale)
    openness: int = Field(5, ge=1, le=10, description="Curiosity, creativity, openness to experience")
    conscientiousness: int = Field(5, ge=1, le=10, description="Organization, dependability, self-discipline")
    extraversion: int = Field(5, ge=1, le=10, description="Sociability, assertiveness, positive emotions")
    agreeableness: int = Field(5, ge=1, le=10, description="Cooperation, trust, altruism")
    neuroticism: int = Field(5, ge=1, le=10, description="Emotional instability, anxiety, moodiness")
    
    # Behavioral modifiers (1-10 scale)
    risk_tolerance: int = Field(5, ge=1, le=10, description="Willingness to take risks under pressure")
    empathy_level: int = Field(5, ge=1, le=10, description="Tendency to help others in need")
    leadership: int = Field(5, ge=1, le=10, description="Tendency to take charge in groups")
    
    # Background
    backstory: str = Field("", description="Brief life history and relevant background")
    skills: list[str] = Field(default_factory=list, description="Notable skills and abilities")
    relationships: dict[str, str] = Field(default_factory=dict, description="Relationships to other agents")
    
    # Dynamic state (updated during simulation)
    stress_level: int = Field(3, ge=1, le=10, description="Current stress/anxiety level")
    health: int = Field(10, ge=0, le=10, description="Current physical health")
    inventory: list[str] = Field(default_factory=list, description="Items currently carried")
    location: str = Field("unknown", description="Current location in the world")
    
    def to_prompt_description(self) -> str:
        """Generate a system prompt description of this persona"""
        traits = []
        
        # Interpret Big Five traits
        if self.openness >= 7:
            traits.append("curious and creative")
        elif self.openness <= 3:
            traits.append("practical and conventional")
            
        if self.conscientiousness >= 7:
            traits.append("organized and dependable")
        elif self.conscientiousness <= 3:
            traits.append("spontaneous and flexible")
            
        if self.extraversion >= 7:
            traits.append("outgoing and assertive")
        elif self.extraversion <= 3:
            traits.append("reserved and introspective")
            
        if self.agreeableness >= 7:
            traits.append("cooperative and trusting")
        elif self.agreeableness <= 3:
            traits.append("competitive and skeptical")
            
        if self.neuroticism >= 7:
            traits.append("emotionally sensitive and prone to anxiety")
        elif self.neuroticism <= 3:
            traits.append("emotionally stable and calm")
        
        # Behavioral traits
        if self.risk_tolerance >= 7:
            traits.append("brave and willing to take risks")
        elif self.risk_tolerance <= 3:
            traits.append("cautious and risk-averse")
            
        if self.empathy_level >= 7:
            traits.append("deeply empathetic")
        elif self.empathy_level <= 3:
            traits.append("focused on self-preservation")
            
        if self.leadership >= 7:
            traits.append("a natural leader")
        elif self.leadership <= 3:
            traits.append("preferring to follow others")
        
        traits_str = ", ".join(traits) if traits else "balanced personality"
        skills_str = ", ".join(self.skills) if self.skills else "no special skills"
        
        description = f"""You are {self.name}, a {self.age}-year-old {self.sex} {self.occupation}.

Personality: You are {traits_str}.

Background: {self.backstory if self.backstory else 'An ordinary person caught in extraordinary circumstances.'}

Skills: {skills_str}

Current State:
- Stress Level: {self.stress_level}/10 {'(very stressed)' if self.stress_level >= 7 else '(calm)' if self.stress_level <= 3 else '(moderately stressed)'}
- Health: {self.health}/10 {'(critically injured)' if self.health <= 2 else '(injured)' if self.health <= 5 else '(healthy)'}
- Location: {self.location}
- Inventory: {', '.join(self.inventory) if self.inventory else 'nothing'}

Stay in character. React authentically based on your personality and current emotional state."""
        
        return description


class PersonaTemplate(BaseModel):
    """Template for generating personas"""
    name: str
    age_range: tuple[int, int] = (18, 65)
    sex: Literal["male", "female", "non-binary", "random"] = "random"
    occupation: str
    
    # Trait ranges for randomization
    openness_range: tuple[int, int] = (3, 8)
    conscientiousness_range: tuple[int, int] = (3, 8)
    extraversion_range: tuple[int, int] = (3, 8)
    agreeableness_range: tuple[int, int] = (3, 8)
    neuroticism_range: tuple[int, int] = (3, 8)
    
    risk_tolerance_range: tuple[int, int] = (3, 8)
    empathy_level_range: tuple[int, int] = (3, 8)
    leadership_range: tuple[int, int] = (3, 8)
    
    backstory: str = ""
    skills: list[str] = Field(default_factory=list)

