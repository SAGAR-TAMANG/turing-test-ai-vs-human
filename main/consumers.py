from channels.generic.websocket import WebsocketConsumer, AsyncWebsocketConsumer
from asgiref.sync import async_to_sync
import json
from django.template.loader import render_to_string
import uuid
from openai import OpenAI
from dotenv import load_dotenv
import os
from django.core.cache import cache          # ◀ NEW
load_dotenv()

message_id = uuid.uuid4().hex
contents_div_id = f"message-response-{message_id}"

class HumanChatConsumer(WebsocketConsumer):
    def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )

        # create the counter the first time a room is used  ◀ NEW
        cache.add(f"turn_counter:{self.room_name}", 0)

        self.last_contents_div_id = None   # keep it per‑connection
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name, self.channel_name
        )

    def receive(self, text_data):
        """
        Handle an incoming WebSocket message.

        • Odd turn  → render user bubble + “AI typing” placeholder.
        • Even turn → render final AI bubble with the *same* contents_div_id.
        The ID is kept in the Django cache so all connections in the room
        share it.
        """
        data = json.loads(text_data or "{}")
        message_text = data.get("message", "").strip()
        if not message_text:
            return                                   # ignore blank payloads

        # Keys that are unique *per room* (not per socket)
        counter_key = f"turn_counter:{self.room_name}"
        cid_key     = f"pair_cid:{self.room_name}"

        turn_number = cache.incr(counter_key)        # 1, 2, 3 …
        print("TURN:", turn_number)                  # (debug)

        # ─── ODD turn: user bubble + AI placeholder ───────────────────────
        if turn_number % 2:                          # 1st, 3rd, 5th …
            # Generate & cache a fresh id for this 2‑message pair
            cid = f"message-response-{uuid.uuid4().hex}"
            cache.set(cid_key, cid, None)            # no timeout

            # 1️⃣ user bubble
            html_user = render_to_string(
                "chat/user_msg.html",
                {"message_text": message_text, "contents_div_id": cid},
            )
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {"type": "chat.message", "html": html_user},
            )

            # 2️⃣ AI “typing…” placeholder
            html_placeholder = render_to_string(
                "chat/ai_msg.html",
                {"contents_div_id": cid},
            )
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {"type": "chat.message", "html": html_placeholder},
            )

        # ─── EVEN turn: final AI bubble ───────────────────────────────────
        else:                                        # 2nd, 4th, 6th …
            cid = cache.get(cid_key)
            if cid is None:
                # Fallback: shouldn’t happen unless cache cleared mid‑pair
                cid = f"message-response-{uuid.uuid4().hex}"

            html_ai_final = render_to_string(
                "chat/ai_msg_final.html",
                {"message": message_text, "contents_div_id": cid},
            )
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {"type": "chat.message", "html": html_ai_final},
            )

            # Pair finished → clear cid so next message starts a new one
            cache.delete(cid_key)

    def chat_message(self, event):
        self.send(text_data=event["html"])

class ChatConsumerDemo(WebsocketConsumer):
  def connect(self):
    self.user = self.scope['user']
    self.messages = [
      {
        "role": "assistant",
        "content": "I am giving you a name: 'Onhuhondhan' or 'অনুসন্ধান' in Assamese. You are to act like the first Assamese GPT to be built in the world. Introduct yourself with this name during the initial contact with the user while introducing yourself. The user can talk with you in Assamese langauge, be it with Assamese script or in English script (but talking in Assamese). If the user talks in any other language, then reply that you are designed to talk in Assamese."
      },
    ]
    
    sutra_url = 'https://api.two.ai/v2'
    self.client = OpenAI(base_url=sutra_url, api_key=os.getenv("SUTRA_API_KEY"))

    self.accept()

  def disconnect(self, code):
    pass
  
  def receive(self, text_data):
    text_data_json = json.loads(text_data)
    message_text = text_data_json["message"]

    if not message_text.strip():
      return
    
    # print("Message:", message_text)
    
    # Show users message
    user_message_html = render_to_string(
      "chat/user_msg.html",
      {
        "message_text": message_text,
      },
    )

    # Adding message to history

    self.messages.append(
      {
        "role": "user",
        "content": message_text
      }
    )

    self.send(text_data=user_message_html)

    # render an empty text 

    message_id = uuid.uuid4().hex
    contents_div_id = f"message-response-{message_id}"
    system_message_html = render_to_string(
      "chat/ai_msg.html",
      {
        "contents_div_id": contents_div_id,
      },
    )

    self.send(text_data=system_message_html)
    
    
    # from portkey_ai import Portkey

    # client = Portkey(
    #   api_key=os.getenv("PORTKEY_API_KEY"),
    #   virtual_key=os.getenv("VIRTUAL_KEY"),
    # )

    # stream_prompt_completion = client.chat.completions.create(
    #   messages=self.messages,
    #   model= 'gemini-pro',
    #   stream=True,
    #   temperature=0.8,
    #   max_tokens=180,
    # )
    
    chunks = []

    stream = self.client.chat.completions.create(
      model='sutra-light',
      messages = self.messages,
      max_tokens=180,
      temperature=0.3,
      stream=True
    )

    for chunk in stream:
        message_chunk = chunk.choices[0].delta.content
        if len(chunk.choices) > 0:
            content = chunk.choices[0].delta.content
            if content:
              chunks.append(message_chunk)
              chunk = f'<div hx-swap-oob="beforeend:#{contents_div_id}">{_format_token(message_chunk)}</div>'
              self.send(text_data=chunk)

    system_message = ''.join(chunks)

    final_message_html = render_to_string(
      'chat/ai_msg_final.html',
      {
        'contents_div_id': contents_div_id,
        'message': system_message,
      },
    )

    # Save message

    self.messages.append(
      {
        "role": "system",
        "content": system_message,
      }
    )

    print("TOTAL:", self.messages)

    self.send(text_data=final_message_html)

def _format_token(token: str) -> str:
  # apply very basic formatting while we're rendering tokens in real-time
  token = token.replace("\n", "<br>")
  return token