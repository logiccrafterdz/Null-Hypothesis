"""
Setup script for Null Hypothesis Quant Research Engine
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="null-hypothesis",
    version="1.0.0",
    author="Null Hypothesis Team",
    description="A quant research engine that set out to find alpha and failed to reject its own null hypothesis instead",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        "pandas>=2.2.0",
        "numpy>=1.26.3",
        "MetaTrader5>=5.0.45",
        "ta>=0.11.0",
        "pandas-ta>=0.3.14b",
        "backtesting>=0.4.1",
        "scikit-learn>=1.4.0",
        "streamlit>=1.31.0",
        "python-telegram-bot>=21.0",
        "SQLAlchemy>=2.0.27",
        "scipy>=1.12.0",
        "python-dotenv>=1.0.0",
        "cryptography>=41.0.0",
    ],
    entry_points={
        "console_scripts": [
            "null-hypothesis=main:main",
        ],
    },
)
