try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension

setup(name='cly',
      url='http://swapoff.org/cly',
      download_url='http://swapoff.org/cly',
      author='Alec Thomas',
      author_email='alec@swapoff.org',
      version='0.9',
      description='A module for adding powerful text-based consoles to your application.',
      long_description=\
"""CLY is a Python module for simplifying the creation of interactive shells.
Kind of like the builtin "cmd" module on steroids.""",
      license='BSD',
      platforms=['any'],
      packages=['cly'],
      zip_safe=False,
      test_suite='cly.test.suite',
      classifiers=['Development Status :: 3 - Alpha',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: BSD License',
                   'Operating System :: OS Independent',
                   'Topic :: System :: Shells',
                   'Environment :: Console',
                   'Topic :: Software Development :: Libraries'],
      ext_modules=[Extension('cly.rlext', ['cly/rlext.c'],
                             libraries = ['readline', 'curses'])],
      install_requires=['future==0.18.2'],
  )
