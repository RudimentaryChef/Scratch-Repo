import pprint
from random import choice
from time import sleep
from tqdm import trange
from environment.dice_adventure_python_env import DiceAdventurePythonEnv

pp = pprint.PrettyPrinter(indent=2)
def main(env):

    action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                  5: 'submit', 6: 'pinga', 7: 'pingb', 8: 'pingc', 9: 'pingd', 10: 'undo'}
    amap_rev = {v: k for k, v in action_map.items()}

    action_sequences = [
        # Pin planning
        [("1S", "up"), ("1S", "up"), ("1S", "pinga"), ("1S", "submit")],
        [("2S", "pingb"), ("2S", "submit")],
        [("3S", "down"), ("3S", "left"), ("3S", "pingc"), ("3S", "submit")],
        # Action planning
        [("1S", "up"), ("1S", "right"), ("1S", "submit")],
        [("2S", "down"), ("2S", "submit")],
        [("3S", "up"), ("3S", "submit")]

    ]

    for seq in action_sequences:
        for i in seq:
            p = env.game.board.objects[i[0]]
            env.step(amap_rev[i[1]], player=i[0])
            print(f"Pin x: {p.pin_x} | Pin y: {p.pin_y}")
            env.render()
            # sleep(1)
    env.render()
    #pp.pprint(env.get_state())


def speed_test(env):
    for i in trange(1000000000):
        a = choice(action_nums)

        # print("Level: ", env.game.curr_level_num)
        """
        print(f"Character: {env.player} | Action: {actions[a]}")
        print(f"ACTION PLAN: {env.game.board.objects[env.player].action_plan}")
        print(f"Phase: {env.game.phases[env.game.phase_num]}")
        print(f"Level: {env.game.curr_level_num}")
        print(f"HEALTH: {[env.game.board.objects[p].health for p in env.game.config['PLAYER_CODES']]}")
        print(f"ACTION POINTS: {[env.game.board.objects[p].action_points for p in env.game.config['PLAYER_CODES']]}")
        """
        #print(f"Phase: {env.game.phases[env.game.phase_num]}")
        #print(f"Level: {env.game.curr_level_num}")



        # print(f"Round: {env.game.num_rounds}")
        # print(f"Character: {env.player} | Action: {actions[a]}")
        res = env.step(a)

        # env.game.render()
        # pp.pprint(env.get_state())
        # sleep(1)


seeds = [i for i in range(500)]
chars = ["1S", "2S", "3S"]
actions = ['left', 'right', 'up', 'down', 'wait', 'submit', 'pinga', 'pingb', 'pingc', 'pingd', 'undo']
action_nums = [i for i in range(len(actions))]

env = DiceAdventurePythonEnv(id_=1,
                             level=1,
                             player="1S",
                             model_dir="model",
                             server="local",  # "unity"
                             round_cap=2,
                             level_sampling=True,
                             automate_players=True,
                             set_random_seed=True,
                             render_verbose=True,
                             num_repeats=2
                             )
speed_test(env)
# main(env)
# state = env.game.get_state()
# with open("sample_lowfi_state.json", "w") as file:
#    file.write(json.dumps(state, indent=2))
# print(state)

