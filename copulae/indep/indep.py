from typing import Collection

import numpy as np

from copulae.copula import BaseCopula, Summary
from copulae.stats import random_uniform
from copulae.types import Array
from copulae.utility.annotations import *

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


class IndepCopula(BaseCopula[int]):
    def __init__(self, dim=2, fields: Collection[str] = None):
        r"""
        The Independence copula is the copula that results from a dependency structure in which each individual
        variable is independent of each other. It has no parameters and is defined as

        .. math::

            C(u_1, \dots, u_d) = \prod_i u_i

        Parameters
        ----------
        dim: int, optional
            The dimension of the copula

        fields: list of str
            The names of the data's columns
        """
        super().__init__(dim, "Independent")
        if fields is not None:
            self._columns = list(map(str, fields))
            assert len(fields) == dim, "number of fields must match copula dimension"

    @validate_data_dim({"x": [1, 2]})
    @shape_first_input_to_cop_dim
    @squeeze_output
    def cdf(self, x: Array, log=False):
        return np.log(x).sum(1) if log else x.prod(1)

    def fit(self, data, x0=None, method='ml', verbose=1, optim_options=None, ties='average'):
        print('Fitting not required for Independent Copula')
        return self

    @property
    def params(self):
        return self.dim

    @validate_data_dim({"x": [1, 2]})
    @shape_first_input_to_cop_dim
    @squeeze_output
    def pdf(self, x: Array, log=False):
        return np.repeat(0 if log else 1, len(x))

    @cast_output
    def random(self, n: int, seed: int = None):
        return random_uniform(n, self.dim, seed)

    @select_summary
    def summary(self, category: Literal['copula', 'fit'] = 'copula'):
        return Summary(self, {})
