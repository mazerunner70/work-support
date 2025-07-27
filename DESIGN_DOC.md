# Work Support Python Server - Design Document

## Overview

The Work Support Python Server is a data harvesting and API service that integrates with GitHub and Jira to collect and store team member activity data. The server runs scheduled data collection every 2 hours and provides REST API endpoints to access the harvested information.

## Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub API    │    │   Jira API      │    │   SQLite DB     │
│   (Issues)      │    │   (Issues)      │    │   (Local)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Python Server  │
                    │  (FastAPI)      │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │  REST API       │
                    │  Endpoints      │
                    └─────────────────┘
```

## Core Components

### 1. Configuration Management
- **Properties File**: `config/team_members.properties`
  - Maps team member names to their Jira and GitHub IDs
  - Configurable Jira labels for issue filtering
  - API keys and endpoints configuration

### 2. Data Models
- **Team Member**: Name, Jira ID, GitHub ID
- **Issue**: Key, summary, assignee, status, labels, issue_type, parent_key, created/updated dates
- **Issue Type**: ID, name, URL, child type IDs for hierarchical relationships
- **Harvest Job**: Timestamp, status, records processed

### 3. Database Schema (SQLite)
```sql
-- Team members table
CREATE TABLE team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    jira_id TEXT NOT NULL,
    github_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Issue types table
CREATE TABLE issue_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT,
    child_type_ids TEXT, -- JSON array of child type IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Issues table
CREATE TABLE issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_key TEXT NOT NULL UNIQUE,
    summary TEXT,
    assignee TEXT,
    status TEXT,
    labels TEXT, -- JSON array
    issue_type_id INTEGER,
    parent_key TEXT, -- Reference to parent issue key
    source TEXT NOT NULL, -- 'jira' or 'github'
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    harvested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_type_id) REFERENCES issue_types(id)
);

-- Harvest jobs table
CREATE TABLE harvest_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT, -- 'running', 'completed', 'failed'
    records_processed INTEGER DEFAULT 0,
    error_message TEXT
);

-- Data reload tracking table
CREATE TABLE reload_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reload_started TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
    completed_at TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    error_message TEXT,
    source TEXT DEFAULT 'manual', -- 'manual', 'automatic', 'scheduled'
    triggered_by TEXT, -- user info for manual reloads, 'system' for others
    issues_deleted INTEGER DEFAULT 0, -- count of old issues deleted
    duration_seconds INTEGER -- total duration in seconds
);
```

## API Integration

### GitHub API Integration
- **Authentication**: Personal Access Token
- **Endpoints Used**:
  - `GET /search/issues` - Search issues by assignee and labels
- **Rate Limiting**: Respect GitHub's rate limits (5000 requests/hour for authenticated users)

### Jira API Integration
- **Authentication**: API Token + Email
- **Endpoints Used**:
  - `GET /rest/api/3/search` - Search issues by JQL query
- **Rate Limiting**: Respect Jira's rate limits
- **Hierarchical Issue Types**: Support for parent-child issue type relationships

## Data Harvesting Process

### Scheduled Harvesting
- **Frequency**: Every 2 hours
- **Process**:
  1. Read team member configuration and issue type hierarchy
  2. For Jira harvesting:
     - Start with Product Version issues: `project in (IAIPORT, AIPRDV, AIMP, IACU) AND type = "Product Version" AND labels = SE_product_family`
     - For each Product Version found, query child issue types (Feature, Customer Adoption)
     - For each Feature/Customer Adoption, query their child issue types (Story, Task)
     - Continue hierarchical traversal using childTypeIds until leaf nodes
  3. For GitHub harvesting:
     - Query GitHub for issues with specified label assigned to each team member
  4. Store/update issues in SQLite database with parent-child relationships
  5. Log harvest job status

### Full Data Reload Process
- **Trigger**: Manual via API endpoint or scheduled maintenance
- **Process**:
  1. Check if reload is already running (prevent concurrent reloads)
  2. Create reload tracking record with `reload_started` timestamp
  3. Perform complete data harvesting (same as scheduled process)
  4. Track progress in reload tracking table
  5. Upon completion, execute cleanup transaction:
     - Delete all issues where `harvested_at < reload_started`
     - Delete reload tracking record
  6. If any step fails, mark reload as failed and preserve existing data

### Server Startup Recovery Process
- **Trigger**: Automatic on server startup
- **Process**:
  1. Check for orphaned reload tracking records (status = 'running')
  2. If found, perform recovery cleanup:
     - Delete all issues harvested during the interrupted reload (`harvested_at >= reload_started`)
     - Mark the interrupted reload as 'failed' with appropriate error message
     - Log recovery action with details
  3. Check if automatic reload is needed:
     - Look for most recent completed/failed reload
     - If none exist, or timestamp is older than reload interval, trigger new reload
     - Log automatic reload initiation
  4. Continue with normal server startup
  5. If recovery was performed, log warning about interrupted reload

### Data Persistence
- **Database**: SQLite (file-based, survives server restarts)
- **Backup Strategy**: Regular database file backups
- **Data Retention**: Configurable retention period for old issues

### Data Reload Management
The system implements a reload tracking mechanism to manage complete data refreshes:

1. **Reload Initiation**: When a full data reload is triggered:
   - Insert a new row in `reload_tracking` table with `reload_started` timestamp
   - Set status to 'running'

2. **Data Collection**: During the reload process:
   - Harvest all data as normal, updating `harvested_at` timestamps
   - Track progress in `reload_tracking.records_processed`

3. **Cleanup Transaction**: After all data is collected:
   - Begin a database transaction
   - Delete all issues where `harvested_at < reload_started`
   - Update `reload_tracking` status to 'completed'
   - Set `completed_at` timestamp and `records_processed`
   - Commit the transaction

4. **Error Handling**: If reload fails:
   - Update `reload_tracking` status to 'failed'
   - Set `completed_at` timestamp
   - Log error message
   - Old data remains intact
   - Reload record is preserved for audit trail

5. **Server Shutdown Recovery**: On server startup:
   - Check for any `reload_tracking` records with status 'running'
   - If found, this indicates an interrupted reload
   - Automatically clean up any partial data: delete issues where `harvested_at >= reload_started`
   - Mark the interrupted reload as 'failed' with appropriate error message
   - Log recovery action for audit purposes

6. **Automatic Reload Triggering**: On server startup:
   - Check the timestamp of the most recent completed/failed reload
   - If no reload records exist, or the most recent is older than the reload interval, automatically trigger a new reload
   - Uses the same reload interval configuration as scheduled harvesting
   - Ensures data is always reasonably fresh on server restart

7. **Enhanced Logging & Metrics**: Comprehensive reload tracking with:
   - **Duration tracking**: Start/end times and total duration in seconds
   - **Progress statistics**: Records processed, old issues deleted
   - **Source identification**: 'manual', 'automatic', or 'scheduled'
   - **User context**: Who triggered manual reloads, 'system' for automated
   - **Structured logging**: Emoji-coded log levels for easy scanning
   - **Performance metrics**: Time since last reload, next reload schedule

8. **Audit Trail**: All reload attempts are preserved:
   - Successful reloads: status='completed' with completion timestamp
   - Failed reloads: status='failed' with error details
   - Interrupted reloads: status='failed' after recovery cleanup
   - Automatic startup reloads: logged and tracked like manual reloads

### Hierarchical JQL Query Algorithm
The system implements a recursive algorithm to harvest issues based on the issue type hierarchy:

1. **Initial Query**: Start with Product Version issues
   ```jql
   project in (IAIPORT, AIPRDV, AIMP, IACU) AND type = "Product Version" AND labels = SE_product_family
   ```

2. **Recursive Traversal**: For each issue found at each level:
   - Store the issue in the database with its issue type and parent reference
   - Query for child issues using the parent issue key and child issue types
   - Continue until reaching leaf nodes (issues with no child types)

3. **Query Pattern**: For each level, construct JQL queries like:
   ```jql
   parent = "PV-123" AND type IN ("Feature", "Customer Adoption")
   parent = "FEAT-456" AND type IN ("Story", "Task")
   ```

4. **Error Handling**: Handle unknown issue types by mapping them to the "Error-Type Not Known" category

## API Endpoints

### 1. Get Issue Keys
```
GET /api/issues/keys
```

**Response**:
```json
{
  "issue_keys": ["PROJ-123", "PROJ-456", "repo#789"],
  "total_count": 3,
  "harvested_at": "2024-01-15T10:30:00Z"
}
```

**Query Parameters**:
- `source` (optional): Filter by 'jira' or 'github'
- `assignee` (optional): Filter by team member name
- `label` (optional): Filter by specific label
- `issue_type` (optional): Filter by issue type name
- `parent_key` (optional): Filter by parent issue key

### 2. Get Issue Hierarchy
```
GET /api/issues/hierarchy
```

**Response**:
```json
{
  "hierarchy": [
    {
      "issue_key": "PV-123",
      "summary": "Product Version 1.0",
      "issue_type": "Product Version",
      "children": [
        {
          "issue_key": "FEAT-456",
          "summary": "Feature A",
          "issue_type": "Feature",
          "children": [
            {
              "issue_key": "STORY-789",
              "summary": "User Story 1",
              "issue_type": "Story",
              "children": []
            }
          ]
        }
      ]
    }
  ],
  "total_count": 1,
  "harvested_at": "2024-01-15T10:30:00Z"
}
```

**Query Parameters**:
- `root_type` (optional): Filter by root issue type (default: "Product Version")
- `max_depth` (optional): Maximum depth to traverse (default: 5)

### 3. Trigger Full Data Reload
```
POST /api/harvest/reload
```

**Response**:
```json
{
  "reload_id": 123,
  "reload_started": "2024-01-15T10:30:00Z",
  "status": "running"
}
```

**Query Parameters**:
- `force` (optional): Force reload even if one is already running

### 4. Get Reload Status
```
GET /api/harvest/reload/{reload_id}
```

**Response**:
```json
{
  "reload_id": 123,
  "reload_started": "2024-01-15T10:30:00Z",
  "status": "completed",
  "completed_at": "2024-01-15T11:30:00Z",
  "records_processed": 1500
}
```

### 5. Get Reload History
```
GET /api/harvest/reload
```

**Response**:
```json
[
  {
    "reload_id": 123,
    "reload_started": "2024-01-15T10:30:00Z",
    "status": "completed",
    "completed_at": "2024-01-15T11:30:00Z",
    "records_processed": 1500
  },
  {
    "reload_id": 122,
    "reload_started": "2024-01-14T08:15:00Z",
    "status": "failed",
    "completed_at": "2024-01-14T08:20:00Z",
    "records_processed": 0
  }
]
```

**Query Parameters**:
- `limit` (optional): Maximum number of records to return (default: 10, max: 100)
- `status` (optional): Filter by status: 'running', 'completed', 'failed'

## Configuration

### Issue Type Hierarchy
The system uses a predefined hierarchy of Jira issue types to enable hierarchical data harvesting:

```typescript
export const ISSUE_TYPES: IssueType[] = [
  {
    id: 10004,
    name: 'Product Version',
    url: 'https://iagtech.atlassian.net/rest/api/2/universal_avatar/view/type/issuetype/avatar/10664?size=medium',
    childTypeIds: [10000, 11140] // Feature and Customer Adoption
  },
  {
    id: 10000,
    name: 'Feature', 
    url: 'https://iagtech.atlassian.net/images/icons/issuetypes/epic.svg',
    childTypeIds: [10101, 10104] // Story and Task
  },
  {
    id: 11140,
    name: 'Customer Adoption',
    url: 'https://iagtech.atlassian.net/rest/api/2/universal_avatar/view/type/issuetype/avatar/10321?size=medium', 
    childTypeIds: [10101] // Story
  },
  {
    id: 10101,
    name: 'Story',
    url: 'https://iagtech.atlassian.net/images/icons/issuetypes/story.svg',
    childTypeIds: [] // No children
  },  
  {
    id: 10104,
    name: 'Task',
    url: 'https://iagtech.atlassian.net/rest/api/2/universal_avatar/view/type/issuetype/avatar/10318?size=medium',
    childTypeIds: [] // No children
  },
  {
    id: -1,
    name: 'Error-Type Not Known',
    url: 'https://iagtech.atlassian.net/images/icons/issuetypes/story.svg',
    childTypeIds: [] // No children
  }
];
```

### Properties File Structure (`config/team_members.properties`)
```properties
# Team Members Configuration
team.member.john.doe.name=John Doe
team.member.john.doe.jira_id=john.doe@company.com
team.member.john.doe.github_id=john-doe

team.member.jane.smith.name=Jane Smith
team.member.jane.smith.jira_id=jane.smith@company.com
team.member.jane.smith.github_id=jane-smith

# Jira Configuration
jira.base_url=https://company.atlassian.net
jira.api_token=your_jira_api_token
jira.email=your_email@company.com
jira.issue_label=work-support

# GitHub Configuration
github.api_token=your_github_personal_access_token
github.issue_label=work-support

# Harvesting Configuration
harvest.interval_hours=2
harvest.retention_days=90
```

## Technology Stack

### Core Framework
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and ORM
- **Pydantic**: Data validation using Python type annotations

### Scheduling
- **APScheduler**: Advanced Python Scheduler for background jobs

### HTTP Client
- **httpx**: Modern HTTP client for Python
- **aiohttp**: Async HTTP client/server framework

### Database
- **SQLite**: Lightweight, file-based database
- **Alembic**: Database migration tool

## Project Structure
```
work-support/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # Configuration management
│   │   ├── issue_types.py      # Issue type hierarchy configuration
│   │   └── team_members.properties
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # Database models
│   │   └── schemas.py          # Pydantic schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── github_service.py   # GitHub API integration
│   │   ├── jira/              # Modular Jira API integration
│   │   │   ├── service.py     # Main service orchestrator
│   │   │   ├── client.py      # HTTP client & authentication
│   │   │   ├── parsers.py     # Data parsing & transformation
│   │   │   └── operations/    # Specialized operations
│   │   │       ├── search.py  # Search operations
│   │   │       ├── changelog.py # Changelog operations
│   │   │       └── metadata.py # Connection & metadata
│   │   ├── harvest_service.py  # Data harvesting logic
│   │   └── hierarchy_service.py # Hierarchical issue traversal
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API endpoints
│   │   └── dependencies.py     # API dependencies
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py          # Utility functions
│       └── jql_builder.py      # JQL query construction utilities
├── migrations/                 # Database migrations
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

## Security Considerations

### API Key Management
- Store API keys in environment variables or secure configuration
- Never commit API keys to version control
- Use different API keys for different environments

### Rate Limiting
- Implement rate limiting for API endpoints
- Respect external API rate limits
- Add exponential backoff for failed requests

### Data Privacy
- Ensure harvested data complies with company policies
- Implement data retention policies
- Log access to sensitive data

## Monitoring and Logging

### Logging Strategy
- Structured logging with different levels (DEBUG, INFO, WARNING, ERROR)
- Log harvest job status and performance metrics
- Log API request/response for debugging

### Health Checks
- Database connectivity check
- External API connectivity check
- Harvest job status monitoring
- Reload tracking status check (detect orphaned reloads)

## Deployment

### Development
- Local SQLite database
- Environment-based configuration
- Hot reload for development

### Production
- Environment-specific configuration
- Database backup strategy
- Process monitoring and restart capabilities
- Systemd service configuration for automatic startup

## Future Enhancements

### Phase 2 Features
- Additional API endpoints for detailed issue information
- Team member activity dashboards
- Issue trend analysis
- Slack/Teams integration for notifications
- Webhook support for real-time updates

### Phase 3 Features
- Multi-team support
- Advanced filtering and search
- Data visualization
- Export capabilities
- Integration with additional tools (Confluence, etc.)

## Implementation Timeline

### Week 1
- Set up project structure and dependencies
- Implement configuration management and issue type hierarchy
- Create database models and migrations with parent-child relationships
- Implement server startup recovery mechanism

### Week 2
- Implement GitHub and Jira API integrations
- Create hierarchical JQL query builder and traversal service
- Implement recursive data harvesting algorithm

### Week 3
- Implement REST API endpoints including hierarchy endpoint
- Add error handling and logging for hierarchical queries
- Create tests for issue type hierarchy and JQL queries

### Week 4
- Integration testing with real Jira data
- Performance optimization for deep hierarchies
- Documentation and deployment setup

## Success Metrics

- **Data Accuracy**: 99%+ accuracy in harvested data
- **Performance**: API response time < 200ms
- **Reliability**: 99.9% uptime for harvesting jobs
- **Scalability**: Support for 50+ team members
- **Maintainability**: Comprehensive test coverage (>80%) 