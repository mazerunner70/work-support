# Work Support Python Server

A data harvesting and API service that integrates with GitHub and Jira to collect and store team member activity data. The server runs scheduled data collection every 2 hours and provides REST API endpoints to access the harvested information.

## Features

- **Scheduled Data Harvesting**: Automatically collects issue data from GitHub and Jira every 2 hours
- **Team Member Management**: Configurable team member profiles with Jira and GitHub IDs
- **Persistent Storage**: SQLite database that survives server restarts
- **REST API**: Simple API endpoints to access harvested data
- **Label-based Filtering**: Harvest issues matching specific labels
- **Multi-source Integration**: Support for both GitHub and Jira APIs

## Quick Start

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token
- Jira API Token
- Team member information (names, Jira IDs, GitHub IDs)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd work-support
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the application:
   - Copy `config/team_members.properties.example` to `config/team_members.properties`
   - Update the properties file with your team members and API credentials

5. Initialize the database:
```bash
alembic upgrade head
```

6. Start the server:
```bash
uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`

## Configuration

### Team Members Properties File

Edit `config/team_members.properties` to configure your team:

```properties
# Team Members Configuration
team.member.john.doe.name=John Doe
team.member.john.doe.jira_id=john.doe@company.com
team.member.john.doe.github_id=john-doe

# Jira Configuration
jira.base_url=https://company.atlassian.net
jira.api_token=your_jira_api_token
jira.email=your_email@company.com
jira.issue_label=work-support

# GitHub Configuration
github.api_token=your_github_personal_access_token
github.issue_label=work-support
```

### Environment Variables

You can also use environment variables for sensitive configuration:

```bash
export JIRA_API_TOKEN=your_token
export GITHUB_API_TOKEN=your_token
export JIRA_EMAIL=your_email@company.com
```

## API Endpoints

### Get Issue Keys

Retrieve a list of issue keys from harvested data.

```
GET /api/issues/keys
```

**Query Parameters:**
- `source` (optional): Filter by 'jira' or 'github'
- `assignee` (optional): Filter by team member name
- `label` (optional): Filter by specific label

**Response:**
```json
{
  "issue_keys": ["PROJ-123", "PROJ-456", "repo#789"],
  "total_count": 3,
  "harvested_at": "2024-01-15T10:30:00Z"
}
```

### Health Check

Check the health status of the service.

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "last_harvest": "2024-01-15T10:30:00Z"
}
```

## Data Harvesting

The server automatically harvests data every 2 hours. The harvesting process:

1. Reads team member configuration
2. Queries Jira for issues with the specified label assigned to each team member
3. Queries GitHub for issues with the specified label assigned to each team member
4. Stores/updates the data in the SQLite database
5. Logs the harvest job status

### Manual Harvest Trigger

You can manually trigger a harvest job:

```
POST /api/harvest/trigger
```

## Database

The application uses SQLite for data storage. The database file is located at `./data/work_support.db` by default.

### Database Schema

- **team_members**: Team member information
- **issues**: Harvested issue data
- **harvest_jobs**: Harvest job execution history

### Backup

Database backups are automatically created every 24 hours (configurable) and stored in `./data/backups/`.

## Development

### Project Structure

```
work-support/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config/                 # Configuration management
│   ├── models/                 # Database models
│   ├── services/               # Business logic
│   ├── api/                    # API endpoints
│   └── utils/                  # Utility functions
├── migrations/                 # Database migrations
├── tests/                      # Test suite
├── config/                     # Configuration files
└── data/                       # Database and backups
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
isort .
```

### Type Checking

```bash
mypy app/
```

## Deployment

### Docker

Build and run with Docker:

```bash
docker build -t work-support .
docker run -p 8000:8000 work-support
```

### Production

For production deployment:

1. Use environment variables for sensitive configuration
2. Set up proper logging
3. Configure database backups
4. Use a process manager (systemd, supervisor, etc.)
5. Set up monitoring and alerting

## Security Considerations

- Store API keys securely (environment variables or secure vault)
- Never commit API keys to version control
- Implement proper access controls for the API
- Regular security updates for dependencies
- Monitor API usage and implement rate limiting

## Troubleshooting

### Common Issues

1. **API Authentication Errors**: Verify your API tokens are correct and have the necessary permissions
2. **Database Errors**: Ensure the database directory exists and is writable
3. **Harvesting Failures**: Check the logs for specific error messages
4. **Rate Limiting**: The application respects API rate limits, but you may need to adjust harvesting frequency

### Logs

Logs are written to stdout/stderr and can be configured for file output in production.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.