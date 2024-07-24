"""Base functionality for all BayBE surrogates."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

import pandas as pd
from attrs import define, field
from cattrs import override
from cattrs.dispatch import (
    StructuredValue,
    StructureHook,
    TargetType,
    UnstructuredValue,
    UnstructureHook,
)
from sklearn.preprocessing import MinMaxScaler

from baybe.exceptions import ModelNotTrainedError
from baybe.objectives.base import Objective
from baybe.parameters.base import Parameter
from baybe.searchspace import SearchSpace
from baybe.serialization.core import (
    converter,
    get_base_structure_hook,
    unstructure_base,
)
from baybe.serialization.mixin import SerialMixin
from baybe.utils.dataframe import to_tensor
from baybe.utils.scaling import ParameterScalerProtocol

if TYPE_CHECKING:
    from botorch.models.model import Model
    from botorch.models.transforms.outcome import OutcomeTransform
    from botorch.posteriors import GPyTorchPosterior, Posterior
    from sklearn.compose import ColumnTransformer
    from torch import Tensor

_ONNX_ENCODING = "latin-1"
"""Constant signifying the encoding for onnx byte strings in pretrained models.

NOTE: This encoding is selected by choice for ONNX byte strings.
This is not a requirement from ONNX but simply for the JSON format.
The byte string from ONNX `.SerializeToString()` method has unknown encoding,
which results in UnicodeDecodeError when using `.decode('utf-8')`.
The use of latin-1 ensures there are no loss from the conversion of
bytes to string and back, since the specification is a bijection between
0-255 and the character set.
"""


class _NoTransform(Enum):
    """Sentinel class."""

    IDENTITY_TRANSFORM = auto()


_IDENTITY_TRANSFORM = _NoTransform.IDENTITY_TRANSFORM
"""Sentinel to indicate the absence of a transform where `None` is ambiguous."""


class SurrogateProtocol(Protocol):
    """Type protocol specifying the interface surrogate models need to implement."""

    def fit(
        self,
        searchspace: SearchSpace,
        objective: Objective,
        measurements: pd.DataFrame,
    ) -> None:
        """Fit the surrogate to training data in a given modelling context.

        For details on the expected method arguments, see
        :meth:`baybe.recommenders.base.RecommenderProtocol`.
        """

    def to_botorch(self) -> Model:
        """Create the botorch-ready representation of the fitted model."""


@define
class Surrogate(ABC, SurrogateProtocol, SerialMixin):
    """Abstract base class for all surrogate models."""

    # Class variables
    joint_posterior: ClassVar[bool]
    """Class variable encoding whether or not a joint posterior is calculated."""

    supports_transfer_learning: ClassVar[bool]
    """Class variable encoding whether or not the surrogate supports transfer
    learning."""

    _input_transform: Callable[[pd.DataFrame], pd.DataFrame] | None = field(
        init=False, default=None, eq=False
    )
    """Callable preparing surrogate inputs for training/prediction.

    Transforms a dataframe containing parameter configurations in experimental
    representation to a corresponding dataframe containing their **scaled**
    computational representation. Only available after the surrogate has been fitted."""

    _output_transform: Callable[[pd.DataFrame], pd.DataFrame] | None = field(
        init=False, default=None, eq=False
    )
    """Callable preparing surrogate outputs for training.

    Transforms a dataframe containing target measurements in experimental
    representation to a corresponding dataframe containing their **scaled**
    computational representation. Only available after the surrogate has been fitted."""

    # TODO: type should be `Standardize | _NoTransform`` but is currently
    #   omitted due to: https://github.com/python-attrs/cattrs/issues/531
    _output_scaler = field(init=False, default=None, eq=False)
    """Optional callable for scaling output values.

    Scales a tensor containing target measurements in computational representation
    to make them ready for processing by the surrogate. Only available after the
    surrogate has been fitted."""

    def to_botorch(self) -> Model:  # noqa: D102
        # See base class.
        from baybe.surrogates._adapter import AdapterModel

        return AdapterModel(self)

    @staticmethod
    def _make_parameter_scaler(
        parameter: Parameter,
    ) -> ParameterScalerProtocol | None:
        """Return the scaler to be used for the given parameter."""
        return MinMaxScaler()

    @staticmethod
    def _make_target_scaler() -> OutcomeTransform | None:
        """Return the scaler to be used for target scaling."""
        from botorch.models.transforms.outcome import Standardize

        # TODO: Multi-target extension
        return Standardize(1)

    def _make_input_scaler(self, searchspace: SearchSpace) -> ColumnTransformer:
        """Make the input scaler for transforming computational dataframes."""
        from sklearn.compose import make_column_transformer

        # Create the composite scaler from the parameter-wise scaler objects
        transformers = [
            (
                "passthrough" if (s := self._make_parameter_scaler(p)) is None else s,
                [c for c in p.comp_rep_columns if c in searchspace.comp_rep_columns],
            )
            for p in searchspace.parameters
        ]
        scaler = make_column_transformer(*transformers, verbose_feature_names_out=False)

        scaler.fit(searchspace.comp_rep_bounds)

        return scaler

    def _make_output_scaler(
        self, objective: Objective, measurements: pd.DataFrame
    ) -> OutcomeTransform | _NoTransform:
        """Make the output scaler for transforming computational dataframes."""
        import torch

        scaler = self._make_target_scaler()
        if scaler is None:
            return _IDENTITY_TRANSFORM

        # TODO: Consider taking into account target boundaries when available
        scaler(torch.from_numpy(objective.transform(measurements).values))
        scaler.eval()

        return scaler

    def transform_inputs(self, df: pd.DataFrame, /) -> pd.DataFrame:
        """Transform an experimental parameter dataframe."""
        if self._input_transform is None:
            raise ModelNotTrainedError("The model must be trained first.")
        return self._input_transform(df)

    def transform_outputs(self, df: pd.DataFrame, /) -> pd.DataFrame:
        """Transform an experimental measurement dataframe."""
        if self._output_transform is None:
            raise ModelNotTrainedError("The model must be trained first.")
        return self._output_transform(df)

    def posterior(self, candidates: pd.DataFrame, /) -> Posterior:
        """Evaluate the surrogate model at the given candidate points."""
        p = self._posterior(to_tensor(self.transform_inputs(candidates)))
        if self._output_scaler is not _IDENTITY_TRANSFORM:
            p = self._output_scaler.untransform_posterior(p)
        return p

    @abstractmethod
    def _posterior(self, candidates: Tensor, /) -> Posterior:
        """Perform the actual posterior evaluation logic."""

    @staticmethod
    def _get_model_context(searchspace: SearchSpace, objective: Objective) -> Any:
        """Get the surrogate-specific context for model fitting.

        By default, no context is created. If context is required, subclasses are
        expected to override this method.
        """
        return None

    def fit(
        self,
        searchspace: SearchSpace,
        objective: Objective,
        measurements: pd.DataFrame,
    ) -> None:
        """Train the surrogate model on the provided data.

        Args:
            searchspace: The search space in which experiments are conducted.
            objective: The objective to be optimized.
            measurements: The training data in experimental representation.

        Raises:
            ValueError: If the search space contains task parameters but the selected
                surrogate model type does not support transfer learning.
            NotImplementedError: When using a continuous search space and a non-GP
                model.
        """
        # TODO: consider adding a validation step for `measurements`

        # Check if transfer learning capabilities are needed
        if (searchspace.n_tasks > 1) and (not self.supports_transfer_learning):
            raise ValueError(
                f"The search space contains task parameters but the selected "
                f"surrogate model type ({self.__class__.__name__}) does not "
                f"support transfer learning."
            )
        if (not searchspace.continuous.is_empty) and (
            "GaussianProcess" not in self.__class__.__name__
        ):
            raise NotImplementedError(
                "Continuous search spaces are currently only supported by GPs."
            )

        # Create scaler objects
        input_scaler = self._make_input_scaler(searchspace)
        output_scaler = self._make_output_scaler(objective, measurements)

        def transform_inputs(df: pd.DataFrame, /) -> pd.DataFrame:
            """Fitted input transformation pipeline."""
            # IMPROVE: This method currently relies on two workarounds required
            #   due the working mechanism of sklearn's ColumnTransformer:
            #   * Unfortunately, the transformer returns a raw array, meaning that
            #       column names need to be manually attached afterward.
            #   * In certain cases (e.g. in hybrid spaces), the method needs
            #       to transform only a subset of columns. Unfortunately, it is not
            #       possible to use a subset of columns once the transformer is set up,
            #       which is a side-effect of the first point. As a workaround,
            #       we thus fill the missing columns with NaN and subselect afterward.

            # For the workaround, collect all comp rep columns of the parameters
            # that are actually present in the given dataframe. At the end,
            # we'll filter the transformed augmented dataframe down to these columns.
            exp_rep_cols = [p.name for p in searchspace.parameters]
            comp_rep_cols = []
            for col in [c for c in df.columns if c in exp_rep_cols]:
                parameter = next(p for p in searchspace.parameters if p.name == col)
                comp_rep_cols.extend(parameter.comp_rep_columns)

            # Actual workaround: augment the dataframe with NaN for missing parameters
            df_augmented = df.reindex(columns=exp_rep_cols)

            # The actual transformation step
            out = input_scaler.transform(
                searchspace.transform(df_augmented, allow_extra=True)
            )
            out = pd.DataFrame(
                out, index=df.index, columns=input_scaler.get_feature_names_out()
            )

            # Undo the augmentation, taking into account that not all comp rep
            # parameter columns may actually be part of the search space due
            # to other preprocessing steps.
            comp_rep_cols = list(set(comp_rep_cols).intersection(out.columns))
            return out[comp_rep_cols]

        def transform_outputs(df: pd.DataFrame, /) -> pd.DataFrame:
            """Fitted output transformation pipeline."""
            import torch

            dft = objective.transform(df)

            if output_scaler is _IDENTITY_TRANSFORM:
                return dft

            out = output_scaler(torch.from_numpy(dft.values))[0]
            return pd.DataFrame(out.numpy(), index=df.index, columns=dft.columns)

        # Store context-specific transformations
        self._input_transform = transform_inputs
        self._output_transform = transform_outputs
        self._output_scaler = output_scaler

        # Transform and fit
        train_x, train_y = to_tensor(
            self.transform_inputs(measurements),
            self.transform_outputs(measurements),
        )
        self._fit(train_x, train_y, self._get_model_context(searchspace, objective))

    @abstractmethod
    def _fit(self, train_x: Tensor, train_y: Tensor, context: Any = None) -> None:
        """Perform the actual fitting logic."""


@define
class GaussianSurrogate(Surrogate, ABC):
    """A surrogate model providing Gaussian posterior estimates."""

    def _posterior(self, candidates: Tensor, /) -> GPyTorchPosterior:
        # See base class.

        import torch
        from botorch.posteriors import GPyTorchPosterior
        from gpytorch.distributions import MultivariateNormal

        # Construct the Gaussian posterior from the estimated first and second moment
        mean, var = self._estimate_moments(candidates)
        if not self.joint_posterior:
            var = torch.diag_embed(var)
        mvn = MultivariateNormal(mean, var)
        return GPyTorchPosterior(mvn)

    @abstractmethod
    def _estimate_moments(self, candidates: Tensor, /) -> tuple[Tensor, Tensor]:
        """Estimate first and second moments of the Gaussian posterior.

        The second moment may either be a 1-D tensor of marginal variances for the
        candidates or a 2-D tensor representing a full covariance matrix over all
        candidates, depending on the ``joint_posterior`` flag of the model.
        """


def _make_hook_decode_onnx_str(
    raw_unstructure_hook: UnstructureHook,
) -> UnstructureHook:
    """Wrap an unstructuring hook to let it also decode the contained ONNX string."""

    def wrapper(obj: StructuredValue) -> UnstructuredValue:
        dct = raw_unstructure_hook(obj)
        if "onnx_str" in dct:
            dct["onnx_str"] = dct["onnx_str"].decode(_ONNX_ENCODING)

        return dct

    return wrapper


def _make_hook_encode_onnx_str(raw_structure_hook: StructureHook) -> StructureHook:
    """Wrap a structuring hook to let it also encode the contained ONNX string."""

    def wrapper(dct: UnstructuredValue, _: TargetType) -> StructuredValue:
        if (onnx_str := dct.get("onnx_str")) and isinstance(onnx_str, str):
            dct["onnx_str"] = onnx_str.encode(_ONNX_ENCODING)
        obj = raw_structure_hook(dct, _)

        return obj

    return wrapper


def _block_serialize_custom_architecture(
    raw_unstructure_hook: UnstructureHook,
) -> UnstructureHook:
    """Raise error if attempt to serialize a custom architecture surrogate."""
    # TODO: Ideally, this hook should be removed and unstructuring the Surrogate
    #   base class should automatically invoke the blocking hook that is already
    #   registered for the "CustomArchitectureSurrogate" subclass. However, it's
    #   not clear how the base unstructuring hook needs to be modified to accomplish
    #   this, and furthermore the problem will most likely become obsolete in the future
    #   because the role of the subclass will probably be replaced with a surrogate
    #   protocol.

    def wrapper(obj: StructuredValue) -> UnstructuredValue:
        if obj.__class__.__name__ == "CustomArchitectureSurrogate":
            raise NotImplementedError(
                "Serializing objects of type 'CustomArchitectureSurrogate' "
                "is not supported."
            )

        return raw_unstructure_hook(obj)

    return wrapper


# Register (un-)structure hooks
# IMPROVE: Ideally, the ONNX-specific hooks should simply be registered with the ONNX
#   class, which would avoid the nested wrapping below. However, this requires
#   adjusting the base class (un-)structure hooks such that they consistently apply
#   existing hooks of the concrete subclasses.
converter.register_unstructure_hook(
    Surrogate,
    _make_hook_decode_onnx_str(
        _block_serialize_custom_architecture(
            lambda x: unstructure_base(x, overrides={"_model": override(omit=True)})
        )
    ),
)
converter.register_structure_hook(
    Surrogate, _make_hook_encode_onnx_str(get_base_structure_hook(Surrogate))
)
