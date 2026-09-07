from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend_db.models.base import Base
from backend_db.models.mixins import IdMixin, TimestampMixin


class AppUser(IdMixin, TimestampMixin, Base):
    """系统用户基础资料，不保存明文密码。"""

    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)

    credential: Mapped["UserCredential | None"] = relationship(
        "UserCredential",
        back_populates="user",
        uselist=False,
    )


class UserCredential(TimestampMixin, Base):
    """由 B 生成、由 A 保存的密码散列。"""

    __tablename__ = "user_credential"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
    )

    user: Mapped[AppUser] = relationship(
        "AppUser",
        back_populates="credential",
    )


class AuthRole(IdMixin, TimestampMixin, Base):
    """系统级或项目级角色定义。"""

    __tablename__ = "auth_role"

    role_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    role_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    permissions: Mapped[list["AuthRolePermission"]] = relationship(
        "AuthRolePermission",
        back_populates="role",
    )


class AuthPermission(IdMixin, TimestampMixin, Base):
    """由系统版本维护的稳定权限代码。"""

    __tablename__ = "auth_permission"

    permission_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
    )
    permission_name: Mapped[str] = mapped_column(String(128), nullable=False)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    roles: Mapped[list["AuthRolePermission"]] = relationship(
        "AuthRolePermission",
        back_populates="permission",
    )


class AuthRolePermission(Base):
    """角色与权限的多对多关系。"""

    __tablename__ = "auth_role_permission"

    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("auth_role.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("auth_permission.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    role: Mapped[AuthRole] = relationship(
        "AuthRole",
        back_populates="permissions",
    )
    permission: Mapped[AuthPermission] = relationship(
        "AuthPermission",
        back_populates="roles",
    )


class AuthUserRole(Base):
    """用户的系统级角色。"""

    __tablename__ = "auth_user_role"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth_role.id", ondelete="RESTRICT"), primary_key=True
    )


class ProjectMember(IdMixin, TimestampMixin, Base):
    """用户在项目中的成员身份。"""

    __tablename__ = "project_member"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ProjectMemberRole(Base):
    """项目成员的项目级角色。"""

    __tablename__ = "project_member_role"

    project_member_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("project_member.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth_role.id", ondelete="RESTRICT"), primary_key=True
    )
