import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class PRStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class GitHubConnection(Base):
    """Conexión OAuth con GitHub"""

    __tablename__ = "github_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Owner Data
    owner_user_id = Column(String(255), nullable=True, index=True)
    owner_email = Column(String(255), nullable=True, index=True)

    # OAuth Data
    github_user_id = Column(String(50), nullable=False, unique=True)
    github_username = Column(String(100), nullable=False)
    access_token = Column(Text, nullable=False)  # Encrypted
    token_type = Column(String(20), default="bearer")
    scope = Column(Text, nullable=False)

    # Installation Data
    installation_id = Column(String(50), nullable=True)
    account_type = Column(String(20), default="user")  # user or organization
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    repositories = relationship(
        "GitHubRepository", back_populates="connection", cascade="all, delete-orphan"
    )


class GitHubRepository(Base):
    """Repositorio sincronizado de GitHub"""

    __tablename__ = "github_repositories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(
        String(36), ForeignKey("github_connections.id"), nullable=False
    )

    # Repository Data
    github_repo_id = Column(String(50), nullable=False, unique=True)
    full_name = Column(String(200), nullable=False)  # owner/repo
    name = Column(String(100), nullable=False)
    owner = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    homepage_url = Column(String(500), nullable=True)
    default_branch = Column(String(100), default="main")
    is_private = Column(Boolean, default=False)

    # Site Detection
    site_type = Column(String(50), nullable=True)  # nextjs, gatsby, hugo, html, etc.
    base_path = Column(String(200), default="/")
    build_command = Column(String(200), nullable=True)
    output_dir = Column(String(200), nullable=True)

    # Audit Configuration
    auto_audit = Column(Boolean, default=False)
    auto_pr = Column(Boolean, default=False)
    branch_name_pattern = Column(String(100), default="seo-fix-{date}")

    # State
    last_audited_at = Column(DateTime, nullable=True)
    last_commit_sha = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    connection = relationship("GitHubConnection", back_populates="repositories")
    pull_requests = relationship(
        "GitHubPullRequest", back_populates="repository", cascade="all, delete-orphan"
    )


class GitHubPullRequest(Base):
    """Pull Request creado por el sistema"""

    __tablename__ = "github_pull_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(
        String(36), ForeignKey("github_repositories.id"), nullable=False
    )
    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True)

    # PR Data
    github_pr_id = Column(String(50), nullable=False)
    pr_number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    branch_name = Column(String(100), nullable=False)
    base_branch = Column(String(100), default="main")

    # Changes
    files_changed = Column(Integer, default=0)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    modified_files = Column(JSON, nullable=True)  # List of file paths

    # Status
    status = Column(Enum(PRStatus), default=PRStatus.PENDING)
    html_url = Column(String(500), nullable=False)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Expected Improvements
    expected_improvements = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    repository = relationship("GitHubRepository", back_populates="pull_requests")
    audit = relationship("Audit")


class GitHubWebhookEvent(Base):
    """Log de eventos de webhook de GitHub"""

    __tablename__ = "github_webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(
        String(36), ForeignKey("github_repositories.id"), nullable=True
    )

    event_type = Column(String(50), nullable=False)  # push, pull_request, installation
    event_id = Column(String(100), nullable=False, unique=True)
    payload = Column(JSON, nullable=False)

    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
