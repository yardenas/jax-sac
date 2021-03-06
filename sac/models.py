import haiku as hk
import jax
import jax.nn as jnn
import jax.numpy as jnp
from tensorflow_probability.substrates import jax as tfp

tfd = tfp.distributions
tfb = tfp.bijectors


class Actor(hk.Module):
    def __init__(self, output_sizes, min_stddev):
        super().__init__()
        self.output_sizes = output_sizes
        self._min_stddev = min_stddev

    def __call__(self, observation):
        mlp = hk.nets.MLP(self.output_sizes)
        mu, stddev = jnp.split(mlp(observation), 2, -1)
        stddev = jnn.softplus(stddev) + self._min_stddev
        multivariate_normal_diag = tfd.MultivariateNormalDiag(
            loc=mu,
            scale_diag=stddev
        )
        # Squash actions to [-1, 1]
        squashed = tfd.TransformedDistribution(
            multivariate_normal_diag,
            StableTanhBijector()
        )
        return SampleDist(squashed)


class DoubleCritic(hk.Module):
    def __init__(self, output_sizes):
        super().__init__()
        self.output_sizes = output_sizes

    def __call__(self, observation, action):
        x = jnp.concatenate([observation, action], -1)
        mlp1 = hk.nets.MLP(self.output_sizes)
        mlp2 = hk.nets.MLP(self.output_sizes)

        def to_dist(q_fn):
            mu = jnp.squeeze(q_fn(x), -1)
            return tfd.Normal(loc=mu, scale=1.0)

        return jax.tree_map(to_dist, [mlp1, mlp2])


class EntropyBonus(hk.Module):
    def __init__(self):
        super().__init__()

    def __call__(self, log_pi):
        log_temprature = hk.get_parameter(
            "log_temprature",
            shape=[1, ],
            dtype=jnp.float32,
            init=hk.initializers.Constant(0.0)
        )
        return -jnp.exp(log_temprature) * log_pi


# Following https://github.com/tensorflow/probability/issues/840 and
# https://github.com/tensorflow/probability/issues/840.
class StableTanhBijector(tfb.Tanh):
    def __init__(self, validate_args=False, name='tanh_stable_bijector'):
        super(StableTanhBijector, self).__init__(validate_args=validate_args,
                                                 name=name)

    def _inverse(self, y):
        dtype = y.dtype
        y = y.astype(jnp.float32)
        y = jnp.clip(y, -0.99999997, 0.99999997)
        y = jnp.arctanh(y)
        return y.astype(dtype)


class SampleDist(object):
    def __init__(self, dist, samples=100):
        self._dist = dist
        self._samples = samples

    @property
    def name(self):
        return 'SampleDist'

    def __getattr__(self, name):
        return getattr(self._dist, name)

    def mean(self, seed):
        samples = self._dist.sample(self._samples, seed=seed)
        return jnp.mean(samples, 0)

    def mode(self, seed):
        sample = self._dist.sample(self._samples, seed=seed)
        logprob = self._dist.log_prob(sample)
        return sample[jnp.argmax(logprob)]

    def entropy(self, seed):
        sample = self._dist.sample(self._samples, seed=seed)
        logprob = self.log_prob(sample)
        return -jnp.mean(logprob, 0)
