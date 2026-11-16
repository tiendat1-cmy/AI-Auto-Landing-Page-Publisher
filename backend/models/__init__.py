from sqlalchemy.orm import configure_mappers

from models.generation import (
    GENERATION_STATUSES,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUCCESS,
    Generation,
)
from models.project import Project
from models.template import Template

configure_mappers()

__all__ = [
    "GENERATION_STATUSES",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SUCCESS",
    "Generation",
    "Project",
    "Template",
]
