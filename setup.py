from setuptools import setup, find_packages

setup(
    name="philotes",
    version="0.3.0",


    description="Linux-First Communication Application Container",
    author="Philotes Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "philotes = philotes.main:main",
            "philo-chat = philotes.subapps.philo_chat:run_philo_chat_subprocess",
        ],
    },
    python_requires=">=3.8",
)
