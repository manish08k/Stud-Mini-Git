from setuptools import setup, find_packages

setup(
    name="stud",
    version="0.1.0",
    description="VCS + package manager + workflows + AI in one tool",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["pyyaml"],
    extras_require={"rich": ["rich>=13.0"]},
    entry_points={"console_scripts": ["stud=stud.cli.main:main"]},
)
