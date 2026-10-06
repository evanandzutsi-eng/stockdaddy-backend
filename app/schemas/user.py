from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Must be at least 8 characters")

class UserLogin(BaseModel):
    """Schema for user authentication."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Schema for returning user data. Strictly excludes hashed_password."""
    id: str
    email: EmailStr
    is_active: bool
    is_kyc_verified: bool
    created_at: datetime

    # Pydantic V2 configuration to allow reading from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    """Schema for JWT issuance."""
    access_token: str
    token_type: str = "bearer"