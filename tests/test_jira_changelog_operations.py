"""
Unit tests for Jira changelog operations response parsing.
"""
import pytest
from unittest.mock import Mock, AsyncMock
import logging
from datetime import datetime

from app.services.jira.operations.changelog import JiraChangelogOperations
from app.services.jira.client import JiraClient


class TestJiraChangelogOperations:
    """Test cases for changelog operations response parsing."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock Jira client for testing."""
        client = Mock(spec=JiraClient)
        client.make_request = AsyncMock()
        client.handle_response = Mock()
        return client
    
    @pytest.fixture
    def changelog_ops(self, mock_client):
        """Changelog operations instance with mocked client."""
        return JiraChangelogOperations(mock_client)
    
    def test_process_changelog_response_success(self, changelog_ops, caplog):
        """Test successful parsing of a valid changelog response."""
        # Arrange
        valid_response = {
            "issueChangeLogs": [
                {
                    "issueId": "10100",
                    "changeHistories": [
                        {
                            "id": "10001",
                            "created": 1492070429,
                            "author": {
                                "accountId": "5b10a2844c20165700ede21g",
                                "displayName": "John Doe",
                                "emailAddress": "john.doe@example.com"
                            },
                            "items": [
                                {
                                    "field": "status",
                                    "fieldId": "status",
                                    "fieldtype": "jira",
                                    "fromString": "To Do",
                                    "toString": "In Progress"
                                }
                            ]
                        }
                    ]
                },
                {
                    "issueId": "10101", 
                    "changeHistories": [
                        {
                            "id": "10002",
                            "created": 1492071429,
                            "author": {
                                "accountId": "5b10a2844c20165700ede21g",
                                "displayName": "Jane Smith",
                                "emailAddress": "jane.smith@example.com"
                            },
                            "items": [
                                {
                                    "field": "assignee",
                                    "fieldId": "assignee",
                                    "fieldtype": "jira",
                                    "fromString": "Administrator",
                                    "toString": "Jane Smith"
                                }
                            ]
                        }
                    ]
                }
            ],
            "nextPageToken": "token123"
        }
        
        # Act
        with caplog.at_level(logging.INFO):
            result = changelog_ops._process_changelog_response(valid_response, 1, 1)
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "10001"
        assert result[0]["issueId"] == "10100"  # Added by parsing logic
        assert result[1]["id"] == "10002"
        assert result[1]["issueId"] == "10101"  # Added by parsing logic
        assert "🔍 PARSE: Found 2 changelog entries across 2 issues" in caplog.text
        assert "🔍 PARSE: Changelog entry structure:" in caplog.text
    
    def test_process_changelog_response_empty_values(self, changelog_ops, caplog):
        """Test parsing response with empty issueChangeLogs array."""
        # Arrange
        empty_response = {
            "issueChangeLogs": [],
            "nextPageToken": None
        }
        
        # Act
        with caplog.at_level(logging.INFO):
            result = changelog_ops._process_changelog_response(empty_response, 1, 1)
        
        # Assert
        assert result == []
        assert "🔍 PARSE: Found 0 changelog entries across 0 issues" in caplog.text
        assert "🔍 PARSE: No changelog entries found in response" in caplog.text
    
    def test_process_changelog_response_missing_key(self, changelog_ops, caplog):
        """Test parsing response missing the 'issueChangeLogs' key."""
        # Arrange
        invalid_response = {
            "data": [{"id": "12345"}],  # Wrong key name
            "nextPageToken": None
        }
        
        # Act
        with caplog.at_level(logging.ERROR):
            result = changelog_ops._process_changelog_response(invalid_response, 1, 1)
        
        # Assert
        assert result == []
        assert "🔍 PARSE: Response missing 'issueChangeLogs' key" in caplog.text
        assert "available keys: ['data', 'nextPageToken']" in caplog.text
    
    def test_process_changelog_response_not_list(self, changelog_ops, caplog):
        """Test parsing response where 'issueChangeLogs' is not a list."""
        # Arrange
        invalid_response = {
            "issueChangeLogs": "not a list",  # Wrong data type
            "nextPageToken": None
        }
        
        # Act
        with caplog.at_level(logging.ERROR):
            result = changelog_ops._process_changelog_response(invalid_response, 1, 1)
        
        # Assert
        assert result == []
        assert "🔍 PARSE: issueChangeLogs is not a list: <class 'str'>" in caplog.text
    
    def test_process_changelog_response_not_dict(self, changelog_ops, caplog):
        """Test parsing response that is not a dictionary."""
        # Arrange
        invalid_response = "not a dict"
        
        # Act
        with caplog.at_level(logging.ERROR):
            result = changelog_ops._process_changelog_response(invalid_response, 1, 1)
        
        # Assert
        assert result == []
        assert "🔍 PARSE: Response is not a JSON object: <class 'str'>" in caplog.text
    
    def test_process_changelog_response_none_response(self, changelog_ops, caplog):
        """Test parsing None response."""
        # Act
        with caplog.at_level(logging.ERROR):
            result = changelog_ops._process_changelog_response(None, 1, 1)
        
        # Assert
        assert result == []
        assert "🔍 PARSE: Response is not a JSON object: <class 'NoneType'>" in caplog.text
    
    @pytest.mark.asyncio
    async def test_bulk_fetch_changelogs_empty_input(self, changelog_ops):
        """Test bulk fetch with empty issue list."""
        # Act
        result = await changelog_ops.bulk_fetch_changelogs([])
        
        # Assert
        assert result == []
        # Verify no API calls were made
        changelog_ops.client.make_request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_changelogs_api_error(self, changelog_ops, caplog):
        """Test handling of API errors during chunk fetching."""
        # Arrange
        changelog_ops.client.make_request.side_effect = Exception("API Error")
        
        # Act
        with caplog.at_level(logging.ERROR):
            result = await changelog_ops._fetch_chunk_changelogs(["ISSUE-1"], 1)
        
        # Assert
        assert result == []
        assert "Error fetching changelogs for chunk 1, page 1: API Error" in caplog.text
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_changelogs_success_single_page(self, changelog_ops):
        """Test successful fetching of changelogs for a single page."""
        # Arrange
        mock_response = Mock()
        changelog_ops.client.make_request.return_value = mock_response
        
        api_response = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [
                        {"id": "12345", "created": 1492070429},
                        {"id": "12346", "created": 1492071429}
                    ]
                }
            ]
            # No nextPageToken means single page
        }
        changelog_ops.client.handle_response.return_value = api_response
        
        # Act
        result = await changelog_ops._fetch_chunk_changelogs(["ISSUE-1"], 1)
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "12345"
        assert result[0]["issueId"] == "ISSUE-1"
        assert result[1]["id"] == "12346"
        assert result[1]["issueId"] == "ISSUE-1"
        
        # Verify API call was made correctly
        changelog_ops.client.make_request.assert_called_once_with(
            method="POST",
            endpoint="changelog/bulkfetch",
            payload={
                "issueIdsOrKeys": ["ISSUE-1"],
                "maxResults": 1000
            },
            timeout=30.0
        )
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_changelogs_pagination(self, changelog_ops):
        """Test fetching changelogs with pagination."""
        # Arrange
        mock_response = Mock()
        changelog_ops.client.make_request.return_value = mock_response
        
        # First page response
        first_page_response = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [{"id": "12345", "created": 1492070429}]
                }
            ],
            "nextPageToken": "token123"
        }
        
        # Second page response (no more pages)
        second_page_response = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [{"id": "12346", "created": 1492071429}]
                }
            ]
            # No nextPageToken
        }
        
        changelog_ops.client.handle_response.side_effect = [
            first_page_response,
            second_page_response
        ]
        
        # Act
        result = await changelog_ops._fetch_chunk_changelogs(["ISSUE-1"], 1)
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "12345"
        assert result[0]["issueId"] == "ISSUE-1"
        assert result[1]["id"] == "12346"
        assert result[1]["issueId"] == "ISSUE-1"
        
        # Verify both API calls were made
        assert changelog_ops.client.make_request.call_count == 2
        
        # Check first call
        first_call = changelog_ops.client.make_request.call_args_list[0]
        assert first_call[1]["payload"]["issueIdsOrKeys"] == ["ISSUE-1"]
        assert "nextPageToken" not in first_call[1]["payload"]
        
        # Check second call includes pagination token
        second_call = changelog_ops.client.make_request.call_args_list[1]
        assert second_call[1]["payload"]["nextPageToken"] == "token123"
    
    def test_process_changelog_response_mixed_issues(self, changelog_ops, caplog):
        """Test parsing response with some issues having changeHistories and others not."""
        # Arrange
        mixed_response = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [
                        {"id": "10001", "created": 1492070429}
                    ]
                },
                {
                    "issueId": "ISSUE-2"
                    # Missing changeHistories key
                },
                {
                    "issueId": "ISSUE-3",
                    "changeHistories": []  # Empty array
                },
                {
                    "issueId": "ISSUE-4",
                    "changeHistories": [
                        {"id": "10002", "created": 1492071429}
                    ]
                }
            ]
        }
        
        # Act
        with caplog.at_level(logging.INFO):
            result = changelog_ops._process_changelog_response(mixed_response, 1, 1)
        
        # Assert
        assert len(result) == 2  # Only issues with actual changelog entries
        assert result[0]["id"] == "10001"
        assert result[0]["issueId"] == "ISSUE-1"
        assert result[1]["id"] == "10002"
        assert result[1]["issueId"] == "ISSUE-4"
        assert "🔍 PARSE: Found 2 changelog entries across 4 issues" in caplog.text
    
    def test_process_changelog_response_invalid_issue_structure(self, changelog_ops, caplog):
        """Test parsing response with invalid issue structure."""
        # Arrange
        invalid_response = {
            "issueChangeLogs": [
                "not a dict",  # Invalid structure
                {
                    "issueId": "ISSUE-2",
                    "changeHistories": [{"id": "10001", "created": 1492070429}]
                }
            ]
        }
        
        # Act
        with caplog.at_level(logging.INFO):
            result = changelog_ops._process_changelog_response(invalid_response, 1, 1)
        
        # Assert
        assert len(result) == 1  # Only valid issues processed
        assert result[0]["id"] == "10001"
        assert result[0]["issueId"] == "ISSUE-2"
        assert "🔍 PARSE: Found 1 changelog entries across 2 issues" in caplog.text
    
    def test_process_changelog_response_timestamp_conversion(self, changelog_ops, caplog):
        """Test that Unix timestamps are correctly converted to datetime objects."""
        # Arrange
        response_with_timestamps = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [
                        {
                            "id": "10001",
                            "created": 1492070429,  # Unix timestamp in seconds
                            "author": {
                                "accountId": "5b10a2844c20165700ede21g",
                                "displayName": "John Doe"
                            },
                            "items": [
                                {
                                    "field": "status",
                                    "fromString": "To Do",
                                    "toString": "In Progress"
                                }
                            ]
                        },
                        {
                            "id": "10002", 
                            "created": 1747752719677,  # Unix timestamp in milliseconds (like in the user's example)
                            "author": {
                                "accountId": "5b10a2844c20165700ede21g",
                                "displayName": "Jane Smith"
                            },
                            "items": [
                                {
                                    "field": "assignee",
                                    "fromString": "Admin",
                                    "toString": "Jane Smith"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Act
        with caplog.at_level(logging.INFO):
            result = changelog_ops._process_changelog_response(response_with_timestamps, 1, 1)
        
        # Assert
        assert len(result) == 2
        
        # Check first changelog entry (seconds timestamp)
        assert result[0]["id"] == "10001"
        assert result[0]["issueId"] == "ISSUE-1"
        assert isinstance(result[0]["created"], datetime)
        assert result[0]["created"] == datetime.fromtimestamp(1492070429)
        
        # Check second changelog entry (milliseconds timestamp)
        assert result[1]["id"] == "10002"
        assert result[1]["issueId"] == "ISSUE-1"
        assert isinstance(result[1]["created"], datetime)
        # Should be converted from milliseconds: 1747752719677 / 1000 = 1747752719.677
        assert result[1]["created"] == datetime.fromtimestamp(1747752719.677)
    
    def test_process_changelog_response_invalid_timestamp(self, changelog_ops, caplog):
        """Test handling of invalid timestamps."""
        # Arrange
        response_with_invalid_timestamp = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [
                        {
                            "id": "10001",
                            "created": "invalid-timestamp",  # Invalid timestamp
                            "author": {"displayName": "John Doe"},
                            "items": [{"field": "status"}]
                        },
                        {
                            "id": "10002",
                            "created": 999999999999999999999,  # Extremely large timestamp that might fail
                            "author": {"displayName": "Jane Smith"},
                            "items": [{"field": "assignee"}]
                        }
                    ]
                }
            ]
        }
        
        # Act
        with caplog.at_level(logging.WARNING):
            result = changelog_ops._process_changelog_response(response_with_invalid_timestamp, 1, 1)
        
        # Assert
        assert len(result) == 2
        
        # First entry should keep original invalid value
        assert result[0]["created"] == "invalid-timestamp"
        
        # Second entry might also keep original value if conversion fails
        # (the extremely large timestamp might exceed system limits)
        assert "created" in result[1]  # Field should still exist
    
    def test_process_changelog_response_missing_timestamp(self, changelog_ops):
        """Test handling of changelog entries without created timestamp."""
        # Arrange
        response_without_timestamp = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [
                        {
                            "id": "10001",
                            # Missing "created" field
                            "author": {"displayName": "John Doe"},
                            "items": [{"field": "status"}]
                        }
                    ]
                }
            ]
        }
        
        # Act
        result = changelog_ops._process_changelog_response(response_without_timestamp, 1, 1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["id"] == "10001"
        assert result[0]["issueId"] == "ISSUE-1"
        assert "created" not in result[0]  # Field should not be added if missing
    
    def test_process_changelog_response_milliseconds_timestamp(self, changelog_ops):
        """Test specific handling of milliseconds timestamps like those from Jira."""
        # Arrange
        response_with_milliseconds = {
            "issueChangeLogs": [
                {
                    "issueId": "ISSUE-1",
                    "changeHistories": [
                        {
                            "id": "10001",
                            "created": 1747752719677,  # The exact timestamp from the user's error
                            "author": {"displayName": "Test User"},
                            "items": [{"field": "status"}]
                        }
                    ]
                }
            ]
        }
        
        # Act
        result = changelog_ops._process_changelog_response(response_with_milliseconds, 1, 1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["id"] == "10001"
        assert isinstance(result[0]["created"], datetime)
        
        # Verify the timestamp was correctly converted from milliseconds
        expected_datetime = datetime.fromtimestamp(1747752719.677)
        assert result[0]["created"] == expected_datetime
        
        # Verify it's a reasonable date (should be in 2025)
        assert result[0]["created"].year == 2025 