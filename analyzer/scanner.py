IGNORE_SOURCE_EXTS = [
    ".c",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".rs",
    ".go",
    ".py",
    ".java" ".class",
    ".html",
    ".js",
    ".ts",
    ".lua",
    ".pl",
    ".rb",
]

ARCHIVE_MIME = [
    "application/x-archive",
    "application/x-bzip2",
    "application/gzip",
    "application/x-xz",
    "application/zip",
    "application/x-tar",
    "application/x-7z-compressed",
]


class Scanner:
    def __init__(self, path, tags):
        self.path = path

    @property
    def results(self):
        return None
