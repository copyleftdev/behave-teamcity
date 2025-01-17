from setuptools import setup

setup(
    name='hudl_behave_teamcity',
    version="0.1.49",
    packages=['hudl_behave_teamcity'],
    url='https://github.com/hudl/behave-teamcity',
    author='Ilja Bauer',
    author_email='i.bauer@cuescience.de',
    description='TeamCity test report formatter for behave',
    install_requires=["behave", "teamcity-messages"],
    keywords=['testing', 'behave', 'teamcity', 'formatter', 'report']
)
