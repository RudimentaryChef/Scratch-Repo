from abc import ABC
from datetime import datetime
# from dice_adventure import DiceAdventure
from dice_adventure import TerminationException
from dice_adventure_python_env import DiceAdventurePythonEnv
# from gymnasium.vector import AsyncVectorEnv
# from gymnasium.vector import SyncVectorEnv
# from gymnasium import make
from os import makedirs
from stable_baselines3 import PPO
from stable_baselines3.common.utils import set_random_seed
# from stable_baselines3.common.env_util import DummyVecEnv
# from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv
# from stable_baselines3.common.vec_env import VecMonitor
from tqdm import tqdm

# One hundred billion
NUM_TIME_STEPS = 100000000000


def main(player="1S"):
    tensor_board_log = "./dice_adventure_tensorboard/"
    monitor_dir = "./monitoring/"
    model_filename = "dice_adventure_ppo_model"
    log_filename = "dice_adventure_ppo_model_logfile.txt"
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
    model = PPO("MlpPolicy", vec_env, verbose=0, tensorboard_log=tensor_board_log, device="cpu")
    try:
        save_callback = SaveCallback(model_filename=model_filename, log_filename=log_filename)
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
                                      # server="unity",
                                      server="local",
                                      # Kwargs
                                      level=1, render=False, num_repeats=1000, level_sampling=True, round_cap=250,
                                      track_metrics=False, metrics_dir=monitor_dir)
    set_random_seed(int(env_id))
    return _init


class SaveCallback(BaseCallback, ABC):
    def __init__(self, model_filename, log_filename):
        super().__init__()
        self.time_steps = 0
        self.threshold = 250000
        self.logfile_threshold = 1000
        self.model_filename = model_filename
        self.log_filename = log_filename
        self.version = 1

        self.pbar = tqdm(total=NUM_TIME_STEPS)
        with open(self.log_filename, "w") as file:
            file.write("timestamp,time_steps,version\n")

    def _on_step(self):
        self.time_steps += 1
        self.pbar.update(1)

        if self.time_steps % self.threshold == 0:
            self.save_model()
        else:
            if self.time_steps % self.logfile_threshold == 0:
                self.save_logfile()

    def save_model(self):
        self.model.save(self.model_filename)
        self.save_logfile()
        self.version += 1

    def save_logfile(self):
        with open(self.log_filename, "a") as file:
            file.write(",".join([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(self.time_steps),
                f"{self.version}\n"
            ]))


if __name__ == "__main__":
    main()
