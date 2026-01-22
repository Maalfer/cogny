from setuptools import setup, find_packages

setup(
    name="cogny",
    version="1.0.6",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=[
        "PySide6",
    ],
    entry_points={
        "console_scripts": [
            "cogny = main:main",
        ],
    },
)
