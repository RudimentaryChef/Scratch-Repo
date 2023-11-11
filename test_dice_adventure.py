from dice_adventure import DiceAdventure
import json
from random import choice
from random import seed
from time import sleep
from tqdm import trange


def speed_test(game):
    for _ in trange(1000000000):
        c = choice(chars)
        a = choice(actions)
        game.send_action(c, a)
        print("Level: ", game.curr_level_num)
        print(f"Character: {c} | Action: {a}")
        print(f"Phase: {game.phases[game.phase_num]}")
        sleep(.1)

seed(0)
chars = ["1S", "2S", "3S"]
actions = ['left', 'right', 'up', 'down', 'wait', 'submit', 'PA', 'PB', 'PC', 'PD', 'undo']
# Speed test no render
game = DiceAdventure(level=1, render=True, num_repeats=0)
speed_test(game)

state = game.get_state()
with open("sample_lowfi_state.json", "w") as file:
    file.write(json.dumps(state, indent=2))
print(state)
