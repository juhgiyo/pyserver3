from setuptools import setup,find_packages
try:
    with open('VERSION.txt', 'r') as v:
        version = v.read().strip()
except Exception:
    version = '0.0.0-dev'

setup(
  name = 'pyserver3',
  packages = find_packages(exclude=["dist"]),
  description = 'TCP/UDP Aysnchronous Server/Client Library',
  author = 'Woong Gyu La',
  author_email = 'juhgiyo@gmail.com',
  version=version,
  url = 'https://github.com/juhgiyo/pyserver3', # use the URL to the github repo
  keywords = ['tcp', 'udp', 'server', 'library'], # arbitrary keywords
  license="The MIT License (MIT)",
  install_requires=['pyserialize'],
  classifiers = [
    # How mature is this project? Common values are
    #   3 - Alpha
    #   4 - Beta
    #   5 - Production/Stable
    'Development Status :: 3 - Alpha',
    'Programming Language :: Python :: 3',
  ],
)