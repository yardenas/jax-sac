import random

import numpy as np


class ReplayBuffer(object):
    def __init__(self, capacity, seed, batch_size):
        self._random = random.Random(seed)
        self.capacity = capacity
        self.buffer = []
        self.position = 0
        self._batch_size = batch_size

    def store(self, observation, action, reward, next_observation, terminal,
              *args, **kwargs):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (
            observation, action, reward, next_observation, terminal)
        self.position = int((self.position + 1) % self.capacity)

    def sample(self, samples):
        for _ in range(samples):
            batch = self._random.sample(self.buffer, self._batch_size)
            observation, action, reward, next_observation, terminal = map(
                np.stack, zip(*batch))
            yield dict(observation=observation, action=action,
                       reward=reward, next_observation=next_observation,
                       terminal=terminal)

    def __len__(self):
        return len(self.buffer)
