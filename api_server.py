#!/usr/bin/env python3
import os
import json
import socket
import secrets
import uvicorn
import contextlib
import time
import re
import asyncio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Security, status, Request, BackgroundTasks
from fastapi.security.api_key import APIKeyHeader, APIKey
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pyrogram import Client
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

# Configuration
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
SESSION = os.getenv("LOGIN", "linkbot")
LINKS_FILE = Path("links.json")

# Generate API key if it doesn't exist
API_KEY_FILE = Path(".api_key")
if not API_KEY_FILE.exists():
    api_key = secrets.token_urlsafe(32)
    with API_KEY_FILE.open("w") as f:
        f.write(api_key)
    print(f"Generated new API key: {api_key}")
else:
    with API_KEY_FILE.open("r") as f:
        api_key = f.read().strip()
    print("Using existing API key")

# API key security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Create Pyrogram client
client = Client(SESSION, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE)

# Transaction cache to avoid processing the same transaction twice
# Structure: {chat_id: {transaction_id: timestamp}}
transaction_cache = {}

# Message history storage
# Structure: {chat_id: [{"cabinet_name": str, "cabinet_id": str, "message": str, "timestamp": float, "message_id": int}]}
message_history = {}

# Set to track processed message IDs to avoid duplicates
# Structure: {chat_id: {message_id: timestamp}}
processed_message_ids = {}

# Command regexes for bot functionality
CMD_LINK = re.compile(r"#link\s+(.+)", re.I)
CMD_DEL = re.compile(r"#del\s+(\d+)", re.I)
CMD_SEND = re.compile(r"#(\d+)\s+(.+)", re.S)

# Bot state
MY_ID = None
pending_name = None  # For link creation

# Background task to handle bot commands in messages
async def handle_bot_messages():
    """Background task to handle bot commands in Saved Messages"""
    print("Starting bot message handling...")

    # Set polling interval (in seconds)
    polling_interval = 3

    global pending_name, MY_ID

    while True:
        try:
            if client.is_connected and MY_ID:
                # Process messages in Saved Messages (from self)
                async for message in client.get_chat_history("me", limit=10):
                    # Skip already processed messages
                    if message.chat.id in processed_message_ids and message.id in processed_message_ids[message.chat.id]:
                        continue

                    # Track this message as processed
                    if message.chat.id not in processed_message_ids:
                        processed_message_ids[message.chat.id] = {}
                    processed_message_ids[message.chat.id][message.id] = time.time()

                    # Process only text messages
                    if message.text:
                        # Process #list command
                        if message.text.lower().strip() == "#list":
                            links = load_links()
                            msg = "\n".join(f"{i+1}. {l['name']}  (ID {l['id']})"
                                           for i, l in enumerate(links)) or "No links found."
                            await client.send_message("me", msg)
                            continue

                        # Process #link command
                        if message.text.lower().startswith("#link"):
                            match = CMD_LINK.match(message.text)
                            if match:
                                pending_name = match.group(1).strip()
                                await client.send_message("me", "Now go to the target chat and send `...`")
                            else:
                                await client.send_message("me", "Format: #link Name")
                            continue

                        # Process #del command
                        if message.text.lower().startswith("#del"):
                            match = CMD_DEL.match(message.text)
                            if match:
                                idx = int(match.group(1)) - 1
                                if delete_link(idx):
                                    await client.send_message("me", "✅ Link deleted.")
                                else:
                                    await client.send_message("me", "❌ No such link number.")
                            else:
                                await client.send_message("me", "Format: #del Number")
                            continue

                # Check other chats for "..." to create links
                if pending_name:
                    for dialog in await client.get_dialogs(limit=50):
                        chat = dialog.chat
                        # Skip Saved Messages
                        if chat.id == MY_ID:
                            continue

                        # Check recent messages in this chat
                        async for msg in client.get_chat_history(chat.id, limit=5):
                            # Skip messages from others
                            if msg.from_user and msg.from_user.id != MY_ID:
                                continue

                            # Check for "..." message
                            if msg.text and msg.text.strip() == "...":
                                # Create the link
                                add_link(chat.id, pending_name)

                                # Delete the "..." message
                                await client.delete_messages(chat.id, msg.id)

                                # Notify in Saved Messages
                                await client.send_message("me", f"✅ Link '{pending_name}' created.")

                                # Reset pending_name
                                pending_name = None
                                break
        except Exception as e:
            print(f"Error in message handler: {e}")

        # Wait before next check
        await asyncio.sleep(polling_interval)

# Background monitoring task
async def monitor_linked_chats():
    """Background task to monitor linked chats for new messages"""
    print("Starting chat monitoring background task...")

    # Set polling interval (in seconds)
    polling_interval = 5

    while True:
        try:
            if client.is_connected:
                # Get all linked chats
                links = load_links()
                if not links:
                    print("No linked chats found. Waiting...")
                else:
                    print(f"Checking {len(links)} linked chats for new messages...")

                    for link in links:
                        chat_id = link["id"]
                        chat_name = link["name"]

                        try:
                            # Get recent messages from this chat
                            messages = []
                            async for msg in client.get_chat_history(chat_id, limit=5):
                                messages.append(msg)

                                # Check for cabinet messages
                                if msg.text and "[" in msg.text and "]" in msg.text and ":" in msg.text:
                                    # Convert Pyrogram date to timestamp
                                    timestamp = msg.date.timestamp() if hasattr(msg.date, "timestamp") else time.time()

                                    # Parse and store cabinet message with message ID
                                    parsed = parse_cabinet_message(
                                        chat_id,
                                        msg.text,
                                        timestamp,
                                        chat_name,
                                        message_id=msg.id
                                    )
                                    if parsed:
                                        print(f"Found cabinet message in chat {chat_name} (ID: {msg.id})")

                        except Exception as e:
                            print(f"Error checking chat {chat_id} ({chat_name}): {e}")
                            continue
            else:
                print("Client not connected. Skipping chat monitoring.")

        except Exception as e:
            print(f"Error in monitoring task: {e}")

        # Wait before next check
        await asyncio.sleep(polling_interval)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize the Telegram client
    print("Starting Telegram client...")
    monitoring_task = None
    message_handler_task = None
    global MY_ID

    try:
        await client.start()
        print("Telegram client started successfully")

        # Get our user ID
        me = await client.get_me()
        MY_ID = me.id
        print(f"Bot user ID: {MY_ID}")

        # Start background monitoring task
        monitoring_task = asyncio.create_task(monitor_linked_chats())
        print("Background monitoring task started")

        # Start message handler task
        message_handler_task = asyncio.create_task(handle_bot_messages())
        print("Message handler task started")

    except Exception as e:
        print(f"Error starting Telegram client: {e}")
        print("API server will continue running, but message sending may not work")

    yield  # Server is running

    # Shutdown: stop the Telegram client
    print("Shutting down Telegram client...")

    # Cancel monitoring task if running
    if monitoring_task:
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            print("Monitoring task cancelled")

    # Cancel message handler task if running
    if message_handler_task:
        message_handler_task.cancel()
        try:
            await message_handler_task
        except asyncio.CancelledError:
            print("Message handler task cancelled")

    if client.is_connected:
        await client.stop()

    print("Telegram client stopped successfully")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Telegram Bot API",
    description="""
    API for sending messages via Telegram user bot

    ## Message Response Parsing

    When sending messages through the /send endpoint, the API will:

    1. Send your message to the specified chat
    2. Wait 10 seconds for a response
    3. Check the response message for specific patterns

    ### Success/Failure Detection

    - If the response contains "Exception: params count", the API returns failure status
    - If the response contains "Выплата добавлена в очередь", the API returns success status

    ### Auto-Withdraw Detection

    For payment messages, the API will parse and return the auto-withdraw status:

    - "Автовывод: ДА" - auto_withdraw field is set to true
    - "Автовывод: НЕТ" - auto_withdraw field is set to false

    ## Cabinet Message Tracking

    The API automatically tracks cabinet messages in the format:

    ```
    [cabinet_name#cabinet_id] Автоматическое оповещение: Message content
    ```

    Example: `[redisonpay#947] Автоматическое оповещение: Выплата#2259417 в обработке`

    ### Cabinet Message Endpoints

    - **GET /messages/recent** - Get cabinet messages from the last 3 hours (or custom time period)
    - **GET /messages/all** - Get all cabinet messages collected since the API started

    Messages are returned in reverse chronological order (newest first).
    """,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Models
class ChatLink(BaseModel):
    id: int
    name: str

class ChatList(BaseModel):
    chats: List[ChatLink]

class Message(BaseModel):
    chat_id: int
    text: str

class LinkMessage(BaseModel):
    link_number: int
    text: str

class LinkCreate(BaseModel):
    chat_id: int
    name: str

class LinkDeleteRequest(BaseModel):
    link_number: int

class MessageResponse(BaseModel):
    success: bool
    message: str
    auto_withdraw: Optional[bool] = None

class CabinetMessage(BaseModel):
    chat_id: int
    chat_name: str
    cabinet_name: str
    cabinet_id: str
    message: str
    timestamp: float
    message_id: Optional[int] = None

class CabinetMessageList(BaseModel):
    messages: List[CabinetMessage]

# Helper functions
def load_links():
    if LINKS_FILE.exists():
        with LINKS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_links(data):
    with LINKS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_link(chat_id: int, name: str):
    links = load_links()
    links.append({"id": chat_id, "name": name})
    save_links(links)
    return True

def delete_link(idx: int):
    links = load_links()
    if 0 <= idx < len(links):
        links.pop(idx)
        save_links(links)
        return True
    return False

def parse_cabinet_message(chat_id, text, timestamp, chat_name="", message_id=None):
    """Parse cabinet message and store in message history"""
    # Parse message like: [redisonpay#947] Автоматическое оповещение: Message content
    # Using a different regex approach to better capture the full message after the colon
    cabinet_match = re.match(r'\[([\w]+)#(\d+)\]\s+([^:]+):(.*)', text)

    if cabinet_match:
        cabinet_name = cabinet_match.group(1)
        cabinet_id = cabinet_match.group(2)

        # Extract the full message content after the colon
        prefix_part = f"[{cabinet_name}#{cabinet_id}] {cabinet_match.group(3)}:"
        message_content = text[len(prefix_part):].strip()

        # Print for debugging
        print(f"Parsed message content: '{message_content}'")

        # If the regex failed to capture message content properly, try another approach
        if not message_content and ":" in text:
            colon_pos = text.find(":")
            if colon_pos > 0:
                message_content = text[colon_pos+1:].strip()
                print(f"Alternative parsing used, message content: '{message_content}'")

        # Check if this message ID has already been processed
        if message_id is not None:
            # Initialize chat in processed IDs if not exists
            if chat_id not in processed_message_ids:
                processed_message_ids[chat_id] = {}

            # If this message ID is already in our processed set, skip it
            if message_id in processed_message_ids[chat_id]:
                print(f"Skipping already processed message ID {message_id}")
                return None

            # Add to processed messages
            processed_message_ids[chat_id][message_id] = timestamp

        # Create message entry
        message_entry = {
            "cabinet_name": cabinet_name,
            "cabinet_id": cabinet_id,
            "message": message_content,
            "timestamp": timestamp,
            "chat_id": chat_id,
            "chat_name": chat_name,
            "message_id": message_id
        }

        # Initialize chat in history if not exists
        if chat_id not in message_history:
            message_history[chat_id] = []

        # Add message to history
        message_history[chat_id].append(message_entry)

        print(f"Added cabinet message: {cabinet_name}#{cabinet_id} - {message_content[:30]}...")

        # Clean old processed message IDs (older than 24 hours)
        current_time = time.time()
        for chat in list(processed_message_ids.keys()):
            for msg_id in list(processed_message_ids[chat].keys()):
                if current_time - processed_message_ids[chat][msg_id] > 86400:  # 24 hours
                    del processed_message_ids[chat][msg_id]

        return message_entry

    return None

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == api_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )

# API routes
@app.get("/", tags=["Status"])
async def root():
    return {"status": "running", "message": "Telegram Bot API is running"}

@app.get("/links", response_model=ChatList, tags=["Links"])
async def get_links(api_key: APIKey = Depends(get_api_key)):
    """
    Get all available links.

    Returns:
        List of all links with their ids and names
    """
    links = load_links()
    return ChatList(chats=[ChatLink(id=link["id"], name=link["name"]) for link in links])

@app.post("/links", response_model=MessageResponse, tags=["Links"])
async def create_link(link: LinkCreate, api_key: APIKey = Depends(get_api_key)):
    """
    Create a new link to a chat.

    Args:
        chat_id: The ID of the chat to link
        name: The name/label for this link

    Returns:
        Success status and message
    """
    try:
        # Add the link
        add_link(link.chat_id, link.name)
        return MessageResponse(
            success=True,
            message=f"Link '{link.name}' created for chat {link.chat_id}"
        )
    except Exception as e:
        print(f"Error creating link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link: {str(e)}"
        )

@app.delete("/links", response_model=MessageResponse, tags=["Links"])
async def delete_link_endpoint(request: LinkDeleteRequest, api_key: APIKey = Depends(get_api_key)):
    """
    Delete a link by its number.

    Args:
        link_number: The number of the link to delete (as shown in the list)

    Returns:
        Success status and message
    """
    link_idx = request.link_number - 1
    if delete_link(link_idx):
        return MessageResponse(
            success=True,
            message=f"Link #{request.link_number} deleted successfully"
        )
    else:
        return MessageResponse(
            success=False,
            message=f"No link found with number {request.link_number}"
        )

@app.get("/chats", response_model=ChatList, tags=["Chats"])
async def get_chats(api_key: APIKey = Depends(get_api_key)):
    links = load_links()
    return ChatList(chats=[ChatLink(id=link["id"], name=link["name"]) for link in links])

@app.post("/send", response_model=MessageResponse, tags=["Messages"])
async def send_message(
    message: Message,
    api_key: APIKey = Depends(get_api_key)
):
    """
    Send a message to a Telegram chat and analyze the response.

    Returns:
      - success: Whether the message was successfully processed
      - message: Status message with details
      - auto_withdraw: For payment messages, indicates if auto-withdraw is enabled (true/false/null)
    """
    try:
        # Check if client is initialized
        if not client.is_connected:
            await client.start()

        # Import asyncio
        import asyncio

        # Send message
        sent_message = await client.send_message(message.chat_id, message.text)

        # Wait for reply message (wait 10 seconds to ensure we get the response)
        print(f"Waiting for response to message: {message.text[:30]}...")
        await asyncio.sleep(10)

        # Safely get response message
        response_message = None
        try:
            # Get chat info for message history
            chat = await client.get_chat(message.chat_id)
            chat_name = chat.title if chat.title else f"User {chat.first_name}" if hasattr(chat, "first_name") else str(message.chat_id)

            # Get recent messages (convert async generator to list)
            new_messages = []
            async for msg in client.get_chat_history(
                message.chat_id,
                limit=10  # Get more messages to ensure we capture the response
            ):
                new_messages.append(msg)

                # Check for cabinet messages in history
                if msg.text and "[" in msg.text and "]" in msg.text and ":" in msg.text:
                    # Convert Pyrogram date to timestamp
                    timestamp = msg.date.timestamp() if hasattr(msg.date, "timestamp") else time.time()
                    # Include message ID to prevent duplicates
                    parse_cabinet_message(message.chat_id, msg.text, timestamp, chat_name, message_id=msg.id)

            # Log all recent messages for debugging
            print(f"Found {len(new_messages)} recent messages in chat")

            # Filter messages to only include those sent AFTER our message
            sent_date = sent_message.date
            print(f"Our message sent at: {sent_date}")

            # Sort messages by date (newest first is default from Pyrogram)
            filtered_messages = []
            for msg in new_messages:
                if msg.id != sent_message.id:  # Skip our own message
                    print(f"Message: ID={msg.id}, Date={msg.date}, Text={msg.text[:30]}...")
                    if msg.date > sent_date:
                        print(f"  ✓ Message is newer than our sent message")
                        filtered_messages.append(msg)
                    else:
                        print(f"  ✗ Message is older than our sent message - ignoring")

            print(f"Found {len(filtered_messages)} messages after our sent message")

            # First try to find messages with payment confirmation text
            for msg in filtered_messages:
                if "Выплата добавлена в очередь" in msg.text:
                    print(f"Found payment confirmation message: {msg.text[:50]}...")
                    response_message = msg
                    break

            # Also check explicitly for cabinet messages in filtered messages
            for msg in filtered_messages:
                if msg.text and "[" in msg.text and "]" in msg.text and ":" in msg.text:
                    # Convert Pyrogram date to timestamp
                    timestamp = msg.date.timestamp() if hasattr(msg.date, "timestamp") else time.time()
                    # Try to parse as cabinet message, including message ID
                    parsed = parse_cabinet_message(
                        message.chat_id,
                        msg.text,
                        timestamp,
                        chat_name,
                        message_id=msg.id
                    )
                    if parsed:
                        print(f"Found and parsed cabinet message in filtered messages (ID: {msg.id})")

            # If we didn't find a payment message, take the newest message after ours
            if not response_message and filtered_messages:
                msg = filtered_messages[0]  # First message is newest
                print(f"Using newest message as response: {msg.text[:50]}...")
                response_message = msg

            if not response_message:
                print("No response message found in chat history")

        except Exception as e:
            print(f"Error getting response message: {e}")
            # Continue with default response

        # Set default response - assume failure if no response message
        success = False
        response_text = "No response received - payment likely failed"
        auto_withdraw = None

        if response_message:
            text = response_message.text

            # Log the actual message for debugging
            print(f"Analyzing response message: {text}")

            # Check for error messages
            if "Exception: params count" in text:
                success = False
                response_text = "Failed: Exception params count error"

            # Check for success message with transaction details - must match exactly
            elif "Выплата добавлена в очередь" in text:
                success = True
                response_text = "Payment successfully queued"

                # Extract transaction details using regex
                txn_id = None
                txn_match = re.search(r'Транзакция#(\d+)', text)
                if txn_match:
                    txn_id = txn_match.group(1)
                    print(f"Transaction ID: {txn_id}")

                    # Check if we've already processed this transaction for this chat
                    chat_transactions = transaction_cache.get(message.chat_id, {})

                    if txn_id in chat_transactions:
                        print(f"Transaction {txn_id} already processed, ignoring")
                        success = False
                        response_text = "Duplicate transaction"
                        return MessageResponse(
                            success=success,
                            message=response_text,
                            auto_withdraw=None
                        )

                    # Store this transaction in the cache
                    if message.chat_id not in transaction_cache:
                        transaction_cache[message.chat_id] = {}

                    # Store with timestamp
                    transaction_cache[message.chat_id][txn_id] = time.time()
                    print(f"Added transaction {txn_id} to cache for chat {message.chat_id}")

                    # Clean old transactions (older than 1 hour)
                    current_time = time.time()
                    for chat_id in list(transaction_cache.keys()):
                        for tx_id in list(transaction_cache[chat_id].keys()):
                            if current_time - transaction_cache[chat_id][tx_id] > 3600:  # 1 hour
                                del transaction_cache[chat_id][tx_id]
                                print(f"Removed old transaction {tx_id} from cache")

                # Parse auto withdraw status (case insensitive)
                if "автовывод: да" in text.lower():
                    auto_withdraw = True
                    print("Auto-withdraw: YES")
                elif "автовывод: нет" in text.lower():
                    auto_withdraw = False
                    print("Auto-withdraw: NO")
                else:
                    print("Auto-withdraw status not found in response")
            else:
                # Any other response is treated as failure
                success = False
                response_text = "Unexpected response format"
        else:
            # No response message received
            success = False
            response_text = "No response received - payment likely failed"

        return MessageResponse(
            success=success,
            message=response_text,
            auto_withdraw=auto_withdraw
        )
    except Exception as e:
        print(f"Error in send_message endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )

@app.get("/messages/recent", response_model=CabinetMessageList, tags=["Messages"])
async def get_recent_messages(hours: int = 3, cabinet_name: str = None, api_key: APIKey = Depends(get_api_key)):
    """
    Get cabinet messages from all chats from the last specified hours.

    Args:
        hours: Number of hours to look back (default: 3)
        cabinet_name: Filter by cabinet name (optional)

    Returns:
        List of cabinet messages from the specified time period
    """
    recent_messages = []
    current_time = time.time()
    time_limit = current_time - (hours * 3600)  # Convert hours to seconds

    # Collect messages from all chats
    for chat_id, messages in message_history.items():
        for msg in messages:
            # Filter by timestamp and cabinet name if provided
            if (msg["timestamp"] >= time_limit and
                (cabinet_name is None or msg["cabinet_name"].lower() == cabinet_name.lower())):
                recent_messages.append(CabinetMessage(
                    chat_id=chat_id,
                    chat_name=msg["chat_name"],
                    cabinet_name=msg["cabinet_name"],
                    cabinet_id=msg["cabinet_id"],
                    message=msg["message"],
                    timestamp=msg["timestamp"],
                    message_id=msg["message_id"]  # Include the message ID
                ))

    # Sort by timestamp (newest first)
    recent_messages.sort(key=lambda x: x.timestamp, reverse=True)

    return CabinetMessageList(messages=recent_messages)

@app.post("/send-to-link", response_model=MessageResponse, tags=["Messages"])
async def send_to_link(message: LinkMessage, api_key: APIKey = Depends(get_api_key)):
    """
    Send a message to a linked chat by its number.

    Args:
        link_number: The number of the link (as shown in #list command)
        text: The message to send

    Returns:
        Success status and message
    """
    try:
        # Check if client is initialized
        if not client.is_connected:
            await client.start()

        # Get links
        links = load_links()
        link_idx = message.link_number - 1

        # Check if link exists
        if not (0 <= link_idx < len(links)):
            return MessageResponse(
                success=False,
                message=f"No link found with number {message.link_number}"
            )

        # Get chat ID
        chat_id = links[link_idx]["id"]
        link_name = links[link_idx]["name"]

        # Send message
        await client.send_message(chat_id, message.text)

        return MessageResponse(
            success=True,
            message=f"Message sent to {link_name} (link #{message.link_number})"
        )
    except Exception as e:
        print(f"Error sending message to link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message to link: {str(e)}"
        )

@app.get("/messages/all", response_model=CabinetMessageList, tags=["Messages"])
async def get_all_messages(cabinet_name: str = None, api_key: APIKey = Depends(get_api_key)):
    """
    Get all cabinet messages from all chats.

    Args:
        cabinet_name: Filter by cabinet name (optional)

    Returns:
        List of all cabinet messages
    """
    all_messages = []

    # Collect messages from all chats
    for chat_id, messages in message_history.items():
        for msg in messages:
            # Filter by cabinet name if provided
            if cabinet_name is None or msg["cabinet_name"].lower() == cabinet_name.lower():
                all_messages.append(CabinetMessage(
                    chat_id=chat_id,
                    chat_name=msg["chat_name"],
                    cabinet_name=msg["cabinet_name"],
                    cabinet_id=msg["cabinet_id"],
                    message=msg["message"],
                    timestamp=msg["timestamp"],
                    message_id=msg["message_id"]  # Include the message ID
                ))

    # Sort by timestamp (newest first)
    all_messages.sort(key=lambda x: x.timestamp, reverse=True)

    return CabinetMessageList(messages=all_messages)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log request
    print(f"Request: {request.method} {request.url}")

    # Process request
    response = await call_next(request)

    # Return response
    return response

def get_local_ip():
    """Get the local IP address of the machine"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Run the API server
if __name__ == "__main__":
    # Get local IP
    local_ip = get_local_ip()
    port = 8000
    
    # Print server information
    print(f"\n{'='*50}")
    print(f" Telegram Bot API Server")
    print(f"{'='*50}")
    print(f" Local URL: http://{local_ip}:{port}")
    print(f" API Key: {api_key}")
    print(f" Endpoints:")
    print(f"   - GET    /chats - List all available chats")
    print(f"   - POST   /send  - Send a message to a chat")
    print(f"   - GET    /links - List all links")
    print(f"   - POST   /links - Create a new link to a chat")
    print(f"   - DELETE /links - Delete a link")
    print(f"   - POST   /send-to-link - Send a message to a linked chat by number")
    print(f"   - GET    /messages/recent - Get cabinet messages from last 3 hours")
    print(f"   - GET    /messages/all - Get all cabinet messages")
    print(f" API Documentation: http://{local_ip}:{port}/docs")
    print(f"{'='*50}\n")
    
    # Start the server with auto-restart on failure
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )