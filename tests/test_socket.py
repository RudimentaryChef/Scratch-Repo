from json import dumps
from json import loads
from random import choice
from websockets.sync.client import connect


def main():
    players = ["human", "dwarf", "giant"]
    test_get_state(players)
    test_execute_action(players)


def get_state(player):
    state = send('{"command":"get_state"}', player)
    print(state)
    return loads(state)


def send(message, player):
    url = f"ws://localhost:4649/hmt/{player}"
    with connect(url) as websocket:
        websocket.send(message)
        return websocket.recv()


def send_action(action, port):
    return send(action, port)


def test_get_state(players):
    for p in players:
        state = get_state(p)
        with open(f"sample_state-port-{p}.json", "w") as file:
            file.write(dumps(state, indent=2))


def test_execute_action(players):
    for p in players:
        actions = {0: 'interact', 1: 'left', 2: 'right', 3: 'up', 4: 'down'}
        action = choice(list(actions.keys()))
        # Command to send to Game env
        action_command = {"command": "execute_action",
                          "action": "move" if action != 0 else "interact",
                          "inputs": [actions[action]] if action != 0 else []}
        send_action(str(action_command), p)


if __name__ == "__main__":
    main()
