from setuptools import setup, find_packages

setup(
    name="devdash",
    version="0.9",
    author="Benoit Hamelin",
    email="benoit@benoithamelin.com",
    description="Automatic developer dashboard",
    packages=find_packages(),
    install_requires=["ipywidgets", "ipython", "watchdog"]
)
