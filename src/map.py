""" Data Image Maps

This module contains tools which allow for easy interaction with data
encoded in the pixel values of image files. This includes grayscale
heat maps (Monochromatic) as well as higher resolution multi-channel 
(Polychromatic) data encoding formats.
"""



import os
import tempfile
from shutil import rmtree
from PIL import Image
from enum import Enum

from reorder import ReversibleReorder
from access import RegionAccessFormat,StaticAccessManager,DynamicAccessManager,RegionAccessFormat



MAX_PALETTE_WIDTH = 2**16
"""int: Maximum image width allowed when generating palettes for 
	ColorValueFormat(s)

When set to an int value all calls to ColorValueFormat.palette will
check for total width prior to image generation and redefine generation
parameters so the width falls within this limit. 

When set to None this redefinition process is skipped entirely.
"""

MONOCHROME_VERIFY_CHANNELS = False
"""bool: Flag that enables the checking for matching channel values
	on each Monochromatic color to value conversion
"""

MONOCHROMATIC_ALPHA_VALUE=255
"""int: Alpha channel value used in monochromatic color formats"""

POLYCHROME_DEFAULT_STRIPE_WIDTH = 8
"""int: Width value for stripe for the default color types formats of
	the Polychrome Class. (Polychrome.RGB and Polychrome.RGBA)

Value must be a power of 2 to avoid incompatibility with either RGB
or RGBA format types.
	
Changing value after Polychrome class has already been defined will
have no effect on default format stripe width.  
"""

REORDER_RGB = {
	'RGB': None,
	'RBG': ReversibleReorder([0, 2, 1], 3),
	'GRB': ReversibleReorder([1, 0, 2], 3),
	'GBR': ReversibleReorder([1, 2, 0], 3),
	'BRG': ReversibleReorder([2, 0, 1], 3),
	'BGR': ReversibleReorder([2, 1, 0], 3),
}
"""dict: Dictionary of ReversibleReorder objects for every possible
	type of channel reordering for the RGB format type.

Used by the Polychrome ColorValueFormat to generate the different
reordered formats for RGB type formats
"""

REORDER_RGBA = {
	'RGBA': None,
	'RGAB': ReversibleReorder([0, 1, 3, 2], 4),
	'RBGA': ReversibleReorder([0, 2, 1, 3], 4),
	'RBAG': ReversibleReorder([0, 2, 3, 1], 4),
	'RAGB': ReversibleReorder([0, 3, 1, 2], 4),
	'RABG': ReversibleReorder([0, 3, 2, 1], 4),
	'GRBA': ReversibleReorder([1, 0, 2, 3], 4),
	'GRAB': ReversibleReorder([1, 0, 3, 2], 4),
	'GBRA': ReversibleReorder([1, 2, 0, 3], 4),
	'GBAR': ReversibleReorder([1, 2, 3, 0], 4),
	'GARB': ReversibleReorder([1, 3, 0, 2], 4),
	'GABR': ReversibleReorder([1, 3, 2, 0], 4),
	'BRGA': ReversibleReorder([2, 0, 1, 3], 4),
	'BRAG': ReversibleReorder([2, 0, 3, 1], 4),
	'BGRA': ReversibleReorder([2, 1, 0, 3], 4),
	'BGAR': ReversibleReorder([2, 1, 3, 0], 4),
	'BARG': ReversibleReorder([2, 3, 0, 1], 4),
	'BAGR': ReversibleReorder([2, 3, 1, 0], 4),
	'ARGB': ReversibleReorder([3, 0, 1, 2], 4),
	'ARBG': ReversibleReorder([3, 0, 2, 1], 4),
	'AGRB': ReversibleReorder([3, 1, 0, 2], 4),
	'AGBR': ReversibleReorder([3, 1, 2, 0], 4),
	'ABRG': ReversibleReorder([3, 2, 0, 1], 4),
	'ABGR': ReversibleReorder([3, 2, 1, 0], 4),
}
"""dict: Dictionary of ReversibleReorder objects for every possible
	type of channel reordering for the RGBA format type.
	
Used by the Polychrome ColorValueFormat to generate the different
reordered formats for RGBA type formats
"""

DEBUG_VERBOSE = True
"""bool: Flag that enable verbose debug printing in certain functions"""

DEBUG_DATA_IMAGE_FOLDER = '..\example_data_images'
"""str: path to folder containing appropriatly formated
	data image files for use in unit tests. 
	
Only used when module is run as __main__. Value is not
important outside of this context.
"""


''' Private Utility Functions'''
def _rec_region_blocks_iterator(iter_queue,yield_stack=[]):
	if iter_queue:
		d,b = iter_queue[0]
		for c in range(0,d,b):
			yield from _rec_region_blocks_iterator(iter_queue[1:],yield_stack+[(c,c+b)])
	else:
		yield tuple(d for point in zip(*yield_stack) for d in point)

def _region_blocks_iterator(dimension,block_dimension):
	yield from _rec_region_blocks_iterator(tuple((d,block_dimension[i]) for i,d in enumerate(dimension)))
'''Block Functions'''	

def _get_block_as_point(block,block_dimension): 
	return tuple(bp*block_dimension[i] for i,bp in enumerate(block)) 

def _get_possible_divisions(n, div_size_min=1, div_size_max=None):
	if div_size_max is None: 
		div_size_max = n
	
	if div_size_min > div_size_max: return tuple()
	elif div_size_min == div_size_max: raise NotImplementedError
	
	divisions = {}
	for div in range(div_size_min,div_size_max):
		if n%div != 0: continue
		divisions[div] = 0
		for sub_div in range(2,div):
			if div%sub_div != 0: continue
			divisions[div] += 1
	
	return sorted(divisions.items(),key=lambda x: x[1],reverse=True)

def _image_from_kwargs(image=None,filename=None,**kwargs):
	if image is not None: return image
	elif filename is not None: return Image.open(filename)
	else: raise ValueError('Could not get image from keywords provided')

def _calc_coverage(ranges):
	ranges = sorted(ranges,key=lambda r: r[1]-r[0],reverse=True)
	ranges.sort(key=lambda r: r[0])
	
	coverage_ranges = []
	combined = set()
	for i,r0 in enumerate(ranges):
		if r0 in combined: continue
		
		overlap = [r0]
		
		for j in range(i+1,len(ranges)):
			if overlap[-1][1] > ranges[j][0]:
				combined.add(ranges[j])
				if overlap[-1][1] <= ranges[j][1]:
					overlap.append(ranges[j])
			else: break
		
		if len(overlap) > 1:
			r1 = overlap[-1]
			coverage_ranges.append((r0[0],max(r0[1],r1[1])))
		else:
			coverage_ranges.append(r0)
	return coverage_ranges



''' map_unwrap helpers '''
def pivots(line, key=lambda x,y: x==y, front=True, back=True, rtn_type=list):
	"""TODO DOC: 0"""
	n = len(line)
	
	if front: # Find pivots from front
		forward_value = line[0]
		forward_pivots = set()
		for p in range(1,n):
			if key(line[p],forward_value):
				forward_pivots.add((n-1)-p)
	else: forward_pivots = range(n-1)
	
	if back: # Find pivots from back
		backward_value = line[-1]
		pivots = set()
		for p in forward_pivots: 
			if key(line[p],backward_value):
				pivots.add(p)
	elif front: pivots = forward_pivots
	else: pivots = rtn_type()
	
	# Find intersection of front and back pivots depending on inclusion
	# if front and back: pivots = forward_pivots.intersection(backward_pivots)
	# elif front:        pivots = forward_pivots
	# elif back:         pivots = backward_pivots
	# else:              pivots = rtn_type()
	
	if isinstance(pivots,rtn_type):
		return pivots
	else: # Attempt to convert pivots to type
		return rtn_type(pivots)
def all_loops(line,key=lambda x,y: x==y,check_indexes=None):
	"""TODO DOC: 0"""
	n = len(line)
	
	if check_indexes is not None: 
		# Check subset of pivot points for line
		pivot_points = list(check_indexes)
	else: 
		# Check all possible pivot points for line
		pivot_points = pivots(line,key=key,rtn_type=set)
		
	# Sort pivots so early break can be used if remaining segment is single color
	pivot_points.sort(reverse=True)
	
	# True if checks for loop can be skipped
	looped = False
	
	# Indexes which repeat at the end
	loop_points = []
	for rp in pivot_points:
		if looped: # Remaining indexes all confirmed to pass check
			loop_points.append(rp)
			continue
		
		svalue=None
		single_value = True
		
		allowed_misses = 0 # Unimplemented feature which allows for partial matches
		
		for i in range(rp): # Loops through every index up to pivot
			if not(key(line[i],line[(n-1)-(rp-i)])): # Compares points in the loop
				allowed_misses -= 1
				if allowed_misses < 0: break
			
			if single_value: # Single value check has not failed
				if svalue is None: # Setting value on first check
					svalue = line[i]
				elif not(key(line[i],svalue)): # Compares equality of current color and first color
					single_value=False
		if allowed_misses >= 0: # Valid loop
			loop_points.append(rp)
			if single_value and svalue is not None: # Loop contained only one color
				looped=True
	
	return tuple(loop_points)
class MapUnwrapper:
	"""TODO DOC: 0"""
	def __init__(unwrapper, image=None, filepath=None, data_format=None):
		if image is not None:
			unwrapper.wrapped_img = image
		elif filepath is not None:
			if not(filepath.endswith(('.png','.PNG'))): 
				raise NotImplementedError
			unwrapper.wrapped_img = Image.open(filepath)
		
		unwrapper.width,unwrapper.height = unwrapper.wrapped_img.size
		unwrapper.current_row = 0
		unwrapper.current_col = None
		
		unwrapper.pix = None
		unwrapper.preloaded = False
	
	def __getitem__(unwrapper,key):
		if isinstance(key,tuple) and len(key) == 2:
			x,y = key
		else: x,y = key,key
		
		if unwrapper._get_major_iter_axis() == 'col':
			x = unwrapper.current_col 
		if unwrapper._get_major_iter_axis() == 'row':
			y = unwrapper.current_row
		
		if unwrapper.preloaded: return unwrapper.pix[x,y]
		else: return unwrapper.wrapped_img.getpixel((x,y))
	def __len__(unwrapper):
		if unwrapper._get_major_iter_axis() == 'col':
			return unwrapper.height
		if unwrapper._get_major_iter_axis() == 'row':
			return unwrapper.width
	def _get_major_iter_axis(unwrapper):
		if unwrapper.current_col is not None and unwrapper.current_row is None:
			return 'col'
		elif unwrapper.current_row is not None and unwrapper.current_col is None:
			return 'row'
	def _set_major_iter_axis(unwrapper,axis):
		if axis.lower() == 'row':
			unwrapper.current_col = None
			unwrapper.current_row = 0
		elif axis.lower() == 'col':
			unwrapper.current_col = 0
			unwrapper.current_row = None
	def _get_major_iter_axis_value(unwrapper):
		if unwrapper._get_major_iter_axis() == 'col':
			return unwrapper.current_col
		elif unwrapper._get_major_iter_axis() == 'row':
			return unwrapper.current_row
	def _set_major_iter_axis_value(unwrapper,value):
		if unwrapper._get_major_iter_axis() == 'col':
			if value < unwrapper.width:
				unwrapper.current_col = value
			else: raise ValueError
		elif unwrapper._get_major_iter_axis() == 'row':
			if value < unwrapper.height:
				unwrapper.current_row = value
			else: raise ValueError
	def _iter_axis(unwrapper,axis=None,step=1):
		if axis is not None: unwrapper._set_major_iter_axis(axis)
		
		if unwrapper._get_major_iter_axis() == 'col': n = unwrapper.width
		elif unwrapper._get_major_iter_axis() == 'row': n =unwrapper.height
		
		unwrapper._set_major_iter_axis_value(0)
		for i in range(0,n,step):
			unwrapper._set_major_iter_axis_value(i)
			yield i
		
	def __iter__(unwrapper):
		if unwrapper.current_col is not None and unwrapper.current_row is None:
			for row in range(unwrapper.height):
				yield unwrapper[row]
		elif unwrapper.current_row is not None and unwrapper.current_col is None:
			for col in range(unwrapper.width):
				yield unwrapper[col]
		else: raise Exception('Can not iterate over map without setting axis')
	def preload(unwrapper):
		'''TODO REMOVE: functionality as it is not used in current implementation'''
		if not unwrapper.preloaded:
			unwrapper.pix = unwrapper.wrapped_img.load()


'''Public Utility Functions'''
def map_value_coverage(*maps): 
	"""TODO DOC: 0"""
	return _calc_coverage([(map.min_value,map.max_value) for map in maps])
	
def map_unwrap(image=None,filepath=None,row=True,col=True, shift=(0,0), sampling=1,verify=True,verbose=True):
	"""TODO DOC: 0"""
	
	muw = MapUnwrapper(image=image, filepath=filepath)
	
	def color_key(a,b):
		if len(a) == len(b):
			for i in range(len(a)):
				if a[i] != b[i]: return False
			return True
		return False
	
	step_size = int(1/sampling)
	
	shared_row_loops = None
	# Verbose print interval for row finding loop (prints every 10%)
	row_verbose_trigger = int(muw.height/step_size/10)
	if row_verbose_trigger == 0: row_verbose_trigger = 1
	
	if row: # Row wrap check enabled
		if step_size > muw.width: raise ValueError('Sampling of %f resulted in step size too low to unwrap map rows.'%sampling)
		
		# Pre-Check possible loop indexes (index color-comparison)
		for i,r in enumerate(muw._iter_axis('row',step=step_size)):
			if shared_row_loops is None:  
				shared_row_loops = pivots(muw,key=color_key,rtn_type=set)
			else:
				shared_row_loops = shared_row_loops.intersection(pivots(muw,key=color_key,rtn_type=set))
				
			# Break out of Pre-Check early if elimination no longer needed
			if len(shared_row_loops) == 1: break
			elif len(shared_row_loops) == 0: break
			
			# Verbose printout
			if verbose and i%row_verbose_trigger == 0:
				if len(shared_row_loops) == 0 or len(shared_row_loops) > 10 :
					p_shared = '%d possible shared loops'%len(shared_row_loops)
				else: p_shared = 'Possible Shared Loops: %s'%shared_row_loops
				print('\t[%d]Pre-Checking Row %d: %s'%(i,r,p_shared),flush=True,end='\n')
		# Check looping for index positions (row color-comparison)
		for i,r in enumerate(muw._iter_axis('row',step=step_size)):
			if shared_row_loops is None: 
				shared_row_loops = set(all_loops(muw,key=color_key))
			else: 
				shared_row_loops = shared_row_loops.intersection(set(all_loops(muw,key=color_key,check_indexes=shared_row_loops)))
			
			#Break out of Loop Check early if 
			#	elimination no longer needed
			#	verify not enabled
			if not(verify) and len(shared_row_loops) == 1: break
			elif len(shared_row_loops) == 0: break
			
			# Verbose printout loop update
			if verbose and i%row_verbose_trigger == 0:
				if 1 > len(shared_row_loops) > 10 :
					p_shared = '%d shared loops'%len(shared_row_loops)
				else: p_shared = 'Shared Loops: %s'%shared_row_loops
				print('\t[%d]Checking Row %d: %s'%(i,r,p_shared),flush=True,end='\n')
		# Verbose printout for output	
		if verbose:
			if len(shared_row_loops) > 0:
				if len(shared_row_loops) == 1:
					print('Row looping point found: %s'%shared_row_loops,flush=True)
				else:
					print('More than one row looping point found: %s'%shared_row_loops,flush=True)
			else:
				print('No row looping point found',flush=True)
	else: shared_row_loops = set()
	
	
	shared_col_loops = None
	# Verbose print interval for column finding loop (prints every 10%)
	col_verbose_trigger = int(muw.width/step_size/10)
	if col_verbose_trigger == 0: col_verbose_trigger = 1
	
	if col:
		if step_size > muw.height: raise ValueError('Sampling of %f resulted in step size too low to unwrap map columns.'%sampling)
		
		# Pre-Check possible loop indexes (index color-comparison)
		for i,c in enumerate(muw._iter_axis('col',step=step_size)):
			if shared_col_loops is None:
				shared_col_loops = pivots(muw,key=color_key,rtn_type=set)
			else: 
				shared_col_loops = shared_col_loops.intersection(pivots(muw,key=color_key,rtn_type=set))
			
			# Break out of Pre-Check early if elimination no longer needed
			if len(shared_col_loops) == 1: break
			elif len(shared_col_loops) == 0: break
			
			# Verbose printout
			if verbose and i%col_verbose_trigger == 0:
				if len(shared_col_loops) == 0 or len(shared_col_loops) > 10 :
					p_shared = '%d possible shared loops'%len(shared_col_loops)
				else: p_shared = 'Possible Shared Loops: %s'%shared_col_loops
				print('\t[%d]Pre-Checking Column %d: %s'%(i,c,p_shared),flush=True,end='\n')
		
		# Check looping for index positions (column color-comparison)
		for i,c in enumerate(muw._iter_axis('col',step=step_size)):
			if shared_col_loops is None: 
				shared_col_loops = set(all_loops(muw,key=color_key))
			else: 
				shared_col_loops = shared_col_loops.intersection(set(all_loops(muw,key=color_key,check_indexes=shared_col_loops)))
			
			# Break out of Checking loop early if 
			#	elimination no longer needed
			#	and verify not enabled
			if not(verify) and len(shared_col_loops) == 1: break
			elif len(shared_col_loops) == 0: break
			
			# Verbose printout loop update
			if verbose and i%col_verbose_trigger == 0: 
				if 1 > len(shared_col_loops) > 10 :
					p_shared = '%d shared loops'%len(shared_col_loops)
				else: p_shared = 'Shared Loops: %s'%shared_col_loops
				print('\t[%d]Checking Column %d: %s'%(i,c,p_shared),flush=True,end='\n')
			
		# Verbose printout for output	
		if verbose:
			if len(shared_col_loops) > 0:
				if len(shared_col_loops) == 1:
					print('Column looping point found: %s'%shared_col_loops,flush=True)
				else:
					print('More than one column looping point found: %s'%shared_col_loops,flush=True)
			else:
				print('No column looping point found',flush=True)
	else: shared_col_loops = set()	
	
	# Crop Width
	if len(shared_row_loops) == 0:
		crop_width = muw.width
	elif len(shared_row_loops) == 1:
		crop_width = muw.width - (shared_row_loops.pop() + 1)
	else: 
		if verbose: print('Multiple Row Loops: %s'%shared_row_loops,flush=True)
		crop_width = muw.width - (max(shared_row_loops) + 1)
		
	# Crop Height
	if len(shared_col_loops) == 0:
		crop_height = muw.height
	elif len(shared_col_loops) == 1:
		crop_height = muw.height - (shared_col_loops.pop() + 1)
	else: 
		if verbose: print('Multiple Column Loops: %s'%shared_col_loops,flush=True)
		crop_height = muw.height - (max(shared_col_loops) + 1)
	
	# Verbose Crop Dimentions printout
	if verbose: print('Crop Dimentions: (%d,%d)'%(crop_width,crop_height),flush=True)
	
	return muw.wrapped_img.crop((*shift,crop_width+shift[0],crop_height+shift[1]))

def map_unsplit(splits=None,**kwargs):
	"""TODO DOC: 0"""
	width = kwargs['width'] if 'width' in kwargs else 1
	height = kwargs['height'] if 'height' in kwargs else 1
	
	unsplit = Image.new('RGBA',(width,height),(0,0,0,0))
	
	def _unsplit_generator(unsplit):
		#TODO ADD: Ability to shift based on keywords and min width and height values
		min_width,min_height = 0,0
		max_width,max_height = unsplit.size
		while(True):
			sdim,img = yield
			if isinstance(sdim,tuple):
				if len(sdim) == 4:
					x1,y1,x2,y2 = sdim
				elif len(sdim) == 2:
					x1,y1 = sdim
					x2,y2 = x1+img.width , y1+img.height
					sdim = (x1,y1,x2,y2)
				else:
					raise IndexError('_unsplit_generator function was sent incorrectly sized position coordinates. Expected (position , data) with position of either length 2 or 4, but recieved %s'%((sdim,img)))
			else: 
				raise TypeError('_unsplit_generator function was sent incorrectly typed position coordinates. Expected to be sent (tuple , PIL.Image), but instead recieved %s'%((type(sdim),type(img))))
				
			if x2 > max_width or y2 > max_height:
				max_width = max(x2,max_width)
				max_height = max(y2,max_height)
				unsplit = unsplit.crop((0,0,max_width,max_height))
				
			unsplit.paste(img,sdim)
			
			yield unsplit
			
	if splits is not None:
		#TODO CHECK: correctness of non-generator returning call
		generator = _unsplit_generator(unsplit)
		for x1 in splits:
			for y1 in splits[x1]:
				next(generator)
				unsplit = generator.send( ( (x1,y1) , splits[x1][y1].data if isinstance(splits[x1][y1],ValueMap) else splits[x1][y1]) )
		return unsplit
	else:
		generator = _unsplit_generator(unsplit)
		return generator

def map_stitch(map, *stitch_components, data_format=None):
	"""TODO DOC: 0"""
	
	if map is not None: stitch_components = map,*stitch_components
	
	width,height = None,None
	min_value,max_value = None,None
	
	saved_access_formats = {}
	
	stitch_maps = []
	coverage_maps_lookup = {}
	for map_stitch_data in stitch_components:
		if isinstance(map_stitch_data,(tuple,dict)):
			if isinstance(map_stitch_data,tuple): 
				*args,kwargs = map_stitch_data
			elif isinstance(map_stitch_data,dict): 
				args = tuple()
				kwargs = map_stitch_data
			
			map_stitch_img = _image_from_kwargs(**kwargs)
			map_stitch_format = kwargs.get('data_format',args[2] if len(args) >= 3 else None)
			
			stitch_map = DynamicRegionValueMap(*args,**kwargs)
			coverage_data = {}
			if map_stitch_format in Monochrome:
				for v,cnt in enumerate(map_stitch_img.getchannel(0).histogram()):
					if v == map_stitch_format.min_color()[0]:
						coverage_data[-1] = coverage_data.get(-1,0) + cnt
					elif v == map_stitch_format.max_color()[0]:
						coverage_data[1] = coverage_data.get(1,0) + cnt
					else:
						coverage_data[0] = coverage_data.get(0,0) + cnt
				coverage_maps_lookup[stitch_map] = coverage_data
				#coverage_maps.append((stitch_map,coverage_data))
		
		elif isinstance(map_stitch_data,ValueMap):
			stitch_map = map_stitch_data
			saved_access_formats[stitch_map] = stitch_map.get_access_format()
		else: raise TypeError('stitch component data was of incompatible type')
		
		if isinstance(stitch_map,ValueMap):
			# width 
			if width is None: width = stitch_map.width
			elif width != stitch_map.width: raise ValueError
			# height
			if height is None: height = stitch_map.height
			elif height != stitch_map.height: raise ValueError
			# min_alue
			if min_value is None: min_value = stitch_map.min_value
			else: min_value = min(min_value,stitch_map.min_value)
			# max_value
			if max_value is None: max_value = stitch_map.max_value
			else: max_value = max(max_value,stitch_map.max_value)
			
			if isinstance(stitch_map,DynamicRegionValueMap):
				stitch_map.set_access_format(map.get_access_format() if map is not None else RegionAccessFormat.BLOCK_HORIZONTAL)
			stitch_maps.append(stitch_map)
		else: raise ValueError('Unable to interpret stitch component as a ValueMap')
		
	stitch_maps.sort(key=lambda m: m.scale())
	stitch_coverage = map_value_coverage(*stitch_maps)
	
	def rec_all_coverages(map_stack,coverage_stack=[],coverage_groups=None):
		if coverage_groups is None: coverage_groups = []
		
		if map_stack:
			rec_all_coverages(map_stack[1:],coverage_stack,coverage_groups)
			rec_all_coverages(map_stack[1:],coverage_stack+[map_stack[0]],coverage_groups)
		else: coverage_groups.append(coverage_stack)
		
		return coverage_groups
	def full_coverage(maps,extrema_only=False):
		test_coverage = map_value_coverage(*maps)
		
		if extrema_only:
			nonlocal min_value,max_value
			
			pass_min,pass_max = False,False
			
			for r in test_coverage:
				if r[0] <= min_value: pass_min = True
				if r[1] >= max_value: pass_max = True
				
				if pass_min and pass_max: return True
			
			return pass_min and pass_max
		else:
			nonlocal stitch_coverage
			
			if len(test_coverage) != len(stitch_coverage): return False
			for i in range(len(stitch_coverage)):
				tc_min,tc_max = test_coverage[i]
				sc_min,sc_max = stitch_coverage[i]
				
				if tc_min <= sc_min and tc_max >= sc_max: continue
				else: return False
			return True
	
	found_full_coverage = False
	for coverage_group in sorted(rec_all_coverages([cmap for cmap in coverage_maps_lookup]),key=lambda c: len(c)):
		if full_coverage(coverage_group):
			coverage_maps = coverage_group
			found_full_coverage = True
			break
	if found_full_coverage:
		coverage_maps = [cmap for cmap in sorted(coverage_maps, key=lambda m: coverage_maps_lookup[m][0],reverse=True)]
	else:
		coverage_maps = [cmap for cmap,_ in sorted(coverage_maps_lookup.items(), key=lambda m: m[1][0],reverse=True)]
		coverage_maps = [cmap for i,cmap in enumerate(coverage_maps) if not(full_coverage(coverage_maps[:i], extrema_only=True))]
	coverage_maps_lookup = None
	
	
	def get_prelim(xy):
		nonlocal coverage_maps
		for map in coverage_maps:
			if map.on_extrema(xy) == 0:
				return map[xy]
		return None
	
	if map is None: 
		map = RegionValueMap(min_value,max_value,data_format, access_format=RegionAccessFormat.BLOCK_HORIZONTAL, size=(width,height))
	
	#print('%s\t(%s,\t%s)\t%s'%(map.size,map.min_value,map.max_value,map.access_manager.format))
	print('stitch_maps: %s'%(map_value_coverage(*stitch_maps),))
	for smap in stitch_maps:
		print('\t%s\t(%s,\t%s)\t%s'%(smap.size,smap.min_value,smap.max_value,smap.access_manager.format))
	print('coverage_maps')
	for cmap in coverage_maps:
		print('\t%s\t(%s,\t%s)\t%s'%(cmap.size,cmap.min_value,cmap.max_value,cmap.access_manager.format))
		
	for xy in map:
		
		prelim_value = get_prelim(xy)
		
		found_value = False
		found_min,found_max = None,None
		
		for smap in stitch_maps:
			if (prelim_value is not None and (
				prelim_value < smap.min_value or
				prelim_value > smap.max_value)): continue
				
			value_extrema = smap.on_extrema(xy)
			if value_extrema == 0:
				map[xy] = smap[xy]
				found_value = True
			elif value_extrema == -1:
				if found_max is None: found_max = smap[xy]
				else: found_max = min(found_max, smap.min_value)
			elif value_extrema == 1:
				if found_min is None: found_min = smap[xy]
				else: found_min = max(found_min, smap.max_value)
				
		if not found_value:
			if found_min is not None and found_max is not None:
				map[xy] = (found_min+found_max)/2
			elif found_min is not None:
				map[xy] = found_min
			elif found_max is not None:
				map[xy] = found_max
			else: ValueError('Could not determine value for point %s'%(xy,))
	
	for smap in saved_access_formats: 
		smap.set_access_format(saved_access_formats[smap])
	
	return map	



'''Color Value Format Classes'''
class ColorValueFormat(Enum):
	"""TODO DOC: 0"""
	def __call__(format,arg,**kwargs):
		"""TODO DOC: 2"""
		if isinstance(arg,(list,tuple)) and (len(arg) == 3 or len(arg) == 4):
			return format.get_value(arg,**kwargs)
		else:
			return format.get_color(arg,**kwargs)
	
	def _scale_value_up(value, min_value, max_value, cap):   return (cap*value-cap*min_value)/(max_value-min_value)
	def _scale_value_down(value, min_value, max_value, cap): return ((value*max_value - value*min_value)/cap) + min_value
	def _band_count(format): return len(format.getbands())
	
	def converter(original_format, other_format=None, original_kwargs={}, other_kwargs={}, **kwargs):
		'''	Provides conversion function with preset parameters 
				Allows for passing of formats without dealing with range arguments
			Args:
				original_format (ColorValueFormat): Format used to convert input values
				other_format (:obj:'ColorValueFormat', optional): Format used to convert result of original conversion. 
					Defaults to None.
				original_kwargs (:obj:'dict', optional): Keyword arguments used exclusively with calls to 'original_format.
					Defaults to None.
				original_kwargs (:obj:'dict', optional): Keyword arguments used exclusively with calls to 'other_format'.
					Defaults to None.
				**kwargs: Keywords given to format(s) for every conversion.
					Common keywords include 'min_value' and 'max_value', but other keywords 
					accepted by the format(s) can be provided as well
			Returns:
				function: A conversion function which takes similar arguments to calls to the format(s), but
				with the preset keywords included.
				
				Providing the optional 'other_format' argument returns a direct format to format conversion.
				
				Providing either of the optional 'original_kwargs' or 'other_kwargs' applies the contained 
				keywords exclusively to their respective call functions. 
		''' 
		def single_converter(*args,**kws):
			'''Conversion function for a single format
				
				Args:
					*args: Variable length list of arguments used for format conversion
					**kws: Additional keyword arguments used when performing conversion
				Returns:
					The return value. Expected to be either a float value or a color tuple
					
					Result of converting the provided arguments using call to 'original_format',
					and the keywords in both the 'kws' and 'kwargs' variables.
			'''
			return original_format(*args,**kws,**original_kwargs,**kwargs)
		def double_converter(*args,**kws): 
			'''Conversion function between two formats
				
				Args:
					*args: Variable length list of arguments used for first format conversion
						Expected to contain a color tuple matching 'orignal_format' specs
					**kws: Additional keyword arguments used when performing both conversions
				Returns:
					The return value. Expected to be color tuple matching 'other_format' specs.
					
					Product of converting the provided arguments using call to 'original_format',
					and the keywords in both the 'kws' and 'kwargs' variables. Then converting the
					resulting value using call to 'other_format' and the keywords in both the 
					'kws' and 'kwargs' variables.
			'''
			value = original_format(*args,**kws,**kwargs)
			return other_format(value,**kws,**kwargs)
		def double_keyword_converter(*args,**kws):
			'''Conversion function between two formats using seperate keyword dictionaries
				
				Args:
					*args: Variable length list of arguments used for first format conversion
						Expected to contain a color tuple matching 'orignal_format' specs
					**kws: Additional keyword arguments used when performing both conversions
				Returns:
					The return value. Expected to be color tuple matching 'other_format' specs.
					
					Product of converting the provided arguments using call to 'original_format',
					and the keywords in both the 'kws' and 'original_kwargs' variables. Then 
					converting the resulting value using call to 'other_format' and the keywords 
					in both the 'kws' and 'other_kwargs' variables.
			'''
			value = original_format(*args,**kws,**original_kwargs,**kwargs)
			return other_format(value,**kws,**other_kwargs,**kwargs)
		if other_format is None:
			return single_converter
		else:
			return double_keyword_converter	
	def palette(format,min_value,max_value,step=None,swatch_width=1,swatch_height=128,full=False,verbose=False):
		'''Generates Palette image for the ColorValueFormat obj accross the given range.
		
		Note:
			When the step parameter is left undefined and the difference between 'min_value' and 'max_value'
			is less than 1, the step value is defined based on the number of divisions equalling 1000. 
			When the difference is greater than 1, divisions are defined by a step size equal to 1.
			
			
		Args:
			min_value (float): Minimum value in the palettes range.
			max_value (float): Maximum value in the palettes range.
			step (:obj:'int', optional): Value increase between each color swatch in the palette.
				Defaults to None.
			swatch_width (:obj:'int', optional): Pixel width of each color swatch.
				Defaults to 1.
			swatch_height (:obj:'int', optional): Pixel height of each color swatch. 
				Defaults to 128.
			full (:obj:'bool', optional): Override for step argument. Sets step to the highest value
				that displays every possible color in range. Not recommended for larger scaled formats.
				Defaults to False.
			verbose (:obj:'bool', optional): Enables process information to be printed to the terminal.
				Defaults to False.
		
		Returns:
			PIL.Image: Image containing the colors associated with equally spaced values in formats palette range.
			
			Dimentions of full palette image equals 'divisions'*swatch_width x swatch_height. 
			With 'divisions' defined by the number of steps to get from 'min_value' to 'max_value'.
			
			If MAX_PALETTE_WIDTH is not None the palette will be divided as to be at max that many pixels wide.
		'''
		if full: 
			step = format.get_scale(min_value=min_value,max_value=max_value)
		
		if step is None:
			divisions = int(max_value-min_value)
			if divisions == 0:
				divisions = 1000
			step = int(max_value-min_value)/divisions
		else: divisions = int((max_value - min_value)//step)
		
		
		if MAX_PALETTE_WIDTH is not None and divisions*swatch_width > MAX_PALETTE_WIDTH:
			if verbose: 
				print('Palette width over maximum.\nReducing divisions from %d to %d'%(divisions,divisions:=MAX_PALETTE_WIDTH//swatch_width),flush=True)
			else: divisions = MAX_PALETTE_WIDTH//swatch_width
			step = int(max_value-min_value)/divisions
			
		splits = {}
		for i,value in enumerate((min_value + d*step for d in range(divisions))):
			if verbose and i%1000 == 0: print('Swatch[%d/%d](%d)'%(i,divisions,i*swatch_width),flush=True,end='\r')
				
			splits[i*swatch_width] = {0:Image.new(format.mode(),(swatch_width,swatch_height),format(value,min_value=min_value,max_value=max_value))}
		return map_unsplit(splits)
	def all_palettes(formats,min_value,max_value,step=None,swatch_width=1,swatch_height=64,full=False,verbose=False):
		'''Generates a single image containing the palettes of each ColorValueFormat object given.
		
		Args:
			formats (:obj:'iter' of :obj:'ColorValueFormat'): Some sequence of formats for a 
				ColorValueFormat subclass. Can also be the subclass of ColorValueFormat itself 
				to get all of its formats contained formats' palettes. 
			min_value (float): Minimum value in the palettes range.
			max_value (float): Maximum value in the palettes range.
			step (:obj:'int', optional): Value increase between each color swatch in the palette.
				Defaults to None.
			swatch_width (:obj:'int', optional): Pixel width of each color swatch.
				Defaults to 1.
			swatch_height (:obj:'int', optional): Pixel height of each color swatch. 
				Defaults to 64.
			full (:obj:'bool', optional): Override for step argument. Sets step to the highest value
				that displays every possible color in range. Not recommended for larger scaled formats.
				Defaults to False.
			verbose (:obj:'bool', optional): Enables process information to be printed to the terminal.
				Defaults to False.
		
		Returns:
			PIL.Image: Image containing the palettes of every format in formats. 
			
			Dimentions of full image equals 'divisions'*swatch_width x swatch_height*len(formats). 
			With 'divisions' defined by the number of steps to get from 'min_value' to 'max_value'.
			
			See palette function definition for more information about individual format palettes.
			'''
		
		palettes = {}
		for i,format in enumerate(formats):
			if verbose: print('Making Palette for %s'%(format),flush=True)
			palettes[i*swatch_height] = format.palette(min_value=min_value,max_value=max_value,step=step,swatch_width=swatch_width,swatch_height=swatch_height)
		return map_unsplit({0:palettes})	
	
	def getbands(format):
		"""TODO DOC: 1"""
		return tuple(format.mode())
	def value_as_bands(value,n,band_width):
		"""TODO DOC: 1"""
		if value > 2**(n*band_width) or value < 0:
			raise ValueError("Value not able to be represented in %d %d-wide value bands"%(n,band_width))
		band_mask = (2**band_width)-1
		return tuple(((value>>(band_width*((n-1)-i)))&band_mask) for i in range(n))	
	
	def max_value(format,min_value,max_value): 
		"""TODO DOC: 1"""
		return format.get_value( format.max_color(), min_value=min_value, max_value=max_value)
	def min_value(format,min_value,max_value):
		"""TODO DOC: 1"""
		return format.get_value( format.min_color(), min_value=min_value, max_value=max_value)
	def max_color(format):
		"""TODO DOC: 1"""
		return tuple( 255 for _ in range(format._band_count()))
	def min_color(format):
		"""TODO DOC: 1"""
		return tuple(  0 for _ in range(format._band_count()))
	def min(format,arg,**kwargs): 
		"""TODO DOC: 1"""
		return ((isinstance(arg,(list,tuple)) 
			and (len(arg) == 3 or len(arg) == 4) 
			and format.min_value(**kwargs) == format(arg,**kwargs)) 
			or (arg == format.min_value(**kwargs)))
	def max(format,arg,**kwargs): 
		"""TODO DOC: 1"""
		return ((isinstance(arg,(list,tuple)) 
			and (len(arg) == 3 or len(arg) == 4) 
			and format.max_value(**kwargs) == format(arg,**kwargs))
			or (arg == format.max_value(**kwargs)))
	def mode(format):
		"""TODO DOC: 1"""
		if format.name.startswith('RGBA'):  return 'RGBA'
		elif format.name.startswith('RGB'): return 'RGB'
		else: raise NotImplementedError
	def get_scale(format,min_value,max_value):
		"""TODO DOC: 1"""
		return (max_value - min_value)/len(format)
		
	#Functions to implement in each subclass
	def get_value(format,*args,**kwargs): raise NotImplementedError
	def get_color(format,*args,**kwargs): raise NotImplementedError
	def __len__(format):                  raise NotImplementedError

class Monochromatic(ColorValueFormat):
	def _scale_value_up(value, min_value, max_value, cap=255):   return ColorValueFormat._scale_value_up( value, min_value, max_value, 255)
	def _scale_value_down(value, min_value, max_value, cap=255): return ColorValueFormat._scale_value_down( value, min_value, max_value, 255)
	def _is_monochrome(*bands): return False if len(tuple( (bands[i-1],b) for i,b in enumerate(bands) if i > 0 and b!=bands[i-1])) else True
	
	def min_color(format):
		"""TODO DOC: 1"""
		if (mode:=format.mode())=='RGBA': 
			return (0,0,0, MONOCHROMATIC_ALPHA_VALUE)
		return super().min_color()
	def max_color(format): 
		"""TODO DOC: 1"""
		if (mode:=format.mode())=='RGBA': 
			return (255,255,255, MONOCHROMATIC_ALPHA_VALUE)
		return super().max_color()
	def __len__(format): return 255

class Monochrome(Monochromatic):
	RGB=0
	RGBA=1
	def get_value(format, color, min_value, max_value):
		"""TODO DOC: 1"""
		if MONOCHROME_VERIFY_CHANNELS and  not(Monochrome._is_monochrome(*color)):
			raise ValueError('Attempted to convert non-monochrome color %s using %s ColorValueFormat.'%(color,format),'Set MONOCHROME_VERIFY_CHANNELS equal to False to ignore check')
		return int(Monochrome._scale_value_down(color[0],min_value,max_value))
	
	def get_color(format, value, min_value, max_value):
		"""TODO DOC: 1"""
		band_value = int(Monochrome._scale_value_up(value,min_value,max_value))
		return tuple( band_value if i < 3 else 255 for i in range(format._band_count()))

class Polychromatic(ColorValueFormat):
	def _get_reorder_function(format): return None
	def reorder_color(format,color,reverse=False):
		"""TODO DOC: 1"""
		if format._get_reorder_function() is None: return color
		
		return format._get_reorder_function()(color,reverse=reverse)
	
	def min_color(format):
		"""TODO DOC: 1"""
		if (mode := format.mode())=='RGB': return (0,0,0)
		elif mode == 'RGBA':             return (0,0,0,0)
		else: raise NotImplementedError
	def max_color(format): 
		"""TODO DOC: 1"""
		if (mode := format.mode())=='RGB': return (255,255,255)
		elif mode == 'RGBA':             return (255,255,255,255)
		else: raise NotImplementedError
	def __len__(format): 
		"""TODO DOC: 2"""
		return (2**(8*format._band_count()))-1
	
class Polychrome(Polychromatic):
	"""TODO DOC: 0"""
	# 'RGB' type formats
	#  'RGB' alias formats
	RGB_s1 = (24, REORDER_RGB['RGB'])
	RGB_s2 = (12, REORDER_RGB['RGB'])
	RGB_s4 = ( 6, REORDER_RGB['RGB'])
	RGB_s8 = ( 3, REORDER_RGB['RGB'])
	RGB = (24//POLYCHROME_DEFAULT_STRIPE_WIDTH, REORDER_RGB['RGB'])
	
	# 'RGB' enum member formats
	RGB_RGB_s1 = (24, REORDER_RGB['RGB'])
	RGB_RGB_s2 = (12, REORDER_RGB['RGB'])
	RGB_RGB_s4 = ( 6, REORDER_RGB['RGB'])
	RGB_RGB_s8 = ( 3, REORDER_RGB['RGB'])
	
	RGB_RBG_s1 = (24, REORDER_RGB['RBG'])
	RGB_RBG_s2 = (12, REORDER_RGB['RBG'])
	RGB_RBG_s4 = ( 6, REORDER_RGB['RBG'])
	RGB_RBG_s8 = ( 3, REORDER_RGB['RBG'])
	
	RGB_GRB_s1 = (24, REORDER_RGB['GRB'])
	RGB_GRB_s2 = (12, REORDER_RGB['GRB'])
	RGB_GRB_s4 = ( 6, REORDER_RGB['GRB'])
	RGB_GRB_s8 = ( 3, REORDER_RGB['GRB'])
	
	RGB_GBR_s1 = (24, REORDER_RGB['GBR'])
	RGB_GBR_s2 = (12, REORDER_RGB['GBR'])
	RGB_GBR_s4 = ( 6, REORDER_RGB['GBR'])
	RGB_GBR_s8 = ( 3, REORDER_RGB['GBR'])
	
	RGB_BRG_s1 = (24, REORDER_RGB['BRG'])
	RGB_BRG_s2 = (12, REORDER_RGB['BRG'])
	RGB_BRG_s4 = ( 6, REORDER_RGB['BRG'])
	RGB_BRG_s8 = ( 3, REORDER_RGB['BRG'])
	
	RGB_BGR_s1 = (24, REORDER_RGB['BGR'])
	RGB_BGR_s2 = (12, REORDER_RGB['BGR'])
	RGB_BGR_s4 = ( 6, REORDER_RGB['BGR'])
	RGB_BGR_s8 = ( 3, REORDER_RGB['BGR'])
	
	# 'RGBA' type formats
	#  'RGBA' alias formats
	RGBA_S1 = (32, REORDER_RGBA['RGBA'])
	RGBA_S2 = (16, REORDER_RGBA['RGBA'])
	RGBA_S4 = ( 8, REORDER_RGBA['RGBA'])
	RGBA_S8 = ( 4, REORDER_RGBA['RGBA'])
	RGBA = (32//POLYCHROME_DEFAULT_STRIPE_WIDTH, REORDER_RGBA['RGBA'])
	
	# 'RGBA' enum member formats
	RGBA_RGBA_s1 = (32, REORDER_RGBA['RGBA'])
	RGBA_RGBA_s2 = (16, REORDER_RGBA['RGBA'])
	RGBA_RGBA_s4 = ( 8, REORDER_RGBA['RGBA'])
	RGBA_RGBA_s8 = ( 4, REORDER_RGBA['RGBA'])
	
	RGBA_RGAB_s1 = (32, REORDER_RGBA['RGAB'])
	RGBA_RGAB_s2 = (16, REORDER_RGBA['RGAB'])
	RGBA_RGAB_s4 = ( 8, REORDER_RGBA['RGAB'])
	RGBA_RGAB_s8 = ( 4, REORDER_RGBA['RGAB'])
	
	RGBA_RBGA_s1 = (32, REORDER_RGBA['RBGA'])
	RGBA_RBGA_s2 = (16, REORDER_RGBA['RBGA'])
	RGBA_RBGA_s4 = ( 8, REORDER_RGBA['RBGA'])
	RGBA_RBGA_s8 = ( 4, REORDER_RGBA['RBGA'])
	
	RGBA_RBAG_s1 = (32, REORDER_RGBA['RBAG'])
	RGBA_RBAG_s2 = (16, REORDER_RGBA['RBAG'])
	RGBA_RBAG_s4 = ( 8, REORDER_RGBA['RBAG'])
	RGBA_RBAG_s8 = ( 4, REORDER_RGBA['RBAG'])
	
	RGBA_RAGB_s1 = (32, REORDER_RGBA['RAGB'])
	RGBA_RAGB_s2 = (16, REORDER_RGBA['RAGB'])
	RGBA_RAGB_s4 = ( 8, REORDER_RGBA['RAGB'])
	RGBA_RAGB_s8 = ( 4, REORDER_RGBA['RAGB'])
	
	RGBA_RABG_s1 = (32, REORDER_RGBA['RABG'])
	RGBA_RABG_s2 = (16, REORDER_RGBA['RABG'])
	RGBA_RABG_s4 = ( 8, REORDER_RGBA['RABG'])
	RGBA_RABG_s8 = ( 4, REORDER_RGBA['RABG'])
	
	RGBA_GRBA_s1 = (32, REORDER_RGBA['GRBA'])
	RGBA_GRBA_s2 = (16, REORDER_RGBA['GRBA'])
	RGBA_GRBA_s4 = ( 8, REORDER_RGBA['GRBA'])
	RGBA_GRBA_s8 = ( 4, REORDER_RGBA['GRBA'])
	
	RGBA_GRAB_s1 = (32, REORDER_RGBA['GRAB'])
	RGBA_GRAB_s2 = (16, REORDER_RGBA['GRAB'])
	RGBA_GRAB_s4 = ( 8, REORDER_RGBA['GRAB'])
	RGBA_GRAB_s8 = ( 4, REORDER_RGBA['GRAB'])
	
	RGBA_GBRA_s1 = (32, REORDER_RGBA['GBRA'])
	RGBA_GBRA_s2 = (16, REORDER_RGBA['GBRA'])
	RGBA_GBRA_s4 = ( 8, REORDER_RGBA['GBRA'])
	RGBA_GBRA_s8 = ( 4, REORDER_RGBA['GBRA'])
	
	RGBA_GBAR_s1 = (32, REORDER_RGBA['GBAR'])
	RGBA_GBAR_s2 = (16, REORDER_RGBA['GBAR'])
	RGBA_GBAR_s4 = ( 8, REORDER_RGBA['GBAR'])
	RGBA_GBAR_s8 = ( 4, REORDER_RGBA['GBAR'])
	
	RGBA_GARB_s1 = (32, REORDER_RGBA['GARB'])
	RGBA_GARB_s2 = (16, REORDER_RGBA['GARB'])
	RGBA_GARB_s4 = ( 8, REORDER_RGBA['GARB'])
	RGBA_GARB_s8 = ( 4, REORDER_RGBA['GARB'])
	
	RGBA_GABR_s1 = (32, REORDER_RGBA['GABR'])
	RGBA_GABR_s2 = (16, REORDER_RGBA['GABR'])
	RGBA_GABR_s4 = ( 8, REORDER_RGBA['GABR'])
	RGBA_GABR_s8 = ( 4, REORDER_RGBA['GABR'])
	
	RGBA_BRGA_s1 = (32, REORDER_RGBA['BRGA'])
	RGBA_BRGA_s2 = (16, REORDER_RGBA['BRGA'])
	RGBA_BRGA_s4 = ( 8, REORDER_RGBA['BRGA'])
	RGBA_BRGA_s8 = ( 4, REORDER_RGBA['BRGA'])
	
	RGBA_BRAG_s1 = (32, REORDER_RGBA['BRAG'])
	RGBA_BRAG_s2 = (16, REORDER_RGBA['BRAG'])
	RGBA_BRAG_s4 = ( 8, REORDER_RGBA['BRAG'])
	RGBA_BRAG_s8 = ( 4, REORDER_RGBA['BRAG'])
	
	RGBA_BGRA_s1 = (32, REORDER_RGBA['BGRA'])
	RGBA_BGRA_s2 = (16, REORDER_RGBA['BGRA'])
	RGBA_BGRA_s4 = ( 8, REORDER_RGBA['BGRA'])
	RGBA_BGRA_s8 = ( 4, REORDER_RGBA['BGRA'])
	
	RGBA_BGAR_s1 = (32, REORDER_RGBA['BGAR'])
	RGBA_BGAR_s2 = (16, REORDER_RGBA['BGAR'])
	RGBA_BGAR_s4 = ( 8, REORDER_RGBA['BGAR'])
	RGBA_BGAR_s8 = ( 4, REORDER_RGBA['BGAR'])
	
	RGBA_BARG_s1 = (32, REORDER_RGBA['BARG'])
	RGBA_BARG_s2 = (16, REORDER_RGBA['BARG'])
	RGBA_BARG_s4 = ( 8, REORDER_RGBA['BARG'])
	RGBA_BARG_s8 = ( 4, REORDER_RGBA['BARG'])
	
	RGBA_BAGR_s1 = (32, REORDER_RGBA['BAGR'])
	RGBA_BAGR_s2 = (16, REORDER_RGBA['BAGR'])
	RGBA_BAGR_s4 = ( 8, REORDER_RGBA['BAGR'])
	RGBA_BAGR_s8 = ( 4, REORDER_RGBA['BAGR'])
	
	RGBA_ARGB_s1 = (32, REORDER_RGBA['ARGB'])
	RGBA_ARGB_s2 = (16, REORDER_RGBA['ARGB'])
	RGBA_ARGB_s4 = ( 8, REORDER_RGBA['ARGB'])
	RGBA_ARGB_s8 = ( 4, REORDER_RGBA['ARGB'])
	
	RGBA_ARBG_s1 = (32, REORDER_RGBA['ARBG'])
	RGBA_ARBG_s2 = (16, REORDER_RGBA['ARBG'])
	RGBA_ARBG_s4 = ( 8, REORDER_RGBA['ARBG'])
	RGBA_ARBG_s8 = ( 4, REORDER_RGBA['ARBG'])
	
	RGBA_AGRB_s1 = (32, REORDER_RGBA['AGRB'])
	RGBA_AGRB_s2 = (16, REORDER_RGBA['AGRB'])
	RGBA_AGRB_s4 = ( 8, REORDER_RGBA['AGRB'])
	RGBA_AGRB_s8 = ( 4, REORDER_RGBA['AGRB'])
	
	RGBA_AGBR_s1 = (32, REORDER_RGBA['AGBR'])
	RGBA_AGBR_s2 = (16, REORDER_RGBA['AGBR'])
	RGBA_AGBR_s4 = ( 8, REORDER_RGBA['AGBR'])
	RGBA_AGBR_s8 = ( 4, REORDER_RGBA['AGBR'])
	
	RGBA_ABRG_s1 = (32, REORDER_RGBA['ABRG'])
	RGBA_ABRG_s2 = (16, REORDER_RGBA['ABRG'])
	RGBA_ABRG_s4 = ( 8, REORDER_RGBA['ABRG'])
	RGBA_ABRG_s8 = ( 4, REORDER_RGBA['ABRG'])
	
	RGBA_ABGR_s1 = (32, REORDER_RGBA['ABGR'])
	RGBA_ABGR_s2 = (16, REORDER_RGBA['ABGR'])
	RGBA_ABGR_s4 = ( 8, REORDER_RGBA['ABGR'])
	RGBA_ABGR_s8 = ( 4, REORDER_RGBA['ABGR'])
	
	
	def _get_reorder_function(format): return format.value[1]
	def _stripe(value, n, stripe_width):
		num_bits = n*8
		if value > 2**(num_bits) or value < 0: 
			raise ValueError(
				'Value of %s is not representable'%(value),
				'Value must be positive' if value < 0 else 'Requires more than the %d bits allowed by %d stripes.'%(num_bits,n)
			)
		
		if num_bits%stripe_width != 0: 
			raise ValueError('The number of bits %d is not divisible by the stripe width %d'%(num_bits,stripe_width))
		
		num_stripes = num_bits//stripe_width
		stripe_mask = (2**stripe_width)-1
		
		value_bands = [0x0 for _ in range(n)]
		
		for i,stripe in enumerate(Polychrome.value_as_bands(value,num_stripes,band_width=stripe_width)):
			value_bands[i%n] = (value_bands[i%n]<<stripe_width)|stripe
		
		return tuple(value_bands)
	def _unstripe(color, n, stripe_width):
		num_bits = n*8
		if num_bits%stripe_width != 0: 
			raise ValueError('The number of bits %d is not divisible by the stripe width %d'%(num_bits,stripe_width))
		
		num_stripes = num_bits//stripe_width
		if num_stripes%n != 0:
			raise ValueError('The number of stripes %d is not divisible by the number of channels %d'%(num_stripes,n))
		
		num_channel_stripes = num_stripes//n 
		
		value_bands = [ Polychrome.value_as_bands(channel,num_channel_stripes,band_width=stripe_width) for channel in color]	
		
		unstriped_value = 0x0
		for i in range(num_stripes):
			unstriped_value = (unstriped_value<<stripe_width)|(value_bands[i%n][i//n])
		
		return unstriped_value
	def _stripe_width(format, n=None):
		if n is None: 
			n = format._band_count()
		return n*8//format.value[0]
	
	def get_value(format, color, min_value, max_value):
		"""TODO DOC: 1"""
		n = format._band_count()
		
		color = format.reorder_color(color)
		
		raw_value = Polychrome._unstripe( color, n, format._stripe_width(n))
		
		#Applies conversion to rescale value to given min and max
		return Polychrome._scale_value_down( raw_value, min_value, max_value, len(format))
		
	def get_color(format, value, min_value, max_value):
		"""TODO DOC: 1"""
		n = format._band_count()
		
		scaled_value = int(Polychrome._scale_value_up( value, min_value, max_value, len(format)))
		
		color =  Polychrome._stripe( scaled_value, n, format._stripe_width(n))
		
		return format.reorder_color(color, reverse=True)	



'''Data Map Classes'''
class DataMap:
	"""TODO DOC: 0"""
	ACCEPTED_IMAGE_FILE_TYPES = ('.png','.PNG')
	def _data_from_kwargs(map,image=None,filename=None,size=None,**kwargs):
		"""TODO DOC: 2"""
		if image is not None:
			map.data = image
		elif filename is not None:
			if filename.endswith(map.__class__.ACCEPTED_IMAGE_FILE_TYPES):
				map.data = Image.open(filename)
			else: 
				raise NotImplementedError(
					"Unsupported image file type for '%s' file"%(filename,),
					"To change the file extentions supported by this class, set %s.ACCEPTED_IMAGE_FILE_TYPES to a tuple containing the '.%s' extention"%(map.__class__,filename.split(',')[-1])
				)
		elif size is not None:
			map.data = None
			map.size = size
			return
		else: raise ValueError('No source given for map data')
		
		map.size = map.data.size
		
	'''Methods to be implemented in subclasses'''
	def __iter__(map):                  raise NotImplementedError
	def __getitem__(map, point):        raise NotImplementedError
	def __setitem__(map, point, value): raise NotImplementedError
	def __delitem__(map, point):        raise NotImplementedError

class ValueMap(DataMap):
	"""TODO DOC: 0"""
	
	def __init__(map, 
			min_value,max_value,
			data_format,
			access_format=RegionAccessFormat.LINEAR_HORIZONTAL,
			access_manager=StaticAccessManager,
			**data_kwargs):
		"""TODO DOC: 2"""
		
		map.min_value=min_value
		map.max_value=max_value
		
		map.data_format = data_format
		
		map.data_converter = map.data_format.converter(
			min_value=map.min_value,
			max_value=map.max_value,
		)
		
		# Sets 'data','size','width', and 'height' attributes
		map._data_from_kwargs(**data_kwargs)
		
		map.access_manager = access_manager(
			access_format,
			map.size,
			fetch_function=lambda x:map.data
		)
		
	def __iter__(map): yield from map.access_manager
	def __getitem__(map, xy): 
		return map.data_converter(map.access_manager.get_point(xy).getpixel(map.in_dimensions(xy)))
	def __setitem__(map, xy, value): 
		map.access_manager.set_point(xy).putpixel(map.in_dimensions(xy),map.data_converter(value))
	
	def _data_from_kwargs(map,data=None,**data_kwargs):
		"""TODO DOC: 2"""
		if data is not None: 
			raise NotImplementedError("The 'data' keyword is currently unsupported by the %s class."%(map.__class__)) 
		
		super()._data_from_kwargs(**data_kwargs)
		if map.data is None: 
			map.data = Image.new(map.data_format.mode(),map.size)
		map.width,map.height = map.size
		
	def get_access_format(map): 
		"""TODO DOC: 1"""
		return map.access_manager.format
	def set_access_format(map,access_format):
		"""TODO DOC: 1"""
		map.access_manager.update(format=access_format)	
	
	def scale(map): 
		"""TODO DOC: 1"""
		return map.data_format.get_scale(map.min_value,map.max_value)
	def in_range(map, value): 
		"""TODO DOC: 1"""
		return map.min_value <= value <= map.max_value
	def in_dimensions(map,xy):
		"""TODO DOC: 1"""
		if 0 > xy[0] >= map.width: 
			raise ValueError("'xy' value of %s is outside the allowed width dimensions of map"%(xy,))
		elif 0 > xy[1] >= map.height: 
			raise ValueError("'xy' value of %s is outside the allowed height dimensions of map"%(xy,))
		else: return xy
	def on_extrema(map,xy):
		"""TODO DOC: 1"""
		value = map[xy]
		if map.data_format.min(value, min_value=map.min_value, max_value=map.max_value): 
			return -1
		elif map.data_format.max(value, min_value=map.min_value, max_value=map.max_value): 
			return 1
		else: 
			return 0
	
	def convert(map, data_format, map_type=None, **kwargs):
		"""TODO DOC: 1"""
		conversion_img = map.data.copy() 
		
		data_converter = data_format.converter(
			min_value=map.min_value, 
			max_value=map.max_value
		)
		
		for xy in map:
			conversion_img.putpixel(xy,data_converter(map[xy]))
		
		if map_type is not None:
			return map_type(
				map.min_value, map.max_value, 
				data_format, 
				image=conversion_img
			)
		else:
			return map.__class__(
				map.min_value, map.max_value, 
				data_format, 
				image=conversion_img
			)
	def draw_clear(map): 
		"""TODO DOC: 1"""
		map.draw_img = None
	def draw(map, points, color=(255,255,255), clear=False): 
		"""TODO DOC: 1"""
		if clear or not(hasattr(map,'draw_img')) or map.draw_img is None:
			map.draw_img = map.data.copy()
		
		pix = map.draw_img.load()
		
		for xy in points:
			pix[xy] = color
		return map.draw_img
	def show(map, data_format=None, draw=False): 
		"""TODO DOC: 1"""
		if (data_format is not None and 
			data_format is not map.data_format):
			
			map.convert(data_format).show()
		elif draw:
			if hasattr(map,'draw_img') and  map.draw_img is not None:
				map.draw_img.show()
			else: raise ValueError('%s does not have drawing available to show'%map.__class__)
		else: map.data.show()
	def save(map, filename, data_format=None): 
		"""TODO DOC: 1"""
		if (data_format is not None and 
			data_format is not map.data_format):
			
			map.convert(data_format).save(filename)
		
		else: map.data.save(filename)

class RegionValueMap(ValueMap):
	"""TODO DOC: 0"""
	MIN_WIDTH_DIVISIONS  = 8#16
	MAX_WIDTH_DIVISIONS  = 128
	MIN_HEIGHT_DIVISIONS = 8#16
	MAX_HEIGHT_DIVISIONS = 128
	MIN_BLOCK_WIDTH  = 32
	MAX_BLOCK_WIDTH  = 0xFFFFFFFF
	MIN_BLOCK_HEIGHT = 32
	MAX_BLOCK_HEIGHT = 0xFFFFFFFF
	
	def __init__(map, 
			min_value,max_value,
			data_format,
			access_format=RegionAccessFormat.LINEAR_HORIZONTAL,
			access_manager=StaticAccessManager,
			**data_kwargs):
		"""TODO DOC: 2"""
		# Sets 'data','size','width', and 'height' attributes
		super().__init__(min_value,max_value,data_format,access_format=access_format,access_manager=access_manager,**data_kwargs)
		map.access_manager.update(
			block_dimension=map.block_size,
			fetch_function=lambda block: map.block_map(_get_block_as_point(block,map.block_size)), 
			#block_as_point(pack(map.block_map), map.block_size),
		)
	def __del__(map):
		try: 
			if map.temporary_directory: 
				rmtree(map.dirpath) 
				print('Deleted temp directory: "%s"'%map.dirpath,flush=True)
		except FileNotFoundError as e:
			print("'%s' directory could not be found when trying to perform cleanup of %s temporary directory "%(map.dirpath, map.__class__.__name__),flush=True)
		except NotADirectoryError as e:
			print("Attempted to cleanup %s temporary directory, but its dirpath attribute '%s' does not correspond to a valid directory"%(map.__class__.__name__,map.dirpath),flush=True)
			raise e
	def __getitem__(map, xy): return map.access_manager.get_point(xy)[map.block_subpoint(xy)]
	def __setitem__(map, xy, value): map.access_manager.set_point(xy)[map.block_subpoint(xy)] = value
	
	def _data_from_kwargs(map, block_size=None, dirpath=None,**data_kwargs):
		"""TODO DOC: 2"""
		if block_size is not None:
			map.block_size = block_size
		else: map.block_size = None 
		
		if dirpath is not None:
			
			map.temporary_directory = False
			map.dirpath = dirpath
			
			if os.path.isdir(map.dirpath): # dirpath is a directory
				size = data_kwargs.get('size',None)
				# Search for size of both the entire map and its component blocks 
				if map.block_size is None or size is None:
					found_blocks = {}
					for filename in os.listdir(map.dirpath):
						filepath = os.path.join(map.dirpath,filename)
						
						if not os.path.isfile(filepath): continue
						if not filename.startswith(map.block_prefix()): continue
						if not filename.endswith(map.__class__.ACCEPTED_IMAGE_FILE_TYPES): continue
						
						prefix,x1,y1,x2,y2 = tuple(int(item if item.isnumeric() else item.split('.')[0] ) if i > 0 else item for i,item in enumerate(filename.split('_')) if i < 5)
						block_size = (x2-x1,y2-y1)
						
						if (map.block_size is not None 
								and (block_size[0] != map.block_size[0]
								or   block_size[1] != map.block_size[1])): continue 
						
						found_blocks.setdefault(block_size,{}).update(
							min_width  = min(found_blocks[block_size].setdefault('min_width',x1),  x1),
							max_width  = max(found_blocks[block_size].setdefault('max_width',x2),  x2),
							min_height = min(found_blocks[block_size].setdefault('min_height',y1), y1),
							max_height = max(found_blocks[block_size].setdefault('max_height',y2), y2),
						)
						found_blocks[block_size].setdefault('blocks',set()).add((x1,y1,x2,y2))
					if len(found_blocks) == 1:
						map.block_size,found_blocks_info = found_blocks.popitem()
						
						if  (found_blocks_info['min_width'] == 0 and found_blocks_info['min_height'] == 0 and 
							(size is None
								or (size[0] == found_blocks_info['max_width']
								and   size[1] == found_blocks_info['max_height']))):
							
							size = found_blocks_info['max_width'],found_blocks_info['max_height']
					elif len(found_blocks) > 1: 
						raise ValueError("Inconsistent block sizes found in '%s' dirpath directory"%map.dirpath)
				# Enough features known to check for complete set of blocks
				if map.block_size is not None and size is not None:
					all_blocks = True
					for box in _region_blocks_iterator(size, map.block_size):
						block_path = map.block_filepath(box)
						if not os.path.isfile(block_path): # Missing block file from map.dirpath
							all_blocks = False
							break
					if all_blocks: # No missing block files
						map.size = size
						map.width,map.height = map.size
						map.block_width,map.block_height = map.block_size
						# Return early after setting appropiate attributes
						return
			elif os.path.exists(map.dirpath): # dirpath already exists
				raise NotADirectoryError("The dirpath keyword argument '%s' passed to %s initializer is not a directory"%(dirpath,map.__class__.__name__))
			else: os.makedirs(map.dirpath,exist_ok=False)
		else: map.temporary_directory = True
		
		# Sets 'data','size','width', and 'height'
		super()._data_from_kwargs(**data_kwargs)
		
		
		if map.block_size is None:
			# Calculate optimal block size
			width_divisions  = _get_possible_divisions(map.width, *map._block_width_range())
			height_divisions = _get_possible_divisions(map.height,*map._block_height_range())
			for block_width,_ in width_divisions:
				for block_height,_ in height_divisions:
					if block_width == block_height: # Take first matching division value between width and height
						map.block_size = block_width,block_height
						break
				if map.block_size is not None: break
			if map.block_size is None: # No matchin division value found between width and height
				map.block_size,_ = zip(
					width_divisions[0]  if len(width_divisions)  > 0 else (map.width,None),
					height_divisions[0] if len(height_divisions) > 0 else (map.height,None),
				)
				
		map.block_width,map.block_height = map.block_size
		
		if map.temporary_directory: map.dirpath = tempfile.mkdtemp()
			
		if map.data is None:
			#TODO ADD: Ability to create blank region maps. (Possible Implimentation possibly in ValueMap._data_from_kwargs)
			raise NotImplementedError
		elif isinstance(map.data,Image.Image):
			for box in _region_blocks_iterator(map.size,map.block_size):
				block_path = map.block_filepath(box)
				
				if os.path.isfile(block_path): continue
				
				map.data.crop(box).save(block_path)
			map.data = None
		else: raise NotImplementedError
		
	def _block_width_range(map):
		return (
			max(map.__class__.MIN_BLOCK_WIDTH, int(map.width/map.__class__.MAX_WIDTH_DIVISIONS)),
			min(map.__class__.MAX_BLOCK_WIDTH, int(map.width/map.__class__.MIN_WIDTH_DIVISIONS))
		)
	def _block_height_range(map):
		return (
			max(map.__class__.MIN_BLOCK_HEIGHT, int(map.height/map.__class__.MAX_HEIGHT_DIVISIONS)),
			min(map.__class__.MAX_BLOCK_HEIGHT, int(map.height/map.__class__.MIN_HEIGHT_DIVISIONS))
		)
	def _boxed(map,block):
		if len(block) == 4: return block
		elif len(block) == 2: 
			return *block,block[0]+map.block_size[0],block[1]+map.block_size[1]
		else: raise ValueError("Could not turn '%s' into box format"%(block,))
	
	def block_prefix(map): 
		"""TODO DOC: 1"""
		return 'VMR'
	def block_filename(map,block): 
		"""TODO DOC: 1"""
		return '%s_%d_%d_%d_%d.png'%(map.block_prefix(), *map._boxed(block))
	def block_filepath(map,block): 
		"""TODO DOC: 1"""
		return os.path.join(map.dirpath, map.block_filename(block))
	def block_subpoint(map, xy): 
		"""TODO DOC: 1"""
		return tuple( d%map.block_size[i] for i,d in enumerate(xy))
	def block_map(map, block): 
		"""TODO DOC: 1"""
		return ValueMap(map.min_value, map.max_value, map.data_format, filename=map.block_filepath(block))
	
	def _combine_regions(map,full=True):
		splits = {}
		for box in _region_blocks_iterator(map.size,map.block_size):
			*xy,_,_ = box
			if full or map.access_manager.has_point(xy):
				vm = map.access_manager.get_point(xy)
				splits.setdefault(xy[0],{})[xy[1]] = vm.data
		return map_unsplit(splits)
	
	def convert(map, data_format, map_type=None, **kwargs): raise NotImplementedError
	def draw(map, points, color=(255,255,255), clear=False):
		"""TODO DOC: 1"""
		if clear or not(hasattr(map,'draw_img')) or map.draw_img is None:
			map.draw_img = map._combine_regions(True)
		
		pix = map.draw_img.load()
		
		for xy in points:
			pix[xy] = color
		return map.draw_img
	def show(map, data_format=None, draw=False, full=True):
		"""TODO DOC: 1"""
		if (data_format is not None and 
			data_format is not map.data_format):
			raise NotImplementedError
		elif draw: 
			if hasattr(map,'draw_img') and  map.draw_img is not None:
				map.draw_img.show()
			else: raise ValueError('%s does not have drawing available to show'%map.__class__)
		else: map._combine_regions(full=full).show()
	def save(map, filename=None, data_format=None, dirpath=None, full=True): 
		"""TODO DOC: 1"""
		if filename is not None and dirpath is None:
			if (data_format is not None and 
				data_format is not map.data_format):
				raise NotImplementedError
			else:
				combined_img = map._combine_regions(full=full)
			combined_img.save(filename)
		elif dirpath is not None and filename is None:
			raise NotImplementedError
		else: raise ValueError('Single save location not given. Must provide a value for either the filename or dirpath keywords')
	
class DynamicRegionValueMap(RegionValueMap):
	"""TODO DOC: 0"""
	def __init__(map,
			min_value,max_value,
			data_format,
			access_format=RegionAccessFormat.LINEAR_HORIZONTAL,
			access_manager=DynamicAccessManager,
			**data_kwargs):
		"""TODO DOC: 2"""
		super().__init__(min_value,max_value,data_format,access_format=access_format,access_manager=access_manager,**data_kwargs)
		if DEBUG_VERBOSE: print('map.block_size = %s'%(map.block_size,))

	

'''map.py Unit Test Functions'''
def _parse_data_image_filename(fn):
	import re
	parse = re.search(r'.+_([\d\-]+)_([\d\-]+)\.png',fn)
	if parse:
		return fn,int(parse.group(1)),int(parse.group(2))
	else: raise ValueError('Could not parse data image filename',fn)

def _get_data_image_filenames(pattern=None):
	import re
	valid_paths=[]
	for filename in os.listdir(DEBUG_DATA_IMAGE_FOLDER):
		if pattern is None or re.search(pattern,filename):
			filepath = os.path.join(DEBUG_DATA_IMAGE_FOLDER,filename)
			if not os.path.isfile(filepath): raise ValueError('Failed')
			valid_paths.append(filepath)
	
	return valid_paths		


'''Public Utility Function tests'''
def test_stitching():
	
	files = _get_data_image_filenames(r'data_image_[\-\d]+_[\-\d]+.png')
	vms = []
	
	for fn in files:
		_,min_value,max_value = _parse_data_image_filename(fn)
		
		print(fn, flush=True)
		
		wrapped_image = map_unwrap(
			filepath=fn,
			col=False,
			shift=(435,0),
			sampling=0.01,
			verbose=True,
		)
		
		vm_kws = dict(
			min_value = min_value,
			max_value = max_value,
			data_format = Monochrome.RGB,
			image=wrapped_image,
			#image=wrapped_image.resize((wrapped_image.width//3,wrapped_image.height//3),resample=Image.NONE),
		)
		
		vms.append(vm_kws)
	
	final_hm = map_stitch(None,*vms,data_format=Polychrome.RGBA_S1)
	
	final_hm.show()
	

'''Data Map subclass tests'''
def test_value_map_class():
	print('====Running ValueMap Class Tests====',flush=True)
	unwrapped_image = map_unwrap(
		filepath='wrapped_test_0_500.png',
		col=False,
		shift=(4350,0),
		sampling=0.01,
		verbose=True,
	)
	map = ValueMap(0,500,Monochrome.RGB,image=unwrapped_image)
	unwrapped_image=None
	
	sum = 0
	for x,y in map:
		if y %120==0 and x%120 ==0:
			sum += map[x,y]
	
def test_region_value_map_class():
	print('====Running RegionValueMap Class Tests====',flush=True)
	unwrapped_image = map_unwrap(
		filepath='wrapped_test_0_500.png',
		col=False,
		shift=(4350,0),
		sampling=0.01,
		verbose=True,
	)
	
	map = RegionValueMap(0,500,Monochrome.RGB,image=unwrapped_image)
	#map = RegionValueMap(0,500,Monochrome.RGB,dirpath='test_0_500')
	unwrapped_image=None
	
	sum = 0
	for x,y in map:
		if y %120==0 and x%120 ==0:
			sum += map[x,y]
	
def test_dynamic_region_value_map_class():
	print('====Running DynamicRegionValueMap Class Tests====',flush=True)
	unwrapped_image = map_unwrap(
		filepath='wrapped_test_0_500.png',
		col=False,
		shift=(4350,0),
		sampling=0.01,
		verbose=True,
	)
	map = DynamicRegionValueMap(0,500,Monochrome.RGB,image=unwrapped_image)
	#map = DynamicRegionValueMap(0,500,Monochrome.RGB,dirpath='test_0_500')
	unwrapped_image=None
	
	sum = 0
	for x,y in map:
		if y %120==0 and x%120 ==0:
			sum += map[x,y]


'''ColorValueFormat tests'''
def test_ColorValueFormat(converter_func=False):
	
	def test_converter():
		def compare_conversions(cA,cB):
			if len(cA) != len(cB): raise ValueError('Incompatible Length')
			for i in range(min(len(cA),len(cB))):
				if cA[i] != cB[i]: return i,cA[i],cB[i]
			return False
		def conversion_chain(converter,n,value,*args,**kwargs):
			chain = [value]
			for i in range(n):
				try: chain.append(converter(chain[i],*args,**kwargs))
				except Exception as e: return [e]
			return chain
		def test_single(value,format,min_value,max_value,verbose=True):
			converters = [
				#BASE
				(format,{'min_value':min_value,'max_value':max_value}),
				
				#Converter Functions 
				#**kwargs <- min_value,max_value
				(format.converter(min_value=min_value,max_value=max_value),{}),
				#**kwargs <- max_value	**kws <- min_value
				(format.converter(max_value=max_value),{'min_value':min_value}),
				#**kwargs <- min_value	**kws <- max_value
				(format.converter(min_value=min_value),{'max_value':max_value}),
				
				#**original_kwargskwargs <- min_value,max_value
				(format.converter(original_kwargs={'min_value':min_value,'max_value':max_value}),{}),
				#**kwargs <- min_value	**original_kwargskwargs <- max_value
				(format.converter(original_kwargs={'max_value':max_value},min_value=min_value),{}),
				#**kws <- min_value	**original_kwargskwargs <- max_value
				(format.converter(original_kwargs={'max_value':max_value}),{'min_value':min_value}),
				#**kwargs <- max_value	**original_kwargskwargs <- min_value
				(format.converter(original_kwargs={'min_value':min_value},max_value=max_value),{}),
				#**kws <- max_value	**original_kwargskwargs <- min_value
				(format.converter(original_kwargs={'min_value':min_value}),{'max_value':max_value}),
				
				#**kws <- min_value,max_value
				(format.converter(),{'min_value':min_value,'max_value':max_value}),
			]#(format.converter(min_value=min_value,max_value=max_value),{'min_value':min_value,'max_value':max_value})
			convert_results = []
			for converter,kwargs in converters:
				convert_results.append((converter,kwargs,conversion_chain(converter,3,value,**kwargs)))
			matches = []
			mismatches = []
			errors = []
			for i,rA in enumerate(convert_results):
				for j,rB in enumerate(convert_results):
					if i >= j: continue
					try:
						if (fail_info:=compare_conversions(rA[2],rB[2])):
							index,a,b = fail_info
							if isinstance(a,Exception): raise a
							elif isinstance(b,Exception): raise b
							else: mismatches.append(((rA,rB),fail_info))
						else: matches.append((rA,rB))
					except Exception as e:
						errors.append(((rA,rB),e))
			print('Single Conversion Test for: %s'%format)
			print('\tMatched %d/%d Conversion Pairs (%.1f%%)'%(len(matches),(len(matches)+len(mismatches)+len(errors)),100*(len(matches)/(len(matches)+len(mismatches)+len(errors)))),flush=True)
			if verbose:
				print('\tUnmatched Conversion Pairs (%d):'%(len(mismatches)))
				for i,mm in enumerate(mismatches):
					pair,fail_info = mm
					rA,rB = pair
					converterA,kwsA,cA=rA
					converterB,kwsB,cB=rB
					
					print('\t\t[%d]Fail: %s'%(i,fail_info),flush=True)
				print('\tError Conversion Pairs (%d):'%(len(errors)))
				for i,err in enumerate(errors):
					pair,e = err
					rA,rB = pair
					converterA,kwsA,cA=rA
					converterB,kwsB,cB=rB
					print('\t\t[%d]Error: %s'%(i,e),flush=True,end='\t')
					unknown_error_reason = True
					print('Converters(%s,%s)'%(converterA,converterB),flush=True,end='\t')
					print('kws(%s,%s)'%(kwsA,kwsB),flush=True,end='\t')
					print('Chains(%s,%s)'%(cA,cB),flush=True,end='\t')
					print()
					
		def test_double(value,format,min_value,max_value,other,alt_min_value,alt_max_value,verbose=True):
			color = format(value,min_value=min_value,max_value=max_value)
			
			'''Matching Range Conversion Tests'''
			no_alt_converters = [
				#Converter Functions 
				#**kwargs <- min_value,max_value
				(format.converter(other,min_value=min_value,max_value=max_value),{}),
				#**kwargs <- max_value	**kws <- min_value
				(format.converter(other,max_value=max_value),{'min_value':min_value}),
				#**kwargs <- min_value	**kws <- max_value
				(format.converter(other,min_value=min_value),{'max_value':max_value}),
				
				#**kws <- min_value,max_value
				(format.converter(other),{'min_value':min_value,'max_value':max_value}),
				
				#**original_kwargskwargs <- min_value,max_value
				(format.converter(other,original_kwargs={'min_value':min_value,'max_value':max_value},other_kwargs={'min_value':min_value,'max_value':max_value}),{}),
				#**kwargs <- min_value	**original_kwargskwargs <- max_value
				(format.converter(other,original_kwargs={'max_value':max_value},other_kwargs={'max_value':max_value},min_value=min_value),{}),
				#**kws <- min_value	**original_kwargskwargs <- max_value
				(format.converter(other,original_kwargs={'max_value':max_value},other_kwargs={'max_value':max_value}),{'min_value':min_value}),
				#**kwargs <- max_value	**original_kwargskwargs <- min_value
				(format.converter(other,original_kwargs={'min_value':min_value},other_kwargs={'min_value':min_value},max_value=max_value),{}),
				#**kws <- max_value	**original_kwargskwargs <- min_value
				(format.converter(other,original_kwargs={'min_value':min_value},other_kwargs={'min_value':min_value}),{'max_value':max_value}),
			]
			
			no_alt_chain = [
				color,
				other(
					format(
						color,
						min_value=min_value,
						max_value=max_value
					),
					min_value=min_value,
					max_value=max_value
				)
			]
			no_alt_convert_results = [((format,other),{'min_value':min_value,'max_value':max_value},no_alt_chain)]
			for converter,kwargs in no_alt_converters:
				no_alt_convert_results.append((converter,kwargs,conversion_chain(converter,1,color,**kwargs)))
			
			
			no_alt_matches = []
			no_alt_mismatches = []
			no_alt_errors = []
			for i,rA in enumerate(no_alt_convert_results):
				for j,rB in enumerate(no_alt_convert_results):
					if i >= j: continue
					try:
						if (fail_info:=compare_conversions(rA[2],rB[2])):
							index,a,b = fail_info
							if isinstance(a,Exception): raise a
							elif isinstance(b,Exception): raise b
							else: no_alt_mismatches.append(((rA,rB),fail_info))
						else: no_alt_matches.append((rA,rB))
					except Exception as e:
						no_alt_errors.append(((rA,rB),e))
			
			print('Double Conversion Test for: %s -> %s'%(format,other))
			print('\tMatching Range Conversions:')
			print('\t\tMatched %d/%d Conversion Pairs (%.1f%%)'%(len(no_alt_matches),(len(no_alt_matches)+len(no_alt_mismatches)+len(no_alt_errors)),100*(len(no_alt_matches)/(len(no_alt_matches)+len(no_alt_mismatches)+len(no_alt_errors)))),flush=True)
			if verbose:
				if verbose >= 2:
					for i,pair in enumerate(no_alt_matches):
						rA,rB = pair
						converterA,kwsA,cA=rA
						converterB,kwsB,cB=rB
						print('\t\t\t[%d]Match: '%(i),flush=True,end='\t')
						if verbose>=3:
							print('Converters(%s,%s)'%(converterA,converterB),flush=True,end='\t')
							print('Chains(%s,%s)'%(cA,cB),flush=True,end='\t')
							print('kws(%s,%s)'%(kwsA,kwsB),flush=True,end='\t')
						print()
						
				if verbose>=2 or no_alt_mismatches: print('\t\tUnmatched Conversion Pairs (%d):'%(len(no_alt_mismatches)))
				for i,mm in enumerate(no_alt_mismatches):
					pair,fail_info = mm
					rA,rB = pair
					converterA,kwsA,cA=rA
					converterB,kwsB,cB=rB
					
					print('\t\t\t[%d]Fail: %s'%(i,fail_info),flush=True)
				if verbose>=2 or no_alt_errors: print('\t\tError Conversion Pairs (%d):'%(len(no_alt_errors)))
				for i,err in enumerate(no_alt_errors):
					pair,e = err
					rA,rB = pair
					try:
						converterA,kwsA,cA=rA
						converterB,kwsB,cB=rB
					except: print(rA); print(rB); raise
					print('\t\t\t[%d]Error: %s'%(i,e),flush=True,end='\t')
					unknown_error_reason = True
					print('Converters(%s,%s)'%(converterA,converterB),flush=True,end='\t')
					print('kws(%s,%s)'%(kwsA,kwsB),flush=True,end='\t')
					print('Chains(%s,%s)'%(cA,cB),flush=True,end='\t')
					print()
			'''Different Range Conversion Tests'''
			alt_converters = [
				#**kwargs <- min_value	**original_kwargskwargs <- max_value
				#(format.converter(other,original_kwargs={'max_value':max_value},other_kwargs={'max_value':alt_max_value},min_value=min_value),{}),
				#**kws <- min_value	**original_kwargskwargs <- max_value
				#(format.converter(other,original_kwargs={'max_value':max_value},other_kwargs={'max_value':alt_max_value}),{'min_value':min_value}),
				#**kwargs <- max_value	**original_kwargskwargs <- min_value
				#(format.converter(other,original_kwargs={'min_value':min_value},other_kwargs={'min_value':alt_min_value},max_value=max_value),{}),
				#**kws <- max_value	**original_kwargskwargs <- min_value
				#(format.converter(other,original_kwargs={'min_value':min_value},other_kwargs={'min_value':alt_min_value}),{'max_value':max_value}),
				
				#**original_kwargskwargs <- min_value,max_value
				(format.converter(other,original_kwargs={'min_value':min_value,'max_value':max_value},other_kwargs={'min_value':alt_min_value,'max_value':alt_max_value}),{}),
			]
			alt_chain = [
				color,
				other(
					format(
						color,
						min_value=min_value,
						max_value=max_value
					),
					min_value=alt_min_value,
					max_value=alt_max_value
				)
			]
			alt_convert_results = [((format,other),{'min_value':min_value,'max_value':max_value,'alt_min_value':alt_min_value,'alt_max_value':alt_max_value},alt_chain)]
			for converter,kwargs in alt_converters:
				alt_convert_results.append((converter,kwargs,conversion_chain(converter,1,color,**kwargs)))
			
			alt_matches = []
			alt_mismatches = []
			alt_errors = []
			for i,rA in enumerate(alt_convert_results):
				for j,rB in enumerate(alt_convert_results):
					if i >= j: continue
					try:
						if (fail_info:=compare_conversions(rA[2],rB[2])):
							index,a,b = fail_info
							if isinstance(a,Exception): raise a
							elif isinstance(b,Exception): raise b
							else: alt_mismatches.append(((rA,rB),fail_info))
						else: alt_matches.append((rA,rB))
					except Exception as e:
						alt_errors.append(((rA,rB),e))
			
			print('\tDifferent Range Conversions:')
			print('\t\tMatched %d/%d Conversion Pairs (%.1f%%)'%(len(alt_matches),(len(alt_matches)+len(alt_mismatches)+len(alt_errors)),100*(len(alt_matches)/(len(alt_matches)+len(alt_mismatches)+len(alt_errors)))),flush=True)
			if verbose:
				if verbose >= 2:
					for i,pair in enumerate(alt_matches):
						rA,rB = pair
						converterA,kwsA,cA=rA
						converterB,kwsB,cB=rB
						print('\t\t\t[%d]Match: '%(i),flush=True,end='\t')
						if verbose>=3:
							print('Converters(%s,%s)'%(converterA,converterB),flush=True,end='\t')
							print('Chains(%s,%s)'%(cA,cB),flush=True,end='\t')
							print('kws(%s,%s)'%(kwsA,kwsB),flush=True,end='\t')
						print()
						
				if verbose>=2 or alt_mismatches: print('\t\tUnmatched Conversion Pairs (%d):'%(len(alt_mismatches)))
				for i,mm in enumerate(alt_mismatches):
					pair,fail_info = mm
					rA,rB = pair
					converterA,kwsA,cA=rA
					converterB,kwsB,cB=rB
					
					print('\t\t\t[%d]Fail: %s'%(i,fail_info),flush=True,end='\t')
					if verbose>=3:
						print('Converters(%s,%s)'%(converterA,converterB),flush=True,end='\t')
						print('Chains(%s,%s)'%(cA,cB),flush=True,end='\t')
						print('kws(%s,%s)'%(kwsA,kwsB),flush=True,end='\t')
					print()
					
				if verbose>=2 or alt_errors: print('\t\tError Conversion Pairs (%d):'%(len(alt_errors)))
				for i,err in enumerate(alt_errors):
					pair,e = err
					rA,rB = pair
					converterA,kwsA,cA=rA
					converterB,kwsB,cB=rB
					
					print('\t\t\t[%d]Error: %s'%(i,e),flush=True,end='\t')
					if verbose>=3:
						print('Converters(%s,%s)'%(converterA,converterB),flush=True,end='\t')
						print('Chains(%s,%s)'%(cA,cB),flush=True,end='\t')
						print('kws(%s,%s)'%(kwsA,kwsB),flush=True,end='\t')
					print()
					
		test_single(100,Monochrome.RGB,0,500)
		test_single(5639,Polychrome.RGB,0,10000)
		test_double(100,Monochrome.RGB,0,500,Polychrome.RGBA,0,1000,verbose=True)
		test_double(255,Monochrome.RGB,0,500,Polychrome.RGB,-10916,8848,verbose=False)
		
		
	if converter_func:
		test_converter()
'''TODO REFACTOR: Above and below functions to combine functionality or rename/reformat to be more descriptive of actual functionality'''
def test_CVF(format,t=1,**kwargs):
	print('Testing: %s'%format)
	import random
	def get_range_kwargs(min_value=None,max_value=None,**kwargs):
		RANGE_MIN = -50000
		RANGE_MAX =  50000
		#Min
		if min_value is None:
			if max_value is not None: min_value = random.uniform(RANGE_MIN,max_value)
			else:                     min_value = random.uniform(RANGE_MIN,RANGE_MAX-1)
		#Max
		if max_value is None: max_value = random.uniform(min_value,RANGE_MAX)
		return {'min_value':min_value,'max_value':max_value}
		
	
	def color_differences(items,verbose=True):
		def cdif(a,b):
			if len(a) != len(b): raise IndexError
			return tuple(abs(a[i] - b[i]) for i in range(len(a)))
		rtn = {}
		for i,item in enumerate(items):
			if i>0:
				dif = cdif(item,items[i-1])
				if sum(dif) > 0:
					rtn[i-1] = (dif,items[i-1],item)
					if verbose: print('\t[%d]Difference %s != %s'%(i-1,items[i-1],item))
		return rtn
	def value_differences(items,verbose=True): 
		rtn = {}
		for i,item in enumerate(items):
			if i>0:
				if item != items[i-1]:
					rtn[i-1] = (abs(items[i-1]-item),items[i-1],item)
					if verbose: print('\t[%d]Difference %s != %s'%(i-1,items[i-1],item))
		return rtn
	def conversion_test(cv,n,verbose=True,test=True,**kwargs):
		
		list_0 = [cv]
		list_1 = []
		if verbose: print('Conversion:',end='\n')
		for i in range(n):
			if verbose: print('\t%s'%list_0 [i],end=' -> ')
			list_1.append(format(list_0 [i],**kwargs))
			if verbose: 
				if i < n-1: print('%s'%(list_1[i],),end=' -> \n')
				else: print('%s'%(list_1[i],),end='\n')
			list_0 .append(format(list_1[i],**kwargs))
		
		if not(test): pass
		elif isinstance(cv, tuple):
			color_differences(list_0)
			value_differences(list_1)
		else:
			value_differences(list_0)
			color_differences(list_1)
		return list_0,list_1	
	def value_conversion_test(value=None,n=3,**kwargs):
		kwargs = get_range_kwargs(**kwargs)
		#Value
		if value is None: value = random.uniform(kwargs['min_value'],kwargs['max_value'])
		conversion_test(value,n,**kwargs)
		return
	
	def full_range_test(verbose=True,TOL=0.0,**kwargs):
		print('\tTesting Full_Range(%s,%s,~%f)...\t'%(kwargs['min_value'],kwargs['max_value'],TOL),flush=True,end='')
		total_correct_values = 0
		total_incorrect_values = 0
		report_data = {}
		for value in range(kwargs['min_value'],kwargs['max_value']):
			correct = True
			val_list,col_list = conversion_test(value,test=False,verbose=False,**kwargs)
			if color_result := color_differences(col_list,verbose=False):
				if not(value in report_data): report_data[value] = {}
				report_data[value]['color'] = color_result
				correct = False
			if value_result := value_differences(val_list,verbose=False):
				if not(value in report_data): report_data[value] = {}
				report_data[value]['value'] = value_result
				for i in value_result:
					if value_result[i][0] > TOL: 
						correct=False
						break
				
			if correct: total_correct_values += 1
			else: total_incorrect_values += 1
		
		
		#Evaluate Report
		if not(total_incorrect_values):
			print('PASSED',flush=True)
			return True
		else:
			print('FAILED',flush=True)
			if verbose >= 1:
				print('\t\tReport{')
				total_primary_color_conversion_failures = 0
				total_primary_value_conversion_failures = 0
				critical_primary_value_conversion_failures = 0
				for value in report_data:
					prt = ''
					if color_result := report_data[value].get('color',False):
						if len(color_result) > 1 or not(0 in color_result):
							if len(prt) == 0: color_prt ='\t\t\t%d:\n'%value
							else: color_prt=''
							color_prt+='\t\t\t\tColor:\n'
							color_prt+='\t\t\t\t\tImportant Conversion Failure:\n'
							
							for i in color_result:
								color_prt+='\t\t\t\t\t\t[c_%d]%s\n'%(i,color_result[i])
							prt+=color_prt
						else:
							total_primary_color_conversion_failures += len(color_result)
					if value_result := report_data[value].get('value',False):
						if len(value_result) > 1 or not(0 in value_result):
							if len(prt) == 0: value_prt ='\t\t\t%d:\n'%value
							else: value_prt=''
							value_prt+='\t\t\t\tValue:\n'
							value_prt+='\t\t\t\t\tImportant Conversion Failure:\n'
							add_value_prt=False
							for i in value_result:
								if value_result[i][0] > TOL or verbose>=3:
									add_value_prt = True
									value_prt+='\t\t\t\t\t\t[v_%d]%s\n'%(i,value_result[i])
							if add_value_prt: prt+=value_prt
						else:
							#print(value_result)
							if 0 in value_result and value_result[0][0] > TOL:
								critical_primary_value_conversion_failures += len(value_result)
							
							total_primary_value_conversion_failures += len(value_result)
					if verbose >= 2:
						if prt: print(prt)
					#print('\t\t\t%s: %s'%(value,report_data[value]),flush=True)
				print('\t\t\tTotal Primary Color Conversion Failures: %d'%total_primary_color_conversion_failures,flush=True)
				print('\t\t\tTotal Primary Value Conversion Failures: %d'%total_primary_value_conversion_failures,flush=True)
				print('\t\t\t\tCRITICAL: %d'%critical_primary_value_conversion_failures,flush=True)
				
				print('\t\t}')
			return False
	def get_testing_range(r): return -r,r+1,r//2
	
	
	if 'min_value' in kwargs and 'max_value' in kwargs:
		#if not('n' in kwargs): kwargs['n'] = 3
		full_range_test(
			min_value=kwargs['min_value'],
			max_value=kwargs['max_value'],
			n=kwargs.get('n',3),
			verbose=kwargs.get('verbose',2),
			TOL=kwargs['TOL'] if 'TOL' in kwargs else format.get_scale(kwargs['min_value'],kwargs['max_value']),
		)
	else:
		testing_range = get_testing_range(kwargs['testing_radius'] if 'testing_radius' in kwargs else 2**16)
		#(-2**32,2**32+1,2**30)
		total_tests = 0
		passed_tests = 0
		for min_value in range(*testing_range):
			for max_value in range(*testing_range):
				if max_value <= min_value: continue
				passed = full_range_test(
					min_value=min_value,
					max_value=max_value,
					n=kwargs['n'] if 'n' in kwargs else 3,
					verbose=kwargs.get('verbose',True),
					TOL=kwargs['TOL'] if 'TOL' in kwargs else format.get_scale(min_value,max_value)
				)
				total_tests += 1
				if passed: passed_tests += 1
		print('Passed %d/%d (%d%%) Tests'%(passed_tests,total_tests,100*(passed_tests/total_tests)),flush=True)
	
 
if __name__ == '__main__':
	Image.MAX_IMAGE_PIXELS = None
	print('Running Unit Tests',flush=True)
	if True:
		print('''Running Unit Tests for ColorValueFormat classes''',flush=True)
		if False: # ColorValueFormat.converter function test
			test_ColorValueFormat(converter_func=True)
		if False: # ColorValueFormat Range Test
			radius = 2**12
			if False: #Monochrome
				for format in Monochrome:
					test_CVF( format, testing_radius=radius, verbose=0)
			if True: #Polychrome
				for format in Polychrome:
					test_CVF( format, testing_radius=radius, verbose=0)
		if False: # ColorValueFormat Palettes 
			if False: #Monochrome
				ColorValueFormat.all_palettes(
					Monochrome,
					0,
					2048,
					step=1,
					swatch_width=1,
					swatch_height=16,
					verbose=True
				).show()
			if True: #Polychrome
				ColorValueFormat.all_palettes(
					Polychrome,
					0,
					2048,#2**14,
					step=1,
					swatch_width=1,
					swatch_height=16,
					verbose=True
				).show()
		
	if False:
		print('''Running Unit Tests for DataMap classes''',flush=True)
		if False: #ValueMap class tests
			test_value_map_class()
		if True: #RegionValueMap class tests
			test_region_value_map_class()
		if False: #DynamicRegionValueMap class tests
			test_dynamic_region_value_map_class()
	
	
	if True:
		print('''Running Unit Tests for public util functions''',flush=True)
		if False: # map_unwrap tests
			# TODO ADD: tests for map_unwrap function
			pass
		if False: #map_unsplit tests
			# TODO ADD: tests for map_unsplit
			pass
		if True: # map_stitch tests
			test_stitching()
