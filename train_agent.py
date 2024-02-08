from abc import ABC
from datetime import datetime
from game.dice_adventure_python_env import DiceAdventurePythonEnv
from game.dice_adventure_python_env import load_model
from os import listdir
from os import makedirs
from os import path
from stable_baselines3 import PPO
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv
from tqdm import tqdm

# One hundred billion
NUM_TIME_STEPS = 100000000000
TENSORBOARD_LOG_DIR = "monitoring/dice_adventure_tensorboard/"
MODEL_DIR = "train/{}/model/"
NUM_ENV_COPIES = 4
# Game Params
AGENT_PLAYER = "Dwarf"  # {Dwarf, Giant, Human}
ALL_PLAYERS = ["Dwarf", "Giant", "Human"]
LOAD_MODEL_FROM_FILE = False


def main():
    save_callback = SaveCallback()

    envs = [
        make_env(env_id=str(i*NUM_ENV_COPIES+j),
                 player=p,
                 model_number=save_callback.model_number)
        for i, p in enumerate(ALL_PLAYERS) for j in range(NUM_ENV_COPIES)
    ]
    # env = DiceAdventurePythonEnv(game, player, model_filename)
    vec_env = SubprocVecEnv(envs)

    if LOAD_MODEL_FROM_FILE:
        model = load_model(model_dir, env=vec_env, device=device)
    else:
        model = PPO("MlpPolicy", vec_env, verbose=0, tensorboard_log=tensor_board_log, device=device, n_steps=2048,
                    batch_size=64)


    model.learn(total_timesteps=NUM_TIME_STEPS, callback=save_callback, progress_bar=False)

    model.save(MODEL_DIR.format(save_callback.model_number) + "dice_adventure_ppo_model_final")
    print("DONE TRAINING!")


def make_env(env_id: str, player: str, model_number: int):
    def _init():
        return DiceAdventurePythonEnv(id_=env_id,
                                      player=player,
                                      model_number=model_number,
                                      env_metrics=True,
                                      server="local",
                                      set_random_seed=True,
                                      # Kwargs
                                      level=1,
                                      render=False,
                                      num_repeats=1000,
                                      level_sampling=True,
                                      round_cap=250,
                                      track_metrics=False,
                                      limit_levels=[1])
    set_random_seed(int(env_id))
    return _init


class SaveCallback(BaseCallback, ABC):
    def __init__(self):
        super().__init__()
        self.time_steps = 0
        self.threshold = 250000
        self.logfile_threshold = 10000
        self.model_filename, self.log_filename, self.model_number = self._get_filepaths()
        self.version = 1
        self.pbar = tqdm(total=NUM_TIME_STEPS)
        # Logfile columns: [timestamp, time_steps, version]

    def _on_step(self):
        self.time_steps += 1
        self.pbar.update(1)

        if self.time_steps % self.threshold == 0:
            self._save_model()
        else:
            if self.time_steps % self.logfile_threshold == 0:
                self._save_logfile()

    def _save_model(self):
        self.model.save(self.model_filename)
        self._save_logfile()
        self.version += 1

    def _save_logfile(self):
        with open(self.log_filename, "a") as file:
            file.write(",".join([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(self.time_steps),
                f"{self.version}\n"
            ]))

    @staticmethod
    def _get_filepaths():
        model_number = max([int(directory) for directory in listdir("train/")])
        model_dir = "train/{}/model/".format(model_number)
        log_dir = "train/{}/log/".format(model_number)
        model_filename = "{}/{}".format(model_dir, "dice_adventure_ppo_model")
        log_filename = "{}/{}".format(log_dir, "dice_adventure_ppo_model_logfile.txt")
        # Create directories
        for dir_ in [model_dir, log_dir]:
            makedirs(dir_, exist_ok=True)
        # Set up log
        with open(log_filename, "w") as file:
            file.write("\n")
        return model_filename, log_filename, model_number


if __name__ == "__main__":
    main()
