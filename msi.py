import configparser
import os
import platform

import pkg_resources
from nsist import main as pynsist_main
from poet import merge_graphs, make_graph

from mockintosh import __version__


def generate_pynsist_config(dependencies, wheel_dir, version):
    cfg = configparser.ConfigParser()
    cfg['Application'] = {
        'name': 'Mockintosh',
        'version': version,
        'publisher': 'UP9 Inc.',
        'entry_point': 'mockintosh:demo_run',
        'console': 'true',
        'icon': 'docs/favicon.ico',
        'license_file': 'LICENSE',
    }

    cfg['Command mockintosh'] = {
        'entry_point': 'mockintosh:initiate',
        'console': 'true',
    }

    cfg['Python'] = {
        'bitness': 64,
        'version': platform.python_version(),
    }

    wheels_list = ["%s==%s" % (package_name, version) for package_name, version in dependencies]

    cfg['Include'] = {
        'pypi_wheels': "\n".join(wheels_list),
        'extra_wheel_sources': wheel_dir,
        'files': '\n'.join([
            'README.md'
        ])
    }

    cfg['Build'] = {
        'installer_name': "Mockintosh_%s_x64.exe" % version
    }

    return cfg


def get_deps(pkgs):
    # copied a piece from `poet`
    nodes = merge_graphs(make_graph(p) for p in pkgs)
    return nodes


def main():
    wheel_dir = "dist-msi"
    os.makedirs(wheel_dir, exist_ok=True)

    dependencies = [(x['name'], x['version']) for x in get_deps(['mockintosh']).values()]
    dependencies.extend((x.key, x.version) for x in pkg_resources.working_set if x.key == 'setuptools')
    cfg = generate_pynsist_config(dependencies, wheel_dir, __version__)
    fname = 'msi.cfg'
    with open(fname, 'w') as fp:
        cfg.write(fp)
    pynsist_main([fname])


if __name__ == '__main__':
    main()
