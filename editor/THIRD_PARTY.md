# Third-party components

The desktop application uses dynamically loaded Python, PySide6 / Shiboken6, Qt 6, and Qt Multimedia's FFmpeg runtime. Their upstream copyright and license notices apply to those components.

- Python: https://www.python.org/ — https://docs.python.org/3/license.html
- PySide6 / Shiboken6: https://code.qt.io/cgit/pyside/pyside-setup.git/
- Qt: https://code.qt.io/cgit/qt/qtbase.git/ — https://www.qt.io/licensing/open-source-lgpl-obligations
- FFmpeg: https://ffmpeg.org/ — https://ffmpeg.org/legal.html
- PyInstaller bootloader: https://github.com/pyinstaller/pyinstaller — GPL with the PyInstaller distribution exception.
- NumPy: https://numpy.org/ — BSD and bundled component licenses; notices in `licenses/numpy/`.
- SoundFile: https://github.com/bastibe/python-soundfile — BSD-3-Clause; dynamically loaded libsndfile uses LGPL-2.1. Notices in `licenses/soundfile/`; the bundled DLL can be replaced in `_internal/_soundfile_data/`. libsndfile source: https://github.com/libsndfile/libsndfile/tree/1.2.2 .
- CFFI and pycparser: https://cffi.readthedocs.io/ and https://github.com/eliben/pycparser — MIT, notices in `licenses/cffi/` and `licenses/pycparser/`.

The `_internal` directory contains the shared libraries used by the Windows application; they have not been statically linked into the application. The application source, dependency version and build scripts are included in the project.

PhiEdit was consulted only as an interaction reference using its installed configuration files. No PhiEdit binaries, fonts, textures or source code are included in the editor.
