from setuptools import setup

setup(
	name='datamapy',
	version='1.0.0',
	author='Joseph Sale',
	author_email='Joseph.Michael.Sale@gmail.com',
	url='https://github.com/JosephMichaelSale/datamapy',
	py_modules=['datamapy.map','datamapy.access','datamapy.reorder'],
	python_requires='>3.8',
	install_requires=['Pillow >= 8.4.0'],
)