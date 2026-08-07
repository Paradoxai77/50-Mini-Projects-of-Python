
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime
import difflib
import enum
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# SQLAlchemy Persistence
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

# Rich UI Library
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text as RichText
from rich.tree import Tree

# Safe terminal symbols (Unicode with ASCII safe rendering)
SYMBOL_CHECK = "[v]" if sys.platform == "win32" and "UTF-8" not in getattr(sys.stdout, "encoding", "").upper() else "✓"
SYMBOL_CROSS = "[x]" if sys.platform == "win32" and "UTF-8" not in getattr(sys.stdout, "encoding", "").upper() else "✗"
SYMBOL_ROCKET = "[*]" if sys.platform == "win32" and "UTF-8" not in getattr(sys.stdout, "encoding", "").upper() else "🚀"
SYMBOL_RECUR = "[~]" if sys.platform == "win32" and "UTF-8" not in getattr(sys.stdout, "encoding", "").upper() else "🔄"

# =====================================================================
# 0. STRUCTURED LOGGING SETUP
# =====================================================================
logger = logging.getLogger("ToDoApp")

def setup_logging(level_name: str = "INFO") -> None:
    """Configures structured logging for application audit trails."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Clear handlers
    logger.handlers.clear()

    # File Handler
    file_handler = logging.FileHandler("todolist.log", encoding="utf-8")
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler (only if DEBUG)
    if level == logging.DEBUG:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)


# =====================================================================
# 1. DOMAIN LAYER (Entities & Value Objects)
# =====================================================================

class Priority(enum.IntEnum):
    """Priority level enum with visual properties and comparison support."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

    @property
    def color(self) -> str:
        return {
            Priority.LOW: "bright_blue",
            Priority.MEDIUM: "green",
            Priority.HIGH: "yellow",
            Priority.URGENT: "bold red",
        }[self]

    @property
    def label(self) -> str:
        return self.name

    @classmethod
    def from_string(cls, val: str) -> Priority:
        val_upper = val.strip().upper()
        for p in cls:
            if p.name == val_upper or str(p.value) == val:
                return p
        return cls.MEDIUM


class RecurrenceRule(str, enum.Enum):
    """Supported task recurrence rules."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM_DAYS = "custom_days"

    @classmethod
    def from_string(cls, val: str) -> RecurrenceRule:
        val_lower = val.strip().lower()
        for r in cls:
            if r.value == val_lower:
                return r
        return cls.NONE


@dataclasses.dataclass
class Task:
    """Core Task domain entity representing a single manageable work item."""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    priority: Priority = Priority.MEDIUM
    category: str = "General"
    tags: Set[str] = dataclasses.field(default_factory=set)
    due_date: Optional[datetime.datetime] = None
    created_at: datetime.datetime = dataclasses.field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    )
    completed_at: Optional[datetime.datetime] = None
    is_completed: bool = False
    is_deleted: bool = False
    parent_id: Optional[int] = None
    dependency_ids: List[int] = dataclasses.field(default_factory=list)
    recurrence: RecurrenceRule = RecurrenceRule.NONE
    recurrence_interval: int = 1

    def is_overdue(self) -> bool:
        """Checks whether task is past due date and incomplete."""
        if not self.due_date or self.is_completed or self.is_deleted:
            return False
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        return self.due_date < now

    def is_due_today(self) -> bool:
        """Checks if task is due on current calendar date."""
        if not self.due_date or self.is_completed or self.is_deleted:
            return False
        today = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).date()
        return self.due_date.date() == today

    def to_dict(self) -> Dict[str, Any]:
        """Serializes domain model to dictionary format."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "category": self.category,
            "tags": list(self.tags),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_completed": self.is_completed,
            "is_deleted": self.is_deleted,
            "parent_id": self.parent_id,
            "dependency_ids": self.dependency_ids,
            "recurrence": self.recurrence.value,
            "recurrence_interval": self.recurrence_interval,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Deserializes task dictionary to Task domain entity."""
        def parse_dt(val: Optional[str]) -> Optional[datetime.datetime]:
            if not val:
                return None
            try:
                return datetime.datetime.fromisoformat(val)
            except ValueError:
                return None

        return cls(
            id=data.get("id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=Priority.from_string(data.get("priority", "MEDIUM")),
            category=data.get("category", "General"),
            tags=set(data.get("tags", [])),
            due_date=parse_dt(data.get("due_date")),
            created_at=parse_dt(data.get("created_at")) or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            completed_at=parse_dt(data.get("completed_at")),
            is_completed=bool(data.get("is_completed", False)),
            is_deleted=bool(data.get("is_deleted", False)),
            parent_id=data.get("parent_id"),
            dependency_ids=data.get("dependency_ids", []),
            recurrence=RecurrenceRule.from_string(data.get("recurrence", "none")),
            recurrence_interval=int(data.get("recurrence_interval", 1)),
        )


# =====================================================================
# 2. PERSISTENCE LAYER (SQLAlchemy & Repository Pattern)
# =====================================================================

Base = declarative_base()


class TaskModel(Base):
    """SQLAlchemy ORM table mapping for Task persistence."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    priority = Column(Integer, nullable=False, default=Priority.MEDIUM.value)
    category = Column(String(100), nullable=False, default="General")
    tags_json = Column(Text, nullable=False, default="[]")
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)
    completed_at = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    dependencies_json = Column(Text, nullable=False, default="[]")
    recurrence = Column(String(50), nullable=False, default="none")
    recurrence_interval = Column(Integer, nullable=False, default=1)

    def to_domain(self) -> Task:
        """Converts ORM record to domain entity."""
        try:
            tags = set(json.loads(self.tags_json)) if self.tags_json else set()
        except Exception:
            tags = set()

        try:
            deps = json.loads(self.dependencies_json) if self.dependencies_json else []
        except Exception:
            deps = []

        return Task(
            id=self.id,
            title=self.title,
            description=self.description or "",
            priority=Priority(self.priority) if self.priority in Priority._value2member_map_ else Priority.MEDIUM,
            category=self.category or "General",
            tags=tags,
            due_date=self.due_date,
            created_at=self.created_at,
            completed_at=self.completed_at,
            is_completed=self.is_completed,
            is_deleted=self.is_deleted,
            parent_id=self.parent_id,
            dependency_ids=deps,
            recurrence=RecurrenceRule.from_string(self.recurrence or "none"),
            recurrence_interval=self.recurrence_interval or 1,
        )

    @classmethod
    def from_domain(cls, task: Task) -> TaskModel:
        """Converts domain entity to ORM record."""
        return cls(
            id=task.id,
            title=task.title,
            description=task.description,
            priority=task.priority.value,
            category=task.category,
            tags_json=json.dumps(list(task.tags)),
            due_date=task.due_date,
            created_at=task.created_at,
            completed_at=task.completed_at,
            is_completed=task.is_completed,
            is_deleted=task.is_deleted,
            parent_id=task.parent_id,
            dependencies_json=json.dumps(task.dependency_ids),
            recurrence=task.recurrence.value,
            recurrence_interval=task.recurrence_interval,
        )


class ITaskRepository(ABC):
    """Abstract interface defining standard Repository pattern contract."""

    @abstractmethod
    def add(self, task: Task) -> Task:
        pass

    @abstractmethod
    def get_by_id(self, task_id: int) -> Optional[Task]:
        pass

    @abstractmethod
    def get_all(self, include_deleted: bool = False) -> List[Task]:
        pass

    @abstractmethod
    def update(self, task: Task) -> Task:
        pass

    @abstractmethod
    def soft_delete(self, task_id: int) -> bool:
        pass

    @abstractmethod
    def restore(self, task_id: int) -> bool:
        pass

    @abstractmethod
    def purge(self, task_id: int) -> bool:
        pass

    @abstractmethod
    def get_subtasks(self, parent_id: int) -> List[Task]:
        pass


class SQLAlchemyTaskRepository(ITaskRepository):
    """Concrete repository implementation using SQLite SQLAlchemy engine."""

    def __init__(self, db_url: str = "sqlite:///todolist.db") -> None:
        self.engine = create_engine(db_url, echo=False, future=True)
        Base.metadata.create_all(bind=self.engine)
        session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.Session = scoped_session(session_factory)

    def add(self, task: Task) -> Task:
        session = self.Session()
        try:
            model = TaskModel.from_domain(task)
            session.add(model)
            session.commit()
            session.refresh(model)
            logger.info(f"Task created with ID {model.id}: '{model.title}'")
            return model.to_domain()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add task: {e}")
            raise
        finally:
            self.Session.remove()

    def get_by_id(self, task_id: int) -> Optional[Task]:
        session = self.Session()
        try:
            model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            return model.to_domain() if model else None
        finally:
            self.Session.remove()

    def get_all(self, include_deleted: bool = False) -> List[Task]:
        session = self.Session()
        try:
            query = session.query(TaskModel)
            if not include_deleted:
                query = query.filter(TaskModel.is_deleted == False)
            models = query.order_by(TaskModel.priority.desc(), TaskModel.created_at.desc()).all()
            return [m.to_domain() for m in models]
        finally:
            self.Session.remove()

    def update(self, task: Task) -> Task:
        session = self.Session()
        try:
            model = session.query(TaskModel).filter(TaskModel.id == task.id).first()
            if not model:
                raise ValueError(f"Task with ID {task.id} not found.")

            model.title = task.title
            model.description = task.description
            model.priority = task.priority.value
            model.category = task.category
            model.tags_json = json.dumps(list(task.tags))
            model.due_date = task.due_date
            model.completed_at = task.completed_at
            model.is_completed = task.is_completed
            model.is_deleted = task.is_deleted
            model.parent_id = task.parent_id
            model.dependencies_json = json.dumps(task.dependency_ids)
            model.recurrence = task.recurrence.value
            model.recurrence_interval = task.recurrence_interval

            session.commit()
            session.refresh(model)
            logger.info(f"Task updated ID {task.id}")
            return model.to_domain()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update task ID {task.id}: {e}")
            raise
        finally:
            self.Session.remove()

    def soft_delete(self, task_id: int) -> bool:
        session = self.Session()
        try:
            model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if model:
                model.is_deleted = True
                session.commit()
                logger.info(f"Soft deleted task ID {task_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to soft delete task ID {task_id}: {e}")
            raise
        finally:
            self.Session.remove()

    def restore(self, task_id: int) -> bool:
        session = self.Session()
        try:
            model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if model:
                model.is_deleted = False
                session.commit()
                logger.info(f"Restored task ID {task_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to restore task ID {task_id}: {e}")
            raise
        finally:
            self.Session.remove()

    def purge(self, task_id: int) -> bool:
        session = self.Session()
        try:
            model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if model:
                session.delete(model)
                session.commit()
                logger.info(f"Purged task ID {task_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to purge task ID {task_id}: {e}")
            raise
        finally:
            self.Session.remove()

    def get_subtasks(self, parent_id: int) -> List[Task]:
        session = self.Session()
        try:
            models = (
                session.query(TaskModel)
                .filter(TaskModel.parent_id == parent_id, TaskModel.is_deleted == False)
                .all()
            )
            return [m.to_domain() for m in models]
        finally:
            self.Session.remove()


# =====================================================================
# 3. COMMAND PATTERN LAYER (Undo / Redo Support)
# =====================================================================

class ICommand(ABC):
    """Abstract interface for Command pattern operations supporting undo/redo."""

    @abstractmethod
    def execute(self) -> Any:
        pass

    @abstractmethod
    def undo(self) -> Any:
        pass

    @abstractmethod
    def description(self) -> str:
        pass


class AddTaskCommand(ICommand):
    """Command encapsulating task creation."""

    def __init__(self, repository: ITaskRepository, task: Task) -> None:
        self.repository = repository
        self.task = task
        self.created_task: Optional[Task] = None

    def execute(self) -> Task:
        self.created_task = self.repository.add(self.task)
        return self.created_task

    def undo(self) -> bool:
        if self.created_task and self.created_task.id:
            return self.repository.purge(self.created_task.id)
        return False

    def description(self) -> str:
        title = self.created_task.title if self.created_task else self.task.title
        return f"Add Task '{title}'"


class UpdateTaskCommand(ICommand):
    """Command encapsulating task field updates."""

    def __init__(self, repository: ITaskRepository, updated_task: Task) -> None:
        self.repository = repository
        self.updated_task = updated_task
        self.previous_task: Optional[Task] = None

    def execute(self) -> Task:
        if self.updated_task.id is not None:
            self.previous_task = self.repository.get_by_id(self.updated_task.id)
        return self.repository.update(self.updated_task)

    def undo(self) -> bool:
        if self.previous_task:
            self.repository.update(self.previous_task)
            return True
        return False

    def description(self) -> str:
        return f"Update Task #{self.updated_task.id} ('{self.updated_task.title}')"


class CompleteTaskCommand(ICommand):
    """Command encapsulating task completion (with recurrence auto-generation)."""

    def __init__(self, repository: ITaskRepository, task_id: int, generated_recurring_task: Optional[Task] = None) -> None:
        self.repository = repository
        self.task_id = task_id
        self.previous_state: Optional[Task] = None
        self.generated_recurring_task: Optional[Task] = generated_recurring_task

    def execute(self) -> Tuple[Task, Optional[Task]]:
        task = self.repository.get_by_id(self.task_id)
        if not task:
            raise ValueError(f"Task #{self.task_id} not found.")

        # Save snapshot for undo
        self.previous_state = dataclasses.replace(task)

        task.is_completed = True
        task.completed_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        updated = self.repository.update(task)

        # Handle recurrence if configured
        new_task = None
        if task.recurrence != RecurrenceRule.NONE and self.generated_recurring_task:
            new_task = self.repository.add(self.generated_recurring_task)
            self.generated_recurring_task = new_task

        return updated, new_task

    def undo(self) -> bool:
        if self.previous_state:
            self.repository.update(self.previous_state)
            if self.generated_recurring_task and self.generated_recurring_task.id:
                self.repository.purge(self.generated_recurring_task.id)
            return True
        return False

    def description(self) -> str:
        return f"Complete Task #{self.task_id}"


class DeleteTaskCommand(ICommand):
    """Command encapsulating soft deletion of a task."""

    def __init__(self, repository: ITaskRepository, task_id: int) -> None:
        self.repository = repository
        self.task_id = task_id
        self.deleted_task: Optional[Task] = None

    def execute(self) -> bool:
        self.deleted_task = self.repository.get_by_id(self.task_id)
        return self.repository.soft_delete(self.task_id)

    def undo(self) -> bool:
        return self.repository.restore(self.task_id)

    def description(self) -> str:
        title = self.deleted_task.title if self.deleted_task else str(self.task_id)
        return f"Soft Delete Task '{title}' (#{self.task_id})"


class RestoreTaskCommand(ICommand):
    """Command encapsulating restoration of a soft-deleted task."""

    def __init__(self, repository: ITaskRepository, task_id: int) -> None:
        self.repository = repository
        self.task_id = task_id

    def execute(self) -> bool:
        return self.repository.restore(self.task_id)

    def undo(self) -> bool:
        return self.repository.soft_delete(self.task_id)

    def description(self) -> str:
        return f"Restore Task #{self.task_id}"


class PurgeTaskCommand(ICommand):
    """Command encapsulating hard deletion/purge of a task."""

    def __init__(self, repository: ITaskRepository, task_id: int) -> None:
        self.repository = repository
        self.task_id = task_id
        self.purged_task: Optional[Task] = None

    def execute(self) -> bool:
        self.purged_task = self.repository.get_by_id(self.task_id)
        return self.repository.purge(self.task_id)

    def undo(self) -> bool:
        if self.purged_task:
            self.repository.add(self.purged_task)
            return True
        return False

    def description(self) -> str:
        title = self.purged_task.title if self.purged_task else str(self.task_id)
        return f"Purge Task '{title}' (#{self.task_id})"


class CommandManager:
    """Manages undo and redo stacks for task operations."""

    def __init__(self, max_history: int = 50) -> None:
        self._undo_stack: List[ICommand] = []
        self._redo_stack: List[ICommand] = []
        self._max_history = max_history

    def execute(self, command: ICommand) -> Any:
        result = command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        return result

    def undo(self) -> Tuple[bool, str]:
        if not self._undo_stack:
            return False, "Nothing to undo."
        cmd = self._undo_stack.pop()
        success = cmd.undo()
        if success:
            self._redo_stack.append(cmd)
            return True, f"Undid action: {cmd.description()}"
        return False, f"Failed to undo: {cmd.description()}"

    def redo(self) -> Tuple[bool, str]:
        if not self._redo_stack:
            return False, "Nothing to redo."
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        return True, f"Redid action: {cmd.description()}"


# =====================================================================
# 4. RECURRENCE & ANALYTICS ENGINES
# =====================================================================

class RecurrenceEngine:
    """Calculates next due dates for repeating tasks."""

    @staticmethod
    def calculate_next_due_date(
        base_date: Optional[datetime.datetime],
        rule: RecurrenceRule,
        interval: int = 1
    ) -> datetime.datetime:
        start = base_date or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        interval = max(1, interval)

        if rule == RecurrenceRule.DAILY:
            return start + datetime.timedelta(days=interval)
        elif rule == RecurrenceRule.WEEKLY:
            return start + datetime.timedelta(weeks=interval)
        elif rule == RecurrenceRule.MONTHLY:
            return start + datetime.timedelta(days=30 * interval)
        elif rule == RecurrenceRule.CUSTOM_DAYS:
            return start + datetime.timedelta(days=interval)
        return start


class AnalyticsEngine:
    """Computes productivity trends, velocity, and completion statistics."""

    @staticmethod
    def compute_stats(tasks: List[Task]) -> Dict[str, Any]:
        total = len(tasks)
        completed = [t for t in tasks if t.is_completed]
        pending = [t for t in tasks if not t.is_completed and not t.is_deleted]
        overdue = [t for t in pending if t.is_overdue()]
        due_today = [t for t in pending if t.is_due_today()]

        completion_rate = (len(completed) / total * 100.0) if total > 0 else 0.0

        # Velocity: completions in last 7 days
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        seven_days_ago = now - datetime.timedelta(days=7)
        recent_completions = [
            t for t in completed if t.completed_at and t.completed_at >= seven_days_ago
        ]

        # Priority breakdown
        priority_dist = {p.name: 0 for p in Priority}
        for t in pending:
            priority_dist[t.priority.name] += 1

        # Category breakdown
        category_dist: Dict[str, int] = {}
        for t in pending:
            category_dist[t.category] = category_dist.get(t.category, 0) + 1

        return {
            "total_tasks": total,
            "completed_count": len(completed),
            "pending_count": len(pending),
            "overdue_count": len(overdue),
            "due_today_count": len(due_today),
            "completion_rate": round(completion_rate, 1),
            "velocity_7_days": len(recent_completions),
            "priority_distribution": priority_dist,
            "category_distribution": category_dist,
        }


# =====================================================================
# 5. SERVICE LAYER (TaskService, Import/Export, Search)
# =====================================================================

class TaskService:
    """Core Business Service orchestrating logic, repository, commands, and rules."""

    def __init__(self, repository: ITaskRepository) -> None:
        self.repository = repository
        self.command_manager = CommandManager()

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        category: str = "General",
        tags: Optional[Set[str]] = None,
        due_date: Optional[datetime.datetime] = None,
        parent_id: Optional[int] = None,
        dependency_ids: Optional[List[int]] = None,
        recurrence: RecurrenceRule = RecurrenceRule.NONE,
        recurrence_interval: int = 1,
    ) -> Task:
        if not title.strip():
            raise ValueError("Task title cannot be empty.")

        task = Task(
            title=title.strip(),
            description=description.strip(),
            priority=priority,
            category=category.strip() or "General",
            tags=tags or set(),
            due_date=due_date,
            parent_id=parent_id,
            dependency_ids=dependency_ids or [],
            recurrence=recurrence,
            recurrence_interval=recurrence_interval,
        )
        cmd = AddTaskCommand(self.repository, task)
        return self.command_manager.execute(cmd)

    def complete_task(self, task_id: int) -> Tuple[Task, Optional[Task]]:
        task = self.repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task #{task_id} not found.")

        # Dependency check: Block if any dependency task is incomplete
        if task.dependency_ids:
            all_tasks = {t.id: t for t in self.repository.get_all()}
            blocking = [
                dep_id for dep_id in task.dependency_ids
                if dep_id in all_tasks and not all_tasks[dep_id].is_completed
            ]
            if blocking:
                raise ValueError(
                    f"Cannot complete Task #{task_id}. It is blocked by incomplete tasks: {blocking}"
                )

        # Prepare recurring task instance if applicable
        next_task = None
        if task.recurrence != RecurrenceRule.NONE:
            next_due = RecurrenceEngine.calculate_next_due_date(
                task.due_date, task.recurrence, task.recurrence_interval
            )
            next_task = Task(
                title=task.title,
                description=task.description,
                priority=task.priority,
                category=task.category,
                tags=set(task.tags),
                due_date=next_due,
                parent_id=task.parent_id,
                dependency_ids=list(task.dependency_ids),
                recurrence=task.recurrence,
                recurrence_interval=task.recurrence_interval,
            )

        cmd = CompleteTaskCommand(self.repository, task_id, generated_recurring_task=next_task)
        return self.command_manager.execute(cmd)

    def soft_delete_task(self, task_id: int) -> bool:
        cmd = DeleteTaskCommand(self.repository, task_id)
        return self.command_manager.execute(cmd)

    def restore_task(self, task_id: int) -> bool:
        cmd = RestoreTaskCommand(self.repository, task_id)
        return self.command_manager.execute(cmd)

    def purge_task(self, task_id: int) -> bool:
        cmd = PurgeTaskCommand(self.repository, task_id)
        return self.command_manager.execute(cmd)

    def undo(self) -> Tuple[bool, str]:
        return self.command_manager.undo()

    def redo(self) -> Tuple[bool, str]:
        return self.command_manager.redo()

    def search_tasks(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        priority: Optional[Priority] = None,
        completed_only: Optional[bool] = None,
        fuzzy_threshold: float = 0.5,
    ) -> List[Task]:
        tasks = self.repository.get_all(include_deleted=False)

        filtered = []
        for task in tasks:
            # Filter by completion status
            if completed_only is not None and task.is_completed != completed_only:
                continue

            # Filter by category
            if category and task.category.lower() != category.lower():
                continue

            # Filter by tag
            if tag and tag.lower() not in {t.lower() for t in task.tags}:
                continue

            # Filter by priority
            if priority and task.priority != priority:
                continue

            # Fuzzy text search on title & description
            if query:
                q_lower = query.lower()
                title_lower = task.title.lower()
                desc_lower = task.description.lower()
                
                ratio_title = difflib.SequenceMatcher(None, q_lower, title_lower).ratio()
                is_match = (
                    q_lower in title_lower
                    or q_lower in desc_lower
                    or ratio_title >= fuzzy_threshold
                )
                if not is_match:
                    continue

            filtered.append(task)

        return filtered

    def export_data(self, file_path: str, fmt: str = "json") -> None:
        tasks = [t.to_dict() for t in self.repository.get_all(include_deleted=True)]
        fmt = fmt.lower()

        if fmt == "json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2)
            logger.info(f"Exported {len(tasks)} tasks to JSON: {file_path}")
        elif fmt == "csv":
            if not tasks:
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    pass
                return

            fieldnames = list(tasks[0].keys())
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for task_dict in tasks:
                    row = task_dict.copy()
                    row["tags"] = ",".join(row["tags"])
                    row["dependency_ids"] = ",".join(map(str, row["dependency_ids"]))
                    writer.writerow(row)
            logger.info(f"Exported {len(tasks)} tasks to CSV: {file_path}")
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    def import_data(self, file_path: str, fmt: str = "json") -> int:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        fmt = fmt.lower()
        imported_count = 0

        if fmt == "json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    task = Task.from_dict(item)
                    task.id = None
                    self.repository.add(task)
                    imported_count += 1
        elif fmt == "csv":
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tags = set(row["tags"].split(",")) if row.get("tags") else set()
                    dep_ids = (
                        [int(x) for x in row["dependency_ids"].split(",") if x.strip()]
                        if row.get("dependency_ids")
                        else []
                    )
                    task = Task(
                        title=row.get("title", "Imported Task"),
                        description=row.get("description", ""),
                        priority=Priority.from_string(row.get("priority", "MEDIUM")),
                        category=row.get("category", "General"),
                        tags=tags,
                        dependency_ids=dep_ids,
                        recurrence=RecurrenceRule.from_string(row.get("recurrence", "none")),
                        recurrence_interval=int(row.get("recurrence_interval", 1)),
                    )
                    self.repository.add(task)
                    imported_count += 1

        logger.info(f"Imported {imported_count} tasks from {file_path}")
        return imported_count


# =====================================================================
# 6. PRESENTATION LAYER (Rich UI Renders & REPL Shell)
# =====================================================================

class RichCLIViewer:
    """Renders formatted tables, panels, and analytics using Rich."""

    def __init__(self) -> None:
        self.console = Console()

    def display_tasks(self, tasks: List[Task], title: str = "To-Do List") -> None:
        if not tasks:
            self.console.print(Panel("[bold yellow]No tasks found.[/bold yellow]", title=title))
            return

        table = Table(title=title, show_header=True, header_style="bold magenta", expand=True)
        table.add_column("ID", style="dim", width=6, justify="center")
        table.add_column("Status", width=8, justify="center")
        table.add_column("Title", style="bold", min_width=20)
        table.add_column("Priority", width=10, justify="center")
        table.add_column("Category", width=12)
        table.add_column("Tags", width=15)
        table.add_column("Due Date", width=14, justify="center")
        table.add_column("Recurrence", width=12, justify="center")

        for task in tasks:
            status = f"[bold green]{SYMBOL_CHECK}[/bold green]" if task.is_completed else f"[bold red]{SYMBOL_CROSS}[/bold red]"
            p_color = task.priority.color
            p_badge = f"[{p_color}]{task.priority.name}[/{p_color}]"

            # Due Date coloring
            if task.is_completed:
                due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
            elif task.is_overdue():
                due_str = f"[bold white on red]{task.due_date.strftime('%Y-%m-%d')}[/bold white on red]"
            elif task.is_due_today():
                due_str = f"[bold black on yellow]{task.due_date.strftime('%Y-%m-%d')}[/bold black on yellow]"
            else:
                due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"

            tags_str = ", ".join(task.tags) if task.tags else "-"
            recurrence_str = (
                f"{task.recurrence.value} ({task.recurrence_interval})"
                if task.recurrence != RecurrenceRule.NONE
                else "-"
            )

            table.add_row(
                str(task.id),
                status,
                task.title,
                p_badge,
                task.category,
                tags_str,
                due_str,
                recurrence_str,
            )

        self.console.print(table)

    def display_subtask_tree(self, parent_task: Task, repository: ITaskRepository) -> None:
        tree = Tree(f"[bold gold1]Task #{parent_task.id}: {parent_task.title}[/bold gold1]")

        subtasks = repository.get_subtasks(parent_task.id or 0)
        if not subtasks:
            tree.add("[italic dim]No subtasks[/italic dim]")
        else:
            for sub in subtasks:
                status = f"[green]{SYMBOL_CHECK}[/green]" if sub.is_completed else f"[red]{SYMBOL_CROSS}[/red]"
                tree.add(f"{status} #{sub.id}: {sub.title} [{sub.priority.name}]")

        self.console.print(tree)

    def display_analytics(self, stats: Dict[str, Any]) -> None:
        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_column()

        # Summary text
        summary = (
            f"[bold]Total Tasks:[/bold] {stats['total_tasks']}\n"
            f"[bold green]Completed:[/bold green] {stats['completed_count']}\n"
            f"[bold yellow]Pending:[/bold yellow] {stats['pending_count']}\n"
            f"[bold red]Overdue:[/bold red] {stats['overdue_count']}\n"
            f"[bold cyan]Due Today:[/bold cyan] {stats['due_today_count']}\n"
            f"[bold magenta]Velocity (7 Days):[/bold magenta] {stats['velocity_7_days']} tasks completed"
        )

        self.console.print(Panel(summary, title="Productivity Dashboard", border_style="cyan"))

        # Visual completion progress bar
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        ) as progress:
            p_task = progress.add_task("[bold cyan]Completion Rate", total=100)
            progress.update(p_task, completed=stats['completion_rate'])


# =====================================================================
# 7. INTERACTIVE REPL SHELL MODE
# =====================================================================

def run_interactive_shell(service: TaskService) -> None:
    """Launches interactive terminal REPL shell."""
    console = Console()
    viewer = RichCLIViewer()

    console.print(
        Panel.fit(
            f"[bold cyan]{SYMBOL_ROCKET} Advanced To-Do List Application Shell[/bold cyan]\n"
            "[dim]Clean Architecture | SOLID | Rich Terminal UI[/dim]",
            border_style="magenta",
        )
    )

    while True:
        console.print(
            "\n[bold green]Commands:[/bold green] "
            "[1] List | [2] Add | [3] Complete | [4] Delete | [5] Search | [6] Analytics | [7] Export | [8] Import | [9] Undo | [10] Redo | [0] Exit"
        )
        choice = Prompt.ask("Select option", default="1")

        if choice == "0":
            console.print("[yellow]Goodbye![/yellow]")
            break
        elif choice == "1":
            tasks = service.repository.get_all()
            viewer.display_tasks(tasks, title="Active Tasks")
        elif choice == "2":
            title = Prompt.ask("Task Title")
            desc = Prompt.ask("Description", default="")
            p_str = Prompt.ask("Priority (LOW, MEDIUM, HIGH, URGENT)", default="MEDIUM")
            cat = Prompt.ask("Category", default="General")
            tags_in = Prompt.ask("Tags (comma-separated)", default="")
            due_in = Prompt.ask("Due Date (YYYY-MM-DD)", default="")

            priority = Priority.from_string(p_str)
            tags = {t.strip() for t in tags_in.split(",") if t.strip()}
            due_dt = None
            if due_in.strip():
                try:
                    due_dt = datetime.datetime.strptime(due_in.strip(), "%Y-%m-%d")
                except ValueError:
                    console.print("[red]Invalid date format. Using None.[/red]")

            try:
                task = service.create_task(
                    title=title,
                    description=desc,
                    priority=priority,
                    category=cat,
                    tags=tags,
                    due_date=due_dt,
                )
                console.print(f"[bold green]{SYMBOL_CHECK} Created Task #{task.id}![/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error creating task: {e}[/bold red]")

        elif choice == "3":
            t_id = Prompt.ask("Enter Task ID to complete", password=False)
            try:
                task_id = int(t_id)
                updated, next_t = service.complete_task(task_id)
                console.print(f"[bold green]{SYMBOL_CHECK} Task #{task_id} completed![/bold green]")
                if next_t:
                    console.print(
                        f"[bold cyan]{SYMBOL_RECUR} Recurrence triggered: Created next task #{next_t.id} due on {next_t.due_date.strftime('%Y-%m-%d')}[/bold cyan]"
                    )
            except Exception as e:
                console.print(f"[bold red]Error completing task: {e}[/bold red]")

        elif choice == "4":
            t_id = Prompt.ask("Enter Task ID to soft-delete")
            try:
                task_id = int(t_id)
                service.soft_delete_task(task_id)
                console.print(f"[bold yellow]Task #{task_id} soft-deleted.[/bold yellow]")
            except Exception as e:
                console.print(f"[bold red]Error deleting task: {e}[/bold red]")

        elif choice == "5":
            query = Prompt.ask("Search query", default="")
            results = service.search_tasks(query=query if query else None)
            viewer.display_tasks(results, title=f"Search Results for '{query}'")

        elif choice == "6":
            tasks = service.repository.get_all()
            stats = AnalyticsEngine.compute_stats(tasks)
            viewer.display_analytics(stats)

        elif choice == "7":
            fmt = Prompt.ask("Format (json/csv)", default="json")
            path = Prompt.ask("Output file path", default=f"tasks_export.{fmt}")
            try:
                service.export_data(path, fmt=fmt)
                console.print(f"[bold green]{SYMBOL_CHECK} Exported to {path}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Export failed: {e}[/bold red]")

        elif choice == "8":
            fmt = Prompt.ask("Format (json/csv)", default="json")
            path = Prompt.ask("Import file path", default=f"tasks_export.{fmt}")
            try:
                count = service.import_data(path, fmt=fmt)
                console.print(f"[bold green]{SYMBOL_CHECK} Successfully imported {count} tasks![/bold green]")
            except Exception as e:
                console.print(f"[bold red]Import failed: {e}[/bold red]")

        elif choice == "9":
            success, msg = service.undo()
            style = "bold green" if success else "bold red"
            console.print(f"[{style}]{msg}[/{style}]")

        elif choice == "10":
            success, msg = service.redo()
            style = "bold green" if success else "bold red"
            console.print(f"[{style}]{msg}[/{style}]")


# =====================================================================
# 8. MAIN CLI ENTRY POINT
# =====================================================================

def main() -> None:
    """Main CLI command dispatcher supporting direct flags and interactive shell."""
    parser = argparse.ArgumentParser(
        description="Advanced Enterprise To-Do List Manager",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--db", default="sqlite:///todolist.db", help="SQLite database URL connection string"
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "ERROR"], help="Configure log verbosity"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Shell
    subparsers.add_parser("shell", help="Launch interactive Rich REPL shell mode")

    # Add Task
    add_p = subparsers.add_parser("add", help="Add a new task")
    add_p.add_argument("title", help="Task title")
    add_p.add_argument("--description", default="", help="Task description")
    add_p.add_argument("--priority", default="MEDIUM", help="Priority: LOW, MEDIUM, HIGH, URGENT")
    add_p.add_argument("--category", default="General", help="Category name")
    add_p.add_argument("--tags", default="", help="Comma-separated tags")
    add_p.add_argument("--due", default="", help="Due date in YYYY-MM-DD format")
    add_p.add_argument("--recurrence", default="none", help="Recurrence: none, daily, weekly, monthly")

    # List Tasks
    list_p = subparsers.add_parser("list", help="List active tasks")
    list_p.add_argument("--category", help="Filter by category")
    list_p.add_argument("--tag", help="Filter by tag")

    # Complete Task
    comp_p = subparsers.add_parser("complete", help="Complete a task by ID")
    comp_p.add_argument("id", type=int, help="Task ID")

    # Delete Task
    del_p = subparsers.add_parser("delete", help="Soft-delete a task by ID")
    del_p.add_argument("id", type=int, help="Task ID")

    # Undo / Redo
    subparsers.add_parser("undo", help="Undo previous task operation")
    subparsers.add_parser("redo", help="Redo previously undone operation")

    # Analytics
    subparsers.add_parser("analytics", help="Show productivity analytics and velocity")

    # Search
    search_p = subparsers.add_parser("search", help="Search tasks with fuzzy title matching")
    search_p.add_argument("query", help="Text search query")

    # Export
    exp_p = subparsers.add_parser("export", help="Export tasks to JSON or CSV")
    exp_p.add_argument("--format", default="json", choices=["json", "csv"], help="Export format")
    exp_p.add_argument("--output", default="tasks.json", help="Output filepath")

    # Import
    imp_p = subparsers.add_parser("import", help="Import tasks from JSON or CSV")
    imp_p.add_argument("--format", default="json", choices=["json", "csv"], help="Import format")
    imp_p.add_argument("--input", required=True, help="Input filepath")

    # Test runner
    subparsers.add_parser("test", help="Run internal Pytest test suite")

    args = parser.parse_args()

    setup_logging(args.log_level)

    # Initialize Persistence & Service
    repo = SQLAlchemyTaskRepository(db_url=args.db)
    service = TaskService(repository=repo)
    viewer = RichCLIViewer()

    if not args.command or args.command == "shell":
        run_interactive_shell(service)
        return

    if args.command == "add":
        due_dt = None
        if args.due:
            due_dt = datetime.datetime.strptime(args.due, "%Y-%m-%d")
        tags = {t.strip() for t in args.tags.split(",") if t.strip()}
        task = service.create_task(
            title=args.title,
            description=args.description,
            priority=Priority.from_string(args.priority),
            category=args.category,
            tags=tags,
            due_date=due_dt,
            recurrence=RecurrenceRule.from_string(args.recurrence),
        )
        rprint(f"[bold green]{SYMBOL_CHECK} Created Task #{task.id}: '{task.title}'[/bold green]")

    elif args.command == "list":
        tasks = service.search_tasks(category=args.category, tag=args.tag)
        viewer.display_tasks(tasks)

    elif args.command == "complete":
        try:
            updated, next_t = service.complete_task(args.id)
            rprint(f"[bold green]{SYMBOL_CHECK} Completed Task #{args.id}[/bold green]")
            if next_t:
                rprint(f"[bold cyan]{SYMBOL_RECUR} Generated next recurring task #{next_t.id}[/bold cyan]")
        except Exception as e:
            rprint(f"[bold red]Error: {e}[/bold red]")

    elif args.command == "delete":
        service.soft_delete_task(args.id)
        rprint(f"[bold yellow]Soft-deleted Task #{args.id}[/bold yellow]")

    elif args.command == "undo":
        success, msg = service.undo()
        rprint(f"[bold green]{msg}[/bold green]" if success else f"[bold red]{msg}[/bold red]")

    elif args.command == "redo":
        success, msg = service.redo()
        rprint(f"[bold green]{msg}[/bold green]" if success else f"[bold red]{msg}[/bold red]")

    elif args.command == "analytics":
        tasks = repo.get_all()
        stats = AnalyticsEngine.compute_stats(tasks)
        viewer.display_analytics(stats)

    elif args.command == "search":
        results = service.search_tasks(query=args.query)
        viewer.display_tasks(results, title=f"Search Results for '{args.query}'")

    elif args.command == "export":
        service.export_data(args.output, fmt=args.format)
        rprint(f"[bold green]{SYMBOL_CHECK} Exported to {args.output}[/bold green]")

    elif args.command == "import":
        count = service.import_data(args.input, fmt=args.format)
        rprint(f"[bold green]{SYMBOL_CHECK} Imported {count} tasks from {args.input}[/bold green]")

    elif args.command == "test":
        import pytest
        sys.exit(pytest.main([__file__, "-v"]))


# =====================================================================
# 9. INTEGRATED AUTOMATED TEST SUITE (Pytest)
# =====================================================================

def test_task_domain_entity():
    """Unit test for Task entity state and methods."""
    task = Task(
        title="Test Unit",
        priority=Priority.HIGH,
        due_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=1),
    )
    assert task.is_overdue() is True
    assert task.priority == Priority.HIGH


def test_repository_crud():
    """Integration test for SQLAlchemy repository CRUD operations."""
    repo = SQLAlchemyTaskRepository(db_url="sqlite:///:memory:")
    task = Task(title="Repo Task", priority=Priority.URGENT, category="Work")
    
    saved = repo.add(task)
    assert saved.id is not None
    assert saved.title == "Repo Task"

    fetched = repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.priority == Priority.URGENT

    fetched.title = "Updated Title"
    repo.update(fetched)
    updated = repo.get_by_id(saved.id)
    assert updated.title == "Updated Title"

    assert repo.soft_delete(saved.id) is True
    assert repo.get_by_id(saved.id).is_deleted is True


def test_command_pattern_undo_redo():
    """Unit test verifying undo and redo stack behavior."""
    repo = SQLAlchemyTaskRepository(db_url="sqlite:///:memory:")
    service = TaskService(repo)

    task = service.create_task("Undo Task")
    assert repo.get_by_id(task.id) is not None

    success, msg = service.undo()
    assert success is True
    assert repo.get_by_id(task.id) is None

    success, msg = service.redo()
    assert success is True
    assert repo.get_by_id(task.id) is not None


def test_dependency_blocking():
    """Unit test verifying task completion blocking on dependencies."""
    repo = SQLAlchemyTaskRepository(db_url="sqlite:///:memory:")
    service = TaskService(repo)

    t1 = service.create_task("Task A")
    t2 = service.create_task("Task B", dependency_ids=[t1.id])

    # Should raise error because Task A is incomplete
    try:
        service.complete_task(t2.id)
        assert False, "Should have raised dependency blocking ValueError"
    except ValueError:
        pass

    # Complete Task A first
    service.complete_task(t1.id)
    # Now Task B should complete successfully
    updated, _ = service.complete_task(t2.id)
    assert updated.is_completed is True


def test_recurrence_engine():
    """Unit test for recurring task creation upon completion."""
    repo = SQLAlchemyTaskRepository(db_url="sqlite:///:memory:")
    service = TaskService(repo)

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    t = service.create_task(
        "Daily Standup",
        due_date=now,
        recurrence=RecurrenceRule.DAILY,
        recurrence_interval=1,
    )

    completed, next_task = service.complete_task(t.id)
    assert completed.is_completed is True
    assert next_task is not None
    assert next_task.due_date.date() == (now + datetime.timedelta(days=1)).date()


def test_json_import_export(tmp_path):
    """Integration test for JSON serialization and import/export."""
    repo = SQLAlchemyTaskRepository(db_url="sqlite:///:memory:")
    service = TaskService(repo)
    service.create_task("Export Task 1", category="Finance")

    file_path = str(tmp_path / "export_test.json")
    service.export_data(file_path, fmt="json")

    repo2 = SQLAlchemyTaskRepository(db_url="sqlite:///:memory:")
    service2 = TaskService(repo2)
    imported_count = service2.import_data(file_path, fmt="json")
    assert imported_count == 1
    imported_tasks = repo2.get_all()
    assert imported_tasks[0].title == "Export Task 1"


if __name__ == "__main__":
    main()
