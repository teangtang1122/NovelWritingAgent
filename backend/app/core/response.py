"""Unified API response format."""
from typing import Any, Dict, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper.
    
    All API responses follow this format:
    {
        "code": 0,       # 0 = success, non-zero = error code
        "message": "",   # Human-readable message
        "data": {...}    # Response payload (optional)
    }
    """
    code: int = 0
    message: str = "success"
    data: Optional[T] = None
    
    @classmethod
    def success(cls, data: Optional[Any] = None, message: str = "success") -> "ApiResponse":
        """Create a success response."""
        return cls(code=0, message=message, data=data)
    
    @classmethod
    def error(cls, code: int, message: str, data: Optional[Any] = None) -> "ApiResponse":
        """Create an error response."""
        return cls(code=code, message=message, data=data)


class ListResponse(BaseModel, Generic[T]):
    """Paginated list response."""
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
