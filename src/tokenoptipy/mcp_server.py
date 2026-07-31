from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import mcp_tools

READ_ONLY = ToolAnnotations(
    title="TokenOptiPy read-only analysis",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

mcp = FastMCP(
    "TokenOptiPy",
    instructions=(
        "Use TokenOptiPy before changing LLM prompts or model-call context to inspect token flows, "
        "and after changes to validate token savings and safety invariants. All tools are local, "
        "read-only, and must not modify project source files."
    ),
    json_response=True,
)


@mcp.tool(
    name="inspect_workspace",
    title="Inspect workspace token flows",
    description=(
        "Scan the local workspace before editing prompts or LLM calls. Returns graph statistics, "
        "token hotspots, and safety findings without returning full prompt bodies."
    ),
    annotations=READ_ONLY,
)
async def inspect_workspace(
    projectPath: str = ".",
    backend: str = "simple",
    limit: int = 10,
    maxFileSize: int = 1_000_000,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        mcp_tools.inspect_workspace,
        projectPath,
        backend,
        limit,
        maxFileSize,
    )


@mcp.tool(
    name="analyze_prompt_file",
    title="Analyze a prompt file",
    description=(
        "Analyze one workspace file for token count, duplicate instructions, filler text, and other "
        "optimization opportunities. The file content stays local and is not returned."
    ),
    annotations=READ_ONLY,
)
async def analyze_prompt_file(filePath: str, backend: str = "simple") -> dict[str, Any]:
    return await asyncio.to_thread(mcp_tools.analyze_prompt_file, filePath, backend)


@mcp.tool(
    name="validate_prompt_change",
    title="Validate a prompt change",
    description=(
        "Compare an original and candidate prompt after an edit. Rejects unsafe changes to required "
        "terms, placeholders, numbers, negations, or indentation-sensitive structure and reports "
        "token savings. Provide text or workspace file paths, but not both for the same side."
    ),
    annotations=READ_ONLY,
)
async def validate_prompt_change(
    originalText: str = "",
    candidateText: str = "",
    originalPath: str = "",
    candidatePath: str = "",
    backend: str = "simple",
    requiredTerms: list[str] | None = None,
    minSemanticScore: float = 0.72,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        mcp_tools.validate_prompt_change,
        originalText,
        candidateText,
        originalPath,
        candidatePath,
        backend,
        requiredTerms,
        minSemanticScore,
    )


@mcp.tool(
    name="query_token_flow",
    title="Query the token graph",
    description=(
        "Search the local TokenGraph for prompts, context variables, files, functions, and model "
        "calls related to a natural-language or keyword query."
    ),
    annotations=READ_ONLY,
)
async def query_token_flow(
    query: str,
    projectPath: str = ".",
    backend: str = "simple",
    limit: int = 20,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        mcp_tools.query_token_flow,
        query,
        projectPath,
        backend,
        limit,
    )


@mcp.tool(
    name="get_traceability",
    title="Get TokenOptiPy traceability",
    description=(
        "Return recent TokenOptiPy MCP tool execution metadata: tool name, status, timestamp, "
        "duration, trace identifier, and a safe summary. Prompt bodies and arguments are excluded."
    ),
    annotations=READ_ONLY,
)
async def get_traceability(limit: int = 20) -> dict[str, Any]:
    return await asyncio.to_thread(mcp_tools.get_traceability, limit)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
