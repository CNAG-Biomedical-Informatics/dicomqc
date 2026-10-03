"""PyInstaller entry point shared by the API supervisor and --worker children."""

from multiprocessing import freeze_support

from dicomqc.api.server import main


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
