"""Dynamic Access Data Buffer

This module includes several tools which generalize the process of
loading large datasets into memory. Also includes abstractions of basic
object forms which allow for easy expansion for more complex types of
access patterns. 
"""



from enum import Enum,auto

from reorder import ReversibleReorder



_DEBUG_VERBOSE = False
"""bool: Flag that enable verbose debug printing in certain functions"""



''' Utility Functions '''
def _rec_multirange_iterator(iter_queue,yield_stack=[]):
	if iter_queue:
		for d in range(iter_queue[0]):
			yield from _rec_multirange_iterator(iter_queue[1:],yield_stack+[d])
	else: yield tuple(yield_stack)	

def multirange(dimension,reorder=None):
	""".. todo::DOC_0"""
	if reorder is not None:
		if not isinstance(reorder,ReversibleReorder):
			reorder = ReversibleReorder(reorder,n=len(dimension))
		
		yield from ( reorder.packed_reorder(point,reverse=True) for point in _rec_multirange_iterator(reorder.packed_reorder(dimension)) )
		
	else: yield from _rec_multirange_iterator(dimension)
'''Region/Block/Point Functions'''	

def _get_region_for_point(point,dimension,region_dimension):
	region = 0
	for i in range(len(point)):
		coordinate_contribution = point[i]//region_dimension[i]
		for j in range(i):
			coordinate_contribution *= dimension[j]//region_dimension[j]
		region += coordinate_contribution
	return region

def _get_block_for_point(point,block_dimension): 
	return tuple(p//block_dimension[i] for i,p in enumerate(point))



'''TODO REFACTOR: Find way to remove Format class. Provides unnecessary complications to expanding AccessFormat'''
class _Format(Enum):
	def _generate_next_value_(name, start, count, last_values):
		value_list = []
		feature = ''
		for c in range(len(name)):
			if name[c] != '_': feature += name[c]
			elif feature:
				value_list.append(feature)
				feature = ''
			elif last_value: value_list.append(last_values[-1][len(value_list)])
			else: value_list.append(None)
		if feature: value_list.append(feature)
		if last_values and len(last_values[-1]) > len(value_list):
			for i,feature in enumerate(value_list):
				if feature != last_values[-1][i]:
					pass#raise ValueError(feature,last_values[-1][i])
			return last_values[-1]
		return value_list

class AccessFormat(Enum):
	""".. todo::DOC_0"""
	def _generate_next_value_(name, start, count, last_values):
		value = _Format._generate_next_value_(name,start,count, last_values)
		if len(value) != 2: 
			raise ValueError('Invalid size of AccessFormat member value', value)
		else: return value
	
	def orientation(format): 
		""".. todo::DOC_1"""
		return format.value[1]
	def mode(format): 
		""".. todo::DOC_1"""
		return format.value[0]
	
	def region(format,point,dimension,**access_kwargs): raise NotImplementedError
	def access_iterator(format): raise NotImplementedError

class RegionAccessFormat(AccessFormat):
	""".. todo::DOC_0"""
	
	LINEAR_VERTICAL = ('LINEAR','VERTICAL')
	VERTICAL = ('LINEAR','VERTICAL')
	LINEAR = ('LINEAR','VERTICAL')
	VERTICAL_LINEAR = ('LINEAR','VERTICAL')
	
	LINEAR_HORIZONTAL = ('LINEAR','HORIZONTAL')
	HORIZONTAL = ('LINEAR','HORIZONTAL')
	HORIZONTAL_LINEAR = ('LINEAR','HORIZONTAL')
	
	BLOCK_VERTICAL = ('BLOCK','VERTICAL')
	BLOCK = ('BLOCK','VERTICAL')
	VERTICAL_BLOCK = ('BLOCK','VERTICAL')
	
	BLOCK_HORIZONTAL = ('BLOCK','HORIZONTAL')
	HORIZONTAL_BLOCK = ('BLOCK','HORIZONTAL')
	
	RANDOM_RANDOM = ('RANDOM','RANDOM')
	RANDOM = ('RANDOM','RANDOM')
	def region(format, point, dimension, block_dimension=None):
		""".. todo::DOC_1"""
		if (mode := format.mode()) == 'LINEAR':
			if block_dimension is not None:
				if (orientation := format.orientation()) == 'HORIZONTAL':
					region_dimension = tuple(bd if d!=0 else dimension[d] for d,bd in enumerate(block_dimension))
				elif orientation == 'VERTICAL':
					region_dimension = tuple(bd if d!=1 else dimension[d] for d,bd in enumerate(block_dimension))
				else: raise NotImplementedError
			else: region_dimension = None
			
			return _get_region_for_point(point,dimension,region_dimension if region_dimension is not None else dimension)
		elif mode == 'BLOCK': 
			return _get_region_for_point(point,dimension,block_dimension if block_dimension is not None else dimension)
		elif mode == 'RANDOM': raise NotImplementedError
		else:                  raise NotImplementedError
	def access_iterator(format, dimension, block_dimension=None):
		""".. todo::DOC_1"""
		if (orientation:=format.orientation()) == 'HORIZONTAL':
			reorder = [ i for i in reversed(range(len(dimension)))]
		elif orientation == 'VERTICAL':
			reorder = None
		else: raise NotImplementedError
			
		if (mode:=format.mode()) == 'LINEAR': 
			yield from multirange(dimension,reorder=reorder)
		elif mode == 'BLOCK': 
			if block_dimension is None: raise ValueError('block_dimension must be provided to use BLOCK AccessFormat mode')
			elif len(block_dimension) != len(dimension): raise ValueError('dimension and block_dimension must be same size')
		
			for block_shifts in multirange(tuple(dimension[i]//block_dimension[i] for i in range(len(dimension))), reorder=reorder):
				shift_amounts = tuple( dbs*block_dimension[i] for i,dbs in enumerate(block_shifts))
				for block_point in multirange(block_dimension,reorder=reorder):
					yield tuple(block_point[i] + shift_amounts[i] for i in range(len(block_point)))
		elif mode == 'RANDOM': raise NotImplementedError
		else:                  raise NotImplementedError



class AccessManager:
	""".. todo::DOC_0"""
	def __init__(manager,access_format,dimension,**access_kwargs):
		""".. todo::DOC_2"""
		# Format
		if isinstance(access_format,AccessFormat):
			manager.format = access_format
		else: raise TypeError("access_format must be of type 'AccessFormat' but instead was of type '%s'"%type(access_format))
		
		# Dimensions
		if isinstance(dimension,(tuple,list)):
			manager.dimension = dimension
		else: raise TypeError("dimension must be of type 'tuple' or 'list' but instead was of type '%s'"%type(dimension))
		
		# Access Keyword Arguments
		manager.access_kwargs = access_kwargs
		
	def __iter__(manager): yield from manager.format.access_iterator(manager.dimension,**manager.access_kwargs)
	def __getitem__(manager, point): return manager.get_point(point)
	
	def _point_region(manager,point, point_info): 
		return point_info.setdefault('point_region', manager.format.region( point, manager.dimension, **manager.access_kwargs))
	
	def mode(manager):
		""".. todo::DOC_1"""
		return manager.format.mode()
	def orientation(manager): 
		""".. todo::DOC_1"""
		return manager.format.orientation()
	
	
	'''Methods that can be implemented in subclasses'''
	def update(manager,format=None,dimension=None,**kwargs):
		""".. todo::DOC_1"""
		if dimension is not None: manager.dimension = dimension
		if format is not None:    manager.format = format
		manager.access_kwargs.update(kwargs)
	def get_point(manager,point,**point_info): 
		""".. todo::DOC_1"""
		return manager.try_point(point,**point_info)
	def set_point(manager,point,**point_info): 
		""".. todo::DOC_1"""
		return manager.try_point(point,**point_info)
	def del_point(manager,point,**point_info): 
		""".. todo::DOC_1"""
		return manager.try_point(point,**point_info)
	
	'''Methods that must be implemented in subclasses'''
	def try_point(manager,point,**point_info): raise NotImplementedError
	def has_point(manager,point,**point_info): raise NotImplementedError

class StaticAccessManager(AccessManager):
	""".. todo::DOC_0"""
	def __init__(manager, access_format, dimension, block_dimension=None, fetch_function=None, **access_kwargs):
		""".. todo::DOC_2"""
		manager.block_dimension = block_dimension if block_dimension is not None else dimension
		
		manager.fetch_function = fetch_function
		
		super().__init__(access_format,dimension,block_dimension=manager.block_dimension,**access_kwargs)
		
		manager.access_regions = {}
	
	def _point_block(manager, point, point_info): 
		return point_info.setdefault('point_block', _get_block_for_point( point, manager.block_dimension))
	
	def fetch(manager,block):
		""".. todo::DOC_1"""
		if manager.fetch_function is not None:
			return manager.fetch_function(block)
			
		else: raise TypeError('AccessManager attempted to fetch block with no known fetch_function')
	
	def update(manager,fetch_function=None,**access_kwargs):
		""".. todo::DOC_1"""
		if fetch_function is not None: manager.fetch_function = fetch_function
		if 'block_dimension' in access_kwargs:
			manager.block_dimension = access_kwargs['block_dimension']
		super().update(**access_kwargs)
	def try_point(manager,point,**point_info):
		""".. todo::DOC_1"""
		point_region = manager._point_region(point,point_info)
		point_block = manager._point_block(point,point_info)
		
		# Data returned if it is already loaded 
		if (point_data := manager.has_point(point,**point_info)): return point_data
		
		manager.access_regions.setdefault(point_region,{})[point_block] = manager.fetch(point_block)
		
		return manager.access_regions[point_region][point_block]
	def has_point(manager,point,**point_info):
		""".. todo::DOC_1"""
		point_region = manager._point_region(point,point_info)
		point_block =  manager._point_block(point,point_info)
		
		if point_region in manager.access_regions:
			if point_block in manager.access_regions[point_region]:
				return manager.access_regions[point_region][point_block]
			else: return False
		else: return False
	
class DynamicAccessManager(StaticAccessManager):
	""".. todo::DOC_0"""
	DEFAULT_BUFFER_SIZE = 1
	
	def __init__(manager,access_format,dimension,block_dimension=None,**access_kwargs):
		""".. todo::DOC_2"""
		super().__init__(access_format,dimension,block_dimension=block_dimension,**access_kwargs)
		
		manager.access_record = {}
	
	def _remove_regions(manager,n=1):
		'''TODO OLD: Below code still works and might be more efficient but does not allow for returning the removed regions. Consider swapping out for final release
		#manager.access_regions = dict(item for i,item in enumerate(sorted(manager.access_regions.items(),key=lambda x: manager.access_record[x[0]],reverse=True)) if i<len(manager.access_regions)-n)
		'''
		rated_region_usage = sorted(manager.access_regions.items(),key=lambda x: manager.access_record[x[0]],reverse=True)
		manager.access_regions = dict( item for item in rated_region_usage[:len(rated_region_usage)-n])
		return tuple(rated_region_usage[len(rated_region_usage)-n:])
	def _del_record(manager, point_region=None): 
		if point_region is not None:
			manager.access_record[point_region] = 0
		else: manager.access_record = {r:0 for r in manager.access_regions}
	def _add_record(manager, point_region, n=1):
		manager.access_record.setdefault(point_region,0)
		manager.access_record[point_region] += n
	
	def get_buffer_size(manager): 
		""".. todo::DOC_1"""
		return manager._buffer_size if hasattr(manager,'_buffer_size') else DynamicAccessManager.DEFAULT_BUFFER_SIZE
	def set_buffer_size(manager, value): 
		""".. todo::DOC_1"""
		manager._buffer_size = value
	
	def try_point(manager,point,**point_info):
		""".. todo::DOC_1"""
		point_region = manager._point_region(point,point_info)
		
		if not(point_region in manager.access_regions):
			if len(manager.access_regions) > manager.get_buffer_size():
				removed = manager._remove_regions()
				if _DEBUG_VERBOSE: print('Deleted Region',removed,flush=True)
				
			if _DEBUG_VERBOSE: print('Get Region: %d'%point_region,flush=True)
			manager._del_record()	
		
		manager._add_record(point_region)
		
		return super().try_point(point,**point_info)
	

