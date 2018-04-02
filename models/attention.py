"""Attention file for location based attention (compatible with tensorflow attention wrapper)"""

import tensorflow as tf
from tensorflow.contrib.seq2seq.python.ops.attention_wrapper import BahdanauAttention
from tensorflow.python.ops import nn_ops
from tensorflow.python.layers import core as layers_core
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import variable_scope
from tensorflow.python.ops import math_ops
from hparams import hparams




def _location_sensitive_score(W_query, W_fil, W_keys):
	"""Impelements Bahdanau-style (cumulative) scoring function.
	This attention is described in:
	J. K. Chorowski, D. Bahdanau, D. Serdyuk, K. Cho, and Y. Ben-
  gio, “Attention-based models for speech recognition,” in Ad-
  vances in Neural Information Processing Systems, 2015, pp.
  577–585.

  #######################################################################
            hybrid attention (content-based + location-based)
        				     f = F * α_{i-1}
     energy = dot(v_a, tanh(W_keys(h_enc) + W_query(h_dec) + W_fil(f)))
  #######################################################################

  Args:
	W_query: Tensor, shape '[batch_size, 1, num_units]' to compare to location features.
	W_location: processed previous alignments into location features, shape '[batch_size, max_time, attention_dim]'
  Returns:
	A '[batch_size, max_time]' attention score (energy)
	"""
	dtype = W_query.dtype
	# Get the number of hidden units from the trailing dimension of query
	num_units = W_query.shape[-1].value or array_ops.shape(W_query)[-1]

	v_a = tf.get_variable(
		'v_a', shape=[num_units], dtype=tf.float32)

	return tf.reduce_sum(v_a * tf.tanh(W_keys + W_query + W_fil), axis=2)

def _smoothing_normalization(e):
	"""Applies a smoothing normalization function instead of softmax
	Introduced in:
		J. K. Chorowski, D. Bahdanau, D. Serdyuk, K. Cho, and Y. Ben-
	  gio, “Attention-based models for speech recognition,” in Ad-
	  vances in Neural Information Processing Systems, 2015, pp.
	  577–585.

	#######################################################################
    				   Smoothing normalization function
    		  a_{i, j} = sigmoid(e_{i, j}) / sum_j(sigmoid(e_{i, j}))
  	#######################################################################

  	Args:
  		e: matrix [batch_size, max_time(memory_time)]: expected to be energy (score)
  			values of an attention mechanism
  	Returns:
  		matrix [batch_size, max_time]: [0, 1] normalized alignments with possible
  			attendance to multiple memory time steps.
  	"""
	return tf.nn.sigmoid(e) / tf.reduce_sum(tf.nn.sigmoid(e), axis=-1, keepdims=True)


class LocationSensitiveAttention(BahdanauAttention):
	"""Impelements Bahdanau-style (cumulative) scoring function.
	Usually referred to as "hybrid" attention (content-based + location-based)
	Extends the additive attention described in:
	"D. Bahdanau, K. Cho, and Y. Bengio, “Neural machine transla-
  tion by jointly learning to align and translate,” in Proceedings
  of ICLR, 2015."
  	to use previous alignments as additional location features.
  	
	This attention is described in:
	J. K. Chorowski, D. Bahdanau, D. Serdyuk, K. Cho, and Y. Ben-
  gio, “Attention-based models for speech recognition,” in Ad-
  vances in Neural Information Processing Systems, 2015, pp.
  577–585.
	"""

	def __init__(self,
				 num_units,
				 memory,
				 memory_sequence_length=None,
				 smoothing=False,
				 name='LocationSensitiveAttention'):
		"""Construct the Attention mechanism.
		Args:
			num_units: The depth of the query mechanism.
			memory: The memory to query; usually the output of an RNN encoder.  This
				tensor should be shaped `[batch_size, max_time, ...]`.
			memory_sequence_length (optional): Sequence lengths for the batch entries
				in memory.  If provided, the memory tensor rows are masked with zeros
				for values past the respective sequence lengths.
			smoothing (optional): Boolean. Determines which normalization function to use.
				Default normalization function (probablity_fn) is softmax. If smoothing is 
				enabled, we replace softmax with:
						a_{i, j} = sigmoid(e_{i, j}) / sum_j(sigmoid(e_{i, j}))
				Introduced in:
					J. K. Chorowski, D. Bahdanau, D. Serdyuk, K. Cho, and Y. Ben-
				  gio, “Attention-based models for speech recognition,” in Ad-
				  vances in Neural Information Processing Systems, 2015, pp.
				  577–585.
				This is mainly used if the model wants to attend to multiple inputs parts 
				at the same decoding step. We probably won't be using it since multiple sound
				frames may depend from the same character, probably not the way around.
				Note:
					We still keep it implemented in case we want to test it. They used it in the
					paper because they were doing speech recognitions, where one phoneme may depend from
					multiple subsequent sound frames.

			name: Name to use when creating ops.
		"""
		#Create normalization function
		#Setting it to None defaults in using softmax
		normalization_function = _smoothing_normalization if (smoothing == True) else None
		super(LocationSensitiveAttention, self).__init__(
				num_units=num_units,
				memory=memory,
				memory_sequence_length=memory_sequence_length,
				probability_fn=normalization_function,
				name=name)

		self.location_convolution = tf.layers.Conv1D(filters=hparams.attention_filters,
			kernel_size=hparams.attention_kernel, padding='same', use_bias=False, 
			name='location_features_convolution')
		self.location_layer = tf.layers.Dense(units=num_units, use_bias=False, 
			dtype=tf.float32, name='location_features_layer')

	def __call__(self, query, state):
		"""Score the query based on the keys and values.
		Args:
			query: Tensor of dtype matching `self.values` and shape
				`[batch_size, query_depth]`.
			state (previous alignments): Tensor of dtype matching `self.values` and shape
				`[batch_size, alignments_size]`
				(`alignments_size` is memory's `max_time`).
		Returns:
			alignments: Tensor of dtype matching `self.values` and shape
				`[batch_size, alignments_size]` (`alignments_size` is memory's
				`max_time`).
		"""
		previous_alignments = state
		with variable_scope.variable_scope(None, "Location_Sensitive_Attention", [query]):

			# processed_query shape [batch_size, query_depth] -> [batch_size, attention_dim]
			processed_query = self.query_layer(query) if self.query_layer else query
			# -> [batch_size, 1, attention_dim]
			processed_query = tf.expand_dims(processed_query, 1)

			# processed_location_features shape [batch_size, max_time, attention dimension]
			# [batch_size, max_time] -> [batch_size, max_time, 1]
			expanded_alignments = tf.expand_dims(previous_alignments, axis=2)
			# location features [batch_size, max_time, filters]
			f = self.location_convolution(expanded_alignments)
			# Projected location features [batch_size, max_time, attention_dim]
			processed_location_features = self.location_layer(f)

			# energy shape [batch_size, max_time]
			energy = _location_sensitive_score(processed_query, processed_location_features, self.keys)

		# alignments shape = energy shape = [batch_size, max_time]
		alignments = self._probability_fn(energy, previous_alignments)

		next_state = alignments
		return alignments, next_state