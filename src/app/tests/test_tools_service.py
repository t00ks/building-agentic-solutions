from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from services.session_context import CURRENT_MCP_SESSION
from services.tools_service import ToolsService


class TestToolsService:

  @pytest.fixture(autouse=True)
  def mock_get_config(self):
    with patch("core.config.get_config") as mock:
      mock.return_value = {
        "mcp": {
          "base_url": "https://test-mcp-url.com",
          "api_key": "test-api-key"
        }
      }
      yield mock

  @pytest.fixture
  def tools_service(self):
    return ToolsService()

  @pytest.mark.asyncio
  async def test_wrap_mcp_tool_with_valid_schema(self, tools_service):
    # Arrange
    mock_tool = MagicMock(spec=BaseTool)
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.args_schema = {
      "properties": {"param1": {"type": "string"}},
      "required": ["param1"]
    }

    lead_id = "test_lead_123"

    # Act
    wrapped_tool = tools_service.wrap_mcp_tool(mock_tool, lead_id)

    # Assert
    assert wrapped_tool.name == "test_tool"
    assert wrapped_tool.description == "A test tool"
    assert wrapped_tool.args_schema == mock_tool.args_schema

  @pytest.mark.asyncio
  async def test_wrap_mcp_tool_removes_lead_id_from_args_schema(self, tools_service):
    # Arrange
    mock_tool = MagicMock(spec=BaseTool)
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.args_schema = {
      "properties": {"param1": {"type": "string"}, "leadId": {"type": "string"}},
      "required": ["param1", "leadId"]
    }

    lead_id = "test_lead_123"

    # Act
    wrapped_tool = tools_service.wrap_mcp_tool(mock_tool, lead_id)

    # Assert
    assert "leadId" not in wrapped_tool.args_schema["properties"]
    assert "leadId" not in wrapped_tool.args_schema["required"]

  @pytest.mark.asyncio
  async def test_wrap_mcp_tool_adds_lead_id_to_kwargs(self, tools_service):
      # Arrange
      mock_tool = MagicMock(spec=BaseTool)
      mock_tool.name = "test_tool"
      mock_tool.description = "A test tool"
      mock_tool.args_schema = {
          "properties": {"param1": {"type": "string"}, "leadId": {"type": "string"}},
          "required": ["param1", "leadId"]
      }

      lead_id = "test_lead_123"
      mock_session = AsyncMock()
      mock_result = MagicMock()
      mock_result.content = [MagicMock(text="Test result")]
      mock_session.call_tool.return_value = mock_result

      # Act
      wrapped_tool = tools_service.wrap_mcp_tool(mock_tool, lead_id)


      # Mock the context for execution
      CURRENT_MCP_SESSION.set(mock_session)

      mock_arun_args = {"param1": "test_value"}
      await wrapped_tool.arun(mock_arun_args)

      # Assert
      mock_session.call_tool.assert_called_once_with("test_tool", {"param1": "test_value", "leadId": lead_id})
