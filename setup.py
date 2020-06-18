from setuptools import setup, find_packages

setup(
    name="hls_browse_imagery_creator",
    version="0.1",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    install_requires=["numpy", "gdal", "xmltodict", "click",],
    extras_require={"testing": ["pytest"]},
    package_data={"hls_browse_imagery_creator": ["data/*.json"]},
    setup_requires=["flake8"],
    entry_points="""
        [console_scripts]
        granule_to_gibs=hls_browse_imagery_creator.granule_to_gibs:granule_to_gibs
    """,
)
