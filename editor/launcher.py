"""Desktop entry point with a persistent startup diagnostic on packaging failures."""
import os
from pathlib import Path
import sys
import traceback

if __name__=='__main__':
    folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'IntervalComposer'
    try:
        from main import main
        (folder/'startup-error.log').unlink(missing_ok=True)
        main()
    except Exception:
        folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'IntervalComposer'
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        sys.exit(1)
