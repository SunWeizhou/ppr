from setuptools import find_packages, setup


setup(
    name="arxiv-recommender-local",
    version="0.1.0",
    description="Local-first arXiv paper recommendation and triage desk",
    py_modules=[
        "app_paths",
        "arxiv_recommender_v5",
        "backup_user_data",
        "config_manager",
        "journal_tracker",
        "journal_update",
        "logger_config",
        "state_store",
        "utils",
        "web_server",
    ],
    packages=find_packages(include=["installer", "installer.*"]),
    include_package_data=True,
    install_requires=[
        "Flask>=3.0.0",
        "flask-cors>=4.0.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
        "feedparser>=6.0.0",
        "sentence-transformers>=2.2.0",
        "transformers>=4.30.0",
        "torch>=2.0.0",
        "python-dateutil>=2.8.0",
    ],
    entry_points={
        "console_scripts": [
            "arxiv-recommender=web_server:main",
        ],
    },
    python_requires=">=3.9",
)
