"""
工具基类
定义所有工具的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """
    工具基类
    所有 Mock API 工具都继承此类
    """

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        执行工具

        Args:
            params: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        pass

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证参数：required key 必须存在且值不为 None/空字符串"""
        required = self.parameters_schema.get("required", [])
        for key in required:
            if key not in params:
                return False
            val = params[key]
            if val is None:
                return False
            if isinstance(val, str) and not val.strip():
                return False
        return True

    async def __call__(self, params: Dict[str, Any]) -> ToolResult:
        """使工具可调用"""
        if not self.validate_params(params):
            return ToolResult(
                success=False,
                error_type="invalid_params",
                error_message=f"缺少必要参数: {self.parameters_schema.get('required', [])}",
            )

        try:
            logger.info(f"执行工具 {self.name}: {params}")
            result = await self.execute(params)
            logger.info(f"工具 {self.name} 执行完成: success={result.success}")
            return result
        except Exception as e:
            logger.error(f"工具 {self.name} 执行异常: {e}")
            return ToolResult(
                success=False,
                error_type="execution_error",
                error_message=str(e),
            )

    def to_openai_function(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }


class ToolRegistry:
    """
    工具注册表
    管理所有可用工具
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"注册工具: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list:
        """列出所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in self._tools.values()
        ]

    def to_openai_functions(self) -> list:
        """转换为 OpenAI Function Calling 格式"""
        return [tool.to_openai_function() for tool in self._tools.values()]
