"""Recommendation strategies based on sampling."""

from typing import Optional

import pandas as pd

from baybe.searchspace import SearchSpace, SearchSpaceType
from baybe.strategies.recommender import NonPredictiveRecommender
from baybe.utils.sampling_algorithms import farthest_point_sampling


class RandomRecommender(NonPredictiveRecommender):
    """
    Recommends experiments randomly.
    """

    compatibility = SearchSpaceType.HYBRID

    def _recommend_hybrid(
        self,
        searchspace: SearchSpace,
        batch_quantity: int,
        candidates_comp: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        cont_random = searchspace.continuous.samples_random(n_points=batch_quantity)
        if searchspace.type == SearchSpaceType.CONTINUOUS:
            return cont_random
        if searchspace.type == SearchSpaceType.DISCRETE:
            return candidates_comp.sample(batch_quantity)
        disc_candidates, _ = searchspace.discrete.get_candidates(True, True)
        disc_random = disc_candidates.sample(n=batch_quantity)

        cont_random.reset_index(drop=True)
        cont_random.index = disc_random.index
        return pd.concat([disc_random, cont_random], axis=1)


class FPSRecommender(NonPredictiveRecommender):
    """An initial strategy that selects the candidates via Farthest Point Sampling."""

    compatibility = SearchSpaceType.DISCRETE

    def _recommend_discrete(
        self,
        searchspace: SearchSpace,
        candidates_comp: pd.DataFrame,
        batch_quantity: int,
    ) -> pd.Index:
        """See base class."""
        ilocs = farthest_point_sampling(candidates_comp.values, batch_quantity)
        return candidates_comp.index[ilocs]
