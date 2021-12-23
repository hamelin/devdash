from setuptools import setup, find_packages


setup(
    name="devdash",
    version="0.9",
    author="Benoit Hamelin",
    email="benoit@benoithamelin.com",
    description="Automatic developer dashboard",
    license="MIT",
    url="https://github.com/hamelin/devdash",
    packages=find_packages(),
    install_requires=["ipywidgets", "ipython", "watchdog"],
    keywords=["Development", "Dashboard", "Jupyter"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Developer Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10"
    ]
)
