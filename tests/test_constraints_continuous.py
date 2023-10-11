"""Test for imposing continuous constraints."""

import pytest
from baybe.constraints import (
    ContinuousEqualityConstraint,
    ContinuousInequalityConstraint,
)

from baybe.utils import add_fake_results


def run_iterations(baybe, n_iterations, batch_quantity):
    """Run a few fake iterations."""
    for _ in range(n_iterations):
        rec = baybe.recommend(batch_quantity=batch_quantity)
        # dont use parameter noise for these tests

        add_fake_results(rec, baybe)

        baybe.add_measurements(rec)

    return baybe.measurements_exp


@pytest.mark.parametrize("parameter_names", [["Conti_finite1", "Conti_finite2"]])
@pytest.mark.parametrize("constraint_names", [["ContiConstraint_1"]])
def test_equality1(baybe, n_iterations, batch_quantity):
    """Test equality constraint with equal weights."""
    res = run_iterations(baybe, n_iterations, batch_quantity)
    print(res)

    assert (
        (1.0 * res["Conti_finite1"] + 1.0 * res["Conti_finite2"])
        .sub(0.3)
        .abs()
        .lt(0.01)
        .all()
    )


@pytest.mark.parametrize("parameter_names", [["Conti_finite1", "Conti_finite2"]])
@pytest.mark.parametrize("constraint_names", [["ContiConstraint_2"]])
def test_equality2(baybe, n_iterations, batch_quantity):
    """Test equality constraint with unequal weights."""
    res = run_iterations(baybe, n_iterations, batch_quantity)
    print(res)

    assert (
        (1.0 * res["Conti_finite1"] + 3.0 * res["Conti_finite2"])
        .sub(0.3)
        .abs()
        .lt(0.01)
        .all()
    )


@pytest.mark.parametrize("parameter_names", [["Conti_finite1", "Conti_finite2"]])
@pytest.mark.parametrize("constraint_names", [["ContiConstraint_3"]])
def test_inequality1(baybe, n_iterations, batch_quantity):
    """Test inequality constraint with equal weights."""
    res = run_iterations(baybe, n_iterations, batch_quantity)
    print(res)

    assert (1.0 * res["Conti_finite1"] + 1.0 * res["Conti_finite2"]).ge(0.299).all()


@pytest.mark.parametrize("parameter_names", [["Conti_finite1", "Conti_finite2"]])
@pytest.mark.parametrize("constraint_names", [["ContiConstraint_4"]])
def test_inequality2(baybe, n_iterations, batch_quantity):
    """Test inequality constraint with unequal weights."""
    res = run_iterations(baybe, n_iterations, batch_quantity)
    print(res)

    assert (1.0 * res["Conti_finite1"] + 3.0 * res["Conti_finite2"]).ge(0.299).all()


def test_invalid_constraints():
    """Test invalid continuous constraint creations."""
    with pytest.raises(ValueError):
        # number of parameters and coefficients doesn't match
        ContinuousEqualityConstraint(parameters=["A", "B"], coefficients=[1.0], rhs=0.0)
        ContinuousEqualityConstraint(
            parameters=["A", "B"], coefficients=[1.0, 2.0, 3.0], rhs=0.0
        )
        ContinuousInequalityConstraint(
            parameters=["A", "B"], coefficients=[1.0], rhs=0.0
        )
        ContinuousInequalityConstraint(
            parameters=["A", "B"], coefficients=[1.0, 2.0, 3.0], rhs=0.0
        )
