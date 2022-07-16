"""Sequence Reordering

This module contains tools which provides a simple API for the
reordering of sequences based on predfined patterns.
"""


'''Reorder Decorators'''
def pack(func):
	""".. todo::DOC_0"""
	def packed_decorator(args,**kwargs): return func(*args,**kwargs)
	return packed_decorator

def unpack(func):
	""".. todo::DOC_0"""
	def unpacked_decorator(*args,**kwargs): return func(args,**kwargs)
	return unpacked_decorator




'''Reorder Errors'''
class ReorderError(Exception): pass

class ReorderPackingError(ReorderError): pass



'''Reorder Classes'''
class Reorder:
	""".. todo::DOC_0"""
	FUNCTION_ARG_MIN = 2
	FUNCTION_ARG_MAX = 10
	def __init__(self, reorder, n=None, unpacked=None, unpack_sequence=None):
		""".. todo::DOC_2"""
		if callable(reorder) and not isinstance(reorder,Reorder):
			n,unpacked = Reorder._reorder_args(reorder,n,unpacked)
		else:
			n = len(reorder) if n is None else n
			unpacked =  False if unpacked is None else unpacked
			if isinstance(reorder,Reorder): 
				reorder = reorder.reorder_function 
			else: reorder = Reorder.get_index_reorder(reorder,unpacked)
		
		self._arg_length = n
		
		self.unpack_sequence = unpack_sequence if unpack_sequence is not None else unpacked
		
		self.reorder_function = pack(reorder) if unpacked else reorder
	def __len__(self): return self._arg_length
	def __call__(self, *sequence,**kwargs):
		""".. todo::DOC_2"""
		if self.unpack_sequence: 
			return self.unpacked_reorder(*sequence,**kwargs)
		else: return self.packed_reorder(*sequence,**kwargs)
	def __repr__(self):
		base_order = tuple(i for i in range(len(self)))
		return '<reorder%s -> %s>'%(
			str(base_order) if self.unpack_sequence else '(%s)'%str(base_order),
			self.packed_reorder(base_order),
		)
		
	def get_sequence_unpack(self): 
		""".. todo::DOC_1"""
		return self.unpack_sequence
	def set_sequence_unpack(self,unpacked): 
		""".. todo::DOC_1"""
		self.unpack_sequence =  unpacked
	def unpacked_reorder(self, *sequence,**kwargs): 
		""".. todo::DOC_1"""
		return self.packed_reorder(sequence,**kwargs)
	def packed_reorder(self, sequence,**kwargs): 
		""".. todo::DOC_1"""
		return self.reorder_function(sequence)
	
	@staticmethod
	def get_index_reorder(indexes,unpacked=False):
		"""Function builder which takes a sequence and return the elements reordered to match the original indexes provided as input.
		
		Args:
			indexes (:obj:`list` of :obj:`int`): Index order the function rearranges inputs into.
			unpacked (:obj:`bool`, optional): Flag which determines if returned function takes input as a packed or unpacked sequence. Defaults to False.
			
		Returns:
			function: A reordering function which takes a sequence as
			input and returns it in the order indicated by the
			*indexes* parameter.
			
			The returned functions input can be either packed or unpacked
			depending on the given *unpacked* flag.
		"""
		def index_reorder(args): return tuple(args[i] for i in indexes)
		return unpack(index_reorder) if unpacked else index_reorder
	
	@staticmethod
	def _reorder_args(reorder,n=None,unpacked=None):
		if n is None:
			for n in range(Reorder.FUNCTION_ARG_MIN,Reorder.FUNCTION_ARG_MAX if Reorder.FUNCTION_ARG_MAX is not None else Reorder.FUNCTION_ARG_MIN):
				try: unpacked = Reorder._is_reorder_unpacked(reorder,n,unpacked)
				except ReorderPackingError as e: pass
				else: return n,unpacked
		elif unpacked is None:
			unpacked = Reorder._is_reorder_unpacked(reorder,n,unpacked)
			return n,unpacked
		else: return n,unpacked
		
		raise ReorderPackingError('Unable to determine how to pack arguments for reorder function')
	
	@staticmethod
	def _is_reorder_unpacked(reorder,n,unpacked=None):
		base_order = tuple(i for i in range(n))
		
		if unpacked is None or unpacked:
			try: reorder(*base_order)
			except TypeError as e: pass
			else: unpacked=True
		if unpacked is None or not(unpacked):
			try: reorder(base_order)
			except (TypeError,IndexError) as e: pass
			else: unpacked=False
		
		if unpacked is None: 
			raise ReorderPackingError('Test failed to call reorder function with %d packed or unpacked arguments'%n)
		else: return unpacked
	
class ReversibleReorder(Reorder):
	""".. todo::DOC_0"""
	def __init__(self,reorder,n=None,unpacked=None,unpack_sequence=None):
		""".. todo::DOC_2"""
		super().__init__(reorder,n=n,unpacked=unpacked,unpack_sequence=unpack_sequence)
		
		if isinstance(reorder,ReversibleReorder):
			self.reverse_reorder_function = reorder.reverse_reorder_function
		elif isinstance(reorder,(list,tuple)):
			reverse_reorder = [None for _ in reorder] 
			for i,o in enumerate(reorder): reverse_reorder[o] = i
			
			self.reverse_reorder_function = ReversibleReorder.get_index_reorder(tuple(reverse_reorder),False)
		else:
			self.reverse_reorder_function = ReversibleReorder.get_reversed(self.reorder_function,self._arg_length,False)
	def __repr__(self): return super().__repr__().replace('->','<->')
	
	def packed_reorder(self, sequence, reverse=False,**kwargs):
		""".. todo::DOC_1"""
		return self.reverse_reorder_function(sequence) if reverse else super().packed_reorder(sequence,reverse=reverse,**kwargs)
	@staticmethod
	def get_reversed(reorder,n=None,unpacked=None):
		"""Function builder which takes a reordering function and
		returns a new function that takes a sequence reordered by
		the original and returns it in the original order.
		
		Args:
			reorder (function): A function that reorders any
				sequence given to it of appropiate length
			n (:obj:`int`, optional): Sequence length accepted by the
				given reorder function. Defaults to None.
			unpacked (:obj:`bool`, optional): Flag which determines if
				given function takes input as a packed or unpacked sequence.
				Defaults to False.
			
		"""
		def _rec_reversed_reorder_function(rec_func):
			def reversed_reorder_unpacked(*args): return reorder(*rec_func(*args))
			def reversed_reorder_packed(args): return reorder(rec_func(args))
			return reversed_reorder_unpacked if unpacked else reversed_reorder_packed 
		def _loop_reversed_reorder_function(loops):
			def reversed_reorder_unpacked(*args):
				for i in range(loops): args = reorder(*args)
				return args
			def reversed_reorder_packed(args):
				for i in range(loops): args = reorder(args)
				return args
			return reversed_reorder_unpacked if unpacked else reversed_reorder_packed  
		
		if isinstance(reorder,Reorder):
			if isinstance(reorder,ReversibleReorder): 
				return reorder.reverse_reorder_function
			n = len(reorder) if n is None else n
			unpacked = False if unpacked is None else unpacked
		else: n,unpacked = ReversibleReorder._reorder_args(reorder,n,unpacked)	 
		
		rev_reorder = reorder
		base_order = tuple(i for i in range(n))
		current_order = rev_reorder(*base_order) if unpacked else rev_reorder(base_order)
		
		loops = 0
		while(sum([1 for i in range(n) if base_order[i] != current_order[i] ]) > 0 ):
			loops += 1
			rev_reorder = _loop_reversed_reorder_function(loops)
			current_order = rev_reorder(*reorder(*base_order)) if unpacked else rev_reorder(reorder(base_order))
		return rev_reorder
'''Reorder Test Functions'''



'''reorder.py Unit Tests'''
def _test_reorder(n):
	import random
	print('Testing Reorder and ReversibleReorder (arg length %d)'%n)
	
	
	'''Test Tracking Helper Functions'''
	pass_count = 0
	fail_count = 0
	def count_test(exp):
		nonlocal pass_count,fail_count
		if exp: pass_count += 1
		else:   fail_count += 1
		return exp
	def report_score(prefix='\t',clear=True):
		nonlocal pass_count,fail_count
		print('%s %d/%d (%.2f%%) tests passing'%(prefix,pass_count,sum((pass_count,fail_count)),100*(pass_count/sum((pass_count,fail_count))))) 
		if clear:
			pass_count=0
			fail_count=0
	def element_match(A,B):
		if len(A) != len(B): return False
		for i in range(len(A)):
			if A[i] != B[i]: return False
		return True
	
	base_order = tuple(i for i in range(n))
	
	reorder = list(base_order)
	random.shuffle(reorder)
	
	'''Reorder Class Test Functions'''
	def packed_reorder_test(func,order_1,reorder):
		order_2 = func(order_1)
		count_test(element_match(reorder,order_2))
	def unpacked_reorder_test(func,order_1,reorder):
		order_2 = func(*order_1)
		count_test(element_match(reorder,order_2))
	def generic_reorder_test(func,order_1,reorder):
		packed_reorder_test(func.packed_reorder,order_1,reorder)
		unpacked_reorder_test(func.unpacked_reorder,order_1,reorder)
	
	'''Reorder Class Tests'''
	# __call__ accepts packed input (ie. __call__(input))
	# without 'unpacked_sequence' keyword
	reorder_obj = Reorder(reorder)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,unpacked=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpacked=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	# with 'unpacked_sequence' keyword
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpack_sequence=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,unpacked=False,unpack_sequence=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,unpacked=True,unpack_sequence=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpacked=False,unpack_sequence=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpacked=True,unpack_sequence=False)
	packed_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	
	# __call__ accepts unpacked input (ie. __call__(*input))
	# without 'unpacked_sequence' keyword
	reorder_obj = Reorder(reorder,unpacked=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpacked=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	# with 'unpacked_sequence' keyword
	reorder_obj = Reorder(reorder,n=n,unpack_sequence=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,unpacked=False,unpack_sequence=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,unpacked=True,unpack_sequence=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpacked=False,unpack_sequence=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	reorder_obj = Reorder(reorder,n=n,unpacked=True,unpack_sequence=True)
	unpacked_reorder_test(reorder_obj,base_order,reorder)
	generic_reorder_test(reorder_obj,base_order,reorder)
	report_score('\tReorder:\t\t')
	
	'''ReversibleReorder Class Test Functions'''
	def packed_reverse_reorder_test(func,order_1,reorder):
		order_2 = func(order_1)
		count_test(element_match(reorder,order_2))
		order_3 = func(order_2,reverse=True)
		count_test(element_match(order_1,order_3))
	def unpacked_reverse_reorder_test(func,order_1,reorder):
		order_2 = func(*order_1)
		count_test(element_match(reorder,order_2))
		order_3 = func(*order_2,reverse=True)
		count_test(element_match(order_1,order_3))
	def generic_reverse_reorder_test(func,order_1,reorder):
		packed_reverse_reorder_test(func.packed_reorder,order_1,reorder)
		unpacked_reverse_reorder_test(func.unpacked_reorder,order_1,reorder)
	
	'''ReversibleReorder Class Tests'''
	# __call__ accepts packed input (ie. __call__(input))
	# without 'unpacked_sequence' keyword
	reverse_reorder = ReversibleReorder(reorder)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,unpacked=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpacked=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	# with 'unpacked_sequence' keyword
	reverse_reorder = ReversibleReorder(reorder,unpack_sequence=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpack_sequence=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,unpacked=False,unpack_sequence=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,unpacked=True,unpack_sequence=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpacked=False,unpack_sequence=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpacked=True,unpack_sequence=False)
	packed_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	report_score('\tReversibleReorder (packed):\t')
	
	
	# __call__ accepts unpacked input (ie. __call__(*input))
	# without 'unpacked_sequence' keyword
	reverse_reorder = ReversibleReorder(reorder,unpacked=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpacked=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	# with 'unpacked_sequence' keyword
	reverse_reorder = ReversibleReorder(reorder,unpack_sequence=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpack_sequence=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,unpacked=False,unpack_sequence=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,unpacked=True,unpack_sequence=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpacked=False,unpack_sequence=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	reverse_reorder = ReversibleReorder(reorder,n=n,unpacked=True,unpack_sequence=True)
	unpacked_reverse_reorder_test(reverse_reorder,base_order,reorder)
	generic_reverse_reorder_test(reverse_reorder,base_order,reorder)
	report_score('\tReversibleReorder (unpacked):\t')
	


if __name__ == '__main__':
	for n in range(Reorder.FUNCTION_ARG_MIN,Reorder.FUNCTION_ARG_MAX):
		_test_reorder(n)