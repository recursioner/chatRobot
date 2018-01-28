import json
from channels import Channel
from channels.auth import channel_session_user_from_http, channel_session_user

from .settings import MSG_TYPE_LEAVE, MSG_TYPE_ENTER, NOTIFY_USERS_ON_ENTER_OR_LEAVE_ROOMS
from .models import Room, Question
from .utils import get_room_or_error, catch_client_error
from .exceptions import ClientError
# This decorator copies the user from the HTTP session (only available in
# websocket.connect or http.request messages) to the channel session (available
# in all consumers with the same reply_channel, so all three here)


@channel_session_user_from_http
def ws_connect(message):
    message.reply_channel.send({"accept": True})
    message.channel_session['rooms'] = []

@channel_session_user
def ws_disconnect(message):
    # Unsubscribe from any connected rooms
    for room_id in message.channel_session.get("rooms", set()):
        try:
            room = Room.objects.get(pk=room_id)
            # Removes us from the room's send group. If this doesn't get run,
            # we'll get removed once our first reply message expires.
            room.websocket_group.discard(message.reply_channel)
        except Room.DoesNotExist:
            pass

def ws_receive(message):
    # All WebSocket frames have either a text or binary payload; we decode the
    # text part here assuming it's JSON.
    # You could easily build up a basic framework that did this encoding/decoding
    # for you as well as handling common errors.
    payload = json.loads(message['text'])
    payload['reply_channel'] = message.content['reply_channel']
    Channel("chat.receive").send(payload)



@channel_session_user
@catch_client_error
def chat_join(message):
    # Find the room they requested (by ID) and add ourselves to the send group
    # Note that, because of channel_session_user, we have a message.user
    # object that works just like request.user would. Security!
    room = get_room_or_error(message["room"], message.user)

    # Send a "enter message" to the room if available
    if NOTIFY_USERS_ON_ENTER_OR_LEAVE_ROOMS:
        room.send_message(None, message.user, MSG_TYPE_ENTER)

    # OK, add them in. The websocket_group is what we'll send messages
    # to so that everyone in the chat room gets them.
    room.websocket_group.add(message.reply_channel)
    message.channel_session['rooms'] = list(set(message.channel_session['rooms']).union([room.id]))
    # Send a message back that will prompt them to open the room
    # Done server-side so that we could, for example, make people
    # join rooms automatically.
    message.reply_channel.send({
        "text": json.dumps({
            "join": str(room.id),
            "title": room.title,
        }),
    })
    
    message.user.username = 'robot'
    room.send_message("Can I ask you some questions?", message.user)



@channel_session_user
@catch_client_error
def chat_leave(message):
    # Reverse of join - remove them from everything.
    room = get_room_or_error(message["room"], message.user)

    # Send a "leave message" to the room if available
    if NOTIFY_USERS_ON_ENTER_OR_LEAVE_ROOMS:
        room.send_message(None, message.user, MSG_TYPE_LEAVE)

    room.websocket_group.discard(message.reply_channel)
    message.channel_session['rooms'] = list(set(message.channel_session['rooms']).difference([room.id]))
    # Send a message back that will prompt them to close the room
    message.reply_channel.send({
        "text": json.dumps({
            "leave": str(room.id),
        }),
    })



@channel_session_user
@catch_client_error
def chat_send(message):
    if int(message['room']) not in message.channel_session['rooms']:
        raise ClientError("ROOM_ACCESS_DENIED")
    room = get_room_or_error(message["room"], message.user)
    room.send_message(message["message"], message.user)

    print(message.channel_session)
    question = Question.objects.filter(session_id = message.channel_session.session_key)
    if(question.count() == 0):
        q = Question.objects.create(session_id=message.channel_session.session_key);
        q.save();
        print(message.channel_session.session_key)
        message.user.username = 'robot'
        room.send_message("what is your name?", message.user)
    else:
        print(question)
        print(len(question))
        q = question[0]
        print(q.session_id)
        print('name: ' + q.name)
        if q.name and q.age and q.sex and q.smoker:
            msg = 'name %s age %s sex %s smoker %s' % (q.name, q.age, q.sex, q.smoker)
        else:
            if not q.name:
                q.name = message['message']
            else:
                if not q.age:
                    q.age = message['message']
                else: 
                    if not q.sex:
                        q.sex = message['message']
                    else:
                        q.smoker = message['message']
        q.save()

        if not q.name:
            msg = 'what is your name?'
        else:
            if not q.age:
                msg = 'what is your age?'
            else:
                if not q.sex:
                    msg = 'what is your sex?'
                else:
                    if not q.smoker:
                        msg = 'are you a smoker?'

        if q.name and q.age and q.sex and q.smoker:
            msg = 'name %s age %s sex %s smoker %s' % (q.name, q.age, q.sex, q.smoker)

        message.user.username = 'robot'
        room.send_message(msg, message.user)
