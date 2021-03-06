import arena
import numpy as np
from tensorflow import keras

trained_model_path = "./lmk2exp_model"
model = keras.models.load_model(trained_model_path)

def extract_user_id(obj_id):
    try:
        return "_".join(obj_id.split("_")[1:])
    except:
        return None

class MeanFilter(object):
    def __init__(self, capacity):
        self.history = []
        self.capacity = capacity

    def add(self, data):
        if len(self.history) >= self.capacity:
            self.history.pop(0)
        self.history += [data]

        return np.mean(self.history, axis=0)
