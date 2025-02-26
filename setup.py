from setuptools import setup, find_packages

setup(
    name="technodada",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.42.0",
        "openai>=1.64.0",
        "python-dotenv>=1.0.0",
    ],
    author="Doc Brown",
    description="A concept inversion system using LLMs",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/heydocbrown/technodada",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
) 