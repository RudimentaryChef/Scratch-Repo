from json import loads
from websockets.sync.client import connect

"""
Identified issues:
1. Giant and Dwarf player sockets are swapped.

2. Directional actions [left, down, right, up] do not produce expected behavior. On first level, the following mapping
   shows how the expected direction results in the actual behavior: 
   up -> left | down -> right | left -> up | right -> down 
   
3. After player places a pin, pin location does not reinitialize to player. Instead, it remains at the location of the
   previous pin.
"""


def main():
    action_list = [
        ("giant", ["up", "up", "pinga", "submit"]),
        ("human", ["down", "down", "pingb", "submit"]),
        ("dwarf", ["right", "pingc"]),
        ("dwarf", ["left", "left", "pingd", "submit"])
    ]
    for actions in action_list:
        send_actions(*actions)


def send_actions(player, actions):
    print("\nBeginning new action sequence for player: {}".format(player))
    url = "ws://localhost:4649/hmt/{}".format(player)

    for a in actions:
        print("Sending action: ({}) for player: ({})".format(a, player))
        execute_action(url, a)


def execute_action(url, action):
    # Command to send to Game env
    action_command = {"command": "execute_action",
                      "action": action}
    # Planning phase: no inputs
    # Pinging phase: no inputs
    return send(url, str(action_command))


def get_state(url):
    state = send(url, '{"command":"get_state"}')
    return loads(state)


def send(url, message):
    with connect(url) as websocket:
        websocket.send(message)
        return websocket.recv()


if __name__ == "__main__":
    main()
