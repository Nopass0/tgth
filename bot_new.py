#!/usr/bin/env python3
import os
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')
LOGIN = os.getenv('LOGIN')

# Create the client
client = Client(
    name=LOGIN,
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE
)

# Store the user ID of the authorized account
my_user_id = None

# Command prefix
CMD_PREFIX = "/"

# Store debug messages here to avoid flooding console
debug_messages = []

# Get our own user ID
async def get_my_user_id():
    global my_user_id
    if my_user_id is None:
        me = await client.get_me()
        my_user_id = me.id
        print(f"Authorized as user ID: {my_user_id}")
    return my_user_id

# HANDLER FOR INCOMING MESSAGES
async def message_handler(client, message):
    """Handle all incoming messages"""
    # Print lots of debug info
    msg_id = getattr(message, 'id', 'unknown')
    chat_id = getattr(message.chat, 'id', 'unknown') if hasattr(message, 'chat') else 'unknown'
    msg_type = getattr(message, 'chat', {}).get('type', 'unknown') if hasattr(message, 'chat') else 'unknown'
    text = getattr(message, 'text', None)
    
    debug_msg = f"NEW MESSAGE: ID={msg_id}, CHAT={chat_id}, TYPE={msg_type}, TEXT={text}"
    debug_messages.append(debug_msg)
    print(debug_msg)
    
    # Also print full message object for debugging
    print(f"FULL MESSAGE: {message}")
    
    # Get sender information
    from_user = getattr(message, 'from_user', None)
    sender_id = getattr(from_user, 'id', 'unknown') if from_user else 'unknown'
    sender_name = getattr(from_user, 'first_name', 'Unknown') if from_user else 'Unknown'
    sender_username = getattr(from_user, 'username', None) if from_user else None
    
    # Skip messages from yourself
    if from_user and from_user.is_self:
        print(f"SKIPPING: Message from self (ID: {sender_id})")
        return
    
    # Format sender name
    if sender_username:
        sender = f"{sender_name} (@{sender_username})"
    else:
        sender = sender_name
    
    print(f"RECEIVED FROM: {sender} (ID: {sender_id})")
    print(f"MESSAGE CONTENT: {text if text else '[non-text content]'}")
    
    # If private chat, respond with a simple message
    if message.chat.type == "private":
        await message.reply("I received your message! I'm a simple echo bot.")

async def main():
    print("Starting Telegram user bot...")
    
    # Start the client
    await client.start()
    me = await client.get_me()
    print(f"Bot started as: {me.first_name}")
    print(f"Username: @{me.username if me.username else 'None'}")
    print(f"User ID: {me.id}")
    
    # Register message handler
    print("Registering message handler...")
    client.add_handler(MessageHandler(message_handler, filters.all))
    
    # Get our own user ID
    await get_my_user_id()
    
    # Send test message to self
    try:
        await client.send_message(my_user_id, "Bot has started. Send a message to test if it works.")
        print("Test message sent to self successfully")
    except Exception as e:
        print(f"ERROR: Could not send test message to self: {e}")
    
    print("\nBot is now running and monitoring for new messages...")
    print("EVERY message will be printed to the console for debugging")
    
    # Keep the client running
    try:
        stop_event = asyncio.Event()
        await stop_event.wait()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())