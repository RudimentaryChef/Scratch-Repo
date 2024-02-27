from stable_baselines3 import PPO
from game.dice_adventure_python_env import DiceAdventurePythonEnv
from time import sleep
from json import dumps


def main2():
    actions = {
        "2S": ["up", "up", "pinga", "submit"]
    }
    action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                  5: 'submit', 6: 'pinga', 7: 'pingb', 8: 'pingc', 9: 'pingd', 10: 'undo'}
    amap_rev = {v: k for k, v in action_map.items()}
    # model_filename = "../train/model/dice_adventure_ppo_model_1.zip"
    model_dir = "train/model/"
    for p, a_list in actions.items():
        env = get_env(p, model_dir)
        # env.render()
        env.load_threshold = 1
        for a in a_list:
            print(f"Sending action: {a} for player: {p}")
            obs, rewards, dones, truncated, info = env.step(amap_rev[a])
            sleep(1)
#giant->dwarf
#dwarf->giant


def main():
    action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                           5: 'submit', 6: 'pinga', 7: 'pingb', 8: 'pingc', 9: 'pingd', 10: 'undo'}
    action_map_rev = {v: k for k, v in action_map.items()}

    model_filename = "train/2/model/dice_adventure_ppo_model.zip"
    model = PPO.load(model_filename)

    player = "Dwarf"
    env = get_env(player, model_filename)
    env.load_threshold = 1
    # state = env.get_state()

    obs = env.reset()[0]
    while True:
        action, _states = model.predict(obs)
        # up -> left | down -> right | left -> up | right -> down
        # action_remap = {"up": "left", "down": "right", "left": "up", "right": "down"}
        # Temporarily remap directional actions
        action_remap = {3: 0, 4: 2, 0: 3, 2: 4}
        if int(action) in action_remap:
            action = action_remap[int(action)]
        print(f"Sending action: {action_map[int(action)]} for player: {player}")
        obs, rewards, dones, truncated, info = env.step(action)
        sleep(1)


def get_env(init_player, model_dir):
    return DiceAdventurePythonEnv(id_=0,
                             level=1,
                             player=init_player,
                             model_number=2,
                             model_dir=model_dir,
                             server="unity",
                             automate_players=True
                             )


if __name__ == "__main__":
    main()
