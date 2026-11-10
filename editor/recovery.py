"""Write a stable snapshot without serializing a live editor model on a worker."""
import json
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal, Slot
from model import Document, atomic_json
from versioning import scale_spatial


def capture(doc, source, draft):
    # Capture only model fields, never transient geometry caches or Qt objects.
    def fields(obj):
        return {name: getattr(obj, name) for name in obj.__dataclass_fields__}
    return json.dumps((doc, source, draft), default=fields, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':'))


def write_snapshot(path, snapshot):
    doc, source, draft = json.loads(snapshot)
    data = Document.pack_project(doc)
    data['source_path'] = source
    if draft is not None:
        data['areaDraft'] = scale_spatial({'regions': [draft]}, 100, True)['regions'][0]
    atomic_json(path, data, compact=True)


class RecoveryWriter(QObject):
    ready = Signal()
    message = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending = self.saved = None
        self.saved_revision = None
        self.ready.connect(self.finish_if_ready)

    @Slot()
    def finish_if_ready(self):
        if self.pending and self.pending[1].done():
            self.flush()

    def flush(self):
        if self.pending is None:
            return
        key, future, revision = self.pending
        self.pending = None
        try:
            future.result()
            self.saved = key
            self.saved_revision = revision
            self.message.emit('已保存自动恢复快照')
        except Exception as error:
            self.message.emit('自动恢复快照写入失败：' + str(error))

    def save(self, path, doc, source, draft, background, revision=None):
        if background:
            self.finish_if_ready()
            if self.pending:
                return  # Retry with the newest state on the next timer tick.
            if (revision is not None and self.saved_revision == revision
                    and self.saved and self.saved[0] == path and path.is_file()):
                return
        else:
            self.flush()
        key = (path, capture(doc, source, draft))
        if self.saved == key and path.is_file():
            self.saved_revision = revision
            return
        future = self.pool.submit(write_snapshot, *key)
        self.pending = key, future, revision
        if background:
            future.add_done_callback(lambda _: self.ready.emit())
        else:
            self.flush()

    def close(self):
        self.flush()
        self.pool.shutdown()
