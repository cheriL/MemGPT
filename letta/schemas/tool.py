from typing import Dict, List, Optional

from pydantic import Field

from letta.functions.helpers import (
    generate_composio_tool_wrapper,
    generate_crewai_tool_wrapper,
    generate_langchain_tool_wrapper,
)
from letta.functions.schema_generator import generate_schema_from_args_schema
from letta.schemas.letta_base import LettaBase
from letta.schemas.openai.chat_completions import ToolCall


class BaseTool(LettaBase):
    __id_prefix__ = "tool"

    # optional fields
    description: Optional[str] = Field(None, description="The description of the tool.")
    source_type: Optional[str] = Field(None, description="The type of the source code.")
    module: Optional[str] = Field(None, description="The module of the function.")

    # optional: user_id (user-specific tools)
    user_id: Optional[str] = Field(None, description="The unique identifier of the user associated with the function.")


class Tool(BaseTool):
    """
    Representation of a tool, which is a function that can be called by the agent.

    Parameters:
        id (str): The unique identifier of the tool.
        name (str): The name of the function.
        tags (List[str]): Metadata tags.
        source_code (str): The source code of the function.
        json_schema (Dict): The JSON schema of the function.

    """

    id: str = BaseTool.generate_id_field()

    name: str = Field(..., description="The name of the function.")
    tags: List[str] = Field(..., description="Metadata tags.")

    # code
    source_code: str = Field(..., description="The source code of the function.")
    json_schema: Dict = Field(default_factory=dict, description="The JSON schema of the function.")

    def to_dict(self):
        """
        Convert tool into OpenAI representation.
        """
        return vars(
            ToolCall(
                tool_id=self.id,
                tool_call_type="function",
                function=self.module,
            )
        )

    @classmethod
    def get_composio_tool(
        cls,
        action: "ActionType",
    ) -> "Tool":
        """
        Class method to create an instance of Letta-compatible Composio Tool.
        Check https://docs.composio.dev/introduction/intro/overview to look at options for get_composio_tool

        This function will error if we find more than one tool, or 0 tools.

        Args:
            action ActionType: A action name to filter tools by.
        Returns:
            Tool: A Letta Tool initialized with attributes derived from the Composio tool.
        """
        from composio_langchain import ComposioToolSet

        composio_toolset = ComposioToolSet()
        composio_tools = composio_toolset.get_tools(actions=[action])

        assert len(composio_tools) > 0, "User supplied parameters do not match any Composio tools"
        assert len(composio_tools) == 1, f"User supplied parameters match too many Composio tools; {len(composio_tools)} > 1"

        composio_tool = composio_tools[0]

        description = composio_tool.description
        source_type = "python"
        tags = ["composio"]
        wrapper_func_name, wrapper_function_str = generate_composio_tool_wrapper(action)
        json_schema = generate_schema_from_args_schema(composio_tool.args_schema, name=wrapper_func_name, description=description)

        # append heartbeat (necessary for triggering another reasoning step after this tool call)
        json_schema["parameters"]["properties"]["request_heartbeat"] = {
            "type": "boolean",
            "description": "Request an immediate heartbeat after function execution. Set to `True` if you want to send a follow-up message or run a follow-up function.",
        }
        json_schema["parameters"]["required"].append("request_heartbeat")

        return cls(
            name=wrapper_func_name,
            description=description,
            source_type=source_type,
            tags=tags,
            source_code=wrapper_function_str,
            json_schema=json_schema,
        )

    @classmethod
    def from_langchain(cls, langchain_tool: "LangChainBaseTool", additional_imports_module_attr_map: dict[str, str] = None) -> "Tool":
        """
        Class method to create an instance of Tool from a Langchain tool (must be from langchain_community.tools).

        Args:
            langchain_tool (LangChainBaseTool): An instance of a LangChain BaseTool (BaseTool from LangChain)
            additional_imports_module_attr_map (dict[str, str]): A mapping of module names to attribute name. This is used internally to import all the required classes for the langchain tool. For example, you would pass in `{"langchain_community.utilities": "WikipediaAPIWrapper"}` for `from langchain_community.tools import WikipediaQueryRun`. NOTE: You do NOT need to specify the tool import here, that is done automatically for you.

        Returns:
            Tool: A Letta Tool initialized with attributes derived from the provided LangChain BaseTool object.
        """
        description = langchain_tool.description
        source_type = "python"
        tags = ["langchain"]
        # NOTE: langchain tools may come from different packages
        wrapper_func_name, wrapper_function_str = generate_langchain_tool_wrapper(langchain_tool, additional_imports_module_attr_map)
        json_schema = generate_schema_from_args_schema(langchain_tool.args_schema, name=wrapper_func_name, description=description)

        # append heartbeat (necessary for triggering another reasoning step after this tool call)
        json_schema["parameters"]["properties"]["request_heartbeat"] = {
            "type": "boolean",
            "description": "Request an immediate heartbeat after function execution. Set to `True` if you want to send a follow-up message or run a follow-up function.",
        }
        json_schema["parameters"]["required"].append("request_heartbeat")

        return cls(
            name=wrapper_func_name,
            description=description,
            source_type=source_type,
            tags=tags,
            source_code=wrapper_function_str,
            json_schema=json_schema,
        )

    @classmethod
    def from_crewai(cls, crewai_tool: "CrewAIBaseTool", additional_imports_module_attr_map: dict[str, str] = None) -> "Tool":
        """
        Class method to create an instance of Tool from a crewAI BaseTool object.

        Args:
            crewai_tool (CrewAIBaseTool): An instance of a crewAI BaseTool (BaseTool from crewai)

        Returns:
            Tool: A Letta Tool initialized with attributes derived from the provided crewAI BaseTool object.
        """
        description = crewai_tool.description
        source_type = "python"
        tags = ["crew-ai"]
        wrapper_func_name, wrapper_function_str = generate_crewai_tool_wrapper(crewai_tool, additional_imports_module_attr_map)
        json_schema = generate_schema_from_args_schema(crewai_tool.args_schema, name=wrapper_func_name, description=description)

        # append heartbeat (necessary for triggering another reasoning step after this tool call)
        json_schema["parameters"]["properties"]["request_heartbeat"] = {
            "type": "boolean",
            "description": "Request an immediate heartbeat after function execution. Set to `True` if you want to send a follow-up message or run a follow-up function.",
        }
        json_schema["parameters"]["required"].append("request_heartbeat")

        return cls(
            name=wrapper_func_name,
            description=description,
            source_type=source_type,
            tags=tags,
            source_code=wrapper_function_str,
            json_schema=json_schema,
        )

    @classmethod
    def load_default_langchain_tools(cls) -> List["Tool"]:
        # For now, we only support wikipedia tool
        from langchain_community.tools import WikipediaQueryRun
        from langchain_community.utilities import WikipediaAPIWrapper

        wikipedia_tool = Tool.from_langchain(
            WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper()), {"langchain_community.utilities": "WikipediaAPIWrapper"}
        )

        return [wikipedia_tool]

    @classmethod
    def load_default_crewai_tools(cls) -> List["Tool"]:
        # For now, we only support scrape website tool
        from crewai_tools import ScrapeWebsiteTool

        web_scrape_tool = Tool.from_crewai(ScrapeWebsiteTool())

        return [web_scrape_tool]

    @classmethod
    def load_default_composio_tools(cls) -> List["Tool"]:
        from composio_langchain import Action

        calculator = Tool.get_composio_tool(action=Action.MATHEMATICAL_CALCULATOR)
        serp_news = Tool.get_composio_tool(action=Action.SERPAPI_NEWS_SEARCH)
        serp_google_search = Tool.get_composio_tool(action=Action.SERPAPI_SEARCH)
        serp_google_maps = Tool.get_composio_tool(action=Action.SERPAPI_GOOGLE_MAPS_SEARCH)

        return [calculator, serp_news, serp_google_search, serp_google_maps]


class ToolCreate(BaseTool):
    id: Optional[str] = Field(None, description="The unique identifier of the tool. If this is not provided, it will be autogenerated.")
    name: Optional[str] = Field(None, description="The name of the function (auto-generated from source_code if not provided).")
    description: Optional[str] = Field(None, description="The description of the tool.")
    tags: List[str] = Field([], description="Metadata tags.")
    source_code: str = Field(..., description="The source code of the function.")
    json_schema: Optional[Dict] = Field(
        None, description="The JSON schema of the function (auto-generated from source_code if not provided)"
    )
    terminal: Optional[bool] = Field(None, description="Whether the tool is a terminal tool (allow requesting heartbeats).")


class ToolUpdate(ToolCreate):
    id: str = Field(..., description="The unique identifier of the tool.")
    description: Optional[str] = Field(None, description="The description of the tool.")
    name: Optional[str] = Field(None, description="The name of the function.")
    tags: Optional[List[str]] = Field(None, description="Metadata tags.")
    source_code: Optional[str] = Field(None, description="The source code of the function.")
    json_schema: Optional[Dict] = Field(None, description="The JSON schema of the function.")
