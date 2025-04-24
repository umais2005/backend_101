from pydantic import BaseModel, Field

class User(BaseModel):
    name : str 
    email : str
    hashed_password : str = Field(exclude=True)
    role : str

class UserSignupModel(BaseModel):
    name : str 
    