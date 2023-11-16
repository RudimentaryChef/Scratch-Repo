from abc import ABC

from dice_adventure import DiceAdventure
from dice_adventure import TerminationException
from dice_adventure_python_env import DiceAdventurePythonEnv
from gymnasium.vector import AsyncVectorEnv
from gymnasium.vector import SyncVectorEnv
from gymnasium import make
from os import makedirs
from stable_baselines3 import PPO
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.env_util import DummyVecEnv
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import BaseCallback
from tqdm import tqdm


NUM_TIME_STEPS = 1000000000


def main(player="1S"):
    tensor_board_log = "./dice_adventure_tensorboard/"
    model_filename = "dice_adventure_ppo_model"
    makedirs(tensor_board_log, exist_ok=True)

    # game = DiceAdventure(level=1, render=False, num_repeats=100)
    players = ["1S", "2S", "3S"]

    envs = [
        lambda: DiceAdventurePythonEnv(player=p,
                                       model_filename=model_filename,
                                       level=1, render=False, num_repeats=1000)
        for p in players
    ]
    # env = DiceAdventurePythonEnv(game, player, model_filename)
    vec_env = DummyVecEnv(envs)
    model = PPO("MlpPolicy", vec_env, verbose=0, tensorboard_log=tensor_board_log)
    try:
        save_callback = SaveCallback(filename=model_filename)
        model.learn(total_timesteps=NUM_TIME_STEPS, callback=save_callback, progress_bar=False)
    except TerminationException:
        pass

    model.save(model_filename)
    print("DONE TRAINING!")
    """
    obs = env.reset()
    while True:
        action, _states = model.predict(obs)
        obs, rewards, dones, info = env.step(action)
    """


def make_env(env_id: str, rank: int, seed: int = 0):
    """
    Utility function for multiprocessed env.

    :param env_id: the environment ID
    :param num_env: the number of environments you wish to have in subprocesses
    :param seed: the inital seed for RNG
    :param rank: index of the subprocess
    """
    def _init():
        env = make(env_id, render_mode="human")
        env.reset(seed=seed + rank)
        return env
    set_random_seed(seed)
    return _init


class SaveCallback(BaseCallback, ABC):
    def __init__(self, filename):
        super().__init__()
        self.time_steps = 0
        self.threshold = 1000000
        self.filename = filename
        self.pbar = tqdm(total=NUM_TIME_STEPS)

    def _on_step(self):
        self.time_steps += 1
        self.pbar.update(1)
        if self.time_steps % self.threshold == 0:
            self.model.save(self.filename)


if __name__ == "__main__":
    main()
