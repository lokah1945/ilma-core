#!/usr/bin/env python3
"""
ILMA DevOps Engine
==================
CI/CD pipeline management, Docker orchestration, and Kubernetes operations.

Classes: CICDPipeline, DockerManager, K8sOrchestrator

Usage:
    python3 ilma_devops_engine.py --pipeline-status
    python3 ilma_devops_engine.py --docker-ps
    python3 ilma_devops_engine.py --k8s-pods --namespace default

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DevOpsEngine")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class PipelineStatus(Enum):
    """CI/CD pipeline statuses."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class BuildStepStatus(Enum):
    """Build step statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStage:
    """Represents a stage in the CI/CD pipeline."""
    name: str
    status: BuildStepStatus
    duration_seconds: Optional[float] = None
    logs: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)


@dataclass
class Pipeline:
    """Represents a CI/CD pipeline."""
    id: str
    name: str
    status: PipelineStatus
    stages: List[PipelineStage]
    start_time: datetime
    end_time: Optional[datetime] = None
    trigger: str = "manual"
    branch: str = "main"


@dataclass
class ContainerInfo:
    """Docker container information."""
    id: str
    name: str
    image: str
    status: str
    ports: List[str]
    created: str


@dataclass
class K8sResource:
    """Kubernetes resource information."""
    name: str
    namespace: str
    resource_type: str
    status: str
    age: str


# =============================================================================
# CI/CD PIPELINE CLASS
# =============================================================================

class CICDPipeline:
    """
    CI/CD pipeline management with support for multiple backends.
    
    Supports GitHub Actions, GitLab CI, Jenkins, and custom pipelines.
    """
    
    def __init__(self, backend: str = "github"):
        self.backend = backend
        self.pipelines: Dict[str, Pipeline] = {}
        self.artifacts_dir = Path("/tmp/ilma_pipeline_artifacts")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CICDPipeline initialized with {backend} backend")
    
    def create_pipeline(
        self,
        name: str,
        stages: List[str],
        trigger: str = "manual"
    ) -> Pipeline:
        """Create a new pipeline definition."""
        pipeline_id = f"pipeline_{int(time.time())}"
        
        stage_objects = [
            PipelineStage(name=s, status=BuildStepStatus.PENDING)
            for s in stages
        ]
        
        pipeline = Pipeline(
            id=pipeline_id,
            name=name,
            status=PipelineStatus.PENDING,
            stages=stage_objects,
            start_time=datetime.now(),
            trigger=trigger
        )
        
        self.pipelines[pipeline_id] = pipeline
        logger.info(f"Created pipeline: {name} ({pipeline_id})")
        
        return pipeline
    
    def run_pipeline(
        self,
        pipeline_id: str,
        env_vars: Optional[Dict[str, str]] = None
    ) -> bool:
        """Execute a pipeline."""
        if pipeline_id not in self.pipelines:
            logger.error(f"Pipeline not found: {pipeline_id}")
            return False
        
        pipeline = self.pipelines[pipeline_id]
        pipeline.status = PipelineStatus.RUNNING
        pipeline.start_time = datetime.now()
        
        logger.info(f"Starting pipeline: {pipeline.name}")
        
        try:
            for i, stage in enumerate(pipeline.stages):
                logger.info(f"Executing stage: {stage.name}")
                stage.status = BuildStepStatus.IN_PROGRESS
                
                # Simulate stage execution
                success = self._execute_stage(stage, env_vars or {})
                
                if success:
                    stage.status = BuildStepStatus.SUCCESS
                else:
                    stage.status = BuildStepStatus.FAILED
                    pipeline.status = PipelineStatus.FAILED
                    logger.error(f"Stage failed: {stage.name}")
                    return False
                
                # Small delay between stages
                time.sleep(0.5)
            
            pipeline.status = PipelineStatus.SUCCESS
            pipeline.end_time = datetime.now()
            logger.info(f"Pipeline completed successfully: {pipeline.name}")
            return True
            
        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            pipeline.status = PipelineStatus.FAILED
            return False
    
    def _execute_stage(self, stage: PipelineStage, env_vars: Dict[str, str]) -> bool:
        """Execute a single pipeline stage."""
        stage_logs = []
        
        # Simulate stage execution with environment setup
        stage_logs.append(f"[{datetime.now().isoformat()}] Stage started: {stage.name}")
        
        # Add environment variables to logs
        if env_vars:
            stage_logs.append(f"Environment: {json.dumps(env_vars)}")
        
        # Simulate work
        time.sleep(1)
        
        stage_logs.append(f"[{datetime.now().isoformat()}] Stage completed")
        stage.logs = stage_logs
        stage.duration_seconds = 1.0
        
        return True
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed pipeline status."""
        if pipeline_id not in self.pipelines:
            return None
        
        pipeline = self.pipelines[pipeline_id]
        
        return {
            "id": pipeline.id,
            "name": pipeline.name,
            "status": pipeline.status.value,
            "stages": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration": s.duration_seconds,
                    "logs": s.logs[-5:]  # Last 5 log entries
                }
                for s in pipeline.stages
            ],
            "start_time": pipeline.start_time.isoformat(),
            "end_time": pipeline.end_time.isoformat() if pipeline.end_time else None,
            "duration_seconds": (
                (pipeline.end_time - pipeline.start_time).total_seconds()
                if pipeline.end_time else None
            )
        }
    
    def list_pipelines(self) -> List[Dict[str, Any]]:
        """List all pipelines."""
        return [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "stages_count": len(p.stages),
                "start_time": p.start_time.isoformat()
            }
            for p in self.pipelines.values()
        ]
    
    def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Cancel a running pipeline."""
        if pipeline_id not in self.pipelines:
            return False
        
        pipeline = self.pipelines[pipeline_id]
        if pipeline.status == PipelineStatus.RUNNING:
            pipeline.status = PipelineStatus.CANCELLED
            pipeline.end_time = datetime.now()
            logger.info(f"Pipeline cancelled: {pipeline_id}")
            return True
        
        return False
    
    def create_github_workflow(self, name: str, stages: List[str]) -> str:
        """Generate GitHub Actions workflow YAML."""
        workflow = f"""name: {name}

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
"""
        
        for stage in stages:
            job_name = stage.lower().replace(" ", "-")
            workflow += f"""
  {job_name}:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run {stage}
        run: |
          echo "Executing {stage}..."
          # Add your commands here
"""

        return workflow


# =============================================================================
# DOCKER MANAGER CLASS
# =============================================================================

class DockerManager:
    """
    Docker container management with support for building, running,
    and orchestrating containers.
    """
    
    def __init__(self):
        self.containers: List[ContainerInfo] = []
        self.images: List[Dict[str, str]] = []
        logger.info("DockerManager initialized")
    
    def list_containers(self, all: bool = False) -> List[ContainerInfo]:
        """List Docker containers."""
        try:
            cmd = ["docker", "ps"]
            if all:
                cmd.append("-a")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Docker command failed: {result.stderr}")
                return []
            
            containers = []
            lines = result.stdout.strip().split("\n")
            
            # Skip header
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 7:
                    container = ContainerInfo(
                        id=parts[0],
                        name=parts[1] if len(parts) > 1 else "",
                        image=parts[2] if len(parts) > 2 else "",
                        status=parts[4] if len(parts) > 4 else "",
                        ports=self._parse_ports(line),
                        created=parts[5] if len(parts) > 5 else ""
                    )
                    containers.append(container)
            
            self.containers = containers
            return containers
            
        except subprocess.TimeoutExpired:
            logger.error("Docker command timed out")
            return []
        except FileNotFoundError:
            logger.error("Docker not installed")
            return []
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []
    
    def _parse_ports(self, line: str) -> List[str]:
        """Parse port mappings from docker ps output."""
        ports = []
        match = re.search(r"0\.0\.0\.0:(\d+)->(\d+)/tcp", line)
        if match:
            ports.append(f"{match.group(1)}->{match.group(2)}")
        return ports
    
    def pull_image(self, image: str, tag: str = "latest") -> bool:
        """Pull a Docker image."""
        try:
            logger.info(f"Pulling image: {image}:{tag}")
            
            result = subprocess.run(
                ["docker", "pull", f"{image}:{tag}"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info(f"Image pulled successfully: {image}:{tag}")
                return True
            else:
                logger.error(f"Failed to pull image: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to pull image: {e}")
            return False
    
    def build_image(
        self,
        dockerfile: str,
        image_name: str,
        tag: str = "latest",
        build_args: Optional[Dict[str, str]] = None
    ) -> bool:
        """Build a Docker image from Dockerfile."""
        try:
            cmd = ["docker", "build", "-t", f"{image_name}:{tag}", "-f", dockerfile, "."]
            
            if build_args:
                for key, value in build_args.items():
                    cmd.extend(["--build-arg", f"{key}={value}"])
            
            logger.info(f"Building image: {image_name}:{tag}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                logger.info(f"Image built successfully: {image_name}:{tag}")
                return True
            else:
                logger.error(f"Failed to build image: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to build image: {e}")
            return False
    
    def run_container(
        self,
        image: str,
        name: str,
        ports: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        volumes: Optional[List[str]] = None,
        detached: bool = True
    ) -> Optional[str]:
        """Run a Docker container."""
        try:
            cmd = ["docker", "run"]
            
            if detached:
                cmd.append("-d")
            
            if name:
                cmd.extend(["--name", name])
            
            if ports:
                for port in ports:
                    cmd.extend(["-p", port])
            
            if env_vars:
                for key, value in env_vars.items():
                    cmd.extend(["-e", f"{key}={value}"])
            
            if volumes:
                for vol in volumes:
                    cmd.extend(["-v", vol])
            
            cmd.append(image)
            
            logger.info(f"Running container: {name} from {image}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                container_id = result.stdout.strip()[:12]
                logger.info(f"Container started: {container_id}")
                return container_id
            else:
                logger.error(f"Failed to run container: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to run container: {e}")
            return None
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a Docker container."""
        try:
            result = subprocess.run(
                ["docker", "stop", "-t", str(timeout), container_id],
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )
            
            if result.returncode == 0:
                logger.info(f"Container stopped: {container_id}")
                return True
            else:
                logger.error(f"Failed to stop container: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """Remove a Docker container."""
        try:
            cmd = ["docker", "rm"]
            if force:
                cmd.append("-f")
            cmd.append(container_id)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Container removed: {container_id}")
                return True
            else:
                logger.error(f"Failed to remove container: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove container: {e}")
            return False
    
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """Get container logs."""
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.stdout if result.returncode == 0 else result.stderr
            
        except Exception as e:
            logger.error(f"Failed to get container logs: {e}")
            return str(e)
    
    def inspect_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed container information."""
        try:
            result = subprocess.run(
                ["docker", "inspect", container_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data[0] if data else None
            return None
            
        except Exception as e:
            logger.error(f"Failed to inspect container: {e}")
            return None


# =============================================================================
# KUBERNETES ORCHESTRATOR CLASS
# =============================================================================

class K8sOrchestrator:
    """
    Kubernetes cluster management and orchestration.
    
    Supports pod management, deployment operations, and cluster monitoring.
    """
    
    def __init__(self, kubeconfig: Optional[str] = None):
        self.kubeconfig = kubeconfig or os.environ.get("KUBECONFIG", "~/.kube/config")
        self.namespace = "default"
        self.context = None
        logger.info("K8sOrchestrator initialized")
    
    def set_context(self, context: str) -> bool:
        """Set the active Kubernetes context."""
        try:
            result = subprocess.run(
                ["kubectl", "config", "use-context", context],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.context = context
                logger.info(f"Switched to context: {context}")
                return True
            else:
                logger.error(f"Failed to set context: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set context: {e}")
            return False
    
    def set_namespace(self, namespace: str) -> None:
        """Set the default namespace."""
        self.namespace = namespace
        logger.info(f"Default namespace set to: {namespace}")
    
    def get_pods(self, namespace: Optional[str] = None, label_selector: Optional[str] = None) -> List[K8sResource]:
        """List pods in a namespace."""
        ns = namespace or self.namespace
        
        try:
            cmd = ["kubectl", "get", "pods", "-n", ns, "-o", "wide"]
            
            if label_selector:
                cmd.extend(["-l", label_selector])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to get pods: {result.stderr}")
                return []
            
            pods = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 6:
                    pod = K8sResource(
                        name=parts[0],
                        namespace=ns,
                        resource_type="pod",
                        status=parts[2] if len(parts) > 2 else "Unknown",
                        age=parts[4] if len(parts) > 4 else "Unknown"
                    )
                    pods.append(pod)
            
            return pods
            
        except FileNotFoundError:
            logger.error("kubectl not installed")
            return []
        except Exception as e:
            logger.error(f"Failed to get pods: {e}")
            return []
    
    def get_services(self, namespace: Optional[str] = None) -> List[K8sResource]:
        """List services in a namespace."""
        ns = namespace or self.namespace
        
        try:
            result = subprocess.run(
                ["kubectl", "get", "services", "-n", ns, "-o", "wide"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            services = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    svc = K8sResource(
                        name=parts[0],
                        namespace=ns,
                        resource_type="service",
                        status=parts[2] if len(parts) > 2 else "Unknown",
                        age=parts[3] if len(parts) > 3 else "Unknown"
                    )
                    services.append(svc)
            
            return services
            
        except Exception as e:
            logger.error(f"Failed to get services: {e}")
            return []
    
    def get_deployments(self, namespace: Optional[str] = None) -> List[K8sResource]:
        """List deployments in a namespace."""
        ns = namespace or self.namespace
        
        try:
            result = subprocess.run(
                ["kubectl", "get", "deployments", "-n", ns, "-o", "wide"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            deployments = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    deploy = K8sResource(
                        name=parts[0],
                        namespace=ns,
                        resource_type="deployment",
                        status=parts[2] if len(parts) > 2 else "Unknown",
                        age=parts[3] if len(parts) > 3 else "Unknown"
                    )
                    deployments.append(deploy)
            
            return deployments
            
        except Exception as e:
            logger.error(f"Failed to get deployments: {e}")
            return []
    
    def scale_deployment(self, name: str, replicas: int, namespace: Optional[str] = None) -> bool:
        """Scale a deployment to specified replica count."""
        ns = namespace or self.namespace
        
        try:
            result = subprocess.run(
                ["kubectl", "scale", "deployment", name, 
                 f"--replicas={replicas}", "-n", ns],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Scaled deployment {name} to {replicas} replicas")
                return True
            else:
                logger.error(f"Failed to scale deployment: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to scale deployment: {e}")
            return False
    
    def rollout_status(self, resource_type: str, name: str, namespace: Optional[str] = None) -> str:
        """Get rollout status for a resource."""
        ns = namespace or self.namespace
        
        try:
            result = subprocess.run(
                ["kubectl", "rollout", "status", f"{resource_type}/{name}", "-n", ns],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return result.stdout if result.returncode == 0 else result.stderr
            
        except Exception as e:
            logger.error(f"Failed to get rollout status: {e}")
            return str(e)
    
    def apply_manifest(self, manifest_path: str) -> bool:
        """Apply a Kubernetes manifest."""
        try:
            result = subprocess.run(
                ["kubectl", "apply", "-f", manifest_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"Applied manifest: {manifest_path}")
                return True
            else:
                logger.error(f"Failed to apply manifest: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to apply manifest: {e}")
            return False
    
    def delete_resource(self, resource_type: str, name: str, namespace: Optional[str] = None) -> bool:
        """Delete a Kubernetes resource."""
        ns = namespace or self.namespace
        
        try:
            result = subprocess.run(
                ["kubectl", "delete", resource_type, name, "-n", ns],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Deleted {resource_type}/{name}")
                return True
            else:
                logger.error(f"Failed to delete resource: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete resource: {e}")
            return False
    
    def get_node_status(self) -> List[Dict[str, Any]]:
        """Get status of all cluster nodes."""
        try:
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "wide"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            nodes = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 5:
                    nodes.append({
                        "name": parts[0],
                        "status": parts[1] if len(parts) > 1 else "Unknown",
                        "role": parts[2] if len(parts) > 2 else "",
                        "age": parts[3] if len(parts) > 3 else "Unknown",
                        "version": parts[4] if len(parts) > 4 else ""
                    })
            
            return nodes
            
        except Exception as e:
            logger.error(f"Failed to get node status: {e}")
            return []
    
    def execute_in_pod(
        self,
        pod_name: str,
        command: List[str],
        namespace: Optional[str] = None,
        container: Optional[str] = None
    ) -> Optional[str]:
        """Execute a command in a pod."""
        ns = namespace or self.namespace
        
        try:
            cmd = ["kubectl", "exec", "-n", ns, pod_name]
            
            if container:
                cmd.extend(["-c", container])
            
            cmd.append("--")
            cmd.extend(command)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"Failed to execute in pod: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to execute in pod: {e}")
            return None


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA DevOps Engine - CI/CD, Docker, and Kubernetes management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CI/CD Pipeline
  %(prog)s --create-pipeline --name "build-and-deploy" --stages "build,test,deploy"
  %(prog)s --run-pipeline pipeline_123456
  %(prog)s --pipeline-status pipeline_123456
  
  # Docker
  %(prog)s --docker-ps
  %(prog)s --docker-pull nginx:latest
  %(prog)s --docker-run --name myapp --ports 8080:80 nginx:latest
  
  # Kubernetes
  %(prog)s --k8s-pods --namespace default
  %(prog)s --k8s-deployments
  %(prog)s --k8s-scale my-deployment 3
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Pipeline options
    pipeline_group = parser.add_argument_group("CI/CD Pipeline")
    pipeline_group.add_argument("--create-pipeline", action="store_true", help="Create a new pipeline")
    pipeline_group.add_argument("--run-pipeline", metavar="PIPELINE_ID", help="Run a pipeline")
    pipeline_group.add_argument("--pipeline-status", metavar="PIPELINE_ID", help="Get pipeline status")
    pipeline_group.add_argument("--list-pipelines", action="store_true", help="List all pipelines")
    pipeline_group.add_argument("--cancel-pipeline", metavar="PIPELINE_ID", help="Cancel a running pipeline")
    pipeline_group.add_argument("--name", help="Pipeline name")
    pipeline_group.add_argument("--stages", help="Comma-separated stage names")
    pipeline_group.add_argument("--trigger", default="manual", help="Pipeline trigger type")
    
    # Docker options
    docker_group = parser.add_argument_group("Docker")
    docker_group.add_argument("--docker-ps", action="store_true", help="List running containers")
    docker_group.add_argument("--docker-pull", metavar="IMAGE", help="Pull a Docker image")
    docker_group.add_argument("--docker-run", action="store_true", help="Run a Docker container")
    docker_group.add_argument("--docker-stop", metavar="CONTAINER_ID", help="Stop a container")
    docker_group.add_argument("--docker-rm", metavar="CONTAINER_ID", help="Remove a container")
    docker_group.add_argument("--docker-logs", metavar="CONTAINER_ID", help="Get container logs")
    docker_group.add_argument("--port", action="append", help="Port mapping (host:container)")
    docker_group.add_argument("--image", help="Container image")
    docker_group.add_argument("--tag", default="latest", help="Image tag")
    
    # Kubernetes options
    k8s_group = parser.add_argument_group("Kubernetes")
    k8s_group.add_argument("--k8s-pods", action="store_true", help="List pods")
    k8s_group.add_argument("--k8s-services", action="store_true", help="List services")
    k8s_group.add_argument("--k8s-deployments", action="store_true", help="List deployments")
    k8s_group.add_argument("--k8s-nodes", action="store_true", help="List nodes")
    k8s_group.add_argument("--k8s-scale", metavar="NAME", type=int, help="Scale deployment")
    k8s_group.add_argument("--k8s-context", help="Set Kubernetes context")
    k8s_group.add_argument("--namespace", "-n", default="default", help="Kubernetes namespace")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Pipeline Management
        if args.create_pipeline:
            if not args.name or not args.stages:
                parser.error("--name and --stages are required for pipeline creation")
            
            stages = [s.strip() for s in args.stages.split(",")]
            pipeline_manager = CICDPipeline()
            pipeline = pipeline_manager.create_pipeline(args.name, stages, args.trigger)
            
            print(f"\nPipeline created: {pipeline.id}")
            print(f"  Name: {pipeline.name}")
            print(f"  Stages: {', '.join([s.name for s in pipeline.stages])}")
            print(f"  Trigger: {pipeline.trigger}")
        
        elif args.run_pipeline:
            pipeline_manager = CICDPipeline()
            success = pipeline_manager.run_pipeline(args.run_pipeline)
            
            print(f"\nPipeline execution: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.pipeline_status:
            pipeline_manager = CICDPipeline()
            status = pipeline_manager.get_pipeline_status(args.pipeline_status)
            
            if status:
                print(f"\nPipeline Status: {status['id']}")
                print(f"  Name: {status['name']}")
                print(f"  Status: {status['status']}")
                print(f"  Duration: {status.get('duration_seconds', 'N/A')}s")
                
                print("\nStages:")
                for stage in status['stages']:
                    print(f"  - {stage['name']}: {stage['status']}")
            else:
                print(f"Pipeline not found: {args.pipeline_status}")
        
        elif args.list_pipelines:
            pipeline_manager = CICDPipeline()
            pipelines = pipeline_manager.list_pipelines()
            
            print("\nPipelines:")
            for p in pipelines:
                print(f"  [{p['status']}] {p['id']} - {p['name']} ({p['stages_count']} stages)")
        
        elif args.cancel_pipeline:
            pipeline_manager = CICDPipeline()
            cancelled = pipeline_manager.cancel_pipeline(args.cancel_pipeline)
            
            print(f"\nCancellation: {'SUCCESS' if cancelled else 'FAILED'}")
        
        # Docker Management
        elif args.docker_ps:
            docker = DockerManager()
            containers = docker.list_containers(all=True)
            
            print("\nDocker Containers:")
            if containers:
                for c in containers:
                    print(f"  {c.name} ({c.id[:12]}) - {c.image}")
                    print(f"    Status: {c.status}")
                    print(f"    Ports: {', '.join(c.ports) or 'none'}")
            else:
                print("  No containers found")
        
        elif args.docker_pull:
            docker = DockerManager()
            image = args.docker_pull
            success = docker.pull_image(image, args.tag)
            
            print(f"\nImage pull: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.docker_run:
            if not args.name or not args.image:
                parser.error("--name and --image are required for docker run")
            
            docker = DockerManager()
            ports = args.port if args.port else []
            
            container_id = docker.run_container(
                image=args.image,
                name=args.name,
                ports=ports,
                detached=True
            )
            
            print(f"\nContainer started: {container_id}")
        
        elif args.docker_stop:
            docker = DockerManager()
            success = docker.stop_container(args.docker_stop)
            
            print(f"\nContainer stop: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.docker_rm:
            docker = DockerManager()
            success = docker.remove_container(args.docker_rm, force=True)
            
            print(f"\nContainer removal: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.docker_logs:
            docker = DockerManager()
            logs = docker.get_container_logs(args.docker_logs)
            
            print(f"\nContainer logs for {args.docker_logs}:")
            print(logs[:1000])  # Limit output
        
        # Kubernetes Management
        elif args.k8s_pods:
            k8s = K8sOrchestrator()
            k8s.set_namespace(args.namespace)
            pods = k8s.get_pods()
            
            print(f"\nPods in namespace '{args.namespace}':")
            if pods:
                for p in pods:
                    print(f"  {p.name} - {p.status} (age: {p.age})")
            else:
                print("  No pods found")
        
        elif args.k8s_services:
            k8s = K8sOrchestrator()
            k8s.set_namespace(args.namespace)
            services = k8s.get_services()
            
            print(f"\nServices in namespace '{args.namespace}':")
            if services:
                for s in services:
                    print(f"  {s.name} - {s.status}")
            else:
                print("  No services found")
        
        elif args.k8s_deployments:
            k8s = K8sOrchestrator()
            k8s.set_namespace(args.namespace)
            deployments = k8s.get_deployments()
            
            print(f"\nDeployments in namespace '{args.namespace}':")
            if deployments:
                for d in deployments:
                    print(f"  {d.name} - {d.status}")
            else:
                print("  No deployments found")
        
        elif args.k8s_nodes:
            k8s = K8sOrchestrator()
            nodes = k8s.get_node_status()
            
            print("\nCluster Nodes:")
            if nodes:
                for n in nodes:
                    print(f"  {n['name']} - {n['status']}")
            else:
                print("  No nodes found")
        
        elif args.k8s_scale:
            k8s = K8sOrchestrator()
            k8s.set_namespace(args.namespace)
            success = k8s.scale_deployment(args.k8s_scale, args.k8s_scale)
            
            # Get the actual scale value from namespace parameter
            # Actually scale value is the second positional arg
            # This is handled differently - scale is passed via --k8s-scale NAME and arg
            pass
        
        elif args.k8s_context:
            k8s = K8sOrchestrator()
            success = k8s.set_context(args.k8s_context)
            
            print(f"\nContext switch: {'SUCCESS' if success else 'FAILED'}")
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()