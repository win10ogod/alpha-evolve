from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="alphaevolve",
    version="0.1.0",
    author="AlphaEvolve Team",
    author_email="your.email@example.com",
    description="A system for evolving code using Large Language Models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/alphaevolve",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[
        "litellm>=0.1.1",
        "pyyaml>=6.0",
        "aiohttp>=3.8.0",
        "nest-asyncio>=1.5.6",
    ],
    entry_points={
        "console_scripts": [
            "alphaevolve=alphaevolve.cli.alphaevolve:main",
        ],
    },
) 