# Copyright 2020 The TensorFlow Probability Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Restructure Bijector."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import six

import tensorflow.compat.v2 as tf

from tensorflow_probability.python.bijectors import bijector
from tensorflow_probability.python.internal import nest_util
from tensorflow.python.util import nest  # pylint: disable=g-direct-tensorflow-import


__all__ = [
    'Restructure',
]


def unique_token_set(source_structure):
  """Checks that structured tokens are unique, and returns the set of values."""
  flat_tokens = nest.flatten(source_structure)
  flat_token_set = set(flat_tokens)
  if len(flat_tokens) != len(flat_token_set):
    raise ValueError('Restructure tokens must be unique. Saw: {}'
                     .format(source_structure))
  return flat_token_set


class Restructure(bijector.Bijector):
  """Converts between nested structures of Tensors.

    This is useful when constructing non-trivial chains of multipart bijectors.
    It partitions inputs into different logical "blocks", which may be fed as
    arguments to downstream multipart bijectors.

    Example Usage:
      ```python

      # What restructure does:
      restructure = Restructure({
        'foo': [0, 1],
        'bar': [3, 2],
        'baz': [4, 5, 6]
      })

      # Note that x is a *python-list* of tensors.
      # To permute elements of an individual Tensor, see `tfb.Permute`.
      x = [1, 2, 4, 8, 16, 32, 64]

      assert restructure.forward(x) == {
          'foo': [1, 2],
          'bar': [8, 4],
          'baz': [16, 32, 64]
      }

      # Where restructure is useful:
      complex_bijector = Chain([
        # Apply different transformations to each block.
        JointMap({
          'foo': ScaleMatVecLinearOperator(...),  # Operates on the full block
          'bar': ScaleMatVecLinearOperator(...),  # Operates on the full block
          'baz': [Exp(), Scale(10.), Shift(-1.)]  # Different bijectors for each
        }),
        # Group the tensor into logical blocks.
        Restructure({
          'foo': [0, 1],
          'bar': [3, 2],
          'baz': [4, 5, 6],
        }),
        # Split an input tensor into 7 chunks.
        Split([2, 4, 6, 8, 10, 12, 14])
      ])
      ```
  """

  def __init__(self,
               output_structure,
               input_structure=None,
               name='restructure'):
    """Creates a `Restructure` bijector.

    Args:
      output_structure: A tf.nest-compatible structure of tokens describing the
        output of `forward` (equivalently, the input of `inverse`).
      input_structure: A tf.nest-compatible structure of tokens describing the
        input to `forward`. If unspecified, a default structure is inferred from
        `output_structure`. The default structure expects a `list` if tokens are
        integers, or a `dict` if the tokens are strings.
      name: Name of this bijector.
    Raises:
      ValueError: If tokens are duplicated, or a required default structure
        cannot be inferred.
    """
    parameters = dict(locals())

    # Get the flat set of tokens, making sure they're unique.
    output_tokens = unique_token_set(output_structure)

    # Create a default input_structure when it isn't provided.
    if input_structure is None:
      # If all tokens are strings, assume input is a dict.
      if all(isinstance(tok, six.string_types) for tok in output_tokens):
        input_structure = {token: token for token in output_tokens}

      # If tokens are contiguous 0-based ints, return a list.
      elif (all(isinstance(tok, six.integer_types) for tok in output_tokens)
            and output_tokens == set(range(len(output_tokens)))):
        input_structure = list(range(len(output_tokens)))

      # Otherwise, we cannot infer a default structure.
      else:
        raise ValueError(('Tokens in output_structure must be all strings or '
                          'contiguous 0-based indices when input_structure '
                          'is not specified. Saw: {}'
                          ).format(output_tokens))

    # If input_structure _is_ provided, make sure tokens are unique
    # and that they match the output_structure tokens.
    else:
      input_tokens = unique_token_set(output_structure)
      if input_tokens != output_tokens:
        raise ValueError(('The `input_structure` tokens must match the '
                          '`output_structure` tokens exactly. Missing from '
                          '`input_structure`: {}. Missing from '
                          '`output_structure`: {}.').format(
                              output_tokens - input_tokens,
                              input_tokens - output_tokens))

    self._input_structure = self._no_dependency(input_structure)
    self._output_structure = self._no_dependency(output_structure)
    super(Restructure, self).__init__(
        forward_min_event_ndims=nest_util.broadcast_structure(
            self._input_structure, None),
        inverse_min_event_ndims=nest_util.broadcast_structure(
            self._output_structure, None),
        is_constant_jacobian=True,
        validate_args=False,
        parameters=parameters,
        name=name)

  @classmethod
  def _parameter_properties(cls, dtype):
    return dict()

  @property
  def _is_permutation(self):
    return True

  def _forward(self, x):
    flat_dict = {}
    nest.map_structure_up_to(
        self._input_structure, flat_dict.setdefault,
        self._input_structure, x)
    result = nest.map_structure(flat_dict.pop, self._output_structure)
    assert not flat_dict  # Should never happen!
    return result

  def _inverse(self, y):
    flat_dict = {}
    nest.map_structure_up_to(
        self._output_structure, flat_dict.setdefault,
        self._output_structure, y)
    result = nest.map_structure(flat_dict.pop, self._input_structure)
    assert not flat_dict  # Should never happen!
    return result

  ### Shape/ndims/etc transformations do the same thing as forward/inverse.

  def _forward_event_shape(self, x_shape, **kwargs):
    return self._forward(x_shape)

  def _inverse_event_shape(self, y_shape, **kwargs):
    return self._inverse(y_shape)

  def _forward_event_shape_tensor(self, x_shape, **kwargs):
    return self._forward(x_shape)

  def _inverse_event_shape_tensor(self, y_shape, **kwargs):
    return self._inverse(y_shape)

  def _forward_dtype(self, x_dtype, **kwargs):
    return self._forward(x_dtype)

  def _inverse_dtype(self, y_dtype, **kwargs):
    return self._inverse(y_dtype)

  def forward_event_ndims(self, x_ndims, **kwargs):
    return self._forward(x_ndims)

  def inverse_event_ndims(self, y_ndims, **kwargs):
    return self._inverse(y_ndims)

  ### Skip convert-to-tensor/caching so we can rearrange nested sub-structures.

  def _call_forward(self, x, name, **kwargs):
    with self._name_and_control_scope(name):
      return self._forward(x, **kwargs)

  def _call_inverse(self, y, name, **kwargs):
    with self._name_and_control_scope(name):
      return self._inverse(y, **kwargs)

  ### Restructure always has constant 0 LDJ.
  # Override top-level methods, since min_event_ndims is undefined.

  def _call_forward_log_det_jacobian(self, x, event_ndims, name, **kwargs):
    with self._name_and_control_scope(name):
      return tf.zeros([], tf.float32)

  def _call_inverse_log_det_jacobian(self, y, event_ndims, name, **kwargs):
    with self._name_and_control_scope(name):
      return tf.zeros([], tf.float32)
