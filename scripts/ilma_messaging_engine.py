#!/usr/bin/env python3
"""
ILMA Messaging Engine - Send messages via Telegram and Discord.

This module provides:
- TelegramAdapter: Send/receive Telegram messages
- DiscordAdapter: Send/receive Discord messages  
- MessageQueue: Queue and process messages asynchronously

Usage:
    python ilma_messaging_engine.py --platform telegram --message "Hello" --chat-id 123456
    python ilma_messaging_engine.py --platform discord --message "Hello" --channel-id abc
    python ilma_messaging_engine.py --queue --batch messages.json

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class MessageStatus(Enum):
    """Message delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Message:
    """Represents a message to be sent."""
    message_id: str
    platform: str
    content: str
    recipient: str  # chat_id for Telegram, channel_id for Discord
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None
    delivered_at: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class MessageResponse:
    """Response from message delivery attempt."""
    success: bool
    message_id: str
    platform_message_id: Optional[str] = None
    error: Optional[str] = None
    response_data: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter:
    """Base class for platform adapters."""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def send(self, message: Message) -> MessageResponse:
        """Send a message. Must be implemented by subclasses."""
        raise NotImplementedError

    def format_message(self, content: str, metadata: Dict[str, Any]) -> str:
        """Format message content with metadata."""
        return content


class TelegramAdapter(BaseAdapter):
    """
    Adapter for Telegram Bot API.
    
    Features:
    - Send text messages
    - Send photos/documents
    - Reply to messages
    - Parse mode (Markdown/HTML)
    - Inline keyboard support
    """

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(
        self,
        api_token: Optional[str] = None,
        parse_mode: str = "Markdown"
    ):
        """
        Initialize Telegram adapter.
        
        Args:
            api_token: Telegram bot token
            parse_mode: Message parse mode (Markdown, HTML, or None)
        """
        super().__init__(api_token)
        self.parse_mode = parse_mode
        self.api_base = f"{self.BASE_URL}{api_token}" if api_token else ""

    def send(self, message: Message) -> MessageResponse:
        """
        Send a message via Telegram.
        
        Args:
            message: Message to send
            
        Returns:
            MessageResponse with delivery status
        """
        if not self.api_token:
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error="Telegram API token not configured"
            )

        try:
            # Build request
            url = f"{self.api_base}/sendMessage"
            
            data = {
                "chat_id": message.recipient,
                "text": message.content,
                "parse_mode": self.parse_mode
            }
            
            # Add reply markup if present
            if message.metadata.get("reply_markup"):
                data["reply_markup"] = json.dumps(message.metadata["reply_markup"])
            
            # Add reply_to_message_id if present
            if message.metadata.get("reply_to_message_id"):
                data["reply_to_message_id"] = message.metadata["reply_to_message_id"]
            
            # Make request
            request = Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                if result.get("ok"):
                    msg_data = result.get("result", {})
                    return MessageResponse(
                        success=True,
                        message_id=message.message_id,
                        platform_message_id=str(msg_data.get("message_id")),
                        response_data=msg_data
                    )
                else:
                    return MessageResponse(
                        success=False,
                        message_id=message.message_id,
                        error=result.get("description", "Unknown error")
                    )
                    
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else "{}"
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get("description", str(e))
            except RequestException:
                error_msg = str(e)
            
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error=f"HTTP {e.code}: {error_msg}"
            )
        except URLError as e:
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error=f"URL error: {e.reason}"
            )
        except Exception as e:
            self.logger.exception(f"Error sending Telegram message: {e}")
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error=str(e)
            )

    def send_photo(
        self,
        recipient: str,
        photo_url: str,
        caption: Optional[str] = None
    ) -> MessageResponse:
        """Send a photo via Telegram."""
        if not self.api_token:
            return MessageResponse(success=False, message_id="", error="API token not configured")

        try:
            url = f"{self.api_base}/sendPhoto"
            data = {
                "chat_id": recipient,
                "photo": photo_url
            }
            if caption:
                data["caption"] = caption

            request = Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("ok"):
                    return MessageResponse(
                        success=True,
                        message_id="",
                        platform_message_id=str(result["result"]["message_id"])
                    )
                return MessageResponse(
                    success=False,
                    message_id="",
                    error=result.get("description", "Failed to send photo")
                )
        except Exception as e:
            return MessageResponse(success=False, message_id="", error=str(e))

    def get_updates(self, offset: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get updates from Telegram."""
        if not self.api_token:
            return []

        try:
            url = f"{self.api_base}/getUpdates"
            params = {"limit": limit}
            if offset:
                params["offset"] = offset
                
            full_url = f"{url}?{json.dumps(params)}"
            request = Request(full_url, method="GET")
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("ok"):
                    return result.get("result", [])
                return []
        except Exception as e:
            self.logger.error(f"Error getting updates: {e}")
            return []


class DiscordAdapter(BaseAdapter):
    """
    Adapter for Discord webhooks.
    
    Features:
    - Send embeds
    - Send files (via URL)
    - Format messages with embeds
    - Rate limit handling
    """

    DISCORD_MAX_MESSAGE_LENGTH = 2000

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord adapter.
        
        Args:
            webhook_url: Discord webhook URL
        """
        super().__init__()
        self.webhook_url = webhook_url
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 0

    def send(self, message: Message) -> MessageResponse:
        """
        Send a message via Discord webhook.
        
        Args:
            message: Message to send
            
        Returns:
            MessageResponse with delivery status
        """
        if not self.webhook_url:
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error="Discord webhook URL not configured"
            )

        try:
            # Check rate limits
            if time.time() < self.rate_limit_reset:
                return MessageResponse(
                    success=False,
                    message_id=message.message_id,
                    error="Rate limited, retry after reset"
                )

            # Build payload
            payload = self._build_payload(message)
            
            request = Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                # Discord returns 204 No Content on success for webhooks
                if response.status == 204:
                    return MessageResponse(
                        success=True,
                        message_id=message.message_id,
                        platform_message_id=message.message_id  # Webhooks don't return IDs
                    )
                else:
                    result = response.read().decode("utf-8")
                    return MessageResponse(
                        success=False,
                        message_id=message.message_id,
                        error=f"Unexpected response: {response.status}"
                    )

        except HTTPError as e:
            if e.code == 429:  # Rate limited
                self.rate_limit_reset = time.time() + 5
                return MessageResponse(
                    success=False,
                    message_id=message.message_id,
                    error="Rate limited by Discord"
                )
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error=f"HTTP {e.code}"
            )
        except URLError as e:
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error=f"URL error: {e.reason}"
            )
        except Exception as e:
            self.logger.exception(f"Error sending Discord message: {e}")
            return MessageResponse(
                success=False,
                message_id=message.message_id,
                error=str(e)
            )

    def _build_payload(self, message: Message) -> Dict[str, Any]:
        """Build Discord webhook payload."""
        # Handle long messages
        content = message.content
        if len(content) > self.DISCORD_MAX_MESSAGE_LENGTH:
            content = content[:self.DISCORD_MAX_MESSAGE_LENGTH - 3] + "..."

        payload: Dict[str, Any] = {
            "content": content,
            "username": message.metadata.get("username", "ILMA Bot"),
            "avatar_url": message.metadata.get("avatar_url")
        }

        # Add embed if specified
        if message.metadata.get("embed"):
            payload["embeds"] = [message.metadata["embed"]]
        elif message.metadata.get("embeds"):
            payload["embeds"] = message.metadata["embeds"]

        return payload

    def create_embed(
        self,
        title: str,
        description: str,
        color: int = 0x3498db,
        fields: Optional[List[Dict[str, str]]] = None,
        footer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Discord embed object.
        
        Args:
            title: Embed title
            description: Embed description
            color: Embed color (integer)
            fields: List of field objects {name, value, inline}
            footer: Footer text
            
        Returns:
            Discord embed dictionary
        """
        embed: Dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        if fields:
            embed["fields"] = [
                {"name": f["name"], "value": f["value"], "inline": f.get("inline", False)}
                for f in fields
            ]
        
        if footer:
            embed["footer"] = {"text": footer}
        
        return embed


class MessageQueue:
    """
    Asynchronous message queue for batch processing.
    
    Features:
    - Priority-based ordering
    - Concurrent delivery
    - Retry with exponential backoff
    - Batch processing
    - Statistics tracking
    """

    def __init__(
        self,
        max_workers: int = 5,
        max_queue_size: int = 1000
    ):
        """
        Initialize message queue.
        
        Args:
            max_workers: Maximum concurrent senders
            max_queue_size: Maximum queue size
        """
        self.queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_queue_size)
        self.max_workers = max_workers
        self.responses: Dict[str, MessageResponse] = {}
        self.stats = {
            "total_processed": 0,
            "total_sent": 0,
            "total_failed": 0,
            "total_retries": 0
        }
        self._running = False
        self._workers: List[threading.Thread] = []
        self.logger = logging.getLogger(f"{__name__}.MessageQueue")

    def add_message(
        self,
        platform: str,
        content: str,
        recipient: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a message to the queue.
        
        Args:
            platform: Target platform (telegram, discord)
            content: Message content
            recipient: Recipient ID
            priority: Message priority
            metadata: Additional metadata
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        
        message = Message(
            message_id=message_id,
            platform=platform,
            content=content,
            recipient=recipient,
            priority=priority,
            metadata=metadata or {}
        )
        
        # Priority queue: negate priority so lowest number has highest priority
        self.queue.put((-priority.value, message))
        
        self.logger.debug(f"Added message {message_id} to queue (priority: {priority.name})")
        return message_id

    def start(self, adapters: Dict[str, BaseAdapter]) -> None:
        """
        Start the queue processing.
        
        Args:
            adapters: Dictionary of platform -> adapter
        """
        if self._running:
            return
        
        self._running = True
        self._adapters = adapters
        
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker,
                args=(adapters,),
                name=f"MessageWorker-{i}"
            )
            worker.daemon = True
            worker.start()
            self._workers.append(worker)
        
        self.logger.info(f"Started {self.max_workers} message queue workers")

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the queue processing."""
        self._running = False
        
        for worker in self._workers:
            worker.join(timeout=timeout)
        
        self._workers.clear()
        self.logger.info("Message queue stopped")

    def _worker(self, adapters: Dict[str, BaseAdapter]) -> None:
        """Worker thread for processing messages."""
        while self._running:
            try:
                _, message = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            adapter = adapters.get(message.platform)
            
            if not adapter:
                self.responses[message.message_id] = MessageResponse(
                    success=False,
                    message_id=message.message_id,
                    error=f"No adapter for platform: {message.platform}"
                )
                self.stats["total_failed"] += 1
                continue
            
            # Retry loop
            max_retries = message.max_retries
            delay = 1.0
            
            for attempt in range(max_retries + 1):
                response = adapter.send(message)
                
                if response.success:
                    self.responses[message.message_id] = response
                    self.stats["total_sent"] += 1
                    break
                
                if attempt < max_retries:
                    self.logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for message {message.message_id}"
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                    self.stats["total_retries"] += 1
                    message.retry_count = attempt + 1
                else:
                    response.error = f"Failed after {max_retries} retries: {response.error}"
                    self.responses[message.message_id] = response
                    self.stats["total_failed"] += 1
            
            self.stats["total_processed"] += 1
            self.queue.task_done()

    def get_response(self, message_id: str) -> Optional[MessageResponse]:
        """Get response for a sent message."""
        return self.responses.get(message_id)

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return self.stats.copy()


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from file."""
    path = Path(config_path)
    if not path.exists():
        return {}
    
    with open(path) as f:
        return json.load(f)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Messaging Engine - Send messages via Telegram/Discord",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --platform telegram --message "Hello World" --chat-id 123456789
  %(prog)s --platform discord --message "Hello" --webhook-url https://discord.com/api/webhooks/...
  %(prog)s --queue --batch messages.json
  %(prog)s --interactive
        """
    )
    
    parser.add_argument("--platform", "-p", choices=["telegram", "discord"],
                       help="Messaging platform")
    parser.add_argument("--message", "-m", help="Message content")
    parser.add_argument("--chat-id", help="Telegram chat ID")
    parser.add_argument("--channel-id", help="Discord channel ID (webhook URL)")
    parser.add_argument("--webhook-url", help="Discord webhook URL")
    
    parser.add_argument("--token", "-t", help="Telegram bot token")
    parser.add_argument("--parse-mode", choices=["Markdown", "HTML", "None"],
                       default="Markdown", help="Telegram parse mode")
    
    parser.add_argument("--queue", "-q", action="store_true", help="Use message queue")
    parser.add_argument("--batch", "-b", help="JSON file with batch messages")
    parser.add_argument("--workers", type=int, default=5, help="Queue workers")
    
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--json-output", "-j", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get tokens from environment if not provided
        telegram_token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN")
        discord_webhook = args.webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
        
        # Interactive mode
        if args.interactive:
            print("ILMA Messaging Engine - Interactive Mode")
            print("=" * 50)
            platform = input("Platform (telegram/discord): ").strip().lower()
            recipient = input("Recipient (chat ID / webhook URL): ").strip()
            message = input("Message: ").strip()
            
            if platform == "telegram":
                if not telegram_token:
                    print("Error: TELEGRAM_BOT_TOKEN not set")
                    return 1
                adapter = TelegramAdapter(api_token=telegram_token)
                msg = Message(
                    message_id=str(uuid.uuid4()),
                    platform="telegram",
                    content=message,
                    recipient=recipient
                )
                response = adapter.send(msg)
            elif platform == "discord":
                if not discord_webhook:
                    print("Error: DISCORD_WEBHOOK_URL not set")
                    return 1
                adapter = DiscordAdapter(webhook_url=discord_webhook)
                msg = Message(
                    message_id=str(uuid.uuid4()),
                    platform="discord",
                    content=message,
                    recipient=recipient
                )
                response = adapter.send(msg)
            else:
                print(f"Unknown platform: {platform}")
                return 1
            
            if response.success:
                print(f"✓ Message sent successfully")
                return 0
            else:
                print(f"✗ Failed: {response.error}")
                return 1
        
        # Batch mode
        if args.batch:
            batch_path = Path(args.batch)
            if not batch_path.exists():
                logger.error(f"Batch file not found: {args.batch}")
                return 1
            
            with open(batch_path) as f:
                batch_data = json.load(f)
            
            messages = batch_data.get("messages", [])
            
            # Setup adapters
            adapters: Dict[str, BaseAdapter] = {}
            if telegram_token:
                adapters["telegram"] = TelegramAdapter(api_token=telegram_token)
            if discord_webhook:
                adapters["discord"] = DiscordAdapter(webhook_url=discord_webhook)
            
            if not adapters:
                logger.error("No adapters configured")
                return 1
            
            # Setup queue
            message_queue = MessageQueue(max_workers=args.workers)
            message_queue.start(adapters)
            
            # Add messages to queue
            for msg_data in messages:
                message_queue.add_message(
                    platform=msg_data["platform"],
                    content=msg_data["content"],
                    recipient=msg_data["recipient"],
                    priority=MessagePriority[msg_data.get("priority", "NORMAL")],
                    metadata=msg_data.get("metadata", {})
                )
            
            # Wait for processing
            time.sleep(len(messages) * 0.5 + 2)
            message_queue.stop()
            
            stats = message_queue.get_stats()
            
            if args.json_output:
                print(json.dumps(stats, indent=2))
            else:
                print(f"Batch processing complete")
                print(f"  Total processed: {stats['total_processed']}")
                print(f"  Sent: {stats['total_sent']}")
                print(f"  Failed: {stats['total_failed']}")
                print(f"  Retries: {stats['total_retries']}")
            
            return 0
        
        # Single message mode
        if args.platform and args.message:
            if args.platform == "telegram":
                if not telegram_token:
                    logger.error("Telegram token not configured")
                    return 1
                if not args.chat_id:
                    logger.error("--chat-id required for Telegram")
                    return 1
                
                adapter = TelegramAdapter(
                    api_token=telegram_token,
                    parse_mode=args.parse_mode
                )
                message = Message(
                    message_id=str(uuid.uuid4()),
                    platform="telegram",
                    content=args.message,
                    recipient=args.chat_id
                )
                response = adapter.send(message)
                
            elif args.platform == "discord":
                if not discord_webhook:
                    logger.error("Discord webhook URL not configured")
                    return 1
                
                adapter = DiscordAdapter(webhook_url=discord_webhook)
                message = Message(
                    message_id=str(uuid.uuid4()),
                    platform="discord",
                    content=args.message,
                    recipient=args.channel_id or "default"
                )
                response = adapter.send(message)
            
            if response.success:
                logger.info("Message sent successfully")
                if args.json_output:
                    print(json.dumps({
                        "success": True,
                        "message_id": response.message_id,
                        "platform_message_id": response.platform_message_id
                    }, indent=2))
                else:
                    print("✓ Message sent successfully")
                return 0
            else:
                logger.error(f"Failed to send message: {response.error}")
                if args.json_output:
                    print(json.dumps({
                        "success": False,
                        "message_id": response.message_id,
                        "error": response.error
                    }, indent=2))
                else:
                    print(f"✗ Failed: {response.error}")
                return 1
        
        # Default: show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    import os
    exit(main())