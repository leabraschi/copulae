from typing import Collection, Optional, Union

import numpy as np
from scipy.stats import multivariate_normal as mvn

from copulae.core import pseudo_obs
from copulae.types import Array
from .estimators import expectation_maximization, gradient_descent, k_means
from .exception import GMCFitMethodError, GMCNotFittedError, GMCParamMismatchError
from .parameter import GMCParam
from .random import random_gmcm

__all__ = ['GaussianMixtureCopula']


class GaussianMixtureCopula:
    r"""
    The Gaussian Mixture Copula (GMC).

    A Gaussian Copula has many normal marginal densities bound together by a single multivariate and uni-model
    Gaussian density. However, if a dataset has multiple modes (peaks) with different dependence structure, the
    applicability of the Gaussian Copula gets severely limited. A Gaussian Mixture Copula on the other hand
    allows modeling of data with many modes (peaks).

    The GMC's dependence structure is obtained from a Gaussian Mixture Model (GMM). For a GMC with :math:`M`
    components and :math:`d` dimensions, the density (PDF) is given by

    .. math::

        \phi = \sum_i^M w_i \phi_i (x_1, x_2, \dots, x_d; \theta_i)

        \text{s.t.}

        \sum^M_i w_i = 1

        0 \leq w_i \leq 1 \forall i \in [1, \dots, M]

        \text{where}

        w_i = \text{weight of the marginal density}

        \phi_i = \text{marginal density}

        \theta_i = \text{parameters of the Gaussian marginal}

    The Gaussian Mixture Copula is thus given by

    .. math::

        C(u_1, u_2, \dots, u_d; \Theta) = \frac{\phi(\Phi_1^{-1}(u_1), \Phi_2^{-1}(u_2), \dots, \Phi_d^{-1}(u_d); \Theta}
            {\phi_1(\Phi_1^{-1}(u_1)) \cdot \phi_2(\Phi_2^{-1}(u_2)) \cdots \phi_d(\Phi_1^{-1}(u_d))}

        \text{where}

        \Phi_i = \text{Inverse function of GMM marginal CDF}

        \Theta = (\w_i, \theta_i) \forall i \in [1, \dots, M]
    """

    def __init__(self, n_clusters: int, ndim: int, param: Union[GMCParam, np.ndarray, Collection[float]] = None):
        """
        Creates a Gaussian Mixture Copula

        Parameters
        ----------
        n_clusters : int
            The number of clusters
        ndim : int
            The number of dimension for each Gaussian component

        param : GMCParam, optional
            The initial parameter for the model
        """
        self.n_clusters = n_clusters
        self.n_dim = ndim
        self.params = param

    def cdf(self, data: Array, log=False) -> Union[np.ndarray, float]:
        """
        Returns the cumulative distribution function (CDF) of the copulae.

        The CDF is also the probability of a RV being less or equal to the value specified. Equivalent to the 'p'
        generic function in R.

        Parameters
        ----------
        data : ndarray
            Vector or matrix of the observed data. This vector must be (n x d) where `d` is the dimension of
            the copula

        log : bool
            If True, the log of the probability is returned

        Returns
        -------
        np.ndarray or float
            The CDF of the random variates
        """
        if self.params is None:
            raise GMCNotFittedError

        out = np.zeros(len(data))
        for prob, mean, cov in self.params:
            out += prob * (mvn.logcdf(data, mean, cov) if log else mvn.logcdf(data, mean, cov))

        return out

    def fit(self, data: np.ndarray, x0: Union[Collection[float], np.ndarray, GMCParam] = None, method='em',
            optim_options: dict = None, ties='average', max_iter=3000, criteria='GMCM', eps=1e-4):
        """
        Fit the copula with specified data

        Parameters
        ----------
        data : ndarray
            Array of data used to fit copula. Usually, data should not be pseudo observations as this will
            skew the model parameters

        x0 : ndarray
            Initial starting point. If value is None, best starting point will be estimated

        method : { 'em' }, optional
            Method of fitting. Supported methods are: 'em' - Expectation Maximization, 'kmean' - K-means

        optim_options : dict, optional
            Keyword arguments to pass into scipy.optimize.minimize. Only applicable for gradient-descent
            optimizations

        ties : { 'average', 'min', 'max', 'dense', 'ordinal' }, optional
            Specifies how ranks should be computed if there are ties in any of the coordinate samples. This is
            effective only if the data has not been converted to its pseudo observations form

        max_iter : int
            Maximum number of iterations

        criteria : { 'GMCM', 'GMM', 'Li' }
            The stopping criteria. Only applicable for Expectation Maximization (EM).  'GMCM' uses the absolute
            difference between the current and last based off the GMCM log likelihood, 'GMM' uses the absolute
            difference between the current and last based off the GMM log likelihood and 'Li' uses the stopping
            criteria defined by Li et. al. (2011)

        eps : float
            The epsilon value for which any absolute delta will mean that the model has converged

        Notes
        -----
        Maximizing the exact likelihood of GMCM is technically intractable using expectation maximization. The
        pseudo-likelihood

        See Also
        --------
        :code:`scipy.optimize.minimize`: the `scipy minimize <https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html#scipy.optimize.minimize>`_ function use for optimization
        """
        method = method.lower()

        if x0 is None or method == 'kmeans':
            self.params = k_means(data, self.n_clusters, self.n_dim)
            if method == 'kmeans':
                return self
        elif isinstance(x0, Collection):
            self.params = GMCParam.from_vector(x0, self.n_clusters, self.n_dim)

        if method == 'pem':
            u = pseudo_obs(data, ties)
            self.params = expectation_maximization(u, self.params, max_iter, criteria, eps)
        elif method == 'sgd':
            u = pseudo_obs(data, ties)
            self.params = gradient_descent(u, self.params, max_iter=max_iter, **optim_options)
        else:
            raise GMCFitMethodError(f"Invalid method: {method}. Use one of (kmeans, pem, sgd)")

        return self

    def log_lik(self, data: np.ndarray, *, to_pobs=True) -> float:
        r"""
         Returns the log likelihood (LL) of the copula given the data.

        The greater the LL (closer to :math:`\infty`) the better.

        Parameters
        ----------
        data: ndarray
            Data set used to calculate the log likelihood
        to_pobs: bool
            If True, converts the data input to pseudo observations.

        Returns
        -------
        float
            Log Likelihood

        """
        data = self.pobs(data) if to_pobs else data

        return self.pdf(data, log=True).sum()

    @property
    def params(self) -> GMCParam:
        """
        The parameter set which describes the copula

        Returns
        -------
        GMCParam
            The model parameter
        """
        raise self._param

    @params.setter
    def params(self, params: Optional[Union[GMCParam, np.ndarray, Collection]]):
        if params is None:
            self._param = None
        elif isinstance(params, GMCParam):
            if params.n_dim != self.n_dim or params.n_clusters != self.n_clusters:
                raise GMCParamMismatchError(f"Expected {self.n_clusters} clusters and {self.n_dim} dimensions "
                                            f"but got {params.n_clusters} and {params.n_dim} respectively instead")
            self._param = params
        elif isinstance(params, Collection):
            self._param = GMCParam.from_vector(params, self.n_clusters, self.n_dim)
        else:
            raise GMCParamMismatchError("Unsupported params type for GaussianMixtureCopula")

    def pdf(self, data: Array, log=False) -> Union[np.ndarray, float]:
        """
        Returns the probability distribution function (PDF) of the copulae.

        The PDF is also the density of the RV at for the particular distribution. Equivalent to the 'd' generic function
        in R.

        Parameters
        ----------
        data: ndarray
            Vector or matrix of observed data

        log: bool, optional
            If True, the density 'd' is given as log(d)

        Returns
        -------
        np.ndarray or float
            The density (PDF) of the RV
        """
        if self.params is None:
            raise GMCNotFittedError

        out = np.zeros(len(data))
        for prob, mean, cov in self.params:
            out += prob * (mvn.logpdf(data, mean, cov) if log else mvn.pdf(data, mean, cov))

        return out

    @staticmethod
    def pobs(data, ties='average'):
        """
        Compute the pseudo-observations for the given data matrix

        Parameters
        ----------
        data: {array_like, DataFrame}
            Random variates to be converted to pseudo-observations

        ties: { 'average', 'min', 'max', 'dense', 'ordinal' }, optional
            Specifies how ranks should be computed if there are ties in any of the coordinate samples

        Returns
        -------
        np.ndarray
            matrix or vector of the same dimension as `data` containing the pseudo observations
        """
        return pseudo_obs(data, ties)

    def random(self, n: int, seed: int = None):
        """
        Generate random observations for the copula

        Parameters
        ----------
        n: int
            Number of observations to be generated

        seed: int, optional
            Seed for the random generator

        Returns
        -------
        np.ndarray
            array of generated observations
        """
        if seed is not None:
            np.random.seed(seed)

        return random_gmcm(n, self.params)

    def summary(self):
        """Constructs the summary information about the copula"""
        raise NotImplementedError
