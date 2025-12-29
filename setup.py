from setuptools import setup

setup(
    name="cmsg",
    version="1.0.0",
    py_modules=["cmsg"],
    entry_points={
        "console_scripts": [
            "cmsg=cmsg:main",
        ],
    },
    python_requires=">=3.6",
)
