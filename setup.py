from setuptools import setup, find_namespace_packages

setup(
    name="philotes",
    version="4.0.1",


    description="Linux-First Communication Application Container",
    author="Philotes Team",
    packages=find_namespace_packages(include=["philotes", "philotes.*"]),
    entry_points={
        "console_scripts": [
            "philotes = philotes.main:main",
            "philo-chat = philotes.subapps.philo_chat:run_philo_chat_subprocess",
            "philo-msgs = philotes.subapps.philo_msgs:run_philo_msgs_subprocess",
            "philo-wordle = philotes.subapps.philo_wordle:run_philo_wordle_subprocess",
            "philo-keep = philotes.subapps.philo_keep:run_philo_keep_subprocess",
        ],
    },
    python_requires=">=3.8",
)
