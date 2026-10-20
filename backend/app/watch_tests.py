import subprocess
import sys

from watchfiles import watch


def main():
    subprocess.run([sys.executable,"-m","pytest","-q"],check=False)
    for _ in watch("app","tests"):
        subprocess.run([sys.executable,"-m","pytest","-q"],check=False)


if __name__=="__main__":
    main()
