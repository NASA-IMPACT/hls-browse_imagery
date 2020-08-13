from setuptools import setup, find_packages

setup(
    name="hls_browse_imagery_creator",
    version="0.1",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    install_requires=[
        "numpy",
        "gdal",
        "xmltodict",
        "click",
        "dicttoxml",
        "lxml"
    ],
    extras_require={"test": ["pytest", "flake8"]},
    package_data={"hls_browse_imagery_creator": ["data/*.json",
                                                 "data/schema/*.xml"]},
    entry_points="""
        [console_scripts]
        granule_to_gibs=hls_browse_imagery_creator.granule_to_gibs:granule_to_gibs
        create_gibs_tile=hls_browse_imagery_creator.create_gibs_tile:create_gibs_tile
        create_gibs_metadata=hls_browse_imagery_creator.create_gibs_metadata:create_gibs_metadata
    """,
)
