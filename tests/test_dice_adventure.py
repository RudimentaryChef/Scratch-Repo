from random import choice
from tqdm import trange
from environment.dice_adventure_python_env import DiceAdventurePythonEnv


def speed_test(env):
    for i in trange(1000000000):
        a = choice(action_nums)

        # print("Level: ", env.game.curr_level_num)
        print(f"Character: {env.player} | Action: {actions[a]}")
        print(f"Phase: {env.game.phases[env.game.phase_num]}")
        # print(f"Round: {env.game.num_rounds}")
        res = env.step(a)
        # sleep(.1)


seeds = [i for i in range(500)]
chars = ["1S", "2S", "3S"]
actions = ['left', 'right', 'up', 'down', 'wait', 'submit', 'PA', 'PB', 'PC', 'PD', 'undo']
action_nums = [i for i in range(len(actions))]

env = DiceAdventurePythonEnv(id_=0,
                             level=1,
                             player="1S",
                             model_dir="model",
                             server="local",  # "unity"
                             round_cap=2,
                             level_sampling=True
                             )
speed_test(env)
# state = env.game.get_state()
# with open("sample_lowfi_state.json", "w") as file:
#    file.write(json.dumps(state, indent=2))
# print(state)

