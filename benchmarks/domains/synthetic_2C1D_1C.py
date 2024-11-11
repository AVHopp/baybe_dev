"""Synthetic function with two continuous and one discrete input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy import pi, sin, sqrt
from pandas import DataFrame
from typing_extensions import override

from baybe.campaign import Campaign
from baybe.parameters import NumericalContinuousParameter, NumericalDiscreteParameter
from baybe.recommenders.pure.nonpredictive.sampling import RandomRecommender
from baybe.searchspace import SearchSpace
from baybe.simulation import simulate_scenarios
from baybe.targets import NumericalTarget, TargetMode
from benchmarks.definition import BenchmarkDefinition
from benchmarks.definition.config import (
    BenchmarkExecutableBase,
    ConvergenceExperimentSettings,
)

if TYPE_CHECKING:
    from mpl_toolkits.mplot3d import Axes3D


def lookup(z: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Lookup function.

    Inputs:
        z   discrete   {1,2,3,4}
        x   continuous [-2*pi, 2*pi]
        y   continuous [-2*pi, 2*pi]
    Output: continuous
    Objective: Maximization
    Optimal Inputs:
        {x: 1.610, y: 1.571, z: 3}
        {x: 1.610, y: -4.712, z: 3}
    Optimal Output: 4.09685
    """
    try:
        assert np.all(-2 * pi <= x) and np.all(x <= 2 * pi)
        assert np.all(-2 * pi <= y) and np.all(y <= 2 * pi)
        assert np.all(np.isin(z, [1, 2, 3, 4]))
    except AssertionError:
        raise ValueError("Inputs are not in the valid ranges.")

    return (
        (z == 1) * sin(x) * (1 + sin(y))
        + (z == 2) * (x * sin(0.9 * x) + sin(x) * sin(y))
        + (z == 3) * (sqrt(x + 8) * sin(x) + sin(x) * sin(y))
        + (z == 4) * (x * sin(1.666 * sqrt(x + 8)) + sin(x) * sin(y))
    )


class Synthetic2C1D1C(BenchmarkExecutableBase[ConvergenceExperimentSettings]):
    """Three Dimensional maximization comparison with random and default recommender."""

    @override
    def __call__(self) -> DataFrame:
        """3 Dimensional maximization comparison with random and default recommender.

        Optimization benchmark with two continuous and one discrete input to
        compare the random and the default recommender on a maximization task.
        """
        parameters = [
            NumericalContinuousParameter("x", (-2 * pi, 2 * pi)),
            NumericalContinuousParameter("y", (-2 * pi, 2 * pi)),
            NumericalDiscreteParameter("z", (1, 2, 3, 4)),
        ]

        objective = NumericalTarget(name="target", mode=TargetMode.MAX).to_objective()
        search_space = SearchSpace.from_product(parameters=parameters)

        scenarios: dict[str, Campaign] = {
            "Random Recommender": Campaign(
                searchspace=search_space,
                recommender=RandomRecommender(),
                objective=objective,
            ),
            "Default Recommender": Campaign(
                searchspace=search_space,
                objective=objective,
            ),
        }

        return simulate_scenarios(
            scenarios,
            self.lookup,
            batch_size=self.settings.batch_size,
            n_doe_iterations=self.settings.n_doe_iterations,
            n_mc_iterations=self.settings.n_mc_iterations,
            impute_mode="error",
            random_seed=self.settings.random_seed,
        )


benchmark_config = ConvergenceExperimentSettings(
    batch_size=5,
    n_doe_iterations=30,
    n_mc_iterations=50,
)

benchmark_function_definition = Synthetic2C1D1C(
    best_possible_result=4.09685,
    settings=benchmark_config,
    lookup=lookup,
    optimal_function_inputs=[
        {"x": 1.610, "y": 1.571, "z": 3},
        {"x": 1.610, "y": -4.712, "z": 3},
    ],
)

benchmark = BenchmarkDefinition(
    identifier="synthetic_2C1D_1C",
    benchmark_function_definition=benchmark_function_definition,
)


if __name__ == "__main__":
    #  Visualize the domain

    import matplotlib.pyplot as plt

    X = np.linspace(-2 * pi, 2 * pi)
    Y = np.linspace(-2 * pi, 2 * pi)
    Z = [1, 2, 3, 4]

    x_mesh, y_mesh = np.meshgrid(X, Y)

    fig = plt.figure(figsize=(10, 10))
    for i, z in enumerate(Z):
        ax: Axes3D = fig.add_subplot(2, 2, i + 1, projection="3d")
        t_mesh = lookup(np.asarray(z), x_mesh, y_mesh)
        ax.plot_surface(x_mesh, y_mesh, t_mesh)
        plt.title(f"{z=}")

    plt.show()
