import re
from subprocess import run


def die(msg, errcode=1):
    print(msg)
    input('Press any key to exit ...')
    exit(errcode)

def get_version():
    with open('setup.py') as file:
        for l in file:
            res = re.search(r"version='([^']+)'", l)
            if res: return(res.group(1))
        if 'res' not in locals(): die("Package version not found")

def cmd(command):
    run(args=command, capture_output=False, encoding='oem')

def install(version):
    uninstall_command = rf'pip uninstall PyUtils'
    install_command = rf'pip install --no-index --find-links ./dist PyUtils=={version}'

    cmd(uninstall_command)
    cmd(install_command)

    pass


if __name__ == '__main__':
    try:
        version = get_version()
        print(f"Press any key to install PyUtils v{version} ...")

        install(version)
    except Exception as e:
        die(e)
    else:
        die("Installed!", 0)
