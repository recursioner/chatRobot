from channels import route
from channels import include

# This function will display all messages received in the console
def message_handler(message):
    print(message['text'])


channel_routing = [
    include("chat.routing.websocket_routing", path=r"^/chat/stream"),

    # Custom handler for message sending (see Room.send_message).
    # Can't go in the include above as it's not got a 'path' attribute to match on.
    include("chat.routing.custom_routing"),

    route("websocket.receive", message_handler)  # we register our message handler
]


