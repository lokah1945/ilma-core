"""
ILMA v4.0 — THE OMEGA COUNCIL
Mixture of Agents Architecture

A council of specialized Sub-Agents that collaborate, debate, and resolve conflicts
automatically without blocking the main Gateway.

SUB-AGENTS:
- SecOps: Security Operations (blocks risky deployments)
- Architect: System Architecture & Code Design
- Nexus: Network Infrastructure & APIs
- Creator: Content Generation & Marketing

CORE: Message Broker (Async Pub/Sub) + L5 Conflict Resolver

SUPREME ARCHITECT: ILMA v4.0 Genesis
"""

from __future__ import annotations
import asyncio
import json
import time
import uuid
import logging
import traceback
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict, deque
from abc import ABC, abstractmethod
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmegaCouncil")


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE BROKER — ASYNC PUB/SUB FOR SUB-AGENTS
# ═══════════════════════════════════════════════════════════════════════════════

class MessagePriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

@dataclass
class CouncilMessage:
    """Internal message format for agent communication."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    recipients: Set[str] = field(default_factory=set)  # empty = broadcast
    topic: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    ttl_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if message TTL has expired."""
        msg_time = datetime.fromisoformat(self.timestamp)
        age = (datetime.now() - msg_time).total_seconds()
        return age > self.ttl_seconds

class AsyncMessageBroker:
    """
    Non-blocking async message broker for Sub-Agent communication.
    Uses topic-based pub/sub with priority queuing.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._priority_queues: Dict[str, asyncio.PriorityQueue] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._dead_letter_queue: asyncio.Queue = asyncio.Queue()
        self._metrics: Dict[str, int] = defaultdict(int)
        
    async def start(self):
        """Start the message broker dispatcher."""
        if self._running:
            return
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        logger.info("[BROKER] Message broker started")
    
    async def stop(self):
        """Stop the message broker gracefully."""
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        logger.info("[BROKER] Message broker stopped")
    
    def subscribe(self, topic: str) -> asyncio.Queue:
        """Subscribe to a topic and return queue for receiving messages."""
        queue = asyncio.Queue(maxsize=100)
        with threading.Lock():
            self._subscribers[topic].append(queue)
        logger.info(f"[BROKER] Subscriber joined topic: {topic}")
        return queue
    
    def unsubscribe(self, topic: str, queue: asyncio.Queue):
        """Unsubscribe from a topic."""
        with threading.Lock():
            if queue in self._subscribers[topic]:
                self._subscribers[topic].remove(queue)
    
    async def publish(self, message: CouncilMessage):
        """Publish a message to a topic (or specific recipients)."""
        self._metrics["published"] += 1
        
        # Priority encode: (priority_value, timestamp, message_id)
        priority_val = message.priority.value
        encoded = (priority_val, message.timestamp, message.id, message)
        
        if message.recipients:
            # Direct message to specific agents
            for recipient in message.recipients:
                topic_queue = asyncio.Queue(maxsize=100)
                with threading.Lock():
                    self._subscribers[f"agent:{recipient}"].append(topic_queue)
                try:
                    await asyncio.wait_for(topic_queue.put(encoded), timeout=1.0)
                except asyncio.TimeoutError:
                    logger.warning(f"[BROKER] Queue full for agent: {recipient}")
        else:
            # Broadcast to topic subscribers
            topic = message.topic
            with threading.Lock():
                queues = list(self._subscribers.get(topic, []))
            
            for queue in queues:
                try:
                    await asyncio.wait_for(queue.put(encoded), timeout=0.1)
                except asyncio.TimeoutError:
                    logger.warning(f"[BROKER] Subscriber queue full for topic: {topic}")
    
    async def request_reply(
        self,
        topic: str,
        payload: Dict[str, Any],
        timeout: float = 30.0,
        correlation_id: Optional[str] = None
    ) -> Optional[CouncilMessage]:
        """Send request and wait for reply with correlation ID."""
        request_id = str(uuid.uuid4())
        reply_topic = f"reply:{request_id}"
        
        reply_queue = self.subscribe(reply_topic)
        
        request = CouncilMessage(
            sender="COUNCIL",
            recipients=set(),
            topic=topic,
            payload=payload,
            priority=MessagePriority.HIGH,
            correlation_id=correlation_id or request_id,
            reply_to=reply_topic,
            metadata={"request_id": request_id}
        )
        
        await self.publish(request)
        
        try:
            _, _, _, reply = await asyncio.wait_for(reply_queue.get(), timeout=timeout)
            return reply
        except asyncio.TimeoutError:
            logger.warning(f"[BROKER] Request timeout: {topic}")
            return None
        finally:
            self.unsubscribe(reply_topic, reply_queue)
    
    async def _dispatch_loop(self):
        """Background dispatcher for dead letter queue processing."""
        while self._running:
            try:
                if not self._dead_letter_queue.empty():
                    dlq_message = await asyncio.wait_for(
                        self._dead_letter_queue.get(), 
                        timeout=1.0
                    )
                    logger.error(f"[BROKER-DLQ] Processing dead letter: {dlq_message.topic}")
                    self._metrics["dead_letter"] += 1
                else:
                    await asyncio.sleep(0.1)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[BROKER] Dispatch error: {e}")
    
    def get_metrics(self) -> Dict[str, int]:
        """Get broker metrics."""
        return dict(self._metrics)


# ═══════════════════════════════════════════════════════════════════════════════
# SUB-AGENT BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class SubAgent(ABC):
    """
    Base class for all Sub-Agents in the Omega Council.
    Each agent runs asynchronously and communicates via message broker.
    """
    
    def __init__(self, name: str, broker: AsyncMessageBroker):
        self.name = name
        self.broker = broker
        self._inbox: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscriptions: List[str] = []
        self._state: Dict[str, Any] = {}
        self._capabilities: List[str] = []
        self._opinions: Dict[str, Any] = {}  # Agent's perspective on pending decisions
        self._veto_power = False
        
    @property
    def capabilities(self) -> List[str]:
        return self._capabilities
    
    @property
    def has_veto_power(self) -> bool:
        return self._veto_power
    
    async def start(self):
        """Start the agent's message processing loop."""
        if self._running:
            return
        self._running = True
        
        # Subscribe to relevant topics
        await self._subscribe_topics()
        
        # Start message processing task
        self._task = asyncio.create_task(self._process_loop())
        logger.info(f"[{self.name}] Agent started")
    
    async def stop(self):
        """Stop the agent gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._unsubscribe_topics()
        logger.info(f"[{self.name}] Agent stopped")
    
    async def _subscribe_topics(self):
        """Subscribe to relevant message topics."""
        for topic in self._get_subscription_topics():
            queue = self.broker.subscribe(topic)
            self._subscriptions.append(topic)
            logger.info(f"[{self.name}] Subscribed to: {topic}")
    
    async def _unsubscribe_topics(self):
        """Unsubscribe from all topics."""
        for topic in self._subscriptions:
            # Note: full unsubscribe requires queue reference
            pass
    
    @abstractmethod
    def _get_subscription_topics(self) -> List[str]:
        """Return list of topics this agent subscribes to."""
        pass
    
    @abstractmethod
    async def _handle_message(self, message: CouncilMessage) -> Optional[CouncilMessage]:
        """
        Handle incoming message and optionally return a reply.
        """
        pass
    
    async def _process_loop(self):
        """Main message processing loop (non-blocking)."""
        # Create a dedicated subscription queue for this agent
        agent_topic = f"agent:{self.name}"
        inbox = self.broker.subscribe(agent_topic)
        self._subscriptions.append(agent_topic)
        
        while self._running:
            try:
                # Wait for message with timeout
                priority, timestamp, msg_id, message = await asyncio.wait_for(
                    inbox.get(), 
                    timeout=1.0
                )
                
                # Check TTL
                if message.is_expired():
                    logger.warning(f"[{self.name}] Discarded expired message: {message.id}")
                    continue
                
                # Process message
                try:
                    reply = await self._handle_message(message)
                    if reply and message.reply_to:
                        reply.reply_to = message.reply_to
                        await self.broker.publish(reply)
                except Exception as e:
                    logger.error(f"[{self.name}] Error handling message: {e}")
                    logger.error(traceback.format_exc())
                    
            except asyncio.TimeoutError:
                # No message, do background processing
                await self._idle_processing()
            except Exception as e:
                logger.error(f"[{self.name}] Processing loop error: {e}")
    
    async def _idle_processing(self):
        """Background processing when no messages."""
        await asyncio.sleep(0.1)
    
    def send_opinion(self, topic: str, opinion: Dict[str, Any]):
        """Send opinion to council's shared context."""
        self._opinions[topic] = opinion
    
    def get_opinion(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get council's opinion on a topic."""
        return self._opinions.get(topic)
    
    async def broadcast(self, topic: str, payload: Dict[str, Any], priority: MessagePriority = MessagePriority.NORMAL):
        """Broadcast a message to all subscribers of a topic."""
        message = CouncilMessage(
            sender=self.name,
            topic=topic,
            payload=payload,
            priority=priority
        )
        await self.broker.publish(message)


# ═══════════════════════════════════════════════════════════════════════════════
# SECOPS AGENT — SECURITY OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class SecOpsAgent(SubAgent):
    """
    SecOps: Security Operations Agent
    - Reviews code for vulnerabilities
    - Checks infrastructure for misconfigurations
    - Can VETO risky deployments
    - Enforces security policies
    """
    
    def __init__(self, broker: AsyncMessageBroker):
        super().__init__("SecOps", broker)
        self._veto_power = True  # SecOps can block deployments
        self._capabilities = ["vuln_scan", "config_audit", "threat_intel", "compliance_check"]
        self._security_policies: Dict[str, Any] = {}
        self._blocked_items: List[Dict] = []
    
    def _get_subscription_topics(self) -> List[str]:
        return [
            "agent:SecOps",
            "topic:deployment_request",
            "topic:code_review",
            "topic:infra_change",
            "topic:security_alert"
        ]
    
    async def _handle_message(self, message: CouncilMessage) -> Optional[CouncilMessage]:
        topic = message.topic
        
        if topic == "topic:deployment_request":
            return await self._review_deployment(message)
        elif topic == "topic:code_review":
            return await self._review_code(message)
        elif topic == "topic:infra_change":
            return await self._review_infra_change(message)
        elif "agent:SecOps" in topic:
            return await self._handle_direct_message(message)
        
        return None
    
    async def _review_deployment(self, message: CouncilMessage) -> CouncilMessage:
        """Review deployment request and potentially veto."""
        payload = message.payload
        deployment_id = payload.get("deployment_id", "unknown")
        code_hash = payload.get("code_hash", "")
        target_env = payload.get("target_environment", "unknown")
        
        logger.info(f"[SecOps] Reviewing deployment: {deployment_id}")
        
        # Simulate security scanning
        await asyncio.sleep(0.5)
        
        # Check for security issues
        issues = await self._scan_for_vulnerabilities(code_hash, target_env)
        
        if issues.get("critical"):
            # VETO the deployment
            veto = CouncilMessage(
                sender="SecOps",
                topic="topic:deployment_veto",
                payload={
                    "deployment_id": deployment_id,
                    "reason": "CRITICAL_SECURITY_VULNERABILITY",
                    "vulnerabilities": issues.get("critical", []),
                    "severity": "CRITICAL",
                    "remediation": issues.get("remediation", [])
                },
                priority=MessagePriority.CRITICAL
            )
            self._blocked_items.append({"deployment_id": deployment_id, "reason": "critical"})
            return veto
        
        # Pass with warnings
        approval = CouncilMessage(
            sender="SecOps",
            topic="topic:deployment_approved",
            payload={
                "deployment_id": deployment_id,
                "warnings": issues.get("warnings", []),
                "security_score": issues.get("score", 85),
                "scan_id": str(uuid.uuid4())
            },
            priority=MessagePriority.HIGH
        )
        return approval
    
    async def _review_code(self, message: CouncilMessage) -> CouncilMessage:
        """Review code for security issues."""
        payload = message.payload
        code = payload.get("code", "")
        language = payload.get("language", "unknown")
        
        issues = self._static_analysis(code, language)
        
        return CouncilMessage(
            sender="SecOps",
            topic="topic:code_review_complete",
            payload={
                "review_id": str(uuid.uuid4()),
                "issues": issues,
                "scan_type": "static_analysis"
            },
            priority=MessagePriority.NORMAL
        )
    
    async def _review_infra_change(self, message: CouncilMessage) -> CouncilMessage:
        """Review infrastructure changes."""
        payload = message.payload
        changes = payload.get("changes", [])
        
        violations = []
        for change in changes:
            if self._check_compliance(change):
                continue
            else:
                violations.append(change)
        
        return CouncilMessage(
            sender="SecOps",
            topic="topic:infra_change_reviewed",
            payload={"violations": violations, "compliant": len(violations) == 0},
            priority=MessagePriority.HIGH
        )
    
    async def _handle_direct_message(self, message: CouncilMessage) -> CouncilMessage:
        """Handle direct messages to SecOps."""
        action = message.payload.get("action")
        
        if action == "get_blocked":
            return CouncilMessage(
                sender="SecOps",
                topic=message.reply_to or "topic:direct_reply",
                payload={"blocked_items": self._blocked_items}
            )
        
        return None
    
    async def _scan_for_vulnerabilities(self, code_hash: str, env: str) -> Dict[str, Any]:
        """Simulate vulnerability scanning."""
        # In production: integrate with actual security tools
        return {
            "critical": [],
            "warnings": ["Update TLS version to 1.3", "Enable CSP headers"],
            "score": 85,
            "remediation": ["Run npm audit fix", "Update OpenSSL"]
        }
    
    def _static_analysis(self, code: str, language: str) -> List[Dict]:
        """Perform static code analysis for security issues."""
        issues = []
        
        # Check for common vulnerabilities
        dangerous_patterns = [
            (r"eval\s*\(", "Code injection via eval()"),
            (r"exec\s*\(", "Command injection via exec()"),
            (r"system\s*\(", "Shell command injection"),
            (r"SELECT.*FROM.*WHERE", "Potential SQL injection"),
            (r"innerHTML\s*=", "XSS via innerHTML"),
            (r"password\s*=\s*['\"][^'\"]{8}['\"]", "Hardcoded password"),
        ]
        
        for pattern, desc in dangerous_patterns:
            if pattern.lower() in code.lower():
                issues.append({"severity": "HIGH", "description": desc, "pattern": pattern})
        
        return issues
    
    def _check_compliance(self, change: Dict) -> bool:
        """Check if infrastructure change is compliant."""
        # Simplified compliance check
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# ARCHITECT AGENT — SYSTEM ARCHITECTURE & CODE DESIGN
# ═══════════════════════════════════════════════════════════════════════════════

class ArchitectAgent(SubAgent):
    """
    Architect: System Architecture Agent
    - Designs system components
    - Reviews code architecture
    - Proposes infrastructure changes
    - Can REQUEST deployments (needs SecOps approval)
    """
    
    def __init__(self, broker: AsyncMessageBroker):
        super().__init__("Architect", broker)
        self._capabilities = ["system_design", "code_review", "refactoring", "performance_tuning"]
        self._pending_deployments: List[Dict] = []
        self._design_patterns: Dict[str, Any] = {}
    
    def _get_subscription_topics(self) -> List[str]:
        return [
            "agent:Architect",
            "topic:design_request",
            "topic:deployment_veto",
            "topic:deployment_approved",
            "topic:code_review_complete"
        ]
    
    async def _handle_message(self, message: CouncilMessage) -> Optional[CouncilMessage]:
        topic = message.topic
        
        if topic == "topic:design_request":
            return await self._design_system(message)
        elif topic == "topic:deployment_veto":
            return await self._handle_veto(message)
        elif topic == "topic:deployment_approved":
            return await self._handle_approval(message)
        elif "agent:Architect" in topic:
            return await self._handle_direct_message(message)
        
        return None
    
    async def _design_system(self, message: CouncilMessage) -> CouncilMessage:
        """Design a system based on requirements."""
        payload = message.payload
        requirements = payload.get("requirements", "")
        
        logger.info(f"[Architect] Designing system for: {requirements[:50]}...")
        
        # Generate architecture design
        design = {
            "components": ["API Gateway", "Auth Service", "Core Engine", "Database"],
            "patterns": ["Microservices", "Event-Driven", "CQRS"],
            "tech_stack": ["FastAPI", "PostgreSQL", "Redis", "Kubernetes"],
            "estimated_complexity": "MEDIUM"
        }
        
        return CouncilMessage(
            sender="Architect",
            topic="topic:design_complete",
            payload={"design": design, "request_id": payload.get("request_id")},
            priority=MessagePriority.HIGH
        )
    
    async def _handle_veto(self, message: CouncilMessage) -> CouncilMessage:
        """Handle SecOps veto - resolve conflict."""
        payload = message.payload
        deployment_id = payload.get("deployment_id")
        reason = payload.get("reason")
        
        logger.warning(f"[Architect] Deployment {deployment_id} was vetoed: {reason}")
        
        # Generate remediation plan
        remediation = await self._create_remediation_plan(payload)
        
        return CouncilMessage(
            sender="Architect",
            topic="topic:remediation_plan",
            payload={
                "deployment_id": deployment_id,
                "remediation": remediation,
                "original_veto_reason": reason
            },
            priority=MessagePriority.HIGH
        )
    
    async def _handle_approval(self, message: CouncilMessage) -> Optional[CouncilMessage]:
        """Handle SecOps approval and proceed with deployment."""
        payload = message.payload
        deployment_id = payload.get("deployment_id")
        
        logger.info(f"[Architect] Deployment {deployment_id} approved")
        
        # Proceed with deployment orchestration
        return CouncilMessage(
            sender="Architect",
            topic="topic:execute_deployment",
            payload={"deployment_id": deployment_id, "approved": True},
            priority=MessagePriority.CRITICAL
        )
    
    async def _handle_direct_message(self, message: CouncilMessage) -> CouncilMessage:
        """Handle direct messages to Architect."""
        action = message.payload.get("action")
        
        if action == "request_deployment":
            # Send to SecOps for approval
            deployment_request = CouncilMessage(
                sender="Architect",
                recipients={"SecOps"},
                topic="topic:deployment_request",
                payload=message.payload.get("deployment_data", {}),
                priority=MessagePriority.HIGH
            )
            await self.broker.publish(deployment_request)
            return CouncilMessage(
                sender="Architect",
                topic=message.reply_to or "topic:direct_reply",
                payload={"status": "pending_approval", "deployment_id": message.payload.get("deployment_data", {}).get("deployment_id")}
            )
        
        return None
    
    async def _create_remediation_plan(self, veto_payload: Dict) -> Dict[str, Any]:
        """Create plan to fix security issues."""
        vulnerabilities = veto_payload.get("vulnerabilities", [])
        
        plan = []
        for vuln in vulnerabilities:
            plan.append({
                "fix": f"Apply security patch for: {vuln}",
                "estimated_time": "15 minutes",
                "verification": "Re-run SecOps scan"
            })
        
        return {"steps": plan, "total_time": "30 minutes"}


# ═══════════════════════════════════════════════════════════════════════════════
# NEXUS AGENT — NETWORK INFRASTRUCTURE & APIs
# ═══════════════════════════════════════════════════════════════════════════════

class NexusAgent(SubAgent):
    """
    Nexus: Network Infrastructure & API Agent
    - Manages network configuration
    - Monitors API endpoints
    - Handles service mesh
    - Coordinates with Cloud providers
    """
    
    def __init__(self, broker: AsyncMessageBroker):
        super().__init__("Nexus", broker)
        self._capabilities = ["network_config", "api_gateway", "load_balancing", "dns_management", "ssl_certs"]
        self._endpoints: Dict[str, Dict] = {}
        self._health_status: Dict[str, str] = {}
    
    def _get_subscription_topics(self) -> List[str]:
        return [
            "agent:Nexus",
            "topic:network_change",
            "topic:execute_deployment",
            "topic:infra_change",
            "topic:health_check"
        ]
    
    async def _handle_message(self, message: CouncilMessage) -> Optional[CouncilMessage]:
        topic = message.topic
        
        if topic == "topic:network_change":
            return await self._configure_network(message)
        elif topic == "topic:execute_deployment":
            return await self._prepare_network_for_deployment(message)
        elif topic == "topic:health_check":
            return await self._perform_health_check(message)
        elif "agent:Nexus" in topic:
            return await self._handle_direct_message(message)
        
        return None
    
    async def _configure_network(self, message: CouncilMessage) -> CouncilMessage:
        """Configure network based on requirements."""
        payload = message.payload
        config_type = payload.get("type", "unknown")
        
        logger.info(f"[Nexus] Configuring network: {config_type}")
        
        # Simulate network configuration
        await asyncio.sleep(0.3)
        
        return CouncilMessage(
            sender="Nexus",
            topic="topic:network_configured",
            payload={
                "type": config_type,
                "status": "applied",
                "config_id": str(uuid.uuid4())
            },
            priority=MessagePriority.NORMAL
        )
    
    async def _prepare_network_for_deployment(self, message: CouncilMessage) -> CouncilMessage:
        """Prepare network for deployment."""
        payload = message.payload
        deployment_id = payload.get("deployment_id")
        
        logger.info(f"[Nexus] Preparing network for deployment: {deployment_id}")
        
        # Configure load balancer, DNS, SSL
        await asyncio.sleep(0.2)
        
        return CouncilMessage(
            sender="Nexus",
            topic="topic:network_ready",
            payload={
                "deployment_id": deployment_id,
                "dns_configured": True,
                "ssl_ready": True,
                "load_balancer_configured": True
            },
            priority=MessagePriority.HIGH
        )
    
    async def _perform_health_check(self, message: CouncilMessage) -> CouncilMessage:
        """Perform health check on endpoints."""
        payload = message.payload
        target = payload.get("target", "all")
        
        status = "healthy" if target != "failing" else "degraded"
        
        return CouncilMessage(
            sender="Nexus",
            topic="topic:health_status",
            payload={
                "target": target,
                "status": status,
                "latency_ms": 45,
                "uptime_percent": 99.9
            },
            priority=MessagePriority.NORMAL
        )
    
    async def _handle_direct_message(self, message: CouncilMessage) -> CouncilMessage:
        """Handle direct messages to Nexus."""
        action = message.payload.get("action")
        
        if action == "get_endpoints":
            return CouncilMessage(
                sender="Nexus",
                topic=message.reply_to or "topic:direct_reply",
                payload={"endpoints": self._endpoints}
            )
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CREATOR AGENT — CONTENT GENERATION & MARKETING
# ═══════════════════════════════════════════════════════════════════════════════

class CreatorAgent(SubAgent):
    """
    Creator: Content Generation & Marketing Agent
    - Generates blog posts, documentation
    - Creates marketing copy
    - Manages SEO optimization
    - Coordinates content calendar
    """
    
    def __init__(self, broker: AsyncMessageBroker):
        super().__init__("Creator", broker)
        self._capabilities = ["content_generation", "seo_optimization", "documentation", "copywriting"]
        self._content_queue: List[Dict] = []
        self._published_content: List[Dict] = []
    
    def _get_subscription_topics(self) -> List[str]:
        return [
            "agent:Creator",
            "topic:content_request",
            "topic:deployment_approved",
            "topic:new_features"
        ]
    
    async def _handle_message(self, message: CouncilMessage) -> Optional[CouncilMessage]:
        topic = message.topic
        
        if topic == "topic:content_request":
            return await self._generate_content(message)
        elif topic == "topic:deployment_approved":
            return await self._create_announcement(message)
        elif topic == "topic:new_features":
            return await self._document_features(message)
        elif "agent:Creator" in topic:
            return await self._handle_direct_message(message)
        
        return None
    
    async def _generate_content(self, message: CouncilMessage) -> CouncilMessage:
        """Generate content based on brief."""
        payload = message.payload
        content_type = payload.get("type", "blog_post")
        topic = payload.get("topic", "")
        keywords = payload.get("keywords", [])
        
        logger.info(f"[Creator] Generating {content_type} about: {topic}")
        
        # Simulate content generation
        await asyncio.sleep(0.5)
        
        content = {
            "title": f"How {topic} Transformed Our Business",
            "body": f"[Generated 2000-word article about {topic}]",
            "seo_score": 95,
            "read_time_minutes": 8,
            "keywords": keywords
        }
        
        self._published_content.append(content)
        
        return CouncilMessage(
            sender="Creator",
            topic="topic:content_created",
            payload={"content": content, "content_id": str(uuid.uuid4())},
            priority=MessagePriority.NORMAL
        )
    
    async def _create_announcement(self, message: CouncilMessage) -> CouncilMessage:
        """Create announcement for successful deployment."""
        payload = message.payload
        deployment_id = payload.get("deployment_id")
        
        announcement = {
            "type": "announcement",
            "title": f"New Feature Deployed: {deployment_id}",
            "message": "We're excited to announce a new feature deployment!"
        }
        
        return CouncilMessage(
            sender="Creator",
            topic="topic:announcement_ready",
            payload=announcement,
            priority=MessagePriority.LOW
        )
    
    async def _document_features(self, message: CouncilMessage) -> CouncilMessage:
        """Document new features."""
        payload = message.payload
        features = payload.get("features", [])
        
        docs = []
        for feature in features:
            docs.append({
                "feature": feature,
                "documentation": f"Auto-generated docs for {feature}"
            })
        
        return CouncilMessage(
            sender="Creator",
            topic="topic:features_documented",
            payload={"docs": docs},
            priority=MessagePriority.NORMAL
        )
    
    async def _handle_direct_message(self, message: CouncilMessage) -> CouncilMessage:
        """Handle direct messages to Creator."""
        action = message.payload.get("action")
        
        if action == "get_content":
            return CouncilMessage(
                sender="Creator",
                topic=message.reply_to or "topic:direct_reply",
                payload={"published": self._published_content}
            )
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# L5 CONFLICT RESOLVER — AUTOMATED MEDIATION
# ═══════════════════════════════════════════════════════════════════════════════

class ConflictType(Enum):
    SECURITY_VS_SPEED = "security_vs_speed"
    ARCHITECTURE_VS_PRACTICALITY = "architecture_vs_practicality"
    CREATIVE_VS_BRAND = "creative_vs_brand"
    RESOURCE_CONTENTION = "resource_contention"
    POLICY_VIOLATION = "policy_violation"

@dataclass
class Conflict:
    id: str
    conflict_type: ConflictType
    parties: List[str]
    issue: str
    party_positions: Dict[str, str]
    stakes: str
    created_at: str

class L5ConflictResolver:
    """
    L5 Autonomous Orchestrator's Conflict Resolution Engine.
    Automatically mediates disputes between Sub-Agents.
    """
    
    def __init__(self, broker: AsyncMessageBroker):
        self.broker = broker
        self._active_conflicts: Dict[str, Conflict] = {}
        self._resolution_history: List[Dict] = []
        self._resolution_strategies: Dict[ConflictType, Callable] = {
            ConflictType.SECURITY_VS_SPEED: self._resolve_security_vs_speed,
            ConflictType.ARCHITECTURE_VS_PRACTICALITY: self._resolve_arch_vs_practical,
            ConflictType.CREATIVE_VS_BRAND: self._resolve_creative_vs_brand,
            ConflictType.RESOURCE_CONTENTION: self._resolve_resource_contention,
            ConflictType.POLICY_VIOLATION: self._resolve_policy_violation,
        }
    
    async def register_conflict(self, conflict: Conflict) -> str:
        """Register a new conflict for resolution."""
        self._active_conflicts[conflict.id] = conflict
        logger.info(f"[L5-RESOLVER] Conflict registered: {conflict.id} ({conflict.conflict_type.value})")
        
        # Trigger automatic resolution
        asyncio.create_task(self._resolve_conflict(conflict.id))
        
        return conflict.id
    
    async def _resolve_conflict(self, conflict_id: str):
        """Automatically resolve a conflict."""
        conflict = self._active_conflicts.get(conflict_id)
        if not conflict:
            return
        
        logger.info(f"[L5-RESOLVER] Resolving conflict: {conflict_id}")
        
        # Select resolution strategy
        strategy = self._resolution_strategies.get(
            conflict.conflict_type, 
            self._default_resolution
        )
        
        # Execute resolution
        resolution = await strategy(conflict)
        
        # Store resolution
        self._resolution_history.append({
            "conflict_id": conflict_id,
            "resolution": resolution,
            "timestamp": datetime.now().isoformat()
        })
        
        # Remove from active
        del self._active_conflicts[conflict_id]
        
        # Broadcast resolution
        resolution_msg = CouncilMessage(
            sender="L5-Resolver",
            topic="topic:conflict_resolved",
            payload={
                "conflict_id": conflict_id,
                "resolution": resolution,
                "affected_parties": conflict.parties
            },
            priority=MessagePriority.HIGH
        )
        await self.broker.publish(resolution_msg)
    
    async def _resolve_security_vs_speed(self, conflict: Conflict) -> Dict[str, Any]:
        """
        Resolve: Architect wants fast deployment, SecOps blocks for security.
        
        Strategy: Security wins. Create expedited remediation path.
        """
        logger.info("[L5-RESOLVER] SECURITY VS SPEED: Security takes precedence")
        
        return {
            "decision": "SECURITY_PREVAILS",
            "rationale": "Security vulnerabilities cannot be traded for speed in production",
            "remediation_path": {
                "step_1": "Architect creates remediation plan (max 2 hours)",
                "step_2": "SecOps reviews remediation (max 1 hour)",
                "step_3": "Parallel security scan during deployment window",
                "step_4": "If critical: deployment delayed. If medium/low: deployed with monitoring"
            },
            "compromise": {
                "Architect": "Faster path after remediation: 3 hours instead of 24 hours",
                "SecOps": "Acceptable risk level: MEDIUM or below"
            },
            "escalation": "If SecOps and Architect disagree after 2 rounds, escalate to Bos"
        }
    
    async def _resolve_arch_vs_practical(self, conflict: Conflict) -> Dict[str, Any]:
        """
        Resolve: Architect wants ideal architecture, practical constraints exist.
        
        Strategy: Pragmatic compromise - implement in phases.
        """
        logger.info("[L5-RESOLVER] ARCHITECTURE VS PRACTICAL: Pragmatic phases")
        
        return {
            "decision": "PHASED_IMPLEMENTATION",
            "rationale": "Ideal architecture achieved through incremental practical steps",
            "phases": [
                {"phase": 1, "timeline": "immediate", "scope": "Core infrastructure only"},
                {"phase": 2, "timeline": "1 month", "scope": "Add observability layer"},
                {"phase": 3, "timeline": "3 months", "scope": "Full architectural vision"}
            ],
            "compromise": {
                "Architect": "Accept technical debt with documented backlog",
                "Practitioner": "Follow architectural guidance for new components"
            }
        }
    
    async def _resolve_creative_vs_brand(self, conflict: Conflict) -> Dict[str, Any]:
        """Resolve creative freedom vs brand guidelines conflict."""
        logger.info("[L5-RESOLVER] CREATIVE VS BRAND: Brand guidelines prevail")
        
        return {
            "decision": "BRAND_GUIDELINES_PREVAIL",
            "rationale": "Brand consistency essential for market positioning",
            "creative_freedom": "Allowed within brand framework",
            "solution": "Creator revises within brand guidelines, maximum 2 revision rounds"
        }
    
    async def _resolve_resource_contention(self, conflict: Conflict) -> Dict[str, Any]:
        """Resolve resource contention between agents."""
        logger.info("[L5-RESOLVER] RESOURCE CONTENTION: Priority-based allocation")
        
        # Priority ranking
        priority_order = {"SecOps": 1, "Architect": 2, "Nexus": 3, "Creator": 4}
        
        sorted_parties = sorted(
            conflict.parties, 
            key=lambda p: priority_order.get(p, 99)
        )
        
        return {
            "decision": "PRIORITY_ALLOCATION",
            "allocation": {party: i+1 for i, party in enumerate(sorted_parties)},
            "rationale": "Security > Architecture > Infrastructure > Content",
            "time_sharing": "If concurrent needed, high-priority gets dedicated time"
        }
    
    async def _resolve_policy_violation(self, conflict: Conflict) -> Dict[str, Any]:
        """Resolve policy violation conflicts."""
        logger.info("[L5-RESOLVER] POLICY VIOLATION: Zero tolerance")
        
        return {
            "decision": "POLICY_VIOLATION_BLOCKED",
            "rationale": "Policy violations cannot be compromised",
            "action": "Operation blocked until policy compliance achieved",
            "appeal": "Only Bos can override policy violations"
        }
    
    async def _default_resolution(self, conflict: Conflict) -> Dict[str, Any]:
        """Default resolution when no specific strategy matches."""
        return {
            "decision": "L5_ARBITRATION",
            "rationale": "Complex trade-off, L5 chooses balanced approach",
            "solution": "Both parties implement 70% of their requirements"
        }


# ═══════════════════════════════════════════════════════════════════════════════
# THE OMEGA COUNCIL ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class OmegaCouncilOrchestrator:
    """
    THE OMEGA COUNCIL — Main orchestrator that manages all Sub-Agents.
    
    Responsibilities:
    - Initialize and manage Sub-Agent lifecycle
    - Route messages between agents
    - Trigger conflict resolution when needed
    - Monitor council health
    - Execute high-level missions
    """
    
    def __init__(self):
        self.broker = AsyncMessageBroker()
        self.agents: Dict[str, SubAgent] = {}
        self.conflict_resolver = L5ConflictResolver(self.broker)
        self._running = False
        self._metrics: Dict[str, Any] = {
            "messages_processed": 0,
            "conflicts_resolved": 0,
            "deployments_approved": 0,
            "deployments_blocked": 0
        }
        
    async def initialize(self):
        """Initialize the Omega Council."""
        logger.info("[COUNCIL] Initializing Omega Council...")
        
        # Start message broker
        await self.broker.start()
        
        # Initialize Sub-Agents
        self.agents["SecOps"] = SecOpsAgent(self.broker)
        self.agents["Architect"] = ArchitectAgent(self.broker)
        self.agents["Nexus"] = NexusAgent(self.broker)
        self.agents["Creator"] = CreatorAgent(self.broker)
        
        # Start all agents
        for agent in self.agents.values():
            await agent.start()
        
        # Subscribe to conflict notifications
        self.broker.subscribe("topic:deployment_veto")
        self.broker.subscribe("topic:conflict_resolved")
        
        self._running = True
        logger.info("[COUNCIL] Omega Council initialized with 4 Sub-Agents")
    
    async def shutdown(self):
        """Shutdown the Omega Council gracefully."""
        logger.info("[COUNCIL] Shutting down Omega Council...")
        
        self._running = False
        
        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()
        
        # Stop broker
        await self.broker.stop()
        
        logger.info("[COUNCIL] Omega Council shutdown complete")
    
    async def execute_mission(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a high-level mission through the council.
        
        Mission format:
        {
            "type": "deploy_feature",
            "payload": {
                "feature": "new_api_endpoint",
                "code": "...",
                "target_env": "production"
            }
        }
        """
        mission_type = mission.get("type")
        logger.info(f"[COUNCIL] Executing mission: {mission_type}")
        
        if mission_type == "deploy_feature":
            return await self._mission_deploy_feature(mission["payload"])
        elif mission_type == "security_audit":
            return await self._mission_security_audit(mission["payload"])
        elif mission_type == "create_content":
            return await self._mission_create_content(mission["payload"])
        else:
            return {"success": False, "error": f"Unknown mission type: {mission_type}"}
    
    async def _mission_deploy_feature(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deploy a feature through the council workflow:
        1. Architect reviews design
        2. SecOps approves security
        3. Nexus prepares network
        4. Creator announces
        """
        deployment_id = str(uuid.uuid4())
        payload["deployment_id"] = deployment_id
        
        # Step 1: Architect requests deployment
        architect_msg = CouncilMessage(
            sender="COUNCIL",
            recipients={"Architect"},
            topic="agent:Architect",
            payload={
                "action": "request_deployment",
                "deployment_data": payload
            },
            priority=MessagePriority.HIGH
        )
        await self.broker.publish(architect_msg)
        
        # Step 2: Wait for SecOps approval
        secops_response = await self.broker.request_reply(
            "topic:deployment_request",
            payload,
            timeout=60.0,
            correlation_id=deployment_id
        )
        
        if not secops_response:
            return {"success": False, "error": "SecOps review timeout"}
        
        if secops_response.topic == "topic:deployment_veto":
            self._metrics["deployments_blocked"] += 1
            
            # Trigger conflict resolution
            conflict = Conflict(
                id=str(uuid.uuid4()),
                conflict_type=ConflictType.SECURITY_VS_SPEED,
                parties=["Architect", "SecOps"],
                issue=f"Deployment {deployment_id} blocked",
                party_positions={
                    "Architect": "Wants fast deployment for business value",
                    "SecOps": "Security vulnerabilities must be fixed first"
                },
                stakes="Production security vs time-to-market",
                created_at=datetime.now().isoformat()
            )
            await self.conflict_resolver.register_conflict(conflict)
            
            return {
                "success": False,
                "deployment_id": deployment_id,
                "blocked": True,
                "reason": secops_response.payload.get("reason"),
                "conflict_id": conflict.id
            }
        
        # Step 3: Nexus prepares network
        nexus_response = await self.broker.request_reply(
            "topic:network_change",
            {"type": "deployment_prep", "deployment_id": deployment_id},
            timeout=30.0
        )
        
        # Step 4: Creator announces
        await self.broker.publish(CouncilMessage(
            sender="COUNCIL",
            topic="topic:new_features",
            payload={"deployment_id": deployment_id, "feature": payload.get("feature")},
            priority=MessagePriority.LOW
        ))
        
        self._metrics["deployments_approved"] += 1
        
        return {
            "success": True,
            "deployment_id": deployment_id,
            "status": "deployed",
            "security_score": secops_response.payload.get("security_score", 100)
        }
    
    async def _mission_security_audit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a full security audit through the council."""
        audit_id = str(uuid.uuid4())
        
        # Request SecOps audit
        secops_response = await self.broker.request_reply(
            "topic:code_review",
            {"code": payload.get("code", ""), "language": payload.get("language", "python")},
            timeout=60.0,
            correlation_id=audit_id
        )
        
        return {
            "success": True,
            "audit_id": audit_id,
            "results": secops_response.payload if secops_response else {}
        }
    
    async def _mission_create_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create content through the council."""
        content_response = await self.broker.request_reply(
            "topic:content_request",
            payload,
            timeout=60.0
        )
        
        return {
            "success": True,
            "content": content_response.payload.get("content") if content_response else None
        }
    
    def get_council_status(self) -> Dict[str, Any]:
        """Get current status of the Omega Council."""
        agent_status = {}
        for name, agent in self.agents.items():
            agent_status[name] = {
                "running": agent._running,
                "capabilities": agent._capabilities,
                "veto_power": agent.has_veto_power
            }
        
        return {
            "council_status": "operational" if self._running else "shutdown",
            "agents": agent_status,
            "active_conflicts": len(self.conflict_resolver._active_conflicts),
            "metrics": self._metrics,
            "broker_metrics": self.broker.get_metrics()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — DEMO
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Demo: Omega Council Orchestrator"""
    print("=" * 80)
    print("ILMA v4.0 — THE OMEGA COUNCIL (Mixture of Agents)")
    print("=" * 80)
    
    # Initialize council
    council = OmegaCouncilOrchestrator()
    await council.initialize()
    
    # Show council status
    status = council.get_council_status()
    print(f"\n[COUNCIL STATUS]")
    for agent, info in status["agents"].items():
        print(f"  {agent}: {'✅' if info['running'] else '❌'} (veto: {info['veto_power']})")
    
    # Test 1: Successful deployment (bypass security for demo)
    print("\n[TEST 1] Simulating deployment workflow...")
    
    # Test 2: Conflict scenario (Architect vs SecOps)
    print("\n[TEST 2] Testing conflict resolution...")
    
    conflict = Conflict(
        id="test-conflict-001",
        conflict_type=ConflictType.SECURITY_VS_SPEED,
        parties=["Architect", "SecOps"],
        issue="Deployment blocked due to SQL injection vulnerability",
        party_positions={
            "Architect": "Deployment needed for product launch tomorrow",
            "SecOps": "Critical SQL injection must be fixed before deployment"
        },
        stakes="Product launch vs Production security",
        created_at=datetime.now().isoformat()
    )
    
    await council.conflict_resolver.register_conflict(conflict)
    await asyncio.sleep(1)  # Let resolution process
    
    print(f"\n[RESOLUTION RESULT]")
    if council.conflict_resolver._resolution_history:
        last_res = council.conflict_resolver._resolution_history[-1]
        print(f"  Decision: {last_res['resolution']['decision']}")
        print(f"  Rationale: {last_res['resolution']['rationale']}")
    
    # Test 3: Get council status
    print("\n[TEST 3] Final council status:")
    final_status = council.get_council_status()
    print(f"  Messages processed: {final_status['metrics']['messages_processed']}")
    print(f"  Conflicts resolved: {final_status['metrics']['conflicts_resolved']}")
    print(f"  Deployments approved: {final_status['metrics']['deployments_approved']}")
    print(f"  Deployments blocked: {final_status['metrics']['deployments_blocked']}")
    
    # Shutdown
    await council.shutdown()
    
    print("\n" + "=" * 80)
    print("OMEGA COUNCIL DEMO COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
