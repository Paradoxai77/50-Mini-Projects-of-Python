# 🚀 Advanced Enterprise To-Do List Application

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Architecture](https://img.shields.io/badge/architecture-Clean%20%2F%20SOLID-brightgreen)
![Persistence](https://img.shields.io/badge/database-SQLite%20%7C%20SQLAlchemy-orange)
![UI](https://img.shields.io/badge/interface-Rich%20CLI%20%2F%20REPL-magenta)
![Testing](https://img.shields.io/badge/testing-Pytest%20Passed-success)

An enterprise-grade, clean-architecture To-Do List application written in Python. Built adhering strictly to SOLID design principles, standard design patterns (Repository Pattern, Command Pattern for Undo/Redo), rich terminal user interface components, SQLite SQLAlchemy ORM persistence, subtask dependency chains, a task recurrence engine, JSON/CSV import/export, and productivity analytics.

---

## 🌟 Visual Architecture & Diagrams

### 1. Clean Layered Architecture Overview

```mermaid
graph TD
    subgraph Presentation ["🎨 Presentation Layer (CLI / REPL Shell)"]
        UI[Rich CLI Viewer & REPL Shell]
        ArgParser[Argparse CLI Commands]
    end

    subgraph Service ["⚙️ Application / Service Layer"]
        TaskService[TaskService Coordinator]
        RecurrenceEngine[Recurrence Engine]
        AnalyticsEngine[Analytics & Velocity Engine]
        ImportExport[JSON / CSV Serializer]
        SearchEngine[Fuzzy Search Engine]
    end

    subgraph Command ["↩️ Command Pattern Layer (Undo / Redo)"]
        CmdMgr[CommandManager Stack]
        CmdAdd[AddTaskCommand]
        CmdComp[CompleteTaskCommand]
        CmdDel[DeleteTaskCommand]
        CmdPurge[PurgeTaskCommand]
    end

    subgraph Persistence ["💾 Persistence Layer (Repository Pattern)"]
        IRepo[ITaskRepository Interface]
        SQLRepo[SQLAlchemyTaskRepository]
        DB[(SQLite Database - todolist.db)]
    end

    subgraph Domain ["📦 Domain Layer (Core Entities & Enums)"]
        TaskEntity[Task Entity Dataclass]
        PriorityEnum[Priority Enum]
        RecurrenceEnum[RecurrenceRule Enum]
    end

    UI --> TaskService
    ArgParser --> TaskService
    TaskService --> CmdMgr
    CmdMgr --> CmdAdd
    CmdMgr --> CmdComp
    CmdMgr --> CmdDel
    CmdMgr --> CmdPurge
    CmdAdd --> IRepo
    CmdComp --> IRepo
    CmdDel --> IRepo
    CmdPurge --> IRepo
    SQLRepo -- Implements --> IRepo
    SQLRepo --> DB
    TaskService --> RecurrenceEngine
    TaskService --> AnalyticsEngine
    TaskService --> SearchEngine
    TaskService --> ImportExport
    SQLRepo --> TaskEntity
    TaskEntity --> PriorityEnum
    TaskEntity --> RecurrenceEnum
```

---

### 2. Command Pattern Undo / Redo Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant REPL as 🖥️ Rich CLI / REPL
    participant Service as ⚙️ TaskService
    participant CmdMgr as ↩️ CommandManager
    participant Cmd as 📦 CompleteTaskCommand
    participant Repo as 💾 TaskRepository
    participant DB as 🗄️ SQLite DB

    User->>REPL: Complete Task #1
    REPL->>Service: complete_task(task_id=1)
    Service->>Cmd: execute()
    Cmd->>Repo: update(is_completed=True)
    Repo->>DB: SQL UPDATE tasks SET is_completed=1
    CmdMgr-->>Service: Push command to Undo Stack
    Service-->>REPL: Task #1 Completed!
    
    User->>REPL: Undo Action
    REPL->>Service: undo()
    Service->>CmdMgr: undo()
    CmdMgr->>Cmd: undo()
    Cmd->>Repo: update(previous_snapshot)
    Repo->>DB: SQL UPDATE tasks SET is_completed=0
    CmdMgr-->>Service: Move command to Redo Stack
    Service-->>REPL: Undid action: Complete Task #1
```

---

### 3. Task Recurrence Engine Flowchart

```mermaid
flowchart LR
    A[Task Marked Complete] --> B{Recurrence Configured?}
    B -- No --> C[Task Completed Finished]
    B -- Daily --> D[Calculate Base Date + 1*Interval Days]
    B -- Weekly --> E[Calculate Base Date + 7*Interval Days]
    B -- Monthly --> F[Calculate Base Date + 30*Interval Days]
    D --> G[Auto-Generate Next Task Instance]
    E --> G
    F --> G
    G --> H[Save New Task to Repository]
```

---

## 🎨 Rich Terminal UI Mockups

### Active Task Table View
```text
                                  To-Do List                                   
┌────┬────────┬─────────────────────────────┬──────────┬───────────┬──────────────┬────────────┬────────────┐
│ ID │ Status │ Title                       │ Priority │ Category  │ Tags         │  Due Date  │ Recurrence │
├────┼────────┼─────────────────────────────┼──────────┼───────────┼──────────────┼────────────┼────────────┤
│ 1  │  [v]   │ Finalize Q3 Financial Plan  │  URGENT  │ Work      │ report, q3   │ 2026-08-10 │ weekly (1) │
│ 2  │  [x]   │ Buy Office Supplies         │  MEDIUM  │ Personal  │ shopping     │ 2026-08-12 │    -       │
│ 3  │  [x]   │ Daily Standup Meeting       │   HIGH   │ Work      │ agile, team  │ 2026-08-07 │ daily (1)  │
└────┴────────┴─────────────────────────────┴──────────┴───────────┴──────────────┴────────────┴────────────┘
```

### Subtask & Dependency Tree View
```text
Task #1: Finalize Q3 Financial Plan [URGENT]
├── [v] #4: Gather Expenses Sub-report [HIGH]
├── [x] #5: Audit Revenue Numbers [URGENT]
└── [x] #6: Draft Executive Summary [MEDIUM] (Blocked by #5)
```

### Productivity Dashboard & Analytics
```text
┌───────────────────────────── Productivity Dashboard ─────────────────────────────┐
│ Total Tasks: 12                                                                 │
│ Completed: 8                                                                    │
│ Pending: 4                                                                      │
│ Overdue: 1                                                                      │
│ Due Today: 2                                                                    │
│ Velocity (7 Days): 6 tasks completed                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
Completion Rate [============================================        ] 66.7%
```

---

## ⚡ Feature Matrix

| Feature | Description | Technical Implementation |
| :--- | :--- | :--- |
| **Clean Architecture** | Decoupled presentation, domain, service, and data layers | SOLID principles & Repository Pattern |
| **Command Pattern (Undo/Redo)** | Full undo and redo capabilities for all task operations | `ICommand` ABC with `CommandManager` stack |
| **SQLAlchemy Persistence** | Robust SQLite database storage with auto-schema creation | SQLAlchemy 2.0 ORM + `TaskModel` mapping |
| **Dependency Chain Control** | Blocks task completion if prerequisite tasks remain incomplete | Foreign ID list verification in `TaskService` |
| **Recurrence Engine** | Auto-schedules next task instance upon completing repeating task | `RecurrenceEngine` date math (Daily, Weekly, Monthly) |
| **Categorization & Multi-Tagging**| Color-coded priorities (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), categories, & tags | Python dataclass + JSON serialized set fields |
| **Fuzzy Title Search** | Intelligent text searching with ratio threshold matching | `difflib.SequenceMatcher` |
| **Import / Export** | Complete database import & export capabilities | Standard JSON & CSV handlers with validation |
| **Productivity Analytics** | Real-time stats, 7-day velocity, overdue alerts, completion rate | `AnalyticsEngine` + Rich visual Progress bar |
| **Rich Terminal REPL & CLI** | Colorful tables, status icons, subtask trees, and interactive shell | `rich` library console components & `argparse` |
| **Automated Testing** | Comprehensive unit & integration tests | `pytest` runner integrated in `ToDoList.py` |

---

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.10+** installed on your system.

### Install Dependencies
```bash
pip install rich sqlalchemy pytest
```

---

## 📖 Command Reference

### Direct CLI Commands

```bash
# 1. Add a new task
python ToDoList.py add "Buy Groceries" --priority HIGH --category Personal --tags shopping,food --due 2026-08-10 --recurrence weekly

# 2. List all tasks (with optional category or tag filtering)
python ToDoList.py list
python ToDoList.py list --category Work
python ToDoList.py list --tag shopping

# 3. Complete a task by ID
python ToDoList.py complete 1

# 4. Soft-delete a task
python ToDoList.py delete 2

# 5. Search tasks using fuzzy matching
python ToDoList.py search "Groceries"

# 6. Display productivity analytics & completion rate
python ToDoList.py analytics

# 7. Export task database to JSON or CSV
python ToDoList.py export --format json --output my_tasks.json
python ToDoList.py export --format csv --output my_tasks.csv

# 8. Import tasks from JSON or CSV file
python ToDoList.py import --format json --input my_tasks.json

# 9. Run automated unit test suite
python ToDoList.py test
```

### Interactive REPL Shell Mode

Launch the full interactive shell mode:
```bash
python ToDoList.py shell
```

**Interactive Menu Options:**
- `[1] List Tasks` - Render colorized table of active tasks
- `[2] Add Task` - Interactive wizard for task parameters
- `[3] Complete Task` - Mark done and auto-trigger recurrence
- `[4] Delete Task` - Soft-delete task
- `[5] Search Tasks` - Instant fuzzy title search
- `[6] Analytics` - Display productivity dashboard & progress meters
- `[7] Export Data` - Export to JSON or CSV
- `[8] Import Data` - Load external JSON or CSV task files
- `[9] Undo Action` - Undo last command in stack
- `[10] Redo Action` - Redo previously undone action
- `[0] Exit` - Close shell session

---

## 🧪 Automated Testing

To execute the embedded pytest test suite:
```bash
python -m pytest ToDoList.py -v
```

**Test Suite Coverage:**
- `test_task_domain_entity`: Domain entity calculations and overdue logic
- `test_repository_crud`: SQLAlchemy repository CRUD, update, and soft-delete
- `test_command_pattern_undo_redo`: Command Pattern undo and redo stack behavior
- `test_dependency_blocking`: Dependency blocking rules
- `test_recurrence_engine`: Recurrence date generation engine
- `test_json_import_export`: JSON serialization and import/export integrity

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for details.
