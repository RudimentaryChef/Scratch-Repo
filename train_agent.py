from abc import ABC
from game.env.dice_adventure_python_env import DiceAdventurePythonEnv
from os import listdir
from os import makedirs
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv
from tqdm import tqdm
from json import loads


############
# TRAINING #
############

def train():
    config = loads(open("game/config/train_config.json").read())
    if config["TRAINING_SETTINGS"]["GLOBAL"]["model_type"] == "ppo":
        _train_ppo(config)
    elif config["TRAINING_SETTINGS"]["GLOBAL"]["model_type"] == "htn":
        _train_htn(config)
    else:
        raise Exception("The DiceAdventurePythonEnv environment only supports model types: {ppo, htn}.")


def _train_ppo(config):
    save_callback = SaveCallback(model_type=config["TRAINING_SETTINGS"]["GLOBAL"]["model_type"],
                                 model_number=config["TRAINING_SETTINGS"]["GLOBAL"]["model_number"],
                                 total_time_steps=config["TRAINING_SETTINGS"]["GLOBAL"]["num_time_steps"],
                                 save_threshold=config["TRAINING_SETTINGS"]["GLOBAL"]["save_threshold"])

    kwargs = {**config["ENV_SETTINGS"], **config["GAME_SETTINGS"], "model_number": save_callback.model_number}
    # Create list of vectorized environments for agent
    vec_env = _make_envs(num_envs=config["TRAINING_SETTINGS"]["GLOBAL"]["num_envs"],
                         players=config["TRAINING_SETTINGS"]["GLOBAL"]["players"],
                         env_args=kwargs)

    # Get tensorboard folder info
    tb_name = config["TRAINING_SETTINGS"]["GLOBAL"]["model_type"] + "_" + str(save_callback.model_number)
    try:
        tb_number = max([int(d.split("_")[-1]) for d in listdir(config["GLOBAL_SETTINGS"]["TENSORBOARD_LOG_DIR"])]) + 1
    except:
        tb_number = 1

    if config["TRAINING_SETTINGS"]["GLOBAL"]["model_file"]:
        model = PPO.load(
            config["TRAINING_SETTINGS"]["GLOBAL"]["model_file"],
            env=vec_env,
            device=config["TRAINING_SETTINGS"]["GLOBAL"]["device"],
            tensorboard_log=config["GLOBAL_SETTINGS"]["TENSORBOARD_LOG_DIR"].format(tb_name+"_"+str(tb_number)))
    else:
        model = PPO("MlpPolicy",
                    vec_env,
                    verbose=0,
                    tensorboard_log=config["GLOBAL_SETTINGS"]["TENSORBOARD_LOG_DIR"].format(tb_name+"_"+str(tb_number)),
                    device=config["TRAINING_SETTINGS"]["GLOBAL"]["device"],
                    # Kwargs
                    **config["TRAINING_SETTINGS"]["PPO"])

    model.learn(total_timesteps=config["TRAINING_SETTINGS"]["GLOBAL"]["num_time_steps"],
                callback=save_callback,
                progress_bar=False,
                tb_log_name=tb_name)

    # model.save(MODEL_DIR.format(save_callback.model_number) + "dice_adventure_ppo_model_final")
    print("DONE TRAINING!")


def _train_htn(config):
    pass


################
# ENVIRONMENTS #
################

def _make_envs(num_envs: int, players: list, env_args: dict):
    envs = [
        _get_env(env_id=str(i * num_envs + j),
                 player=p,
                 env_args=env_args) #,
                 # model_number=save_callback.model_number)
        for i, p in enumerate(players)
        for j in range(num_envs)
    ]
    return SubprocVecEnv(envs)


def _get_env(env_id, player, env_args):
    # Needs to be function so that it is callable
    def env_fxn():
        return DiceAdventurePythonEnv(id_=env_id,
                                      player=player,
                                      # Kwargs
                                      **env_args)

    return env_fxn

################
# MODEL SAVING #
################


class SaveCallback(BaseCallback, ABC):
    def __init__(self, model_type, model_number, total_time_steps, save_threshold):
        super().__init__()
        self.time_steps = 0
        self.save_threshold = save_threshold
        self.model_type = model_type
        self.model_file = None
        self.model_number = model_number
        self.model_dir = "train/{}/model/".format(self.model_number)
        # self.model_filename, self.log_filename, self.model_number = self._get_filepaths()
        self.version = 1
        self.pbar = tqdm(total=total_time_steps)

        self._setup_directories()

    def _setup_directories(self):
        if self.model_type == "ppo":
            self.model_file = "dice_adventure_ppo_modelchkpt-{}"
        elif self.model_type == "htn":
            self.model_file = "dice_adventure_htn_modelchkpt-{}"

        if not self.model_number:
            self.model_number = max([int(directory) for directory in listdir("train/")]) + 1
        makedirs(self.model_dir, exist_ok=True)

    def _on_step(self):
        self.time_steps += 1
        self.pbar.update(1)

        if self.time_steps % self.save_threshold == 0:
            self._save_model()

    def _save_model(self):
        self.model.save(self.model_dir + self.model_file.format(self.version))
        self.version += 1

