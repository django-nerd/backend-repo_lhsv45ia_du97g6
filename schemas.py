"""
Database Schemas for MPU Preparation Platform

Each Pydantic model represents a collection in MongoDB.
Collection name = lowercase of class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class MpuUser(BaseModel):
    """
    Collection: "mpuuser"
    Basic user profile for MPU candidates
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    goal: Optional[str] = Field(None, description="Goal or target date for MPU")
    risk_factors: Optional[List[str]] = Field(default_factory=list, description="Self-identified risk factors")

class TrainingSession(BaseModel):
    """
    Collection: "trainingsession"
    A training session containing questions and results
    """
    user_id: str = Field(..., description="ID of the user taking the session")
    status: Literal['started','submitted'] = Field('started', description="Session status")
    questions: List[dict] = Field(default_factory=list, description="Questions asked in this session")
    answers: Optional[List[dict]] = Field(default=None, description="User answers with timestamps")
    score: Optional[float] = Field(default=None, description="Score percentage 0-100")
    feedback: Optional[str] = Field(default=None, description="Textual feedback summary")

class ChecklistItem(BaseModel):
    """
    Collection: "checklistitem"
    Personalized checklist items for a user
    """
    user_id: str = Field(..., description="ID of the user")
    title: str = Field(..., description="Checklist item title")
    completed: bool = Field(False, description="Completion state")

class AnalysisReport(BaseModel):
    """
    Collection: "analysisreport"
    Stores AI analysis results for user inputs
    """
    user_id: Optional[str] = Field(default=None, description="ID of the user if available")
    input_text: str = Field(..., description="Text provided for analysis")
    sentiment: Literal['positive','neutral','negative'] = Field(...)
    risk_score: float = Field(..., ge=0, le=1, description="Computed risk from 0 to 1")
    key_themes: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
