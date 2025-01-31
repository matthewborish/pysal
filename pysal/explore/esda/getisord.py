"""
Getis and Ord G statistic for spatial autocorrelation
"""
__author__ = "Sergio J. Rey <srey@asu.edu>, Myunghwa Hwang <mhwang4@gmail.com> "
__all__ = ['G', 'G_Local']

from pysal.lib.common import np, stats
from pysal.lib.weights.spatial_lag import lag_spatial as slag
from .tabular import _univariate_handler

PERMUTATIONS = 999


class G(object):
    """
    Global G Autocorrelation Statistic

    Parameters
    ----------
    y             : array (n,1)
                    Attribute values
    w             : W
                   DistanceBand W spatial weights based on distance band
    permutations  : int
                    the number of random permutations for calculating pseudo p_values

    Attributes
    ----------
    y             : array
                    original variable
    w             : W
                    DistanceBand W spatial weights based on distance band
    permutation   : int
                    the number of permutations
    G             : float
                    the value of statistic
    EG            : float
                    the expected value of statistic
    VG            : float
                    the variance of G under normality assumption
    z_norm        : float
                    standard normal test statistic
    p_norm        : float
                    p-value under normality assumption (one-sided)
    sim           : array
                    (if permutations > 0)
                    vector of G values for permutated samples
    p_sim         : float
                    p-value based on permutations (one-sided)
                    null: spatial randomness
                    alternative: the observed G is extreme it is either extremely high or extremely low
    EG_sim        : float
                    average value of G from permutations
    VG_sim        : float
                    variance of G from permutations
    seG_sim       : float
                    standard deviation of G under permutations.
    z_sim         : float
                    standardized G based on permutations
    p_z_sim       : float
                    p-value based on standard normal approximation from
                    permutations (one-sided)

    Notes
    -----
    Moments are based on normality assumption.

    For technical details see :cite:`Getis_2010` and :cite:`Ord_2010`.


    Examples
    --------
    >>> import pysal.lib
    >>> import numpy
    >>> numpy.random.seed(10)

    Preparing a point data set
    >>> points = [(10, 10), (20, 10), (40, 10), (15, 20), (30, 20), (30, 30)]

    Creating a weights object from points
    >>> w = pysal.lib.weights.DistanceBand(points,threshold=15)
    >>> w.transform = "B"

    Preparing a variable
    >>> y = numpy.array([2, 3, 3.2, 5, 8, 7])

    Applying Getis and Ord G test
    >>> from pysal.explore.esda.getisord import G
    >>> g = G(y,w)

    Examining the results
    >>> round(g.G, 3)
    0.557

    >>> round(g.p_norm, 3)
    0.173

    """

    def __init__(self, y, w, permutations=PERMUTATIONS):
        y = np.asarray(y).flatten()
        self.n = len(y)
        self.y = y
        w.transform = "B"
        self.w = w
        self.permutations = permutations
        self.__moments()
        self.y2 = y * y
        y = y.reshape(len(y), 1)  # Ensure that y is an n by 1 vector, otherwise y*y.T == y*y
        self.den_sum = (y * y.T).sum() - (y * y).sum()
        self.G = self.__calc(self.y)
        self.z_norm = (self.G - self.EG) / np.sqrt(self.VG)
        self.p_norm = 1.0 - stats.norm.cdf(np.abs(self.z_norm))

        if permutations:
            sim = [self.__calc(np.random.permutation(self.y))
                   for i in range(permutations)]
            self.sim = sim = np.array(sim)
            above = sim >= self.G
            larger = sum(above)
            if (self.permutations - larger) < larger:
                larger = self.permutations - larger
            self.p_sim = (larger + 1.0) / (permutations + 1.)
            self.EG_sim = sum(sim) / permutations
            self.seG_sim = sim.std()
            self.VG_sim = self.seG_sim ** 2
            self.z_sim = (self.G - self.EG_sim) / self.seG_sim
            self.p_z_sim = 1. - stats.norm.cdf(np.abs(self.z_sim))

    def __moments(self):
        y = self.y
        n = self.n
        w = self.w
        n2 = n * n
        s0 = w.s0
        self.EG = s0 / (n * (n - 1))
        s02 = s0 * s0
        s1 = w.s1
        s2 = w.s2
        b0 = (n2 - 3 * n + 3) * s1 - n * s2 + 3 * s02
        b1 = (-1.) * ((n2 - n) * s1 - 2 * n * s2 + 6 * s02)
        b2 = (-1.) * (2 * n * s1 - (n + 3) * s2 + 6 * s02)
        b3 = 4 * (n - 1) * s1 - 2 * (n + 1) * s2 + 8 * s02
        b4 = s1 - s2 + s02
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2
        self.b3 = b3
        self.b4 = b4
        y2 = y * y
        y3 = y * y2
        y4 = y2 * y2
        EG2 = (b0 * (sum(
            y2) ** 2) + b1 * sum(y4) + b2 * (sum(y) ** 2) * sum(y2))
        EG2 += b3 * sum(y) * sum(y3) + b4 * (sum(y) ** 4)
        EG2NUM = EG2
        EG2DEN = (((sum(y) ** 2 - sum(y2)) ** 2) * n * (n - 1) * (
            n - 2) * (n - 3))
        self.EG2 = EG2NUM / EG2DEN
        self.VG = self.EG2 - self.EG ** 2

    def __calc(self, y):
        yl = slag(self.w, y)
        self.num = y * yl
        return self.num.sum() / self.den_sum

    @property
    def _statistic(self):
        """ Standardized accessor for pysal.explore.esda statistics"""
        return self.G

    @classmethod
    def by_col(cls, df, cols, w=None, inplace=False, pvalue='sim', outvals=None, **stat_kws):
        """
        Function to compute a G statistic on a dataframe

        Arguments
        ---------
        df          :   pandas.DataFrame
                        a pandas dataframe with a geometry column
        cols        :   string or list of string
                        name or list of names of columns to use to compute the statistic
        w           :   pysal weights object
                        a weights object aligned with the dataframe. If not provided, this
                        is searched for in the dataframe's metadata
        inplace     :   bool
                        a boolean denoting whether to operate on the dataframe inplace or to
                        return a series contaning the results of the computation. If
                        operating inplace, the derived columns will be named 'column_g'
        pvalue      :   string
                        a string denoting which pvalue should be returned. Refer to the
                        the G statistic's documentation for available p-values
        outvals     :   list of strings
                        list of arbitrary attributes to return as columns from the
                        G statistic
        **stat_kws  :   keyword arguments
                        options to pass to the underlying statistic. For this, see the
                        documentation for the G statistic.

        Returns
        -------
        If inplace, None, and operation is conducted on dataframe in memory. Otherwise,
        returns a copy of the dataframe with the relevant columns attached.


        """
        return _univariate_handler(df, cols, w=w, inplace=inplace, pvalue=pvalue,
                                   outvals=outvals, stat=cls,
                                   swapname=cls.__name__.lower(), **stat_kws)



class G_Local(object):
    """
    Generalized Local G Autocorrelation

    Parameters
    ----------
    y : array
        variable
    w : W
        DistanceBand, weights instance that is based on threshold distance
        and is assumed to be aligned with y
    transform : {'R', 'B'}
                the type of w, either 'B' (binary) or 'R' (row-standardized)
    permutations : int
                  the number of random permutations for calculating
                  pseudo p values
    star : boolean
           whether or not to include focal observation in sums (default: False)

    Attributes
    ----------
    y : array
       original variable
    w : DistanceBand W
       original weights object
    permutations : int
                  the number of permutations
    Gs : array
        of floats, the value of the orginal G statistic in Getis & Ord (1992)
    EGs : float
         expected value of Gs under normality assumption
         the values is scalar, since the expectation is identical
         across all observations
    VGs : array
         of floats, variance values of Gs under normality assumption
    Zs : array
        of floats, standardized Gs
    p_norm : array
            of floats, p-value under normality assumption (one-sided)
            for two-sided tests, this value should be multiplied by 2
    sim : array
         of arrays of floats (if permutations>0), vector of I values
         for permutated samples
    p_sim : array
           of floats, p-value based on permutations (one-sided)
           null - spatial randomness
           alternative - the observed G is extreme it is either extremely high or extremely low
    EG_sim : array
            of floats, average value of G from permutations
    VG_sim : array
            of floats, variance of G from permutations
    seG_sim : array
             of floats, standard deviation of G under permutations.
    z_sim : array
           of floats, standardized G based on permutations
    p_z_sim : array
             of floats, p-value based on standard normal approximation from
             permutations (one-sided)

    Notes
    -----
    To compute moments of Gs under normality assumption,
    PySAL considers w is either binary or row-standardized.
    For binary weights object, the weight value for self is 1
    For row-standardized weights object, the weight value for self is
    1/(the number of its neighbors + 1).


    For technical details see :cite:`Getis_2010` and :cite:`Ord_2010`.


    Examples
    --------
    >>> import pysal.lib
    >>> import numpy
    >>> numpy.random.seed(10)

    Preparing a point data set

    >>> points = [(10, 10), (20, 10), (40, 10), (15, 20), (30, 20), (30, 30)]

    Creating a weights object from points

    >>> w = pysal.lib.weights.DistanceBand(points,threshold=15)

    Prepareing a variable

    >>> y = numpy.array([2, 3, 3.2, 5, 8, 7])

    Applying Getis and Ord local G test using a binary weights object

    >>> from pysal.explore.esda.getisord import G_Local
    >>> lg = G_Local(y,w,transform='B')

    Examining the results

    >>> lg.Zs
    array([-1.0136729 , -0.04361589,  1.31558703, -0.31412676,  1.15373986,
            1.77833941])
    >>> round(lg.p_sim[0], 3)
    0.101

    >>> numpy.random.seed(10)

    Applying Getis and Ord local G* test using a binary weights object
    >>> lg_star = G_Local(y,w,transform='B',star=True)

    Examining the results
    >>> lg_star.Zs
    array([-1.39727626, -0.28917762,  0.65064964, -0.28917762,  1.23452088,
            2.02424331])
    >>> round(lg_star.p_sim[0], 3)
    0.101

    >>> numpy.random.seed(12345)

    Applying Getis and Ord local G test using a row-standardized weights object
    >>> lg = G_Local(y,w,transform='R')

    Examining the results
    >>> lg.Zs
    array([-0.62074534, -0.01780611,  1.31558703, -0.12824171,  0.28843496,
            1.77833941])
    >>> round(lg.p_sim[0], 3)
    0.103

    >>> numpy.random.seed(10)

    Applying Getis and Ord local G* test using a row-standardized weights object

    >>> lg_star = G_Local(y,w,transform='R',star=True)

    Examining the results
    >>> lg_star.Zs
    array([-0.62488094, -0.09144599,  0.41150696, -0.09144599,  0.24690418,
            1.28024388])
    >>> round(lg_star.p_sim[0], 3)
    0.101

    """
    def __init__(self, y, w, transform='R', permutations=PERMUTATIONS, star=False):
        y = np.asarray(y).flatten()
        self.n = len(y)
        self.y = y
        self.w = w
        self.w_original = w.transform
        self.w.transform = self.w_transform = transform.lower()
        self.permutations = permutations
        self.star = star
        self.calc()
        self.p_norm = np.array(
            [1 - stats.norm.cdf(np.abs(i)) for i in self.Zs])
        if permutations:
            self.__crand()
            sim = np.transpose(self.rGs)
            above = sim >= self.Gs
            larger = sum(above)
            low_extreme = (self.permutations - larger) < larger
            larger[low_extreme] = self.permutations - larger[low_extreme]
            self.p_sim = (larger + 1.0) / (permutations + 1)
            self.sim = sim
            self.EG_sim = sim.mean()
            self.seG_sim = sim.std()
            self.VG_sim = self.seG_sim * self.seG_sim
            self.z_sim = (self.Gs - self.EG_sim) / self.seG_sim
            self.p_z_sim = 1 - stats.norm.cdf(np.abs(self.z_sim))

    def __crand(self):
        y = self.y
        rGs = np.zeros((self.n, self.permutations))
        n_1 = self.n - 1
        rid = list(range(n_1))
        prange = list(range(self.permutations))
        k = self.w.max_neighbors + 1
        rids = np.array([np.random.permutation(rid)[0:k] for i in prange])
        ids = np.arange(self.w.n)
        ido = self.w.id_order
        wc = self.__getCardinalities()
        if self.w_transform == 'r':
            den = np.array(wc) + self.star
        else:
            den = np.ones(self.w.n)
        for i in range(self.w.n):
            idsi = ids[ids != i]
            np.random.shuffle(idsi)
            yi_star = y[i] * self.star
            wci = wc[i]
            rGs[i] = (y[idsi[rids[:, 0:wci]]]).sum(1) + yi_star
            rGs[i] = (np.array(rGs[i]) / den[i]) / (
                self.y_sum - (1 - self.star) * y[i])
        self.rGs = rGs

    def __getCardinalities(self):
        ido = self.w.id_order
        self.wc = np.array(
            [self.w.cardinalities[ido[i]] for i in range(self.n)])
        return self.wc

    def calc(self):
        y = self.y
        y2 = y * y
        self.y_sum = y_sum = sum(y)
        y2_sum = sum(y2)

        if not self.star:
            yl = 1.0 * slag(self.w, y)
            ydi = y_sum - y
            self.Gs = yl / ydi
            N = self.n - 1
            yl_mean = ydi / N
            s2 = (y2_sum - y2) / N - (yl_mean) ** 2
        else:
            self.w.transform = 'B'
            yl = 1.0 * slag(self.w, y)
            yl += y
            if self.w_transform == 'r':
                yl = yl / (self.__getCardinalities() + 1.0)
            self.Gs = yl / y_sum
            N = self.n
            yl_mean = y.mean()
            s2 = y.var()

        EGs_num, VGs_num = 1.0, 1.0
        if self.w_transform == 'b':
            W = self.__getCardinalities()
            W += self.star
            EGs_num = W * 1.0
            VGs_num = (W * (1.0 * N - W)) / (1.0 * N - 1)

        self.EGs = (EGs_num * 1.0) / N
        self.VGs = (VGs_num) * (1.0 / (N ** 2)) * ((s2 * 1.0) / (yl_mean ** 2))
        self.Zs = (self.Gs - self.EGs) / np.sqrt(self.VGs)

        self.w.transform = self.w_original

    @property
    def _statistic(self):
        """Standardized accessor for pysal.explore.esda statistics"""
        return self.Gs

    @classmethod
    def by_col(cls, df, cols, w=None, inplace=False, pvalue='sim', outvals=None, **stat_kws):
        """
        Function to compute a G_Local statistic on a dataframe

        Arguments
        ---------
        df          :   pandas.DataFrame
                        a pandas dataframe with a geometry column
        cols        :   string or list of string
                        name or list of names of columns to use to compute the statistic
        w           :   pysal weights object
                        a weights object aligned with the dataframe. If not provided, this
                        is searched for in the dataframe's metadata
        inplace     :   bool
                        a boolean denoting whether to operate on the dataframe inplace or to
                        return a series contaning the results of the computation. If
                        operating inplace, the derived columns will be named 'column_g_local'
        pvalue      :   string
                        a string denoting which pvalue should be returned. Refer to the
                        the G_Local statistic's documentation for available p-values
        outvals     :   list of strings
                        list of arbitrary attributes to return as columns from the
                        G_Local statistic
        **stat_kws  :   keyword arguments
                        options to pass to the underlying statistic. For this, see the
                        documentation for the G_Local statistic.

        Returns
        --------
        If inplace, None, and operation is conducted on dataframe in memory. Otherwise,
        returns a copy of the dataframe with the relevant columns attached.

        See also
        --------

        G_Local

        """
        return _univariate_handler(df, cols, w=w, inplace=inplace, pvalue=pvalue,
                                   outvals=outvals, stat=cls,
                                   swapname=cls.__name__.lower(), **stat_kws)
