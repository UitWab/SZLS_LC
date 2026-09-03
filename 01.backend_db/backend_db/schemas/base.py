from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    """数据库模块所有对外 DTO 的统一基类。"""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )
