from typing import Literal, TypedDict

from pydantic import BaseModel



class ApiResponse(BaseModel):
    content: str
