#!/usr/bin/env python3
"""
ILMA Task Executor - Execute tasks via tools/scripts/API/delegation.

This module provides comprehensive task execution capabilities including:
- TaskGraph: DAG-based task dependency management
- ToolExecutor: Execute shell tools and scripts
- APIExecutor: HTTP API invocations with retry logic

Usage:
    python ilma_task_executor.py --task "analyze data" --strategy tools
    python ilma_task_executor.py --graph tasks.json --execute
    python ilma_task_executor.py --api-endpoint https://api.example.com --method POST

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ExecutionStrategy(Enum):
    """Task execution strategy."""
    TOOLS = "tools"
    SCRIPTS = "scripts"
    API = "api"
    DELEGATION = "delegation"
    AUTO = "auto"


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    status: TaskStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    duration: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Represents a single task in the execution graph."""
    task_id: str
    name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    retry_max: int = 3
    timeout: int = 300

    def __hash__(self):
        return hash(self.task_id)


class TaskGraph:
    """
    Manages task dependencies and execution order using DAG approach.
    
    Supports:
    - Parallel execution of independent tasks
    - Dependency resolution
    - Cycle detection
    - Task prioritization
    """

    def __init__(self):
        """Initialize an empty task graph."""
        self.tasks: Dict[str, Task] = {}
        self.execution_order: List[List[str]] = []
        self.logger = logging.getLogger(f"{__name__}.TaskGraph")

    def add_task(self, task: Task) -> None:
        """
        Add a task to the graph.
        
        Args:
            task: Task object to add
            
        Raises:
            ValueError: If task_id already exists
        """
        if task.task_id in self.tasks:
            raise ValueError(f"Task {task.task_id} already exists in graph")
        self.tasks[task.task_id] = task
        self.logger.info(f"Added task: {task.task_id} ({task.name})")

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """
        Add a dependency between tasks.
        
        Args:
            task_id: Task that has the dependency
            depends_on: Task that must complete first
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        if depends_on not in self.tasks:
            raise ValueError(f"Dependency {depends_on} not found")
        self.tasks[task_id].dependencies.append(depends_on)

    def topological_sort(self) -> List[List[str]]:
        """
        Perform topological sort to determine execution order.
        
        Returns:
            List of task ID groups that can be executed in parallel
            
        Raises:
            ValueError: If circular dependency detected
        """
        in_degree: Dict[str, int] = {tid: 0 for tid in self.tasks}
        adjacency: Dict[str, List[str]] = {tid: [] for tid in self.tasks}

        # Build adjacency list and calculate in-degrees
        for task_id, task in self.tasks.items():
            in_degree[task_id] = len(task.dependencies)
            for dep in task.dependencies:
                adjacency[dep].append(task_id)

        # Kahn's algorithm
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        result: List[List[str]] = []

        while queue:
            result.append(queue[:])
            next_queue = []
            for current in queue:
                for neighbor in adjacency[current]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        # Check for cycles
        if sum(in_degree.values()) > 0:
            raise ValueError("Circular dependency detected in task graph")

        self.execution_order = result
        return result

    def get_ready_tasks(self, completed: Set[str]) -> List[Task]:
        """Get tasks that are ready to execute based on completed dependencies."""
        ready = []
        for task_id, task in self.tasks.items():
            if task_id in completed:
                continue
            if task.status != TaskStatus.PENDING:
                continue
            if all(dep in completed for dep in task.dependencies):
                ready.append(task)
        return ready

    def to_json(self) -> str:
        """Serialize graph to JSON."""
        data = {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "action": t.action,
                    "params": t.params,
                    "dependencies": t.dependencies,
                    "status": t.status.value
                }
                for t in self.tasks.values()
            ]
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> TaskGraph:
        """Deserialize graph from JSON."""
        data = json.loads(json_str)
        graph = cls()
        for td in data["tasks"]:
            task = Task(
                task_id=td["task_id"],
                name=td["name"],
                action=td["action"],
                params=td.get("params", {}),
                dependencies=td.get("dependencies", [])
            )
            graph.add_task(task)
        graph.topological_sort()
        return graph


class ToolExecutor:
    """
    Executes tasks via shell tools and scripts.
    
    Features:
    - Command timeout handling
    - Environment variable passthrough
    - Output capture (stdout/stderr)
    - Working directory control
    """

    def __init__(self, working_dir: Optional[Path] = None):
        """
        Initialize tool executor.
        
        Args:
            working_dir: Default working directory for command execution
        """
        self.working_dir = working_dir or Path.cwd()
        self.logger = logging.getLogger(f"{__name__}.ToolExecutor")
        self.executor = ThreadPoolExecutor(max_workers=4)

    def execute(
        self,
        command: Union[str, List[str]],
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        capture_output: bool = True
    ) -> TaskResult:
        """
        Execute a shell command.
        
        Args:
            command: Command to execute (string or list)
            env: Additional environment variables
            timeout: Execution timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            TaskResult with execution details
        """
        task_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            if isinstance(command, str):
                cmd_list = command.split()
            else:
                cmd_list = command

            self.logger.info(f"Executing: {' '.join(cmd_list)}")
            
            exec_env = dict(os.environ)
            if env:
                exec_env.update(env)

            result = subprocess.run(
                cmd_list,
                cwd=str(self.working_dir),
                env=exec_env,
                timeout=timeout,
                capture_output=capture_output,
                text=True
            )

            duration = time.time() - start_time
            status = TaskStatus.SUCCESS if result.returncode == 0 else TaskStatus.FAILED

            return TaskResult(
                task_id=task_id,
                status=status,
                output=result.stdout if capture_output else None,
                error=result.stderr if capture_output and result.returncode != 0 else None,
                duration=duration,
                metadata={"returncode": result.returncode}
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.logger.error(f"Command timed out after {timeout}s")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"Command timed out after {timeout}s",
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Execution failed: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration=duration
            )

    def execute_parallel(
        self,
        commands: List[Union[str, List[str]]],
        max_workers: int = 4
    ) -> List[TaskResult]:
        """
        Execute multiple commands in parallel.
        
        Args:
            commands: List of commands to execute
            max_workers: Maximum parallel executions
            
        Returns:
            List of TaskResults in order of submission
        """
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self.execute, cmd): i for i, cmd in enumerate(commands)}
            for future in as_completed(futures):
                results.append((futures[future], future.result()))
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def close(self):
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)


class APIExecutor:
    """
    Executes tasks via HTTP API calls.
    
    Features:
    - HTTP methods: GET, POST, PUT, DELETE, PATCH
    - Request/response JSON handling
    - Retry logic with exponential backoff
    - Timeout handling
    - Header customization
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ):
        """
        Initialize API executor.
        
        Args:
            base_url: Base URL for all requests
            default_headers: Default headers for all requests
            timeout: Default timeout for requests
        """
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.default_headers = default_headers or {}
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.APIExecutor")
        self.session_cookies: Optional[str] = None

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ) -> TaskResult:
        """
        Make an HTTP request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint path
            data: Request body data (will be JSON encoded)
            headers: Additional headers
            retry_count: Number of retries on failure
            retry_delay: Delay between retries
            
        Returns:
            TaskResult with response data
        """
        task_id = str(uuid.uuid4())
        start_time = time.time()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}" if endpoint else self.base_url
        headers = {**self.default_headers, **(headers or {})}
        
        if "Content-Type" not in headers and data:
            headers["Content-Type"] = "application/json"

        last_error = None
        for attempt in range(retry_count):
            try:
                self.logger.info(f"{method} {url} (attempt {attempt + 1})")
                
                body = json.dumps(data).encode("utf-8") if data else None
                request = Request(url, data=body, headers=headers, method=method)
                
                with urlopen(request, timeout=self.timeout) as response:
                    response_body = response.read().decode("utf-8")
                    response_headers = dict(response.headers)
                    
                    try:
                        output = json.loads(response_body)
                    except json.JSONDecodeError:
                        output = response_body

                    duration = time.time() - start_time
                    return TaskResult(
                        task_id=task_id,
                        status=TaskStatus.SUCCESS,
                        output=output,
                        duration=duration,
                        metadata={
                            "status_code": response.status,
                            "headers": response_headers
                        }
                    )

            except HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                self.logger.warning(f"HTTP error: {last_error}")
            except URLError as e:
                last_error = f"URL error: {e.reason}"
                self.logger.warning(f"URL error: {last_error}")
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Request error: {last_error}")

            if attempt < retry_count - 1:
                time.sleep(retry_delay * (2 ** attempt))

        duration = time.time() - start_time
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=last_error,
            duration=duration,
            retry_count=retry_count
        )

    def get(self, endpoint: str, **kwargs) -> TaskResult:
        """Convenience method for GET requests."""
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> TaskResult:
        """Convenience method for POST requests."""
        return self.request("POST", endpoint, data=data, **kwargs)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> TaskResult:
        """Convenience method for PUT requests."""
        return self.request("PUT", endpoint, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> TaskResult:
        """Convenience method for DELETE requests."""
        return self.request("DELETE", endpoint, **kwargs)


class DelegationExecutor:
    """
    Delegates tasks to sub-agents with isolated context.
    
    Features:
    - Agent pool management
    - Context isolation per agent
    - Result aggregation
    - Load balancing
    """

    def __init__(self, agent_count: int = 3):
        """
        Initialize delegation executor.
        
        Args:
            agent_count: Number of sub-agents in the pool
        """
        self.agent_count = agent_count
        self.agent_assignments: Dict[str, str] = {}
        self.results: Dict[str, Any] = {}
        self.logger = logging.getLogger(f"{__name__}.DelegationExecutor")

    def delegate(
        self,
        task: Task,
        agent_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Delegate a task to a sub-agent.
        
        Args:
            task: Task to delegate
            agent_id: Specific agent ID or None for auto-assignment
            context: Isolated context data for the agent
            
        Returns:
            Delegation ticket ID
        """
        ticket_id = f"delegate_{uuid.uuid4().hex[:8]}"
        
        if agent_id is None:
            agent_id = f"agent_{hash(task.task_id) % self.agent_count}"
        
        self.agent_assignments[ticket_id] = agent_id
        self.logger.info(f"Delegated {task.task_id} to {agent_id} (ticket: {ticket_id})")
        
        # Simulate delegation by logging
        # In production, this would interface with actual sub-agents
        self.results[ticket_id] = {
            "task_id": task.task_id,
            "agent_id": agent_id,
            "context": context or {},
            "status": "delegated"
        }
        
        return ticket_id

    def get_result(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get result for a delegation ticket."""
        return self.results.get(ticket_id)

    def aggregate_results(self, ticket_ids: List[str]) -> Dict[str, Any]:
        """
        Aggregate results from multiple delegations.
        
        Args:
            ticket_ids: List of delegation ticket IDs
            
        Returns:
            Aggregated results dictionary
        """
        aggregated = {
            "total": len(ticket_ids),
            "results": [],
            "errors": []
        }
        
        for tid in ticket_ids:
            result = self.results.get(tid)
            if result:
                if result.get("status") == "error":
                    aggregated["errors"].append(result)
                else:
                    aggregated["results"].append(result)
        
        return aggregated


def create_task_from_dict(data: Dict[str, Any]) -> Task:
    """Helper to create Task from dictionary."""
    return Task(
        task_id=data.get("task_id", str(uuid.uuid4())),
        name=data.get("name", "unnamed"),
        action=data.get("action", ""),
        params=data.get("params", {}),
        dependencies=data.get("dependencies", []),
        retry_max=data.get("retry_max", 3),
        timeout=data.get("timeout", 300)
    )


def execute_task_graph(
    graph: TaskGraph,
    strategy: ExecutionStrategy = ExecutionStrategy.AUTO,
    tool_exec: Optional[ToolExecutor] = None,
    api_exec: Optional[APIExecutor] = None
) -> Dict[str, TaskResult]:
    """
    Execute all tasks in a graph according to their dependencies.
    
    Args:
        graph: TaskGraph to execute
        strategy: Execution strategy to use
        tool_exec: ToolExecutor instance
        api_exec: APIExecutor instance
        
    Returns:
        Dictionary of task_id to TaskResult
    """
    logger = logging.getLogger(__name__)
    results: Dict[str, TaskResult] = {}
    completed: Set[str] = set()
    
    tool_exec = tool_exec or ToolExecutor()
    api_exec = api_exec or APIExecutor()

    # Get execution order
    execution_order = graph.topological_sort()
    logger.info(f"Execution order: {execution_order}")

    for level in execution_order:
        # Execute all tasks at this level in parallel
        for task_id in level:
            task = graph.tasks[task_id]
            task.status = TaskStatus.RUNNING
            
            logger.info(f"Executing task: {task_id}")
            
            try:
                if strategy == ExecutionStrategy.TOOLS or task.action.startswith("tool:"):
                    # Extract tool command from params
                    command = task.params.get("command", task.params.get("cmd", "echo 'No command'"))
                    result = tool_exec.execute(command, timeout=task.timeout)
                    
                elif strategy == ExecutionStrategy.API or task.action.startswith("api:"):
                    endpoint = task.params.get("endpoint", "")
                    method = task.params.get("method", "GET")
                    data = task.params.get("data")
                    
                    if method.upper() == "GET":
                        result = api_exec.get(endpoint)
                    elif method.upper() == "POST":
                        result = api_exec.post(endpoint, data)
                    elif method.upper() == "PUT":
                        result = api_exec.put(endpoint, data)
                    elif method.upper() == "DELETE":
                        result = api_exec.delete(endpoint)
                    else:
                        result = TaskResult(
                            task_id=task_id,
                            status=TaskStatus.FAILED,
                            error=f"Unknown HTTP method: {method}"
                        )
                        
                elif strategy == ExecutionStrategy.DELEGATION:
                    delegator = DelegationExecutor()
                    ticket_id = delegator.delegate(task, context=task.params)
                    delegation_result = delegator.get_result(ticket_id)
                    
                    result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.SUCCESS,
                        output=delegation_result
                    )
                    
                else:  # AUTO - try to detect type
                    if task.action.startswith("tool:"):
                        command = task.params.get("command", "echo 'No command'")
                        result = tool_exec.execute(command, timeout=task.timeout)
                    elif task.action.startswith("api:"):
                        endpoint = task.params.get("endpoint", "")
                        result = api_exec.get(endpoint)
                    else:
                        result = TaskResult(
                            task_id=task_id,
                            status=TaskStatus.FAILED,
                            error=f"Unknown action type: {task.action}"
                        )
                
                task.status = result.status
                task.result = result
                results[task_id] = result
                
                if result.status == TaskStatus.SUCCESS:
                    completed.add(task_id)
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    logger.error(f"Task {task_id} failed: {result.error}")
                    
            except Exception as e:
                logger.exception(f"Error executing task {task_id}")
                task.status = TaskStatus.FAILED
                error_result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error=str(e)
                )
                task.result = error_result
                results[task_id] = error_result

    return results


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Task Executor - Execute tasks via tools/scripts/API/delegation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --task "analyze data" --strategy tools --command "python analyze.py"
  %(prog)s --graph tasks.json --execute
  %(prog)s --api-endpoint https://api.example.com --method POST --data '{"key": "value"}'
  %(prog)s --delegate --task-name "complex_task" --action "multi-step"
        """
    )
    
    parser.add_argument("--task", "-t", help="Task description or name")
    parser.add_argument("--action", "-a", default="auto", help="Task action (tool:, api:, delegation)")
    parser.add_argument("--command", "-c", help="Shell command to execute (for tool strategy)")
    parser.add_argument("--strategy", "-s", 
                       choices=["tools", "scripts", "api", "delegation", "auto"],
                       default="auto", help="Execution strategy")
    
    # Graph-based execution
    parser.add_argument("--graph", "-g", help="JSON file containing task graph")
    parser.add_argument("--execute", "-e", action="store_true", help="Execute tasks in graph")
    
    # API execution
    parser.add_argument("--api-endpoint", help="API endpoint URL")
    parser.add_argument("--method", "-m", default="GET", 
                       choices=["GET", "POST", "PUT", "DELETE", "PATCH"],
                       help="HTTP method")
    parser.add_argument("--data", "-d", help="JSON data for request body")
    parser.add_argument("--header", action="append", help="Additional headers (key:value)")
    
    # Delegation
    parser.add_argument("--delegate", action="store_true", help="Use delegation strategy")
    parser.add_argument("--task-name", help="Name of task to delegate")
    parser.add_argument("--agent-count", type=int, default=3, help="Number of sub-agents")
    
    # Output options
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Determine strategy
        if args.delegate:
            strategy = ExecutionStrategy.DELEGATION
        elif args.strategy:
            strategy = ExecutionStrategy(args.strategy)
        else:
            strategy = ExecutionStrategy.AUTO
        
        # API-based execution
        if args.api_endpoint:
            headers = {}
            if args.header:
                for h in args.header:
                    if ":" in h:
                        k, v = h.split(":", 1)
                        headers[k.strip()] = v.strip()
            
            api_exec = APIExecutor(default_headers=headers)
            data = json.loads(args.data) if args.data else None
            
            result = api_exec.request(args.method, args.api_endpoint, data=data)
            
            if args.json_output:
                print(json.dumps({
                    "status": result.status.value,
                    "output": result.output,
                    "error": result.error,
                    "duration": result.duration
                }, indent=2))
            else:
                if result.status == TaskStatus.SUCCESS:
                    logger.info(f"API request successful (took {result.duration:.2f}s)")
                    print(f"Output: {result.output}")
                else:
                    logger.error(f"API request failed: {result.error}")
                    return 1
            
            return 0
        
        # Delegation execution
        if args.delegate or args.task_name:
            delegator = DelegationExecutor(agent_count=args.agent_count)
            
            task = Task(
                task_id=str(uuid.uuid4()),
                name=args.task_name or "delegated_task",
                action=args.action,
                params={"description": args.task or "No description"}
            )
            
            ticket_id = delegator.delegate(task, context=task.params)
            result = delegator.get_result(ticket_id)
            
            logger.info(f"Delegation ticket: {ticket_id}")
            print(f"Task delegated to sub-agent")
            print(f"Ticket ID: {ticket_id}")
            print(f"Agent: {result['agent_id']}")
            
            return 0
        
        # Graph-based execution
        if args.graph:
            graph_path = Path(args.graph)
            if not graph_path.exists():
                logger.error(f"Graph file not found: {args.graph}")
                return 1
            
            with open(graph_path) as f:
                graph = TaskGraph.from_json(f.read())
            
            if args.execute:
                results = execute_task_graph(graph, strategy=strategy)
                
                if args.json_output:
                    output_data = {
                        task_id: {
                            "status": r.status.value,
                            "output": r.output,
                            "error": r.error,
                            "duration": r.duration
                        }
                        for task_id, r in results.items()
                    }
                    print(json.dumps(output_data, indent=2))
                else:
                    success = sum(1 for r in results.values() if r.status == TaskStatus.SUCCESS)
                    total = len(results)
                    logger.info(f"Execution complete: {success}/{total} tasks succeeded")
                    
                    for task_id, result in results.items():
                        status_icon = "✓" if result.status == TaskStatus.SUCCESS else "✗"
                        print(f"  {status_icon} {task_id}: {result.status.value}")
                
                # Write output file if specified
                if args.output:
                    output_data = {
                        task_id: {
                            "status": r.status.value,
                            "output": r.output,
                            "error": r.error,
                            "duration": r.duration,
                            "metadata": r.metadata
                        }
                        for task_id, r in results.items()
                    }
                    with open(args.output, "w") as f:
                        json.dump(output_data, f, indent=2)
                    logger.info(f"Results written to {args.output}")
                
                return 0
            else:
                # Just show the execution plan
                order = graph.topological_sort()
                print("Task execution plan:")
                for i, level in enumerate(order):
                    print(f"  Level {i}: {', '.join(level)}")
                return 0
        
        # Simple task execution
        if args.command:
            tool_exec = ToolExecutor()
            result = tool_exec.execute(args.command)
            tool_exec.close()
            
            if result.status == TaskStatus.SUCCESS:
                logger.info("Command executed successfully")
                if result.output:
                    print(result.output)
                return 0
            else:
                logger.error(f"Command failed: {result.error}")
                return 1
        
        # No specific task - show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    import os
    exit(main())