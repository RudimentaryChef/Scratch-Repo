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
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.vec_env import VecMonitor
from tqdm import tqdm


NUM_TIME_STEPS = 1000000000


def main(player="1S"):
    tensor_board_log = "./dice_adventure_tensorboard/"
    monitor_dir = "./monitoring/"
    model_filename = "dice_adventure_ppo_model"
    makedirs(tensor_board_log, exist_ok=True)

    # game = DiceAdventure(level=1, render=False, num_repeats=100)
    num_env_copies = 3
    players = ["1S", "2S", "3S"]
    envs = [
        make_env(str(i*num_env_copies+j), p, model_filename, monitor_dir)
        for i, p in enumerate(players) for j in range(num_env_copies)
    ]
    # env = DiceAdventurePythonEnv(game, player, model_filename)
    vec_env = SubprocVecEnv(envs)
    # vec_env = DummyVecEnv(envs)
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


def make_env(env_id: str, player: str, model_filename: str, monitor_dir: str):
    def _init():
        return DiceAdventurePythonEnv(id_=env_id,
                                       player=player,
                                       model_filename=model_filename,
                                       level=1, render=False, num_repeats=1000,
                                       track_metrics=False, metrics_dir=monitor_dir)
    set_random_seed(int(env_id))
    return _init


class SaveCallback(BaseCallback, ABC):
    def __init__(self, filename):
        super().__init__()
        self.time_steps = 0
        self.threshold = 250000
        self.filename = filename
        self.pbar = tqdm(total=NUM_TIME_STEPS)

    def _on_step(self):
        self.time_steps += 1
        self.pbar.update(1)
        if self.time_steps % self.threshold == 0:
            self.model.save(self.filename)


if __name__ == "__main__":
    main()
