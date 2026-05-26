# Architecture Overview

## System Overview

```mermaid
graph TB
    Client["Browser Client<br/>(React)"]
    Frontend["Frontend<br/>(React SPA)"]
    API["REST API<br/>(FastAPI)"]
    DB["Database<br/>(PostgreSQL)"]
    Scheduler["Scheduler<br/>(APScheduler)"]
    
    Client -->|HTTP| Frontend
    Frontend -->|HTTP/REST| API
    API -->|SQL| DB
    Scheduler -->|Async Tasks| API
    API -->|Update| DB
```

## Frontend Architecture

```mermaid
graph TB
    App["App.jsx<br/>(auth context)"]
    
    Pages["Pages/"]
    Dashboard["Dashboard.jsx"]
    Chores["Chores.jsx"]
    UserDetail["UserDetail.jsx"]
    Settings["Settings.jsx"]
    
    Components["Components/"]
    UserCard["UserCard.jsx"]
    ChoreList["ChoreList.jsx"]
    ChoreForm["ChoreForm.jsx"]
    ThemeSettings["ThemeSettings.jsx"]
    Log["Log.jsx"]
    
    Utils["Utils/"]
    Auth["auth.ts"]
    Theme["theme.ts"]
    PersonColors["personColors.ts"]
    
    API["API Client"]
    RQ["React Query"]
    
    App --> Pages
    App --> Components
    Pages --> Dashboard
    Pages --> Chores
    Pages --> UserDetail
    Pages --> Settings
    
    Dashboard --> UserCard
    Dashboard --> ChoreList
    Chores --> ChoreForm
    Settings --> ThemeSettings
    Settings --> Log
    
    Components --> API
    Pages --> API
    API --> RQ
    RQ -->|HTTP| Backend["Backend API"]
    
    Components --> Utils
    Pages --> Utils
```

## Backend Architecture

```mermaid
graph TB
    API["FastAPI App<br/>(main.py)"]
    
    Routers["Routers/"]
    AuthRouter["auth.py"]
    ChoresRouter["chores.py"]
    PeopleRouter["people.py"]
    PointsRouter["points.py"]
    LogRouter["log.py"]
    ThemeRouter["theme.py"]
    ConfigRouter["config.py"]
    ExportRouter["export.py"]
    ImportRouter["data_import.py"]
    
    Services["Services/"]
    ChoreService["chore_service.py"]
    Scheduler["scheduler.py"]
    ExportService["export_service.py"]
    ImportService["import_service.py"]
    
    Models["Models/"]
    Person["Person"]
    Chore["Chore"]
    PointsLog["PointsLog"]
    ChoreLog["ChoreLog"]
    TokenBlacklist["TokenBlacklist"]
    Settings["Settings"]
    
    Database["PostgreSQL Database"]
    
    API --> Routers
    
    AuthRouter --> ChoreService
    ChoresRouter --> ChoreService
    ExportRouter --> ExportService
    ImportRouter --> ImportService
    Routers --> Services
    Scheduler --> ChoreService
    
    ChoreService --> Models
    ExportService --> Models
    ImportService --> Models
    Routers --> Models
    
    Models --> Database
    Scheduler -->|async| Database
```

## Data Model

```mermaid
erDiagram
    PERSON ||--o{ CHORE : assigns
    PERSON ||--o{ POINTSLOG : earns
    PERSON ||--o{ CHORELOG : acts_on
    CHORE ||--o{ POINTSLOG : awards
    CHORE ||--o{ CHORELOG : logs
    PERSON ||--o{ TOKENBLACKLIST : invalidates

    PERSON {
        int id PK
        string name UK
        string username UK
        string password_hash
        bool is_admin
        string color
        int goal_7d
        int goal_30d
        string preferred_theme
    }

    CHORE {
        int id PK
        string unique_id UK
        string name
        string schedule_type
        json schedule_config
        string assignment_type
        json eligible_people
        string assignee
        int points
        string state
        bool disabled
        date next_due
        string current_assignee
        int rotation_index
        timestamp last_changed_at
        string last_changed_by
        string last_change_type
        timestamp last_completed_at
        string last_completed_by
    }

    POINTSLOG {
        int id PK
        string person FK
        int points
        string chore_id FK
        timestamp completed_at
    }

    CHORELOG {
        int id PK
        string chore_id FK
        string chore_name
        string person FK
        string action
        timestamp timestamp
        string reassigned_to
    }

    TOKENBLACKLIST {
        int id PK
        string token_jti UK
        timestamp invalidated_at
        timestamp expires_at
    }
```

## Request/Response Flow

### Authentication

```mermaid
sequenceDiagram
    Client->>API: POST /auth/login (username, password)
    API->>Database: Query person by username
    Database-->>API: Person object
    API->>API: Hash password, compare
    API-->>Client: {access_token, user_info}
    Client->>Client: Store token in localStorage
    Note over Client: Add to Authorization header
```

### Chore Completion

```mermaid
sequenceDiagram
    Client->>API: POST /chores/{id}/complete
    API->>Database: Get chore
    API->>ChoreService: complete_chore()
    ChoreService->>Database: Add PointsLog
    ChoreService->>Database: Add ChoreLog (action=completed)
    ChoreService->>ChoreService: Calculate next_due
    ChoreService->>Database: Update chore state
    Database-->>ChoreService: Refresh chore
    ChoreService-->>API: Updated chore
    API-->>Client: ChoreOut (200)
    Client->>Client: Invalidate React Query cache
    Client->>Client: Refetch chores
```

### Automatic Schedule Transition

```mermaid
sequenceDiagram
    Scheduler->>Scheduler: Every minute, check overdue chores
    Scheduler->>Database: Query state=complete AND next_due <= today
    Database-->>Scheduler: List of chores
    Scheduler->>ChoreService: transition_overdue_chores()
    ChoreService->>Database: Add ChoreLog (action=marked_due_by_schedule)
    ChoreService->>Database: Update chore state to 'due'
    Note over ChoreService: Runs automatically, person=system
```

## Frontend Data Flow

```mermaid
graph TB
    QueryClient["React Query<br/>Client"]
    Cache["Query Cache"]
    
    Pages["Pages/Components"]
    useQuery["useQuery()"]
    useMutation["useMutation()"]
    
    API["API Client<br/>(client.js)"]
    HTTP["HTTP"]
    Backend["Backend"]
    
    Pages -->|fetch| useQuery
    useQuery -->|cache hit?| Cache
    useQuery -->|cache miss| API
    Pages -->|mutate| useMutation
    useMutation --> API
    API -->|REST| HTTP
    HTTP --> Backend
    Backend -->|response| HTTP
    HTTP --> API
    API -->|invalidate| Cache
    Cache -->|refetch| useQuery
    useQuery -->|state| Pages
```

## Authentication Flow

```mermaid
graph TB
    Setup["System Setup?"]
    Login["Login Page"]
    Auth["Auth Context"]
    Protected["Protected Pages"]
    
    Setup -->|No| Login
    Login -->|username/password| Auth
    Auth -->|validate| Backend["Backend JWT"]
    Backend -->|token| Auth
    Auth -->|store token| Storage["localStorage"]
    Auth -->|in state| Protected
    Protected -->|token in header| Backend
    Backend -->|verify| Auth
    Auth -->|invalid| Login
```
