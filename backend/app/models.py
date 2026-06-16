import time

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(Float, default=time.time)

    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    repos = relationship("Repository", back_populates="owner", cascade="all, delete-orphan")


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(128), default="default")
    created_at = Column(Float, default=time.time)
    last_used_at = Column(Float, nullable=True)

    user = relationship("User", back_populates="tokens")


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_owner_repo_name"),)

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    is_private = Column(Boolean, default=False)
    default_branch = Column(String(128), default="main")
    created_at = Column(Float, default=time.time)

    owner = relationship("User", back_populates="repos")
    collaborators = relationship(
        "Collaborator", back_populates="repo", cascade="all, delete-orphan"
    )


class Collaborator(Base):
    __tablename__ = "collaborators"
    __table_args__ = (UniqueConstraint("repo_id", "user_id", name="uq_repo_user"),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), default="write")  # read | write | admin

    repo = relationship("Repository", back_populates="collaborators")
    user = relationship("User")
