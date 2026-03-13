from pydantic import BaseModel


class User(BaseModel):
    id: str
    name: str


class Applicant(BaseModel):
    id: str
    name: str
