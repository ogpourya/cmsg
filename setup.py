from setuptools import setup

setup(
    name="cmsg",
    version="0.1.0",
    py_modules=["cmsg"],
    entry_points={
        "console_scripts": [
            "cmsg=cmsg:main",
        ],
    },
    python_requires=">=3.6",
)
