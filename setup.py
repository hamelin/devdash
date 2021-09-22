from setuptools import setup, find_packages

setup(
    name="devdash",
    version="1.0.0",
    author="Benoit Hamelin",
    email="benoit@benoithamelin.com",
    description="Automatic developer dashboard",
    packages=find_packages(),
    install_requires=["ipywidgets", "ipython", "watchdog"]
)
