"""模型包，统一导出所有 ORM 模型"""
from app.models.student import Student
from app.models.image import Image
from app.models.assignment import Assignment
from app.models.annotation import Annotation

__all__ = ["Student", "Image", "Assignment", "Annotation"]
