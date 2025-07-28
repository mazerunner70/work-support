"""
Simple types module for MCP server compatibility.

This provides the TextContent class that was previously imported from mcp.types.
FastMCP 2.x has a different structure, so we provide our own implementation.
"""
from typing import Literal, Union
from pydantic import BaseModel


class TextContent(BaseModel):
    """Text content for MCP responses."""
    type: Literal["text"] = "text"
    text: str

    def __init__(self, text: str, type: str = "text", **kwargs):
        super().__init__(type=type, text=text, **kwargs)


class ImageContent(BaseModel):
    """Image content for MCP responses."""
    type: Literal["image"] = "image"
    data: str
    mimeType: str


# Union type for content
Content = Union[TextContent, ImageContent] 